"""
WingmanEM CLI prototype Chunk #2
Main application logic: menu-driven navigation and password protection.
"""

import getpass
import json
import os
import sys
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

# Keys for direct report dicts (mirror former dataclass fields)
DIRECT_REPORT_KEYS = ("firstName", "lastName", "birthdate", "hireDate", "partnerName")

# Global list of direct reports (each item is a dict with DIRECT_REPORT_KEYS)
direct_reports: list[dict[str, Any]] = []

# Persistence file (same data as direct_reports)
DIRECT_REPORTS_FILE = "direct_reports.json"


# --- Persistence ---
def _load_direct_reports() -> None:
    """Read direct_reports from file into the global list."""
    global direct_reports
    if not os.path.isfile(DIRECT_REPORTS_FILE):
        direct_reports = []
        return
    try:
        with open(DIRECT_REPORTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        direct_reports = data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        direct_reports = []


def _save_direct_reports() -> None:
    """Write the global direct_reports list to file."""
    try:
        with open(DIRECT_REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(direct_reports, f, indent=2)
    except OSError as e:
        print(f"Could not save direct reports: {e}", file=sys.stderr)


# --- Configuration ---
def _get_expected_password() -> str:
    """Expected password from environment; defaults to 'wingman' for local dev."""
    return os.environ.get("WINGMANEM_PASSWORD", "p")


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


# ANSI colors for menu items (enabled=black, disabled=very light gray)
_MENU_COLOR_ENABLED = "\033[30m"   # black
_MENU_COLOR_DISABLED = "\033[2;37m"  # very light gray (dim white)
_MENU_COLOR_RESET = "\033[0m"


def _menu_box(
    title: str,
    options: list[str | tuple[str, bool]],
    width: int = 58,
) -> str:
    """Build a box menu. Options are a label string or (label, enabled); missing enabled = True."""
    border = "╔" + "═" * width + "╗"
    sep = "╠" + "═" * width + "╣"
    bottom = "╚" + "═" * width + "╝"
    lines = ["║" + title[:width].ljust(width) + "║"]
    for opt in options:
        if isinstance(opt, tuple):
            text, enabled = opt
        else:
            text, enabled = opt, True
        content = text[:width].ljust(width)
        color = _MENU_COLOR_ENABLED if enabled else _MENU_COLOR_DISABLED
        lines.append("║" + color + content + _MENU_COLOR_RESET + "║")
    return "\n".join([border, lines[0], sep] + lines[1:] + [bottom])


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


# --- Authentication ---
def authenticate() -> bool:
    """Prompt for password; return True if correct."""
    try:
        password = getpass.getpass("Password: ")
        return password == _get_expected_password()
    except (EOFError, KeyboardInterrupt):
        return False


# --- Main menu ---
MAIN_MENU = _menu_box(
    "                    WingmanEM — Main Menu",
    [
        ("  1. Project Creation & Estimation"),
        ("  2. People Management & Coaching - ***Add/List Items***"),
        ("  3. Manager / Management Improvement"),
        ("  4. Exit"),
    ],
)


def run_main_menu() -> bool:
    """Show main menu and return chosen option (1–4). Returns False to exit."""
    print(MAIN_MENU)
    choice = _prompt_choice("Select an option (1–4): ", 4)
    if choice == 0:
        print("Invalid option. Please enter 1, 2, 3, or 4.")
        _pause()
        return True
    if choice == 4:
        return False
    if choice == 1:
        run_project_estimation_menu()
    elif choice == 2:
        run_people_coaching_menu()
    elif choice == 3:
        run_management_improvement_menu()
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


# --- People Management & Coaching ---
PEOPLE_MENU = _menu_box(
    "           People Management & Coaching",
    [
        ("  1. Upload 1:1 recording (summarize & action items)", False),
        ("  2. View 1:1 trends analysis", False),
        ("  3. Get suggested follow-up topics", False),
        ("  4. View milestone reminders (anniversaries, birthdays)", False),
        ("  5. Administer Direct Reports - ***Add/List Items***"),
        ("  6. Back to main menu", True),
    ],
)


def run_people_coaching_menu() -> None:
    """Sub-menu for people management and coaching."""
    _run_submenu(
        PEOPLE_MENU,
        6,
        {
            1: lambda: print("\n[Placeholder] Upload 1:1 recording — not yet implemented."),
            2: lambda: print("\n[Placeholder] View 1:1 trends — not yet implemented."),
            3: lambda: print("\n[Placeholder] Suggested follow-up topics — not yet implemented."),
            4: lambda: print("\n[Placeholder] Milestone reminders — not yet implemented."),
            5: run_direct_reports_menu,
        },
    )



# --- Administer Direct Reports - ***Add/List Items*** ---


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
    """Prompt for direct report fields and append to direct_reports."""
    _clear_screen()
    print()
    _list_direct_reports()
    print("\n--- Add Direct Report ---")
    firstName = input("First name: ").strip() or "Unknown"
    lastName = input("Last name: ").strip() or "Unknown"
    birthdate = _parse_optional_date("Birthdate (YYYYMMDD or YYYY-MM-DD, or Enter to skip): ")
    hireDate = _parse_optional_date("Hire date (YYYYMMDD or YYYY-MM-DD, or Enter to skip): ")
    partnerName = input("Partner name (or Enter to skip): ").strip() or None
    report: dict[str, Any] = {
        "firstName": firstName,
        "lastName": lastName,
        "birthdate": birthdate.isoformat() if birthdate else None,
        "hireDate": hireDate.isoformat() if hireDate else None,
        "partnerName": partnerName,
    }
    direct_reports.append(report)
    _save_direct_reports()
    print(f"\nAdded: {report['firstName']} {report['lastName']}")
    _list_direct_reports()


def _list_direct_reports() -> None:
    """Display all direct reports in a table (iterates over direct_reports list)."""
    if not direct_reports:
        print("\nNo direct reports yet. Add one from the menu.")
        return
    w_no, w1, w2, w3, w4, w5 = 4, 18, 18, 12, 12, 32
    fmt = f"{{:>{w_no}}} {{:{w1}}} {{:{w2}}} {{:{w3}}} {{:{w4}}} {{:{w5}}}"
    sep = "-" * (w_no + w1 + w2 + w3 + w4 + w5 + 5)
    print()
    print("Direct Reports")
    print()
    print(fmt.format("No.", "First Name", "Last Name", "Birthdate", "Hire Date", "Partner"))
    print(sep)
    for i, r in enumerate(direct_reports, start=1):
        bd = r.get("birthdate") or ""
        hd = r.get("hireDate") or ""
        pn = (r.get("partnerName") or "")[:w5]
        fn = (r.get("firstName") or "")[:w1]
        ln = (r.get("lastName") or "")[:w2]
        print(fmt.format(str(i), fn, ln, bd, hd, pn))
    print(sep)
    print(f"Total: {len(direct_reports)}")


def _delete_direct_report() -> None:
    """Prompt for the number of the direct report to delete, remove it, save to file."""
    _list_direct_reports()
    if not direct_reports:
        return
    try:
        raw = input("\nEnter the number of the direct report to delete: ").strip()
        num = int(raw)
        if 1 <= num <= len(direct_reports):
            removed = direct_reports.pop(num - 1)
            _save_direct_reports()
            print(f"Removed: {removed.get('firstName', '')} {removed.get('lastName', '')}")
        else:
            print(f"Invalid number. Enter 1 to {len(direct_reports)}.")
    except ValueError:
        print("Invalid input. Enter a number.")


DIRECT_REPORTS_MENU = _menu_box(
    "Administer Direct Reports",
    [
        ("  1. Add direct report", True),
        ("  2. List direct reports", True),
        ("  3. Delete a direct report", True),
        ("  4. Back to previous menu", True),
    ],
)


def run_direct_reports_menu() -> bool:
    """Sub-menu for administering direct reports (add/list/delete). Returns True so caller skips pause."""
    _run_submenu(
        DIRECT_REPORTS_MENU,
        4,
        {
            1: _add_direct_report,
            2: _list_direct_reports,
            3: _delete_direct_report,
        },
    )
    return True




# --- Manager / Management Improvement ---
IMPROVEMENT_MENU = _menu_box(
    "           Manager / Management Improvement",
    [
        ("  1. Get daily management tip", False),
        ("  2. Back to main menu", True),
    ],
)


def run_management_improvement_menu() -> None:
    """Sub-menu for management improvement."""
    _run_submenu(
        IMPROVEMENT_MENU,
        2,
        {
            1: lambda: print("\n[Placeholder] Daily management tip — not yet implemented."),
        },
    )


# --- Entry point ---
def main() -> None:
    """Run the CLI: load data, then main menu loop."""
    print("Welcome to WingmanEM.\n")
    _load_direct_reports()
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
