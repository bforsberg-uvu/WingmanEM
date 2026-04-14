"""
WingmanEM — Engineering Manager CLI.

Menu-driven app: direct reports, management tips (Mistral AI), milestone reminders,
1:1 recording upload/summary (Mistral), SQLite + JSON persistence.

Sections (in order):
  1. Configuration (in-memory globals; paths in wingmanem.constants)
  2. Database (SQLAlchemy + SQLite init; JSON mirror writes; load prefers DB, JSON migrates empty tables)
  3. Utilities (config, I/O, menu box & submenu)
  4. Direct reports (model, load/save, list/add/delete/generate/purge)
  5. Management tips (load/save, daily tip from Mistral, view by date)
  6. Milestone reminders (birthdays, anniversaries)
  7. 1:1 recordings (upload, view, delete, purge)
  8. Menus (main, developer, project, people, one-to-one, direct reports)
  9. Authentication
 10. Entry point (main)
"""

import getpass
import json
import os
import random
import sys
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

try:
    from mistralai import Mistral
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

from wingmanem.constants import (
    DATABASE_PATH,
    DIRECT_REPORT_COMP_DATA_FILE,
    DIRECT_REPORT_GOALS_FILE,
    DIRECT_REPORT_OPTIONAL_KEYS,
    DIRECT_REPORTS_FILE,
    EMPLOYEE_COMP_DATA_FILE,
    LEGACY_DIRECT_REPORT_COMP_DATA_FILE,
    MANAGEMENT_TIPS_FILE,
    MENU_BOLD,
    MENU_COLOR_BLACK,
    MENU_COLOR_DISABLED,
    MENU_COLOR_RED,
    MENU_COLOR_RESET,
)

# ============================================================================
# CONFIGURATION & CONSTANTS — in-memory globals (paths live in wingmanem.constants)
# ============================================================================

# Global data (CLI and JSON mirrors)
direct_reports: list[dict[str, Any]] = []
# Each item: {"date": "YYYY-MM-DD", "text": "tip content"}
management_tips: list[dict[str, str]] = []


# ============================================================================
# DATABASE — SQLAlchemy + SQLite (see orm_models.py for table definitions)
# ============================================================================

_db_available: bool = True  # Set False if DB file missing or init fails; app runs without DB.


