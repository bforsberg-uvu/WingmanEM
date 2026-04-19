"""
SQLAlchemy ORM models for WingmanEM SQLite database.

Table names match the legacy sqlite3 schema for compatibility.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AppUserORM(Base):
    """Application login accounts (table `users`). `login_id` is the user-facing ID typed at login."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    last_name: Mapped[str] = mapped_column(Text, nullable=False, default="")
    login_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)


class UserPasswordORM(Base):
    """One hashed password per user; FK to users.id with ON DELETE CASCADE."""

    __tablename__ = "user_passwords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)


class ApiTokenORM(Base):
    """Hashed API tokens for /api/v1 endpoints."""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class DirectReportORM(Base):
    __tablename__ = "direct_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(Text, default="")
    last_name: Mapped[str] = mapped_column(Text, default="")
    street_address_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    street_address_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    zipcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    birthday: Mapped[str | None] = mapped_column(Text, nullable=True)
    hire_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_start_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    partner_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class ManagementTipORM(Base):
    __tablename__ = "management_tips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class OneToOneSummaryORM(Base):
    __tablename__ = "one_to_one_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direct_report_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)


class DirectReportGoalORM(Base):
    __tablename__ = "direct_report_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direct_report_id: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal_completion_date: Mapped[str | None] = mapped_column(Text, nullable=True)


class DirectReportCompDataORM(Base):
    """Per-direct-report compensation inputs (rating, salary, bonus, etc.) persisted in SQLite."""

    __tablename__ = "direct_report_comp_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direct_report_id: Mapped[int] = mapped_column(Integer, nullable=False)
    first_name: Mapped[str] = mapped_column(Text, default="")
    last_name: Mapped[str] = mapped_column(Text, default="")
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    salary: Mapped[int] = mapped_column(Integer, nullable=False)
    percent_change: Mapped[float] = mapped_column(Float, nullable=False)
    dollar_change: Mapped[int] = mapped_column(Integer, nullable=False)
    new_salary: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus: Mapped[int] = mapped_column(Integer, nullable=False)


# Backward-compatible alias
EmployeeCompDataORM = DirectReportCompDataORM
