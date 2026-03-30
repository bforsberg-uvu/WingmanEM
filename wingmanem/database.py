"""
SQLAlchemy engine and session factory for WingmanEM (SQLite).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from wingmanem.orm_models import Base

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _migrate_sqlite_legacy_tables(engine) -> None:
    """Rename legacy SQLite tables when ORM table names change (idempotent)."""
    try:
        with engine.begin() as conn:
            has_legacy = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='employee_comp_data'"
                )
            ).fetchone()
            has_new = conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='direct_report_comp_data'"
                )
            ).fetchone()
            if has_legacy and not has_new:
                conn.execute(text("ALTER TABLE employee_comp_data RENAME TO direct_report_comp_data"))
    except Exception:
        # Non-fatal: create_all may still create missing tables
        pass


def dispose_engine() -> None:
    """Dispose current engine (e.g. before re-init with a different path)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def init_engine(database_path: str) -> bool:
    """
    Create SQLite engine, create missing tables, and configure session factory.
    Returns False if initialization fails.
    """
    global _engine, _SessionLocal
    try:
        dispose_engine()
        abs_path = Path(database_path).resolve()
        # SQLite URL: use forward slashes
        url = "sqlite:///" + str(abs_path).replace("\\", "/")
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        _migrate_sqlite_legacy_tables(_engine)
        Base.metadata.create_all(bind=_engine)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)
        return True
    except Exception:
        dispose_engine()
        return False


def get_engine():
    return _engine


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized; call init_engine first")
    return _SessionLocal()
