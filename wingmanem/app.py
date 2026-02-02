"""
WingmanEM CLI prototype.
Main application logic: menu-driven navigation and password protection.
"""

import getpass
import os
import sys
from collections.abc import Callable


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


def _menu_box(title: str, options: list[str], width: int = 58) -> str:
    """Build a box menu so each content line is exactly `width` chars (right border straight)."""
    border = "╔" + "═" * width + "╗"
    sep = "╠" + "═" * width + "╣"
    bottom = "╚" + "═" * width + "╝"
    lines = ["║" + title[:width].ljust(width) + "║"]
    for opt in options:
        lines.append("║" + opt[:width].ljust(width) + "║")
    return "\n".join([border, lines[0], sep] + lines[1:] + [bottom])


def _run_submenu(
    menu: str,
    max_option: int,
    actions: dict[int, Callable[[], None]],
) -> None:
    """Display a sub-menu in a loop. Option max_option is Back; others run actions[choice]."""
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
            actions[choice]()
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
        "  1. Project Creation & Estimation",
        "  2. People Management & Coaching",
        "  3. Manager / Management Improvement",
        "  4. Exit",
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
        "  1. Input project spec (get structured breakdown)",
        "  2. Sync breakdown to Jira",
        "  3. Ask about project status (natural language)",
        "  4. Back to main menu",
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
        "  1. Upload 1:1 recording (summarize & action items)",
        "  2. View 1:1 trends analysis",
        "  3. Get suggested follow-up topics",
        "  4. View milestone reminders (anniversaries, birthdays)",
        "  5. Back to main menu",
    ],
)


def run_people_coaching_menu() -> None:
    """Sub-menu for people management and coaching."""
    _run_submenu(
        PEOPLE_MENU,
        5,
        {
            1: lambda: print("\n[Placeholder] Upload 1:1 recording — not yet implemented."),
            2: lambda: print("\n[Placeholder] View 1:1 trends — not yet implemented."),
            3: lambda: print("\n[Placeholder] Suggested follow-up topics — not yet implemented."),
            4: lambda: print("\n[Placeholder] Milestone reminders — not yet implemented."),
        },
    )


# --- Manager / Management Improvement ---
IMPROVEMENT_MENU = _menu_box(
    "           Manager / Management Improvement",
    [
        "  1. Get daily management tip",
        "  2. Back to main menu",
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
    """Run the CLI: authenticate, then main menu loop."""
    print("Welcome to WingmanEM.\n")
    if not authenticate():
        print("Authentication failed. Exiting.", file=sys.stderr)
        sys.exit(1)
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