def _write_direct_reports_json_file(reports: list[dict[str, Any]]) -> None:
    """Persist direct reports list to JSON (mirror of DB; same shape as historical file)."""
    try:
        with open(DIRECT_REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(reports, f, indent=2)
    except OSError as e:
        print(f"Could not write {DIRECT_REPORTS_FILE}: {e}", file=sys.stderr)


def _write_management_tips_json_file(tips: list[dict[str, str]]) -> None:
    try:
        with open(MANAGEMENT_TIPS_FILE, "w", encoding="utf-8") as f:
            json.dump(tips, f, indent=2)
    except OSError as e:
        print(f"Could not write {MANAGEMENT_TIPS_FILE}: {e}", file=sys.stderr)


def _write_direct_report_goals_json_file(goals: list[dict[str, Any]]) -> None:
    try:
        with open(DIRECT_REPORT_GOALS_FILE, "w", encoding="utf-8") as f:
            json.dump(goals, f, indent=2)
    except OSError as e:
        print(f"Could not write {DIRECT_REPORT_GOALS_FILE}: {e}", file=sys.stderr)


def _write_direct_report_comp_data_json_file(records: list[dict[str, Any]]) -> None:
    try:
        with open(DIRECT_REPORT_COMP_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
    except OSError as e:
        print(f"Could not write {DIRECT_REPORT_COMP_DATA_FILE}: {e}", file=sys.stderr)


def _db_init() -> None:
    """Create database file and tables via SQLAlchemy ORM metadata."""
    global _db_available
    try:
        from wingmanem.database import init_engine

        _db_available = init_engine(DATABASE_PATH)
        if not _db_available:
            print("Database unavailable (will run without DB): init_engine returned False", file=sys.stderr)
    except Exception as e:
        _db_available = False
        print(f"Database unavailable (will run without DB): {e}", file=sys.stderr)


def _db_replace_direct_reports_from_list(reports: list[dict[str, Any]]) -> None:
    """Replace direct_reports table with the given list (same scope as rewriting direct_reports.json)."""
    if not _db_available:
        return
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportORM

    session = get_session()
    try:
        session.execute(delete(DirectReportORM))
        for r in reports:
            oid = r.get("owner_user_id")
            session.add(
                DirectReportORM(
                    id=int(r.get("id") or 0),
                    first_name=r.get("first_name") or "",
                    last_name=r.get("last_name") or "",
                    street_address_1=r.get("street_address_1"),
                    street_address_2=r.get("street_address_2"),
                    city=r.get("city"),
                    state=r.get("state"),
                    zipcode=r.get("zipcode"),
                    country=r.get("country"),
                    birthday=r.get("birthday"),
                    hire_date=r.get("hire_date"),
                    current_role=r.get("current_role"),
                    role_start_date=r.get("role_start_date"),
                    partner_name=r.get("partner_name"),
                    owner_user_id=int(oid) if oid is not None else None,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_replace_management_tips_from_list(tips: list[dict[str, str]]) -> None:
    """Replace management_tips table with the given list (same scope as rewriting management_tips.json)."""
    if not _db_available:
        return
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import ManagementTipORM

    session = get_session()
    try:
        session.execute(delete(ManagementTipORM))
        for t in tips:
            oid = t.get("owner_user_id") if isinstance(t, dict) else None
            session.add(
                ManagementTipORM(
                    date=t.get("date") or "",
                    text=t.get("text") or "",
                    owner_user_id=int(oid) if oid is not None else None,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_load_direct_reports() -> list[dict[str, Any]]:
    """Load all direct reports from the database as list of dicts (same keys as JSON)."""
    if not _db_available:
        return []
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportORM

    session = get_session()
    try:
        rows = session.scalars(select(DirectReportORM).order_by(DirectReportORM.id)).all()
        out = []
        for row in rows:
            out.append(
                _normalize_direct_report(
                    {
                        "id": row.id,
                        "first_name": row.first_name,
                        "last_name": row.last_name,
                        "street_address_1": row.street_address_1,
                        "street_address_2": row.street_address_2,
                        "city": row.city,
                        "state": row.state,
                        "zipcode": row.zipcode,
                        "country": row.country,
                        "birthday": row.birthday,
                        "hire_date": row.hire_date,
                        "current_role": row.current_role,
                        "role_start_date": row.role_start_date,
                        "partner_name": row.partner_name,
                        "owner_user_id": row.owner_user_id,
                    }
                )
            )
        return out
    finally:
        session.close()


def _db_first_user_id() -> int | None:
    if not _db_available:
        return None
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import AppUserORM

    session = get_session()
    try:
        u = session.scalars(select(AppUserORM).order_by(AppUserORM.id).limit(1)).first()
        return int(u.id) if u else None
    finally:
        session.close()


def _db_count_app_users() -> int:
    if not _db_available:
        return 0
    from sqlalchemy import func, select

    from wingmanem.database import get_session
    from wingmanem.orm_models import AppUserORM

    session = get_session()
    try:
        n = session.scalar(select(func.count()).select_from(AppUserORM))
        return int(n or 0)
    finally:
        session.close()


def _assign_orphan_rows_to_user(user_id: int) -> None:
    """Set NULL owner_user_id on direct_reports and management_tips to this user (first-account claim)."""
    if not _db_available:
        return
    from sqlalchemy import update

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportORM, ManagementTipORM

    session = get_session()
    try:
        session.execute(
            update(DirectReportORM).where(DirectReportORM.owner_user_id.is_(None)).values(owner_user_id=user_id)
        )
        session.execute(
            update(ManagementTipORM).where(ManagementTipORM.owner_user_id.is_(None)).values(owner_user_id=user_id)
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_next_direct_report_id() -> int:
    if not _db_available:
        return 1
    from sqlalchemy import func, select

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportORM

    session = get_session()
    try:
        m = session.scalar(select(func.max(DirectReportORM.id)))
        return int(m or 0) + 1
    finally:
        session.close()


def _db_load_direct_reports_for_user(owner_user_id: int) -> list[dict[str, Any]]:
    if not _db_available:
        return []
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportORM

    session = get_session()
    try:
        rows = session.scalars(
            select(DirectReportORM)
            .where(DirectReportORM.owner_user_id == owner_user_id)
            .order_by(DirectReportORM.id)
        ).all()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                _normalize_direct_report(
                    {
                        "id": row.id,
                        "first_name": row.first_name,
                        "last_name": row.last_name,
                        "street_address_1": row.street_address_1,
                        "street_address_2": row.street_address_2,
                        "city": row.city,
                        "state": row.state,
                        "zipcode": row.zipcode,
                        "country": row.country,
                        "birthday": row.birthday,
                        "hire_date": row.hire_date,
                        "current_role": row.current_role,
                        "role_start_date": row.role_start_date,
                        "partner_name": row.partner_name,
                        "owner_user_id": row.owner_user_id,
                    }
                )
            )
        return out
    finally:
        session.close()


def _db_replace_direct_reports_for_user(owner_user_id: int, reports: list[dict[str, Any]]) -> None:
    """Replace only this user's direct_reports rows; other users' rows are unchanged."""
    if not _db_available:
        return
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportORM

    session = get_session()
    try:
        session.execute(delete(DirectReportORM).where(DirectReportORM.owner_user_id == owner_user_id))
        for r in reports:
            oid = r.get("owner_user_id")
            session.add(
                DirectReportORM(
                    id=int(r.get("id") or 0),
                    first_name=r.get("first_name") or "",
                    last_name=r.get("last_name") or "",
                    street_address_1=r.get("street_address_1"),
                    street_address_2=r.get("street_address_2"),
                    city=r.get("city"),
                    state=r.get("state"),
                    zipcode=r.get("zipcode"),
                    country=r.get("country"),
                    birthday=r.get("birthday"),
                    hire_date=r.get("hire_date"),
                    current_role=r.get("current_role"),
                    role_start_date=r.get("role_start_date"),
                    partner_name=r.get("partner_name"),
                    owner_user_id=int(oid) if oid is not None else owner_user_id,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _save_direct_reports_for_user(owner_user_id: int, reports: list[dict[str, Any]]) -> None:
    """Persist one tenant's direct reports to SQLite."""
    if not _db_available:
        return
    try:
        for r in reports:
            r["owner_user_id"] = owner_user_id
        _db_replace_direct_reports_for_user(owner_user_id, reports)
    except Exception as e:
        print(f"Could not save direct reports for user {owner_user_id}: {e}", file=sys.stderr)


def _db_load_management_tips() -> list[dict[str, Any]]:
    """Load all management tips from the database as list of dicts (date, text, optional owner_user_id)."""
    if not _db_available:
        return []
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import ManagementTipORM

    session = get_session()
    try:
        rows = session.scalars(select(ManagementTipORM).order_by(ManagementTipORM.id)).all()
        return [
            {"date": row.date, "text": row.text, "owner_user_id": row.owner_user_id}
            for row in rows
        ]
    finally:
        session.close()


def _db_load_management_tips_for_user(owner_user_id: int) -> list[dict[str, Any]]:
    if not _db_available:
        return []
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import ManagementTipORM

    session = get_session()
    try:
        rows = session.scalars(
            select(ManagementTipORM)
            .where(ManagementTipORM.owner_user_id == owner_user_id)
            .order_by(ManagementTipORM.id)
        ).all()
        return [{"date": row.date, "text": row.text, "owner_user_id": row.owner_user_id} for row in rows]
    finally:
        session.close()


def _get_latest_management_tip_for_user(owner_user_id: int) -> str:
    if not _db_available:
        return "No tip yet. Generate one from Mistral AI."
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import ManagementTipORM

    session = get_session()
    try:
        row = session.scalars(
            select(ManagementTipORM)
            .where(ManagementTipORM.owner_user_id == owner_user_id)
            .order_by(ManagementTipORM.id.desc())
            .limit(1)
        ).first()
        if row:
            return row.text
        return "No tip yet. Generate one from Mistral AI."
    finally:
        session.close()


def _user_has_management_tip_for_date(owner_user_id: int, date_str: str) -> bool:
    """True if this user already has at least one tip row for the given calendar day (YYYY-MM-DD)."""
    tips = _db_load_management_tips_for_user(owner_user_id)
    prefix = (date_str or "")[:10]
    for t in tips:
        if str(t.get("date") or "")[:10] == prefix:
            return True
    return False


def _ensure_daily_management_tip_for_user(owner_user_id: int) -> None:
    """If Mistral is configured and the user has no tip for today, generate one owned by that user."""
    if not _db_available or not owner_user_id:
        return
    today_str = date.today().isoformat()
    if _user_has_management_tip_for_date(owner_user_id, today_str):
        return
    if not MISTRAL_AVAILABLE or not _get_mistral_api_key():
        return
    _generate_management_tip_with_ai(silent=True, owner_user_id=owner_user_id)


def _db_insert_management_tip(owner_user_id: int | None, date_str: str, text: str) -> None:
    if not _db_available:
        return
    from wingmanem.database import get_session
    from wingmanem.orm_models import ManagementTipORM

    session = get_session()
    try:
        session.add(ManagementTipORM(date=date_str, text=text, owner_user_id=owner_user_id))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _migrate_direct_report_comp_json_file() -> None:
    """Rename legacy comp JSON to the current filename if needed."""
    legacy = LEGACY_DIRECT_REPORT_COMP_DATA_FILE
    current = DIRECT_REPORT_COMP_DATA_FILE
    if os.path.isfile(legacy) and not os.path.isfile(current):
        try:
            os.replace(legacy, current)
        except OSError:
            pass


def _db_populate_from_json_files() -> None:
    """Seed SQLite from JSON only when the corresponding table is empty (migration / first run)."""
    if not _db_available:
        return
    _migrate_direct_report_comp_json_file()
    if not _db_load_direct_reports() and os.path.isfile(DIRECT_REPORTS_FILE):
        try:
            with open(DIRECT_REPORTS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            raw = data if isinstance(data, list) else []
            reports = [_normalize_direct_report(r) for r in raw if isinstance(r, dict)]
            seed_owner = _db_first_user_id()
            if seed_owner is not None:
                for r in reports:
                    if r.get("owner_user_id") is None:
                        r["owner_user_id"] = seed_owner
            if reports:
                _db_replace_direct_reports_from_list(reports)
        except (json.JSONDecodeError, OSError):
            pass
    if not _db_load_management_tips() and os.path.isfile(MANAGEMENT_TIPS_FILE):
        try:
            with open(MANAGEMENT_TIPS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            tips: list[dict[str, str]] = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("date") and item.get("text"):
                        tips.append({"date": str(item["date"])[:10], "text": str(item["text"]).strip()})
                    elif isinstance(item, str) and item.strip():
                        tips.append({"date": date.today().isoformat(), "text": item.strip()})
            tip_owner = _db_first_user_id()
            if tip_owner is not None:
                for t in tips:
                    if isinstance(t, dict) and t.get("owner_user_id") is None:
                        t["owner_user_id"] = tip_owner
            if tips:
                _db_replace_management_tips_from_list(tips)
        except (json.JSONDecodeError, OSError):
            pass
    if not _db_load_all_goals() and os.path.isfile(DIRECT_REPORT_GOALS_FILE):
        try:
            with open(DIRECT_REPORT_GOALS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            raw = data if isinstance(data, list) else []
            goals: list[dict[str, Any]] = []
            for g in raw:
                if isinstance(g, dict) and g.get("direct_report_id") is not None:
                    goals.append({
                        "id": g.get("id"),
                        "direct_report_id": int(g["direct_report_id"]),
                        "goal_title": str(g.get("goal_title") or "")[:50],
                        "goal_description": str(g.get("goal_description") or "")[:100],
                        "goal_completion_date": str(g.get("goal_completion_date") or "")[:10],
                    })
            if goals:
                _db_replace_goals_from_list(goals)
        except (json.JSONDecodeError, OSError):
            pass
    comp_json = (
        DIRECT_REPORT_COMP_DATA_FILE
        if os.path.isfile(DIRECT_REPORT_COMP_DATA_FILE)
        else LEGACY_DIRECT_REPORT_COMP_DATA_FILE
    )
    if not _db_load_direct_report_comp_data() and os.path.isfile(comp_json):
        try:
            with open(comp_json, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                _db_replace_direct_report_comp_data_from_list(data)
        except (json.JSONDecodeError, OSError):
            pass


def _db_insert_one_to_one_summary(direct_report_id: int, date_str: str, response_text: str) -> None:
    """Store a 1:1 summary for a direct report and date."""
    if not _db_available:
        return
    from wingmanem.database import get_session
    from wingmanem.orm_models import OneToOneSummaryORM

    session = get_session()
    try:
        session.add(
            OneToOneSummaryORM(
                direct_report_id=direct_report_id,
                date=date_str,
                response_text=response_text,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_get_one_to_one_summaries(direct_report_id: int) -> list[dict[str, Any]]:
    """Get all 1:1 summaries for a direct report, sorted by date (oldest first)."""
    if not _db_available:
        return []
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import OneToOneSummaryORM

    session = get_session()
    try:
        rows = session.scalars(
            select(OneToOneSummaryORM)
            .where(OneToOneSummaryORM.direct_report_id == direct_report_id)
            .order_by(OneToOneSummaryORM.date)
        ).all()
        return [
            {
                "id": row.id,
                "direct_report_id": row.direct_report_id,
                "date": row.date,
                "response_text": row.response_text,
            }
            for row in rows
        ]
    finally:
        session.close()


def _db_delete_one_to_one_by_report_and_date(direct_report_id: int, date_str: str) -> bool:
    """Delete the 1:1 summary for a direct report on a specific date. Returns True if a row was deleted."""
    if not _db_available:
        return False
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import OneToOneSummaryORM

    session = get_session()
    try:
        res = session.execute(
            delete(OneToOneSummaryORM).where(
                OneToOneSummaryORM.direct_report_id == direct_report_id,
                OneToOneSummaryORM.date == date_str,
            )
        )
        session.commit()
        return res.rowcount > 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_purge_one_to_one_for_report(direct_report_id: int) -> int:
    """Delete all 1:1 summaries for a direct report. Returns number of rows deleted."""
    if not _db_available:
        return 0
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import OneToOneSummaryORM

    session = get_session()
    try:
        res = session.execute(delete(OneToOneSummaryORM).where(OneToOneSummaryORM.direct_report_id == direct_report_id))
        session.commit()
        return res.rowcount
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ----- Direct report goals (Chunk #5) -----


def _db_insert_goal(direct_report_id: int, goal_title: str, goal_description: str, goal_completion_date: str | None) -> int:
    """Insert a goal; returns the new row id."""
    if not _db_available:
        return 0
    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportGoalORM

    session = get_session()
    try:
        row = DirectReportGoalORM(
            direct_report_id=direct_report_id,
            goal_title=goal_title or "",
            goal_description=goal_description or "",
            goal_completion_date=goal_completion_date or "",
        )
        session.add(row)
        session.flush()
        new_id = int(row.id)
        session.commit()
        return new_id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_load_all_goals() -> list[dict[str, Any]]:
    """Load all goals from the database."""
    if not _db_available:
        return []
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportGoalORM

    session = get_session()
    try:
        rows = session.scalars(
            select(DirectReportGoalORM).order_by(DirectReportGoalORM.direct_report_id, DirectReportGoalORM.id)
        ).all()
        return [
            {
                "id": row.id,
                "direct_report_id": row.direct_report_id,
                "goal_title": row.goal_title,
                "goal_description": row.goal_description,
                "goal_completion_date": row.goal_completion_date,
            }
            for row in rows
        ]
    finally:
        session.close()


def _db_load_goals_for_report(direct_report_id: int) -> list[dict[str, Any]]:
    """Load goals for a specific direct report."""
    if not _db_available:
        return []
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportGoalORM

    session = get_session()
    try:
        rows = session.scalars(
            select(DirectReportGoalORM)
            .where(DirectReportGoalORM.direct_report_id == direct_report_id)
            .order_by(DirectReportGoalORM.id)
        ).all()
        return [
            {
                "id": row.id,
                "direct_report_id": row.direct_report_id,
                "goal_title": row.goal_title,
                "goal_description": row.goal_description,
                "goal_completion_date": row.goal_completion_date,
            }
            for row in rows
        ]
    finally:
        session.close()


def _db_delete_goals_for_report(direct_report_id: int) -> int:
    """Delete all goals for a direct report. Returns number deleted."""
    if not _db_available:
        return 0
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportGoalORM

    session = get_session()
    try:
        res = session.execute(delete(DirectReportGoalORM).where(DirectReportGoalORM.direct_report_id == direct_report_id))
        session.commit()
        return res.rowcount
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_delete_goal_by_id(goal_id: int) -> bool:
    """Delete a goal by id. Returns True if deleted."""
    if not _db_available:
        return False
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportGoalORM

    session = get_session()
    try:
        res = session.execute(delete(DirectReportGoalORM).where(DirectReportGoalORM.id == goal_id))
        session.commit()
        return res.rowcount > 0
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_replace_goals_from_list(goals: list[dict[str, Any]]) -> None:
    """Replace direct_report_goals table with the given list (same scope as rewriting goals JSON)."""
    if not _db_available:
        return
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportGoalORM

    session = get_session()
    try:
        session.execute(delete(DirectReportGoalORM))
        for g in goals:
            session.add(
                DirectReportGoalORM(
                    id=int(g.get("id") or 0),
                    direct_report_id=int(g.get("direct_report_id") or 0),
                    goal_title=g.get("goal_title") or "",
                    goal_description=g.get("goal_description") or "",
                    goal_completion_date=g.get("goal_completion_date") or "",
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _report_ids_owned_by_user(owner_user_id: int) -> set[int]:
    return {int(r["id"]) for r in _db_load_direct_reports_for_user(owner_user_id) if r.get("id") is not None}


def user_owns_direct_report(owner_user_id: int, report_id: int) -> bool:
    """True if report_id belongs to this application user (web authorization)."""
    try:
        return int(report_id) in _report_ids_owned_by_user(owner_user_id)
    except (TypeError, ValueError):
        return False


def _load_direct_report_goals_for_user(owner_user_id: int) -> list[dict[str, Any]]:
    rids = _report_ids_owned_by_user(owner_user_id)
    if not rids:
        return []
    all_goals = _db_load_all_goals()
    return [g for g in all_goals if int(g.get("direct_report_id") or 0) in rids]


def _save_direct_report_goals_for_user(owner_user_id: int, goals: list[dict[str, Any]]) -> None:
    rids = _report_ids_owned_by_user(owner_user_id)
    others = [g for g in _db_load_all_goals() if int(g.get("direct_report_id") or 0) not in rids]
    merged = others + list(goals)
    _save_direct_report_goals(merged)


def _delete_all_goals_for_user(owner_user_id: int) -> None:
    rids = _report_ids_owned_by_user(owner_user_id)
    merged = [g for g in _db_load_all_goals() if int(g.get("direct_report_id") or 0) not in rids]
    _save_direct_report_goals(merged)


def _next_goal_id_global() -> int:
    return _next_goal_id(_db_load_all_goals())


def _db_load_direct_report_comp_data() -> list[dict[str, Any]]:
    """Load all rows from direct-report comp data as dicts (shape used by comp letter templates)."""
    if not _db_available:
        return []
    from sqlalchemy import select

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportCompDataORM

    session = get_session()
    try:
        rows = session.scalars(
            select(DirectReportCompDataORM).order_by(DirectReportCompDataORM.direct_report_id)
        ).all()
        return [
            {
                "direct_report_id": row.direct_report_id,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "rating": row.rating,
                "salary": row.salary,
                "percent_change": row.percent_change,
                "dollar_change": row.dollar_change,
                "new_salary": row.new_salary,
                "bonus": row.bonus,
            }
            for row in rows
        ]
    finally:
        session.close()


def _db_replace_direct_report_comp_data_from_list(records: list[dict[str, Any]]) -> None:
    """Replace direct_report_comp_data table from a list of statement dicts (same scope as comp JSON)."""
    if not _db_available:
        return
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportCompDataORM

    session = get_session()
    try:
        session.execute(delete(DirectReportCompDataORM))
        for rec in records:
            if not isinstance(rec, dict):
                continue
            session.add(
                DirectReportCompDataORM(
                    direct_report_id=int(rec.get("direct_report_id") or 0),
                    first_name=str(rec.get("first_name") or ""),
                    last_name=str(rec.get("last_name") or ""),
                    rating=int(rec.get("rating") or 0),
                    salary=int(rec.get("salary") or 0),
                    percent_change=float(rec.get("percent_change") or 0.0),
                    dollar_change=int(rec.get("dollar_change") or 0),
                    new_salary=int(rec.get("new_salary") or 0),
                    bonus=int(rec.get("bonus") or 0),
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_load_direct_report_comp_data_for_user(owner_user_id: int) -> list[dict[str, Any]]:
    rids = _report_ids_owned_by_user(owner_user_id)
    if not rids:
        return []
    return [row for row in _db_load_direct_report_comp_data() if int(row.get("direct_report_id") or 0) in rids]


def _db_merge_replace_comp_data_for_user(owner_user_id: int, records: list[dict[str, Any]]) -> None:
    if not _db_available:
        return
    rids = _report_ids_owned_by_user(owner_user_id)
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportCompDataORM

    session = get_session()
    try:
        if rids:
            session.execute(delete(DirectReportCompDataORM).where(DirectReportCompDataORM.direct_report_id.in_(rids)))
        for rec in records:
            if not isinstance(rec, dict):
                continue
            session.add(
                DirectReportCompDataORM(
                    direct_report_id=int(rec.get("direct_report_id") or 0),
                    first_name=str(rec.get("first_name") or ""),
                    last_name=str(rec.get("last_name") or ""),
                    rating=int(rec.get("rating") or 0),
                    salary=int(rec.get("salary") or 0),
                    percent_change=float(rec.get("percent_change") or 0.0),
                    dollar_change=int(rec.get("dollar_change") or 0),
                    new_salary=int(rec.get("new_salary") or 0),
                    bonus=int(rec.get("bonus") or 0),
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_delete_all_direct_report_comp_data() -> None:
    """Remove all rows from direct-report comp data table."""
    if not _db_available:
        return
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportCompDataORM

    session = get_session()
    try:
        session.execute(delete(DirectReportCompDataORM))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _db_delete_comp_data_for_direct_report(direct_report_id: int) -> None:
    """Remove compensation statement rows for one direct report."""
    if not _db_available:
        return
    from sqlalchemy import delete

    from wingmanem.database import get_session
    from wingmanem.orm_models import DirectReportCompDataORM

    session = get_session()
    try:
        session.execute(
            delete(DirectReportCompDataORM).where(DirectReportCompDataORM.direct_report_id == direct_report_id)
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _load_direct_report_goals() -> list[dict[str, Any]]:
    """Load goals: prefer SQLite; else JSON. Mirror to JSON after DB read. Creates empty pair if missing."""
    if _db_available:
        try:
            goals = _db_load_all_goals()
        except Exception:
            goals = []
        if goals:
            _write_direct_report_goals_json_file(goals)
            return goals
    if not os.path.isfile(DIRECT_REPORT_GOALS_FILE):
        goals = []
        _save_direct_report_goals(goals)
        return goals
    try:
        with open(DIRECT_REPORT_GOALS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        raw = data if isinstance(data, list) else []
        goals = []
        for g in raw:
            if isinstance(g, dict) and g.get("direct_report_id") is not None:
                goals.append({
                    "id": g.get("id"),
                    "direct_report_id": int(g["direct_report_id"]),
                    "goal_title": str(g.get("goal_title") or "")[:50],
                    "goal_description": str(g.get("goal_description") or "")[:100],
                    "goal_completion_date": str(g.get("goal_completion_date") or "")[:10],
                })
        if _db_available:
            try:
                _db_replace_goals_from_list(goals)
            except Exception:
                pass
        _write_direct_report_goals_json_file(goals)
        return goals
    except (json.JSONDecodeError, OSError):
        return []


def _save_direct_report_goals(goals: list[dict[str, Any]]) -> None:
    """Persist goals list: database replace then JSON mirror."""
    if _db_available:
        try:
            _db_replace_goals_from_list(goals)
        except Exception as e:
            print(f"Could not save goals to database: {e}", file=sys.stderr)
    _write_direct_report_goals_json_file(goals)


def _next_goal_id(goals: list[dict[str, Any]]) -> int:
    """Return next available goal id."""
    max_id = 0
    for g in goals:
        try:
            max_id = max(max_id, int(g.get("id") or 0))
        except (TypeError, ValueError):
            pass
    return max_id + 1


def _get_goal_by_id(goal_id: int) -> dict[str, Any] | None:
    """Return a goal dict by id, or None if not found."""
    goals = _load_direct_report_goals()
    for g in goals:
        if g.get("id") == goal_id:
            return dict(g)
    return None


def _update_goal_by_id(
    goal_id: int,
    goal_title: str,
    goal_description: str,
    goal_completion_date: str | None,
) -> bool:
    """Update a goal by id in JSON and DB. Returns True if updated."""
    goals = _load_direct_report_goals()
    for g in goals:
        if g.get("id") == goal_id:
            g["goal_title"] = (goal_title or "")[:50]
            g["goal_description"] = (goal_description or "")[:100]
            g["goal_completion_date"] = (goal_completion_date or "")[:10]
            _save_direct_report_goals(goals)
            return True
    return False


def _delete_goal_by_id(goal_id: int) -> bool:
    """Delete a goal by id from both JSON file and database. Returns True if deleted."""
    goals = _load_direct_report_goals()
    before = len(goals)
    goals = [g for g in goals if g.get("id") != goal_id]
    if len(goals) == before:
        return False
    _save_direct_report_goals(goals)
    return True


def _delete_goals_for_direct_report(direct_report_id: int) -> None:
    """Delete all goals for a direct report from both JSON file and database (cascade delete)."""
    goals = _load_direct_report_goals()
    goals = [g for g in goals if int(g.get("direct_report_id") or 0) != direct_report_id]
    _save_direct_report_goals(goals)


def _delete_all_goals() -> None:
    """Delete all goals (when purging all direct reports)."""
    _save_direct_report_goals([])


def _generate_goals_with_ai(num: int) -> int:
    """Generate goals for direct reports using Mistral AI. Returns count of goals added."""
    if not MISTRAL_AVAILABLE:
        return 0
    api_key = _get_mistral_api_key()
    if not api_key:
        return 0
    if not direct_reports:
        return 0
    num = max(1, min(20, num))
    report_list = [
        {"id": r.get("id"), "first_name": r.get("first_name", ""), "last_name": r.get("last_name", "")}
        for r in direct_reports[:50]
        if r.get("id")
    ]
    if not report_list:
        return 0
    ids_str = ", ".join(str(r["id"]) for r in report_list)
    names_str = ", ".join(f"{r['first_name']} {r['last_name']} (id {r['id']})" for r in report_list)
    prompt = f"""Generate exactly {num} realistic professional development goals for engineering direct reports.

Available direct reports (use only these IDs): {names_str}
Valid direct_report_id values: {ids_str}

Return a single JSON object with key "goals" whose value is an array of {num} objects. Each object must have:
- direct_report_id (integer, must be one of {ids_str})
- goal_title (string, max 50 chars, e.g. "Complete AWS certification")
- goal_description (string, max 100 chars)
- goal_completion_date (string YYYY-MM-DD, or empty string for optional)

Distribute goals across different direct reports. Example:
{{"goals": [{{"direct_report_id": 1, "goal_title": "Complete AWS certification", "goal_description": "Pass AWS Solutions Architect exam by Q2", "goal_completion_date": "2025-06-30"}}, ...]}}

Output only this JSON object, no other text."""

    try:
        client = Mistral(api_key=api_key)
        valid_ids = {r["id"] for r in report_list}
        try:
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except TypeError:
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
        raw = message.choices[0].message.content
        if isinstance(raw, list):
            raw = "".join(
                p.get("text", p.get("content", "")) if isinstance(p, dict) else str(p)
                for p in raw
            )
        else:
            raw = raw or ""
        response_text = raw.strip()
        if response_text.startswith("```"):
            end = response_text.find("\n", 3)
            if end != -1:
                response_text = response_text[end + 1 :].rstrip()
            if response_text.endswith("```"):
                response_text = response_text[:-3].rstrip()

        objects: list[dict] = []
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                arr = parsed.get("goals") or parsed.get("goals_list")
                if isinstance(arr, list):
                    objects = [x for x in arr if isinstance(x, dict)]
                if not objects:
                    for v in parsed.values():
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            objects = [x for x in v if isinstance(x, dict)]
                            break
            elif isinstance(parsed, list):
                objects = [x for x in parsed if isinstance(x, dict)]
        except (json.JSONDecodeError, TypeError):
            pass

        goals = _load_direct_report_goals()
        next_id = _next_goal_id(goals)
        added = 0
        for obj in objects:
            rid = obj.get("direct_report_id")
            if rid is None or int(rid) not in valid_ids:
                continue
            title = str(obj.get("goal_title") or "")[:50]
            desc = str(obj.get("goal_description") or "")[:100]
            comp = str(obj.get("goal_completion_date") or "")[:10]
            goals.append({
                "id": next_id,
                "direct_report_id": int(rid),
                "goal_title": title,
                "goal_description": desc,
                "goal_completion_date": comp,
            })
            next_id += 1
            added += 1
        if added > 0:
            _save_direct_report_goals(goals)
        return added
    except Exception:
        return 0


def _generate_goals_with_ai_for_user(owner_user_id: int, num: int) -> int:
    """Like _generate_goals_with_ai but only for direct reports owned by owner_user_id."""
    if not MISTRAL_AVAILABLE:
        return 0
    api_key = _get_mistral_api_key()
    if not api_key:
        return 0
    direct_reports_local = _db_load_direct_reports_for_user(owner_user_id)
    if not direct_reports_local:
        return 0
    num = max(1, min(20, num))
    report_list = [
        {"id": r.get("id"), "first_name": r.get("first_name", ""), "last_name": r.get("last_name", "")}
        for r in direct_reports_local[:50]
        if r.get("id")
    ]
    if not report_list:
        return 0
    ids_str = ", ".join(str(r["id"]) for r in report_list)
    names_str = ", ".join(f"{r['first_name']} {r['last_name']} (id {r['id']})" for r in report_list)
    prompt = f"""Generate exactly {num} realistic professional development goals for engineering direct reports.

Available direct reports (use only these IDs): {names_str}
Valid direct_report_id values: {ids_str}

Return a single JSON object with key "goals" whose value is an array of {num} objects. Each object must have:
- direct_report_id (integer, must be one of {ids_str})
- goal_title (string, max 50 chars, e.g. "Complete AWS certification")
- goal_description (string, max 100 chars)
- goal_completion_date (string YYYY-MM-DD, or empty string for optional)

Distribute goals across different direct reports. Example:
{{"goals": [{{"direct_report_id": 1, "goal_title": "Complete AWS certification", "goal_description": "Pass AWS Solutions Architect exam by Q2", "goal_completion_date": "2025-06-30"}}, ...]}}

Output only this JSON object, no other text."""

    try:
        client = Mistral(api_key=api_key)
        valid_ids = {r["id"] for r in report_list}
        try:
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except TypeError:
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
        raw = message.choices[0].message.content
        if isinstance(raw, list):
            raw = "".join(
                p.get("text", p.get("content", "")) if isinstance(p, dict) else str(p)
                for p in raw
            )
        else:
            raw = raw or ""
        response_text = raw.strip()
        if response_text.startswith("```"):
            end = response_text.find("\n", 3)
            if end != -1:
                response_text = response_text[end + 1 :].rstrip()
            if response_text.endswith("```"):
                response_text = response_text[:-3].rstrip()

        objects: list[dict] = []
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                arr = parsed.get("goals") or parsed.get("goals_list")
                if isinstance(arr, list):
                    objects = [x for x in arr if isinstance(x, dict)]
                if not objects:
                    for v in parsed.values():
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            objects = [x for x in v if isinstance(x, dict)]
                            break
            elif isinstance(parsed, list):
                objects = [x for x in parsed if isinstance(x, dict)]
        except (json.JSONDecodeError, TypeError):
            pass

        goals = _load_direct_report_goals_for_user(owner_user_id)
        next_id = _next_goal_id_global()
        added = 0
        for obj in objects:
            rid = obj.get("direct_report_id")
            if rid is None or int(rid) not in valid_ids:
                continue
            title = str(obj.get("goal_title") or "")[:50]
            desc = str(obj.get("goal_description") or "")[:100]
            comp = str(obj.get("goal_completion_date") or "")[:10]
            goals.append(
                {
                    "id": next_id,
                    "direct_report_id": int(rid),
                    "goal_title": title,
                    "goal_description": desc,
                    "goal_completion_date": comp,
                }
            )
            next_id += 1
            added += 1
        if added > 0:
            _save_direct_report_goals_for_user(owner_user_id, goals)
        return added
    except Exception:
        return 0


def _generate_direct_report_comp_statements() -> list[dict[str, Any]]:
    """Generate compensation data for direct reports; persist to DB then JSON mirror."""
    if not direct_reports:
        statements: list[dict[str, Any]] = []
        try:
            _db_replace_direct_report_comp_data_from_list(statements)
        except Exception:
            pass
        try:
            _write_direct_report_comp_data_json_file(statements)
        except OSError:
            pass
        return statements
    statements = []
    for r in direct_reports:
        rid = r.get("id")
        if not rid:
            continue
        first = (r.get("first_name") or "").strip() or "Unknown"
        last = (r.get("last_name") or "").strip() or "Direct Report"
        rating = random.randint(1, 5)
        # Base salary range
        salary = random.randint(90000, 200000)
        # Percentage change by rating
        if rating == 5:
            pct = random.uniform(8.0, 12.0)
        elif rating == 4:
            pct = random.uniform(5.0, 8.0)
        elif rating == 3:
            pct = random.uniform(3.0, 5.0)
        elif rating == 2:
            pct = random.uniform(1.0, 3.0)
        else:
            pct = random.uniform(0.0, 1.0)
        dollar_change = int(round(salary * (pct / 100.0)))
        new_salary = salary + dollar_change
        # Bonus reflective of rating: higher rating → higher bonus, capped 10k–30k
        base_bonus = 10000 + (rating - 1) * 5000
        max_bonus = base_bonus + 5000
        bonus = random.randint(base_bonus, max_bonus)
        bonus = max(10000, min(30000, bonus))
        statements.append(
            {
                "direct_report_id": int(rid),
                "first_name": first,
                "last_name": last,
                "rating": rating,
                "salary": salary,
                "percent_change": round(pct, 2),
                "dollar_change": dollar_change,
                "new_salary": new_salary,
                "bonus": bonus,
            }
        )
    try:
        _db_replace_direct_report_comp_data_from_list(statements)
    except Exception:
        pass
    try:
        _write_direct_report_comp_data_json_file(statements)
    except OSError:
        pass
    return statements


def _generate_direct_report_comp_statements_for_user(owner_user_id: int) -> list[dict[str, Any]]:
    """Generate compensation rows only for this user's direct reports; merge into comp table."""
    reports = _db_load_direct_reports_for_user(owner_user_id)
    if not reports:
        _db_merge_replace_comp_data_for_user(owner_user_id, [])
        try:
            _write_direct_report_comp_data_json_file(_db_load_direct_report_comp_data())
        except OSError:
            pass
        return []
    statements: list[dict[str, Any]] = []
    for r in reports:
        rid = r.get("id")
        if not rid:
            continue
        first = (r.get("first_name") or "").strip() or "Unknown"
        last = (r.get("last_name") or "").strip() or "Direct Report"
        rating = random.randint(1, 5)
        salary = random.randint(90000, 200000)
        if rating == 5:
            pct = random.uniform(8.0, 12.0)
        elif rating == 4:
            pct = random.uniform(5.0, 8.0)
        elif rating == 3:
            pct = random.uniform(3.0, 5.0)
        elif rating == 2:
            pct = random.uniform(1.0, 3.0)
        else:
            pct = random.uniform(0.0, 1.0)
        dollar_change = int(round(salary * (pct / 100.0)))
        new_salary = salary + dollar_change
        base_bonus = 10000 + (rating - 1) * 5000
        max_bonus = base_bonus + 5000
        bonus = random.randint(base_bonus, max_bonus)
        bonus = max(10000, min(30000, bonus))
        statements.append(
            {
                "direct_report_id": int(rid),
                "first_name": first,
                "last_name": last,
                "rating": rating,
                "salary": salary,
                "percent_change": round(pct, 2),
                "dollar_change": dollar_change,
                "new_salary": new_salary,
                "bonus": bonus,
            }
        )
    try:
        _db_merge_replace_comp_data_for_user(owner_user_id, statements)
    except Exception:
        pass
    try:
        _write_direct_report_comp_data_json_file(_db_load_direct_report_comp_data())
    except OSError:
        pass
    return statements


def _delete_direct_report_comp_statements() -> None:
    """Delete direct-report comp data file if present and clear DB mirror table."""
    for path in (DIRECT_REPORT_COMP_DATA_FILE, LEGACY_DIRECT_REPORT_COMP_DATA_FILE):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
    _db_delete_all_direct_report_comp_data()


# Backward-compatible helper aliases (older names pointed at JSON-first ordering)
_db_load_employee_comp_data = _db_load_direct_report_comp_data
_db_sync_employee_comp_data_from_list = _db_replace_direct_report_comp_data_from_list
_db_delete_all_employee_comp_data = _db_delete_all_direct_report_comp_data
_generate_employee_comp_statements = _generate_direct_report_comp_statements
_delete_employee_comp_statements = _delete_direct_report_comp_statements
_db_sync_direct_reports_from_list = _db_replace_direct_reports_from_list
_db_sync_management_tips_from_list = _db_replace_management_tips_from_list
_db_sync_goals_from_list = _db_replace_goals_from_list
_db_sync_direct_report_comp_data_from_list = _db_replace_direct_report_comp_data_from_list


# ============================================================================
# UTILITIES — config, I/O, menu building
# ============================================================================

def _get_expected_password() -> str:
    """Expected password from environment; defaults to 'wingman' for local dev."""
    return os.environ.get("WINGMANEM_PASSWORD", "p")


def _get_mistral_api_key() -> str | None:
    return "579aUFUawlFEvqF6aVXIp6YjxYZvyi3O"


def _clear_screen() -> None:
    """Clear terminal for cleaner menu display."""
    os.system("cls" if os.name == "nt" else "clear")


def _prompt_choice(prompt: str, max_option: int) -> int:
    """Prompt for numeric choice; returns 1-based option or 0 on invalid."""
    try:
        raw = input(prompt).strip()
        choice = int(raw)
        if 1 <= choice <= max_option:
            return choice
    except ValueError:
        pass
    return 0


def _pause() -> None:
    """Pause until user presses Enter."""
    input("\nPress Enter to continue...")


def _wrap_text(text: str, width: int) -> list[str]:
    """Wrap text to fit within width, breaking at word boundaries. Returns list of lines."""
    if not text.strip():
        return [""]
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        current: list[str] = []
        current_len = 0
        for w in words:
            if current_len + len(current) + len(w) <= width:
                current.append(w)
                current_len += len(w)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [w] if len(w) <= width else [w[:width]]
                current_len = len(current[0]) if len(w) > width else len(w)
        if current:
            lines.append(" ".join(current))
    return lines


def _menu_box(
    title: str,
    options: list[str | tuple[str, bool] | tuple[str, bool, bool]],
    width: int = 58,
    middle: list[str | tuple[str, str]] | None = None,
    middle_position: str = "top",
) -> str:
    """Build a box menu. Options: label string, (label, enabled), or (label, enabled, red).
    Default font is black; set red=True for red font. If middle is provided, those lines
    appear inside the box. A middle item can be a string (entire line bold) or
    (bold_prefix, rest) so only the bold_prefix is bold.
    middle_position can be 'top' (default) or 'bottom'."""
    border = "╔" + "═" * width + "╗"
    sep = "╠" + "═" * width + "╣"
    bottom = "╚" + "═" * width + "╝"
    title_content = title[:width].ljust(width)
    lines = ["║" + MENU_BOLD + title_content + MENU_COLOR_RESET + "║"]
    for opt in options:
        if isinstance(opt, tuple):
            text = opt[0]
            enabled = opt[1] if len(opt) >= 2 else True
            red = opt[2] if len(opt) >= 3 else False
        else:
            text, enabled, red = opt, True, False
        content = text[:width].ljust(width)
        if not enabled:
            color = MENU_COLOR_DISABLED
        elif red:
            color = MENU_COLOR_RED
        else:
            color = MENU_COLOR_BLACK
        lines.append("║" + color + content + MENU_COLOR_RESET + "║")
    middle_lines: list[str] = []
    if middle:
        for m in middle:
            if isinstance(m, tuple):
                bold_part, rest = m[0], m[1]
                full = bold_part + rest
                wrapped = _wrap_text(full, width - 4)  # Leave room for padding
                for i, wrapped_line in enumerate(wrapped):
                    if i == 0:
                        # First line: make only bold_part bold
                        bold_len = len(bold_part)
                        bold_text = wrapped_line[:bold_len]
                        rest_text = wrapped_line[bold_len:width - 4]
                        # Build content: padding + bold + text + reset + rest + padding
                        content = "  " + MENU_BOLD + bold_text + MENU_COLOR_RESET + rest_text
                        # Pad to width, accounting for invisible ANSI codes
                        visible_len = len("  ") + len(bold_text) + len(rest_text)
                        padding_needed = width - 2 - visible_len
                        content = content + (" " * padding_needed) + "  "
                        middle_lines.append("║" + content + "║")
                    else:
                        # Subsequent lines have no bold
                        padded_line = "  " + wrapped_line[:width - 4].ljust(width - 4) + "  "
                        middle_lines.append("║" + padded_line + "║")
            else:
                for wrapped_line in _wrap_text(m, width):
                    content = wrapped_line[:width].ljust(width)
                    middle_lines.append("║" + MENU_BOLD + content + MENU_COLOR_RESET + "║")
    if middle_lines and middle_position == "bottom":
        return "\n".join([border, lines[0], sep] + lines[1:] + [sep] + middle_lines + [bottom])
    return "\n".join([border, lines[0], sep] + middle_lines + lines[1:] + [bottom])


def _run_submenu(
    menu: str,
    max_option: int,
    actions: dict[int, Callable[[], None | bool]],
) -> None:
    """Display a sub-menu in a loop. Option max_option is Back; others run actions[choice].
    If an action returns True, skip the 'Press Enter' pause (e.g. after returning from a sub-menu)."""
    prompt = f"Select an option (1–{max_option}): "
    while True:
        _clear_screen()
        print(menu)
        choice = _prompt_choice(prompt, max_option)
        if choice == 0:
            print("Invalid option.")
            _pause()
            continue
        if choice == max_option:
            return
        if choice in actions:
            result = actions[choice]()
            if result is not True:
                _pause()


# ============================================================================
# DIRECT REPORTS — model helpers, load/save, list/add/delete/generate/purge
# ============================================================================

def _next_direct_report_id() -> int:
    """Return the next available id for a new direct report."""
    max_id = 0
    for r in direct_reports:
        try:
            max_id = max(max_id, int(r.get("id") or 0))
        except (TypeError, ValueError):
            pass
    return max_id + 1


def _direct_report_name_key(r: dict[str, Any]) -> str:
    """Return a normalized key for first_name + last_name (for duplicate check)."""
    first = (r.get("first_name") or "").strip().lower()
    last = (r.get("last_name") or "").strip().lower()
    return f"{first}|{last}"


def _is_duplicate_direct_report(data: dict[str, Any], existing_keys: set[str]) -> bool:
    """Return True if this report's first_name+last_name is already in existing_keys."""
    key = _direct_report_name_key(data)
    return bool(key and key in existing_keys)


def _normalize_direct_report(r: dict[str, Any]) -> dict[str, Any]:
    """Ensure dict has Direct_Reports table keys; migrate old camelCase keys."""
    key_map = {
        "firstName": "first_name", "lastName": "last_name",
        "birthdate": "birthday", "hireDate": "hire_date", "partnerName": "partner_name",
    }
    out: dict[str, Any] = {}
    for k, v in r.items():
        out[key_map.get(k, k)] = v
    # Required: id (keep if present), first_name, last_name
    if "first_name" not in out or out["first_name"] is None:
        out["first_name"] = ""
    if "last_name" not in out or out["last_name"] is None:
        out["last_name"] = ""
    # Optional
    for key in DIRECT_REPORT_OPTIONAL_KEYS:
        if key not in out:
            out[key] = None
    return out


def _load_direct_reports() -> None:
    """Load direct_reports into memory from SQLite when available; else from JSON. Mirror to JSON after DB load."""
    global direct_reports
    if _db_available:
        try:
            from_db = _db_load_direct_reports()
        except Exception:
            from_db = []
        if from_db:
            direct_reports = from_db
            next_id = _next_direct_report_id()
            for r in direct_reports:
                try:
                    if int(r.get("id") or 0) <= 0:
                        r["id"] = next_id
                        next_id += 1
                except (TypeError, ValueError):
                    r["id"] = next_id
                    next_id += 1
            _write_direct_reports_json_file(direct_reports)
            return
    if os.path.isfile(DIRECT_REPORTS_FILE):
        try:
            with open(DIRECT_REPORTS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            raw = data if isinstance(data, list) else []
            direct_reports = [_normalize_direct_report(r) for r in raw if isinstance(r, dict)]
            next_id = _next_direct_report_id()
            for r in direct_reports:
                try:
                    if int(r.get("id") or 0) <= 0:
                        r["id"] = next_id
                        next_id += 1
                except (TypeError, ValueError):
                    r["id"] = next_id
                    next_id += 1
        except (json.JSONDecodeError, OSError):
            direct_reports = []
    else:
        direct_reports = []
    if _db_available:
        try:
            _db_replace_direct_reports_from_list(direct_reports)
        except Exception:
            pass
    _write_direct_reports_json_file(direct_reports)


def _save_direct_reports() -> None:
    """Persist in-memory direct_reports: database first (full replace), then JSON mirror."""
    if _db_available:
        try:
            _db_replace_direct_reports_from_list(direct_reports)
        except Exception as e:
            print(f"Could not save direct reports to database: {e}", file=sys.stderr)
    _write_direct_reports_json_file(direct_reports)


# ============================================================================
# DIRECT REPORTS: Display & User Operations
# ============================================================================

_LIST_DIRECT_REPORT_COLUMNS = (
    ("id", "ID", 5),
    ("first_name", "First Name", 14),
    ("last_name", "Last Name", 14),
    ("street_address_1", "Street 1", 20),
    ("city", "City", 14),
    ("state", "State", 8),
    ("zipcode", "Zipcode", 10),
    ("birthday", "Birthday", 12),
    ("hire_date", "Hire Date", 12),
    ("current_role", "Current Role", 18),
    ("role_start_date", "Role Start", 12),
    ("partner_name", "Partner", 14),
)


def _print_direct_reports_table(reports: list[dict[str, Any]], title: str) -> None:
    """Print a table of direct reports (database listing)."""
    cols = _LIST_DIRECT_REPORT_COLUMNS
    fmt_parts = [f"{{:>{cols[0][2]}}}"] + [f"{{:{c[2]}}}" for c in cols[1:]]
    fmt = " ".join(fmt_parts)
    total_width = sum(c[2] for c in cols) + len(cols) - 1
    sep = "-" * total_width
    headers = [c[1] for c in cols]
    print(fmt.format(*headers))
    print(sep)
    for r in reports:
        row = []
        for key, _header, width in cols:
            val = r.get(key)
            if val is None:
                val = ""
            s = str(val)[:width] if val else ""
            row.append(s)
        print(fmt.format(*row))
    print(sep)
    print(f"Total: {len(reports)}")


def _list_direct_reports() -> None:
    """Display direct reports from the database."""
    print("\n--- Direct Reports (database) ---\n")
    try:
        db_reports = _db_load_direct_reports()
        if not db_reports:
            print("  No direct reports in database.")
        else:
            _print_direct_reports_table(db_reports, "")
    except Exception as e:
        print(f"  Error loading from database: {e}")
    print("\nAdd or delete from the menu; data is saved to both file and database.")


def _parse_optional_date(prompt: str) -> date | None:
    """Prompt for a date; empty input returns None. Accept YYYY-MM-DD or YYYYMMDD (no hyphens)."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        # Allow digits only (e.g. 19900515) or with hyphens/spaces
        digits_only = raw.replace("-", "").replace(" ", "")
        if digits_only.isdigit() and len(digits_only) == 8:
            try:
                return date(
                    int(digits_only[0:4]),
                    int(digits_only[4:6]),
                    int(digits_only[6:8]),
                )
            except ValueError:
                pass
        else:
            try:
                return datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                pass
        print("  Invalid date. Use YYYY-MM-DD or YYYYMMDD (e.g. 2022-03-15 or 20220315). Try again.")


def _add_direct_report() -> None:
    """Prompt for direct report fields (required: first_name, last_name) and append to direct_reports."""
    _clear_screen()
    print()
    #_list_direct_reports()
    print("\n--- Add Direct Report ---")
    first_name = input("First name (required): ").strip() or "Unknown"
    last_name = input("Last name (required): ").strip() or "Unknown"
    report = _normalize_direct_report({
        "id": _next_direct_report_id(),
        "first_name": first_name,
        "last_name": last_name,
    })
    report["street_address_1"] = input("Street address 1 (or Enter to skip): ").strip() or None
    report["street_address_2"] = input("Street address 2 (or Enter to skip): ").strip() or None
    report["city"] = input("City (or Enter to skip): ").strip() or None
    report["state"] = input("State (or Enter to skip): ").strip() or None
    report["zipcode"] = input("Zipcode (or Enter to skip): ").strip() or None
    report["country"] = input("Country (or Enter to skip): ").strip() or None
    bd = _parse_optional_date("Birthday (YYYYMMDD or YYYY-MM-DD, or Enter to skip): ")
    report["birthday"] = bd.isoformat() if bd else None
    hd = _parse_optional_date("Hire date (YYYYMMDD or YYYY-MM-DD, or Enter to skip): ")
    report["hire_date"] = hd.isoformat() if hd else None
    report["current_role"] = input("Current role (or Enter to skip): ").strip() or None
    rsd = _parse_optional_date("Role start date (YYYYMMDD or YYYY-MM-DD, or Enter to skip): ")
    report["role_start_date"] = rsd.isoformat() if rsd else None
    report["partner_name"] = input("Partner name (or Enter to skip): ").strip() or None
    direct_reports.append(report)
    _save_direct_reports()
    print(f"\nAdded: {report['first_name']} {report['last_name']}")
    #_list_direct_reports()


def _delete_direct_report() -> None | bool:
    """Prompt for the ID of the direct report to delete, remove it, save to file."""
    _list_direct_reports()
    if not direct_reports:
        return True
    raw = input("\nEnter the ID of the direct report to delete (or press Enter to return to menu): ").strip()
    if raw == "":
        return True  # Skip "Press Enter to continue" when returning to menu
    try:
        target_id = int(raw)
        index = next((i for i, r in enumerate(direct_reports) if r.get("id") == target_id), None)
        if index is not None:
            removed = direct_reports.pop(index)
            _save_direct_reports()
            print(f"Removed: {removed.get('first_name', '')} {removed.get('last_name', '')}")
        else:
            print(f"No direct report with ID {target_id}.")
    except ValueError:
        print("Invalid input. Enter the ID number (e.g. from the list above).")


def _generate_direct_reports_with_ai() -> None:
    """Generate realistic direct reports using Mistral AI and add them to the list."""
    if not MISTRAL_AVAILABLE:
        print("\nMistral AI is not installed. Install it with: pip install mistralai")
        return
    
    api_key = _get_mistral_api_key()
    if not api_key:
        print("\nMistral API key not found. Set MISTRAL_API_KEY environment variable.")
        return
    
    _clear_screen()
    print("\n--- Generate Direct Reports with Mistral AI ---")
    try:
        num_reports = input("How many direct reports to generate? (1-10, default 3): ").strip()
        num = int(num_reports) if num_reports else 3
        if not (1 <= num <= 10):
            print("Please enter a number between 1 and 10.")
            return
    except ValueError:
        print("Invalid input. Using default of 3 reports.")
        num = 3
    
    print(f"\nGenerating {num} direct reports using Mistral AI...\n")
    
    try:
        client = Mistral(api_key=api_key)
        existing_names = {_direct_report_name_key(r) for r in direct_reports}
        avoid_names_instruction = ""
        if existing_names:
            names_list = [f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() for r in direct_reports[:30]]
            avoid_names_instruction = f"\nDo NOT create any person with the same first and last name as any of these existing people: {names_list}. All new reports must have unique first and last names."
        prompt = f"""Generate exactly {num} realistic direct reports for a manager. Each report should have a diverse, realistic background.{avoid_names_instruction}

Return a single JSON object with a key "reports" whose value is an array of {num} objects. Each object must have exactly these keys (use null for optional fields if needed): first_name, last_name, street_address_1, street_address_2, city, state, zipcode, country, birthday, hire_date, current_role, role_start_date, partner_name. Dates must be YYYY-MM-DD. Each person must have a unique first_name and last_name combination. Example structure:
{{"reports": [{{"first_name": "Jane", "last_name": "Doe", "street_address_1": "123 Main St", "street_address_2": null, "city": "Boston", "state": "MA", "zipcode": "02101", "country": "USA", "birthday": "1990-05-15", "hire_date": "2021-03-01", "current_role": "Senior Engineer", "role_start_date": "2023-01-01", "partner_name": null}}, ...]}}

Output only this JSON object, no other text."""
        
        try:
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except TypeError:
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
        msg_content = message.choices[0].message.content
        if isinstance(msg_content, list):
            raw = "".join(
                p.get("text", p.get("content", "")) if isinstance(p, dict) else str(p)
                for p in msg_content
            )
        else:
            raw = msg_content or ""
        response_text = raw.strip()
        # Strip markdown code fence if model still adds it
        if response_text.startswith("```"):
            end = response_text.find("\n", 3)
            if end != -1:
                response_text = response_text[end + 1 :].rstrip()
            if response_text.endswith("```"):
                response_text = response_text[:-3].rstrip()

        objects: list[dict] = []
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                arr = parsed.get("reports") or parsed.get("direct_reports")
                if isinstance(arr, list):
                    objects = [x for x in arr if isinstance(x, dict)]
                if not objects:
                    for v in parsed.values():
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            objects = [x for x in v if isinstance(x, dict)]
                            break
            elif isinstance(parsed, list):
                objects = [x for x in parsed if isinstance(x, dict)]
        except (json.JSONDecodeError, TypeError):
            pass
        if not objects and os.environ.get("WINGMANEM_DEBUG"):
            print(f"[Debug] Raw response (first 800 chars):\n{raw[:800]!r}", file=sys.stderr)
        keys_already_used = set(existing_names)
        added_count = 0
        for data in objects:
            if _is_duplicate_direct_report(data, keys_already_used):
                fn = (data.get("first_name") or "").strip()
                ln = (data.get("last_name") or "").strip()
                print(f"  Skipped duplicate: {fn} {ln}")
                continue
            try:
                report = _normalize_direct_report({
                    "id": _next_direct_report_id(),
                    **data
                })
                direct_reports.append(report)
                keys_already_used.add(_direct_report_name_key(report))
                added_count += 1
                print(f"  ✓ Added: {report['first_name']} {report['last_name']}")
            except (ValueError, TypeError):
                pass
        
        if added_count > 0:
            _save_direct_reports()
            print(f"\nSuccessfully added {added_count} direct reports.")
        else:
            print("\nCould not parse any valid direct reports from the response.")
            if os.environ.get("WINGMANEM_DEBUG"):
                print(f"[Debug] Raw response (first 600 chars):\n{raw[:600]!r}", file=sys.stderr)
    
    except Exception as e:
        err = str(e).lower()
        if "401" in err or "unauthorized" in err or "invalid" in err and "key" in err:
            print("\nMistral API key invalid or expired. Set a valid MISTRAL_API_KEY in your environment.")
        elif "timeout" in err or "connection" in err or "network" in err:
            print("\nNetwork error connecting to Mistral AI. Check your internet connection and try again.")
        else:
            print(f"\nError calling Mistral AI: {e}")
        print("Example: export MISTRAL_API_KEY=your_key_here")


def _generate_direct_reports_with_ai_for_user(owner_user_id: int, num: int) -> int:
    """Web: generate up to num Mistral direct reports owned by owner_user_id. Returns count added."""
    if not MISTRAL_AVAILABLE:
        return 0
    api_key = _get_mistral_api_key()
    if not api_key:
        return 0
    num = max(1, min(10, int(num)))
    current = _db_load_direct_reports_for_user(owner_user_id)
    try:
        client = Mistral(api_key=api_key)
        existing_names = {_direct_report_name_key(r) for r in current}
        avoid_names_instruction = ""
        if existing_names:
            names_list = [f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() for r in current[:30]]
            avoid_names_instruction = f"\nDo NOT create any person with the same first and last name as any of these existing people: {names_list}. All new reports must have unique first and last names."
        prompt = f"""Generate exactly {num} realistic direct reports for a manager. Each report should have a diverse, realistic background.{avoid_names_instruction}

Return a single JSON object with a key "reports" whose value is an array of {num} objects. Each object must have exactly these keys (use null for optional fields if needed): first_name, last_name, street_address_1, street_address_2, city, state, zipcode, country, birthday, hire_date, current_role, role_start_date, partner_name. Dates must be YYYY-MM-DD. Each person must have a unique first_name and last_name combination. Example structure:
{{"reports": [{{"first_name": "Jane", "last_name": "Doe", "street_address_1": "123 Main St", "street_address_2": null, "city": "Boston", "state": "MA", "zipcode": "02101", "country": "USA", "birthday": "1990-05-15", "hire_date": "2021-03-01", "current_role": "Senior Engineer", "role_start_date": "2023-01-01", "partner_name": null}}, ...]}}

Output only this JSON object, no other text."""
        try:
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
        except TypeError:
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
        msg_content = message.choices[0].message.content
        if isinstance(msg_content, list):
            raw = "".join(
                p.get("text", p.get("content", "")) if isinstance(p, dict) else str(p)
                for p in msg_content
            )
        else:
            raw = msg_content or ""
        response_text = raw.strip()
        if response_text.startswith("```"):
            end = response_text.find("\n", 3)
            if end != -1:
                response_text = response_text[end + 1 :].rstrip()
            if response_text.endswith("```"):
                response_text = response_text[:-3].rstrip()

        objects: list[dict] = []
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                arr = parsed.get("reports") or parsed.get("direct_reports")
                if isinstance(arr, list):
                    objects = [x for x in arr if isinstance(x, dict)]
                if not objects:
                    for v in parsed.values():
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            objects = [x for x in v if isinstance(x, dict)]
                            break
            elif isinstance(parsed, list):
                objects = [x for x in parsed if isinstance(x, dict)]
        except (json.JSONDecodeError, TypeError):
            pass

        keys_already_used = set(existing_names)
        added_count = 0
        merged = list(current)
        next_id = _db_next_direct_report_id()
        for data in objects:
            if _is_duplicate_direct_report(data, keys_already_used):
                continue
            try:
                report = _normalize_direct_report(
                    {
                        "id": next_id,
                        **data,
                        "owner_user_id": owner_user_id,
                    }
                )
                merged.append(report)
                keys_already_used.add(_direct_report_name_key(report))
                next_id += 1
                added_count += 1
            except (ValueError, TypeError):
                pass
        if added_count > 0:
            _save_direct_reports_for_user(owner_user_id, merged)
        return added_count
    except Exception:
        return 0


def _purge_direct_reports() -> None | bool:
    """Purge all direct reports after confirmation."""
    _list_direct_reports()
    if not direct_reports:
        print("\nNo direct reports to purge.")
        return True
    confirm = input("\nAre you sure you want to delete ALL direct reports? (yes/no): ").strip().lower()
    if confirm == "yes":
        count = len(direct_reports)
        direct_reports.clear()
        _save_direct_reports()
        print(f"\nPurged {count} direct report(s).")
    else:
        print("\nPurge cancelled.")
    return True


# ============================================================================
# MANAGEMENT TIPS — load/save, daily Mistral tip, view by date
# ============================================================================

def _load_management_tips() -> None:
    """Load tips: prefer SQLite; else JSON. Mirror to JSON after DB load. Then seed today’s tip via Mistral if needed."""
    global management_tips
    today_str = date.today().isoformat()
    if _db_available:
        try:
            db_tips = _db_load_management_tips()
        except Exception:
            db_tips = []
        if db_tips:
            management_tips = db_tips
            _write_management_tips_json_file(management_tips)
            last_date = management_tips[-1]["date"] if management_tips else None
            need_new_tip = not management_tips or last_date != today_str
            if need_new_tip and MISTRAL_AVAILABLE and _get_mistral_api_key():
                n_users = _db_count_app_users()
                if n_users == 0:
                    _generate_management_tip_with_ai(silent=True, owner_user_id=None)
                elif n_users == 1:
                    uid = _db_first_user_id()
                    if uid is not None:
                        _generate_management_tip_with_ai(silent=True, owner_user_id=uid)
            return
    if not os.path.isfile(MANAGEMENT_TIPS_FILE):
        management_tips = []
        _save_management_tips()
    else:
        try:
            with open(MANAGEMENT_TIPS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                management_tips = []
                for item in data:
                    if isinstance(item, dict) and item.get("date") and item.get("text"):
                        management_tips.append({"date": str(item["date"])[:10], "text": str(item["text"]).strip()})
                    elif isinstance(item, str) and item.strip():
                        management_tips.append({"date": today_str, "text": item.strip()})
            else:
                management_tips = []
        except (json.JSONDecodeError, OSError):
            management_tips = []
    if _db_available:
        try:
            _db_replace_management_tips_from_list(management_tips)
        except Exception:
            pass
    _write_management_tips_json_file(management_tips)
    last_date = management_tips[-1]["date"] if management_tips else None
    need_new_tip = not management_tips or last_date != today_str
    if need_new_tip and MISTRAL_AVAILABLE and _get_mistral_api_key():
        n_users = _db_count_app_users()
        if n_users == 0:
            _generate_management_tip_with_ai(silent=True, owner_user_id=None)
        elif n_users == 1:
            uid = _db_first_user_id()
            if uid is not None:
                _generate_management_tip_with_ai(silent=True, owner_user_id=uid)


def _save_management_tips() -> None:
    """Persist management_tips: database replace then JSON mirror."""
    if _db_available:
        try:
            _db_replace_management_tips_from_list(management_tips)
        except Exception as e:
            print(f"Could not save management tips to database: {e}", file=sys.stderr)
    _write_management_tips_json_file(management_tips)


def _get_latest_management_tip() -> str:
    """Return the most recent management tip text, or a placeholder if none."""
    if management_tips:
        return management_tips[-1]["text"]
    return "No tip yet. Generate one from Mistral AI."


def _normalize_tip_for_comparison(tip: str) -> str:
    """Normalize tip text for duplicate check: lowercase, single spaces, no leading/trailing space."""
    return " ".join(tip.lower().split())


def _is_duplicate_management_tip_against(text: str, entries: list[dict[str, Any]]) -> bool:
    """Return True if tip text matches any entry's text (normalized)."""
    if not text:
        return False
    normalized_new = _normalize_tip_for_comparison(text)
    for entry in entries:
        if _normalize_tip_for_comparison(str(entry.get("text") or "")) == normalized_new:
            return True
    return False


def _is_duplicate_management_tip(text: str) -> bool:
    """Return True if the tip text is effectively a duplicate of any existing tip in management_tips."""
    return _is_duplicate_management_tip_against(text, management_tips)


def _generate_management_tip_with_ai(*, silent: bool = False, owner_user_id: int | None = None) -> bool:
    """Generate one daily management tip using Mistral AI; append and save. Returns True on success.
    If the suggested tip is a duplicate of an existing one, requests a different tip (up to a few retries).
    If silent is True, do not print success message (e.g. when seeding on startup).
    When owner_user_id is set, the row is stored for that user only (web multi-tenant). When None, owner is NULL (CLI / pre-auth)."""
    global management_tips
    if not MISTRAL_AVAILABLE:
        if not silent:
            print("\nMistral AI is not installed. Install it with: pip install mistralai")
        return False
    api_key = _get_mistral_api_key()
    if not api_key:
        if not silent:
            print("\nMistral API key not found. Set MISTRAL_API_KEY environment variable.")
        return False
    base_prompt = """Generate exactly one short, actionable daily management tip for an engineering manager.
Keep it to one or two sentences. No bullet points or numbering. Output only the tip text, nothing else."""
    max_attempts = 5
    tip_history: list[dict[str, Any]]
    if owner_user_id is not None:
        tip_history = _db_load_management_tips_for_user(owner_user_id)
    else:
        tip_history = list(management_tips)
    try:
        client = Mistral(api_key=api_key)
        for attempt in range(max_attempts):
            avoid_all = [e["text"] for e in tip_history[-20:]]
            if avoid_all:
                avoid = "; ".join(repr(t) for t in avoid_all)
                prompt = f"""{base_prompt}

Do NOT suggest any of these tips (already in your history). Suggest something different:
{avoid}"""
            else:
                # No history (e.g. file missing): pick a random theme so we get a different tip each time
                today_str = date.today().isoformat()
                themes = [
                    "delegation", "conflict resolution", "motivation", "career growth",
                    "running meetings", "prioritization", "remote work", "recognition",
                    "1:1 conversations", "accountability", "giving feedback", "hiring",
                    "burnout prevention", "goal setting", "difficult conversations",
                ]
                theme = random.choice(themes)
                prompt = f"""Today is {today_str}. Generate exactly one short, actionable daily management tip for an engineering manager.
Focus specifically on: {theme}. Give one concrete tip (not generic advice like "listen to your team"). One or two sentences only. Output only the tip text, nothing else."""
            message = client.chat.complete(
                model="mistral-large-latest",
                messages=[{"role": "user", "content": prompt}],
            )
            text = (message.choices[0].message.content or "").strip()
            if not text:
                if not silent and attempt == max_attempts - 1:
                    print("\nMistral AI returned an empty tip.")
                continue
            if _is_duplicate_management_tip_against(text, tip_history):
                continue
            d = date.today().isoformat()
            _db_insert_management_tip(owner_user_id, d, text)
            management_tips.clear()
            management_tips.extend(_db_load_management_tips())
            try:
                _write_management_tips_json_file(
                    [{"date": x["date"], "text": x["text"]} for x in management_tips]
                )
            except OSError:
                pass
            if not silent:
                print(f"\nDaily tip generated: {text}")
            return True
        if not silent:
            print("\nCould not get a non-duplicate tip after several attempts.")
        return False
    except Exception as e:
        err = str(e).lower()
        if "401" in err or "unauthorized" in err or "invalid" in err and "key" in err:
            print("\nMistral API key invalid or expired. Set a valid MISTRAL_API_KEY in your environment.")
        elif "timeout" in err or "connection" in err or "network" in err:
            print("\nNetwork error connecting to Mistral AI. Check your internet connection and try again.")
        else:
            print(f"\nError calling Mistral AI: {e}")
        print("Example: export MISTRAL_API_KEY=your_key_here")
        return False


def _print_management_tips_by_date() -> None:
    """Print management tips from the database, by date."""
    _clear_screen()
    print("\n--- Management Tips by Date (database) ---\n")
    try:
        db_tips = _db_load_management_tips()
        if not db_tips:
            print("  No tips in database.")
        else:
            for entry in db_tips:
                print(f"  {entry['date']}:  {entry['text']}")
    except Exception as e:
        print(f"  Error loading from database: {e}")
    print()


# ============================================================================
# MILESTONE REMINDERS — birthdays & anniversaries (from database)
# ============================================================================

def _compute_milestones_from_reports(reports: list[dict[str, Any]], range_days: int) -> list[tuple[int, str]]:
    """Compute upcoming birthdays and anniversaries for the next range_days. Returns sorted list of (days_until, msg)."""
    today = date.today()
    upcoming: list[tuple[int, str]] = []
    for r in reports:
        bd = r.get("birthday")
        if bd:
            try:
                bd_date = datetime.strptime(bd, "%Y-%m-%d").date()
                next_bd = bd_date.replace(year=today.year)
                days_until = (next_bd - today).days
                if days_until < 0:
                    next_bd = bd_date.replace(year=today.year + 1)
                    days_until = (next_bd - today).days
                if 0 <= days_until <= range_days:
                    upcoming.append((days_until, f"Birthday: {r['first_name']} {r['last_name']} on {next_bd.strftime('%Y-%m-%d')} ({days_until} days)"))
            except Exception:
                pass
        hd = r.get("hire_date")
        if hd:
            try:
                hd_date = datetime.strptime(hd, "%Y-%m-%d").date()
                anniv = hd_date.replace(year=today.year)
                days_until = (anniv - today).days
                if days_until < 0:
                    anniv = hd_date.replace(year=today.year + 1)
                    days_until = (anniv - today).days
                if 0 <= days_until <= range_days:
                    years = anniv.year - hd_date.year
                    upcoming.append((days_until, f"Anniversary: {r['first_name']} {r['last_name']} ({years} years) on {anniv.strftime('%Y-%m-%d')} ({days_until} days)"))
            except Exception:
                pass
    upcoming.sort()
    return [(d, msg) for d, msg in upcoming]


def _view_milestone_reminders() -> None | bool:
    """Show upcoming birthdays and anniversaries from the database."""

    def _print_upcoming(range_days: int) -> None:
        _clear_screen()
        print("\n--- Milestone Reminders (database) ---\n")
        print(f"Showing the next {range_days} days.\n")
        try:
            db_reports = _db_load_direct_reports()
            upcoming = _compute_milestones_from_reports(db_reports, range_days)
            if not upcoming:
                print("  No upcoming birthdays or anniversaries.")
            else:
                for _, msg in upcoming:
                    print(f"  {msg}")
        except Exception as e:
            print(f"  Error loading from database: {e}")
        print()

    _print_upcoming(30)
    while True:
        raw = input("\nView further out? Enter days (e.g. 60, 90, 180) or press Enter to return: ").strip()
        if raw == "":
            return True
        try:
            range_days = int(raw)
            if range_days <= 30:
                print("Please enter a number greater than 30.")
                continue
            _print_upcoming(range_days)
        except ValueError:
            print("Invalid input. Enter a number of days or press Enter to return.")


# ============================================================================
# 1:1 RECORDINGS — upload (Mistral transcribe + summarize), view/delete/purge by report
# ============================================================================

def _prompt_direct_report_id() -> int | None:
    """Show direct reports (short list), prompt for ID; return id or None to cancel."""
    if not direct_reports:
        print("\nNo direct reports. Add one from Administer Direct Reports first.")
        return None
    print("Direct reports:")
    for r in direct_reports:
        print(f"  ID {r.get('id')}: {r.get('first_name', '')} {r.get('last_name', '')}")
    raw = input("\nEnter the direct report ID for this 1:1 (or Enter to cancel): ").strip()
    if not raw:
        return None
    try:
        target_id = int(raw)
    except ValueError:
        print("Invalid ID.")
        return None
    if not any(r.get("id") == target_id for r in direct_reports):
        print(f"No direct report with ID {target_id}.")
        return None
    return target_id


def _upload_one_to_one_recording() -> None:
    """Let user pick a direct report and audio file; transcribe with Mistral, summarize with action items; store in DB."""
    _clear_screen()
    print("\n--- Upload 1:1 Recording ---\n")
    if not MISTRAL_AVAILABLE:
        print("Mistral AI is not installed. Install it with: pip install mistralai")
        return
    api_key = _get_mistral_api_key()
    if not api_key:
        print("Mistral API key not found. Set MISTRAL_API_KEY environment variable.")
        return
    report_id = _prompt_direct_report_id()
    if report_id is None:
        return
    path = input("Enter path to audio file (e.g. .mp3, .wav, .m4a): ").strip()
    if not path:
        print("No file path entered.")
        return
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        return
    filename = os.path.basename(path)
    print(f"\nTranscribing and analyzing with Mistral AI...")
    try:
        client = Mistral(api_key=api_key)
        with open(path, "rb") as f:
            trans = client.audio.transcriptions.complete(
                model="voxtral-mini-latest",
                file={"file_name": filename, "content": f.read()},
            )
        transcript = (getattr(trans, "text", None) or "").strip()
        if not transcript:
            print("No speech detected in the audio.")
            return
        prompt = """Based on the following 1:1 meeting transcript, provide:
1) A brief summary (2–4 sentences).
2) A list of action items and to-dos (who does what, if clear).
3) Suggested follow-up topics for the next meeting.

Format the response clearly with headings (Summary, Action Items, Follow-ups). Use bullet points for lists."""
        full_prompt = f"{prompt}\n\n--- Transcript ---\n{transcript}"
        msg = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": full_prompt}],
        )
        content = msg.choices[0].message.content or ""
        if isinstance(content, list):
            content = "".join(
                p.get("text", p.get("content", "")) if isinstance(p, dict) else str(p) for p in content
            )
        response_text = content.strip()
        if not response_text:
            print("Mistral returned an empty response.")
            return
        print("\n" + "=" * 60)
        print("1:1 Summary & Action Items")
        print("=" * 60)
        print(response_text)
        print("=" * 60)
        date_str = date.today().isoformat()
        _db_insert_one_to_one_summary(report_id, date_str, response_text)
        print(f"\nSaved to database for direct report ID {report_id} on {date_str}.")
    except Exception as e:
        err = str(e).lower()
        if "401" in err or "unauthorized" in err:
            print("Mistral API key invalid or expired. Set MISTRAL_API_KEY.")
        elif "timeout" in err or "connection" in err:
            print("Network error. Check your connection and try again.")
        else:
            print(f"Error: {e}")


def _view_one_to_one_responses() -> None:
    """View 1:1 summaries for a direct report, sorted by date."""
    _clear_screen()
    print("\n--- View 1:1 Summaries by Direct Report ---\n")
    report_id = _prompt_direct_report_id()
    if report_id is None:
        return
    summaries = _db_get_one_to_one_summaries(report_id)
    if not summaries:
        print(f"\nNo 1:1 summaries stored for direct report ID {report_id}.")
        return
    for s in summaries:
        print("\n" + "-" * 50)
        print(f"Date: {s['date']}")
        print("-" * 50)
        print(s["response_text"])
    print()


def _delete_one_to_one_response() -> None:
    """Delete a specific 1:1 summary for a direct report by date."""
    _clear_screen()
    print("\n--- Delete 1:1 Summary ---\n")
    report_id = _prompt_direct_report_id()
    if report_id is None:
        return
    summaries = _db_get_one_to_one_summaries(report_id)
    if not summaries:
        print(f"\nNo 1:1 summaries for direct report ID {report_id}.")
        return
    print("\nSummaries by date:")
    for s in summaries:
        print(f"  {s['date']}")
    date_str = input("\nEnter the date to delete (YYYY-MM-DD) or Enter to cancel: ").strip()
    if not date_str:
        return
    if _db_delete_one_to_one_by_report_and_date(report_id, date_str):
        print(f"Deleted 1:1 summary for {date_str}.")
    else:
        print(f"No summary found for date {date_str}.")


def _purge_one_to_one_responses() -> None:
    """Purge all 1:1 summaries for a direct report."""
    _clear_screen()
    print("\n--- Purge All 1:1 Summaries for a Direct Report ---\n")
    report_id = _prompt_direct_report_id()
    if report_id is None:
        return
    n = _db_purge_one_to_one_for_report(report_id)
    if n > 0:
        print(f"Purged {n} 1:1 summary/summaries for direct report ID {report_id}.")
    else:
        print(f"No 1:1 summaries found for direct report ID {report_id}.")


# ============================================================================
# MENUS — main, developer, project, people & 1:1, direct reports
# ============================================================================
# --- Main menu ---

def _build_main_menu() -> str:
    """Build the main menu with the latest management tip."""
    tip = _get_latest_management_tip()
    return _menu_box(
        "                    WingmanEM — Main Menu",
        [
            ("  1. Project Creation & Estimation"),
            ("  2. People Management & Coaching", True, True),  # red
            ("  3. Exit"),
        ],
        middle=[
            ("DAILY MANAGEMENT TIP:", f" {tip}  "),
        ],
        middle_position="bottom",
    )


def run_main_menu() -> bool:
    """Show main menu and return chosen option (1–3, or 9 for hidden developer menu). Returns False to exit."""
    _clear_screen()
    print(_build_main_menu())
    choice = _prompt_choice("Select an option (1–3): ", 9)
    if choice == 0:
        print("Invalid option. Please enter 1, 2, or 3.")
        _pause()
        return True
    if choice == 9:
        run_developer_menu()
        return True
    if choice in (4, 5, 6, 7, 8):
        print("Invalid option. Please enter 1, 2, or 3.")
        _pause()
        return True
    if choice == 3:
        return False
    if choice == 1:
        run_project_estimation_menu()
    elif choice == 2:
        run_people_coaching_menu()
    return True


# --- Developer menu ---

DEVELOPER_MENU = _menu_box(
    "Developer menu",
    [
        ("  1. Back to main menu", True),
    ],
)


def run_developer_menu() -> bool:
    """Developer menu; returns True so caller skips pause."""
    _run_submenu(
        DEVELOPER_MENU,
        1,
        {},
    )
    return True


# --- Project Creation & Estimation ---

PROJECT_MENU = _menu_box(
    "           Project Creation & Estimation",
    [
        ("  1. Input project spec (get structured breakdown)", False),
        ("  2. Sync breakdown to Jira", False),
        ("  3. Ask about project status (natural language)", False),
        ("  4. Back to main menu", True),
    ],
)


def run_project_estimation_menu() -> None:
    """Sub-menu for project creation and estimation."""
    _run_submenu(
        PROJECT_MENU,
        4,
        {
            1: lambda: print("\n[Placeholder] Input project spec — not yet implemented."),
            2: lambda: print("\n[Placeholder] Sync to Jira — not yet implemented."),
            3: lambda: print("\n[Placeholder] Ask about project status — not yet implemented."),
        },
    )


# --- People Management & Coaching (includes 1:1 submenu) ---

ONE_TO_ONE_MENU = _menu_box(
    "           1:1 Recordings (Upload, View, Delete)",
    [
        ("  1. Summarize 1:1 recording", True),
        ("  2. View 1:1 summaries by direct report", True),
        ("  3. Delete a 1:1 summary by date", True),
        ("  4. Purge all 1:1 summaries for a direct report", True),
        ("  5. Back to previous menu", True),
    ],
)


def run_one_to_one_menu() -> bool:
    """1:1 recordings submenu; returns True to skip pause."""
    _run_submenu(
        ONE_TO_ONE_MENU,
        5,
        {
            1: _upload_one_to_one_recording,
            2: _view_one_to_one_responses,
            3: _delete_one_to_one_response,
            4: _purge_one_to_one_responses,
        },
    )
    return True


PEOPLE_MENU = _menu_box(
    "           People Management & Coaching",
    [
        ("  1. Manage 1:1s", True),
        ("  2. View 1:1 trends analysis", False),
        ("  3. Get suggested follow-up topics", False),
        ("  4. View milestone reminders (anniversaries, birthdays)", True, True),  # red
        ("  5. Administer Direct Reports", True, True),  # red
        ("  6. View management tips by date", True, True),  # red
        ("  7. Back to main menu", True),
    ],
)


def run_people_coaching_menu() -> None:
    """Sub-menu for people management and coaching."""
    _run_submenu(
        PEOPLE_MENU,
        7,
        {
            1: run_one_to_one_menu,
            2: lambda: print("\n[Placeholder] View 1:1 trends — not yet implemented."),
            3: lambda: print("\n[Placeholder] Suggested follow-up topics — not yet implemented."),
            4: _view_milestone_reminders,
            5: run_direct_reports_menu,
            6: _print_management_tips_by_date,
        },
    )


# --- Administer Direct Reports ---

DIRECT_REPORTS_MENU = _menu_box(
    "Administer Direct Reports",
    [
        ("  1. Add direct report", True),
        ("  2. List direct reports", True),
        ("  3. Delete a direct report", True),
        ("  4. Generate direct reports with Mistral AI", MISTRAL_AVAILABLE),
        ("  5. Purge all direct reports", True),
        ("  6. Back to previous menu", True),
    ],
)


def run_direct_reports_menu() -> bool:
    """Sub-menu for administering direct reports (add/list/delete/generate/purge). Returns True so caller skips pause."""
    actions = {
        1: _add_direct_report,
        2: _list_direct_reports,
        3: _delete_direct_report,
        5: _purge_direct_reports,
    }
    if MISTRAL_AVAILABLE:
        actions[4] = _generate_direct_reports_with_ai
    
    _run_submenu(
        DIRECT_REPORTS_MENU,
        6,
        actions,
    )
    return True


# ============================================================================
# AUTHENTICATION (optional; currently bypassed in main)
# ============================================================================

def authenticate() -> bool:
    """Prompt for password; return True if correct."""
    try:
        password = getpass.getpass("Password: ")
        return password == _get_expected_password()
    except (EOFError, KeyboardInterrupt):
        return False


# ============================================================================
# ENTRY POINT
# ============================================================================

def main() -> None:
    """Run the CLI: load data, then main menu loop."""
    print("Welcome to WingmanEM.\n")
    _db_init()
    _db_populate_from_json_files()
    _load_direct_reports()
    _load_management_tips()
# Will be used later:
#    if not authenticate():
#        print("Authentication failed. Exiting.", file=sys.stderr)
#        sys.exit(1)
    try:
        while run_main_menu():
            _clear_screen()
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    print("Goodbye.")


if __name__ == "__main__":
    main()
