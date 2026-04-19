"""Application user accounts: SQLite ORM + Werkzeug password hashing (no Flask import)."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from wingmanem.database import get_session
from wingmanem.orm_models import (
    AppUserORM,
    ApiTokenORM,
    DirectReportCompDataORM,
    DirectReportGoalORM,
    DirectReportORM,
    ManagementTipORM,
    OneToOneSummaryORM,
    UserPasswordORM,
)


def _open_session():
    try:
        return get_session()
    except RuntimeError:
        return None


def create_user(first_name: str, last_name: str, login_id: str, password: str) -> tuple[bool, str, int | None]:
    """Create users row + user_passwords row. Returns (ok, error_message, new_user_id_or_None)."""
    login_id = (login_id or "").strip()
    if not login_id:
        return False, "User ID is required.", None
    if not password:
        return False, "Password is required.", None
    session = _open_session()
    if session is None:
        return False, "Database is not available.", None
    try:
        taken = session.scalars(select(AppUserORM).where(AppUserORM.login_id == login_id)).first()
        if taken:
            return False, "That user ID is already taken.", None
        user = AppUserORM(
            first_name=(first_name or "").strip() or "User",
            last_name=(last_name or "").strip() or "",
            login_id=login_id,
        )
        session.add(user)
        session.flush()
        session.add(
            UserPasswordORM(
                user_id=user.id,
                password_hash=generate_password_hash(password),
            )
        )
        session.commit()
        new_id = user.id
        return True, "", new_id
    except Exception as e:
        session.rollback()
        return False, str(e) or "Could not create account.", None
    finally:
        session.close()


def count_users() -> int:
    """Return number of application user accounts."""
    session = _open_session()
    if session is None:
        return 0
    try:
        n = session.scalar(select(func.count()).select_from(AppUserORM))
        return int(n or 0)
    finally:
        session.close()


def verify_credentials(login_id: str, password: str) -> dict[str, Any] | None:
    """If login_id + password match, return user fields for Flask-Login; else None."""
    lid = (login_id or "").strip()
    if not lid or not password:
        return None
    session = _open_session()
    if session is None:
        return None
    try:
        user = session.scalars(select(AppUserORM).where(AppUserORM.login_id == lid)).first()
        if not user:
            return None
        pw_row = session.scalars(select(UserPasswordORM).where(UserPasswordORM.user_id == user.id)).first()
        if not pw_row or not check_password_hash(pw_row.password_hash, password):
            return None
        return {
            "id": user.id,
            "login_id": user.login_id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
        }
    finally:
        session.close()


def get_user_by_id(user_pk: int) -> dict[str, Any] | None:
    session = _open_session()
    if session is None:
        return None
    try:
        user = session.get(AppUserORM, user_pk)
        if not user:
            return None
        return {
            "id": user.id,
            "login_id": user.login_id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
        }
    finally:
        session.close()


def list_users_with_password_hashes() -> list[dict[str, Any]]:
    """Developer view: joined user + hash rows."""
    session = _open_session()
    if session is None:
        return []
    try:
        users = session.scalars(select(AppUserORM).order_by(AppUserORM.id)).all()
        out: list[dict[str, Any]] = []
        for u in users:
            pw = session.scalars(select(UserPasswordORM).where(UserPasswordORM.user_id == u.id)).first()
            out.append(
                {
                    "id": u.id,
                    "first_name": u.first_name or "",
                    "last_name": u.last_name or "",
                    "login_id": u.login_id,
                    "password_hash": pw.password_hash if pw else "",
                }
            )
        return out
    finally:
        session.close()


def create_api_token_for_user(user_pk: int) -> tuple[bool, str, str | None]:
    """Create and persist a new API token for a user.

    Returns (ok, error_message, plaintext_token_or_None). The plaintext token is only
    available at creation time; the database stores only a hash.
    """
    session = _open_session()
    if session is None:
        return False, "Database is not available.", None
    try:
        user = session.get(AppUserORM, user_pk)
        if not user:
            return False, "User not found.", None
        token = secrets.token_urlsafe(32)
        token_hash = generate_password_hash(token)
        created_at = datetime.now(timezone.utc).isoformat()
        session.add(ApiTokenORM(user_id=user_pk, token_hash=token_hash, created_at=created_at))
        session.commit()
        return True, "", token
    except Exception as e:
        session.rollback()
        return False, str(e) or "Could not create API token.", None
    finally:
        session.close()


def list_api_tokens_for_user(user_pk: int) -> list[dict[str, Any]]:
    """List token rows for the user (hash is not returned)."""
    session = _open_session()
    if session is None:
        return []
    try:
        rows = session.scalars(
            select(ApiTokenORM).where(ApiTokenORM.user_id == user_pk).order_by(ApiTokenORM.id.desc())
        ).all()
        return [{"id": r.id, "created_at": r.created_at} for r in rows]
    finally:
        session.close()


def delete_api_token_for_user(user_pk: int, token_id: int) -> tuple[bool, str]:
    session = _open_session()
    if session is None:
        return False, "Database is not available."
    try:
        row = session.scalars(
            select(ApiTokenORM).where(ApiTokenORM.user_id == user_pk, ApiTokenORM.id == token_id).limit(1)
        ).first()
        if not row:
            return False, "Token not found."
        session.delete(row)
        session.commit()
        return True, ""
    except Exception as e:
        session.rollback()
        return False, str(e) or "Could not delete token."
    finally:
        session.close()


def verify_api_token(token: str) -> int | None:
    """Return user_id for a valid token; else None."""
    t = (token or "").strip()
    if not t:
        return None
    session = _open_session()
    if session is None:
        return None
    try:
        # Small app: linear scan is acceptable; avoids storing token prefixes in DB.
        rows = session.scalars(select(ApiTokenORM)).all()
        for r in rows:
            try:
                if check_password_hash(r.token_hash, t):
                    return int(r.user_id)
            except Exception:
                continue
        return None
    finally:
        session.close()


def _delete_owned_people_data_for_user(session: Session, user_pk: int) -> None:
    """Remove rows that FK-reference this user so DELETE FROM users can succeed.

    `direct_reports.owner_user_id` and `management_tips.owner_user_id` reference
    users.id without ON DELETE CASCADE in SQLite; child report data must go first.
    """
    rids = session.scalars(
        select(DirectReportORM.id).where(DirectReportORM.owner_user_id == user_pk)
    ).all()
    rid_list = [int(x) for x in rids]
    if rid_list:
        session.execute(delete(OneToOneSummaryORM).where(OneToOneSummaryORM.direct_report_id.in_(rid_list)))
        session.execute(delete(DirectReportGoalORM).where(DirectReportGoalORM.direct_report_id.in_(rid_list)))
        session.execute(delete(DirectReportCompDataORM).where(DirectReportCompDataORM.direct_report_id.in_(rid_list)))
        session.execute(delete(DirectReportORM).where(DirectReportORM.owner_user_id == user_pk))
    session.execute(delete(ManagementTipORM).where(ManagementTipORM.owner_user_id == user_pk))


def delete_application_user(user_pk: int) -> tuple[bool, str]:
    """Delete a user row; password row CASCADEs. Purges owned direct reports and tips first."""
    session = _open_session()
    if session is None:
        return False, "Database is not available."
    try:
        user = session.get(AppUserORM, user_pk)
        if not user:
            return False, "User not found."
        _delete_owned_people_data_for_user(session, user_pk)
        session.delete(user)
        session.commit()
        return True, ""
    except Exception as e:
        session.rollback()
        return False, str(e) or "Could not delete user."
    finally:
        session.close()
