"""
Paths, schema keys, and CLI menu styling shared by the app layer.

Filesystem paths come from ``wingmanem.settings`` (environment). ``wingmanem.app``
imports these names so tests can patch ``wingmanem.app.DATABASE_PATH``, etc.
"""

from __future__ import annotations

from wingmanem.settings import (
    DATABASE_PATH,
    DIRECT_REPORT_COMP_DATA_FILE,
    DIRECT_REPORT_GOALS_FILE,
    DIRECT_REPORTS_FILE,
    LEGACY_DIRECT_REPORT_COMP_DATA_FILE,
    MANAGEMENT_TIPS_FILE,
)

# Direct_Reports shape (project_plan.md): required id, first_name, last_name; rest optional
DIRECT_REPORT_OPTIONAL_KEYS = (
    "street_address_1",
    "street_address_2",
    "city",
    "state",
    "zipcode",
    "country",
    "birthday",
    "hire_date",
    "current_role",
    "role_start_date",
    "partner_name",
    "owner_user_id",
)

EMPLOYEE_COMP_DATA_FILE = DIRECT_REPORT_COMP_DATA_FILE

# ANSI colors for CLI menu rendering
MENU_COLOR_BLACK = "\033[30m"
MENU_COLOR_RED = "\033[31m"
MENU_COLOR_DISABLED = "\033[2;37m"  # dim white
MENU_COLOR_RESET = "\033[0m"
MENU_BOLD = "\033[1m"

# Compensation statement rating → short label (Chunk #6 / comp_items)
COMP_RATING_LABELS: dict[int, str] = {
    5: "Exceptional Contribution",
    4: "Exceed Expectations",
    3: "Meets Expectations",
    2: "Missed Expectations",
    1: "Needs improvement",
}
