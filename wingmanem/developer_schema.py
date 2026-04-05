"""DDL strings and model source snippets for the Developer menu (documentation)."""

from __future__ import annotations

import inspect

from wingmanem import orm_models

# SQLite DDL aligned with legacy schema + direct_report_comp_data (ORM-managed).
SQL_DIRECT_REPORTS = """CREATE TABLE IF NOT EXISTS direct_reports (
    id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    street_address_1 TEXT,
    street_address_2 TEXT,
    city TEXT,
    state TEXT,
    zipcode TEXT,
    country TEXT,
    birthday TEXT,
    hire_date TEXT,
    current_role TEXT,
    role_start_date TEXT,
    partner_name TEXT
);"""

SQL_MANAGEMENT_TIPS = """CREATE TABLE IF NOT EXISTS management_tips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    text TEXT NOT NULL
);"""

SQL_ONE_TO_ONE = """CREATE TABLE IF NOT EXISTS one_to_one_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direct_report_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    response_text TEXT NOT NULL
);"""

SQL_GOALS = """CREATE TABLE IF NOT EXISTS direct_report_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direct_report_id INTEGER NOT NULL,
    goal_title TEXT,
    goal_description TEXT,
    goal_completion_date TEXT
);"""

SQL_USERS = """CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    login_id TEXT NOT NULL UNIQUE
);"""

SQL_USER_PASSWORDS = """CREATE TABLE IF NOT EXISTS user_passwords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL
);"""

SQL_DIRECT_REPORT_COMP = """CREATE TABLE IF NOT EXISTS direct_report_comp_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direct_report_id INTEGER NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    rating INTEGER NOT NULL,
    salary INTEGER NOT NULL,
    percent_change REAL NOT NULL,
    dollar_change INTEGER NOT NULL,
    new_salary INTEGER NOT NULL,
    bonus INTEGER NOT NULL
);"""


def build_schema_model_pairs() -> list[dict[str, str]]:
    """Return list of {title, sql, model_py} for side-by-side display."""
    specs = [
        ("users", SQL_USERS, orm_models.AppUserORM),
        ("user_passwords", SQL_USER_PASSWORDS, orm_models.UserPasswordORM),
        ("direct_reports", SQL_DIRECT_REPORTS, orm_models.DirectReportORM),
        ("management_tips", SQL_MANAGEMENT_TIPS, orm_models.ManagementTipORM),
        ("one_to_one_summaries", SQL_ONE_TO_ONE, orm_models.OneToOneSummaryORM),
        ("direct_report_goals", SQL_GOALS, orm_models.DirectReportGoalORM),
        ("direct_report_comp_data", SQL_DIRECT_REPORT_COMP, orm_models.DirectReportCompDataORM),
    ]
    out: list[dict[str, str]] = []
    for title, sql, cls in specs:
        out.append(
            {
                "title": title,
                "sql": sql.strip(),
                "model_py": inspect.getsource(cls).strip(),
            }
        )
    return out
