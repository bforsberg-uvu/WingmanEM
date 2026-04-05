"""Application user accounts: SQLite ORM + Werkzeug password hashing (no Flask import)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from wingmanem.database import get_session
from wingmanem.orm_models import AppUserORM, UserPasswordORM


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


def delete_application_user(user_pk: int) -> tuple[bool, str]:
    """Delete a row from users (user_passwords CASCADE). Returns (ok, error_message)."""
    session = _open_session()
    if session is None:
        return False, "Database is not available."
    try:
        user = session.get(AppUserORM, user_pk)
        if not user:
            return False, "User not found."
        session.delete(user)
        session.commit()
        return True, ""
    except Exception as e:
        session.rollback()
        return False, str(e) or "Could not delete user."
    finally:
        session.close()
