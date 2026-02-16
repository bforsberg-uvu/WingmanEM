"""
WingmanEM CLI prototype Chunk #2
Main application logic: menu-driven navigation and password protection.
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


# ============================================================================
# GLOBAL CONFIG & CONSTANTS
# ============================================================================

# Direct_Reports table structure (project_plan.md): required id, first_name, last_name; rest optional
DIRECT_REPORT_OPTIONAL_KEYS = (
    "street_address_1", "street_address_2", "city", "state", "zipcode", "country",
    "birthday", "hire_date", "current_role", "role_start_date", "partner_name",
)

# Global data
direct_reports: list[dict[str, Any]] = []
# Each item: {"date": "YYYY-MM-DD", "text": "tip content"}
management_tips: list[dict[str, str]] = []

# Persistence files
DIRECT_REPORTS_FILE = "direct_reports.json"
MANAGEMENT_TIPS_FILE = "management_tips.json"

# ANSI colors for menu items
_MENU_COLOR_BLACK = "\033[30m"
_MENU_COLOR_RED = "\033[31m"
_MENU_COLOR_DISABLED = "\033[2;37m"  # very light gray (dim white)
_MENU_COLOR_RESET = "\033[0m"
_MENU_BOLD = "\033[1m"


# ============================================================================
# CONFIGURATION & UTILITY FUNCTIONS
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


# ============================================================================
# MENU & UI FUNCTIONS
# ============================================================================

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
    lines = ["║" + _MENU_BOLD + title_content + _MENU_COLOR_RESET + "║"]
    for opt in options:
        if isinstance(opt, tuple):
            text = opt[0]
            enabled = opt[1] if len(opt) >= 2 else True
            red = opt[2] if len(opt) >= 3 else False
        else:
            text, enabled, red = opt, True, False
        content = text[:width].ljust(width)
        if not enabled:
            color = _MENU_COLOR_DISABLED
        elif red:
            color = _MENU_COLOR_RED
        else:
            color = _MENU_COLOR_BLACK
        lines.append("║" + color + content + _MENU_COLOR_RESET + "║")
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
                        content = "  " + _MENU_BOLD + bold_text + _MENU_COLOR_RESET + rest_text
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
                    middle_lines.append("║" + _MENU_BOLD + content + _MENU_COLOR_RESET + "║")
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
# DIRECT REPORTS: Data Management
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
    """Read direct_reports from file into the global list; normalize keys and assign missing ids.
    If the file does not exist, start with an empty list and create the file."""
    global direct_reports
    if not os.path.isfile(DIRECT_REPORTS_FILE):
        direct_reports = []
        _save_direct_reports()
        return
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


def _save_direct_reports() -> None:
    """Write the global direct_reports list to file."""
    try:
        with open(DIRECT_REPORTS_FILE, "w", encoding="utf-8") as f:
            json.dump(direct_reports, f, indent=2)
    except OSError as e:
        print(f"Could not save direct reports: {e}", file=sys.stderr)


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


def _list_direct_reports() -> None:
    """Display all direct reports in a table with every DirectReport field."""
    if not direct_reports:
        print("\nNo direct reports yet. Add one from the menu.")
        return
    cols = _LIST_DIRECT_REPORT_COLUMNS
    # Build format: first column right-aligned (No.), rest left-aligned
    fmt_parts = [f"{{:>{cols[0][2]}}}"] + [f"{{:{c[2]}}}" for c in cols[1:]]
    fmt = " ".join(fmt_parts)
    total_width = sum(c[2] for c in cols) + len(cols) - 1
    sep = "-" * total_width
    print()
    print("Direct Reports")
    print()
    headers = [c[1] for c in cols]
    print(fmt.format(*headers))
    print(sep)
    for r in direct_reports:
        row = []
        for key, _header, width in cols:
            val = r.get(key)
            if val is None:
                val = ""
            s = str(val)[:width] if val else ""
            row.append(s)
        print(fmt.format(*row))
    print(sep)
    print(f"Total: {len(direct_reports)}")


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
# MANAGEMENT TIPS: Data Management
# ============================================================================

def _load_management_tips() -> None:
    """Read management tips (date + text) from file into the global list.
    File format: list of {"date": "YYYY-MM-DD", "text": "..."}.
    Legacy: list of plain strings is migrated to new format with date set to today.
    If the file does not exist, start with an empty list and create the file.
    If the list is empty or we have not fetched a tip today, fetch a new tip from Mistral AI if available."""
    global management_tips
    today_str = date.today().isoformat()
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
    last_date = management_tips[-1]["date"] if management_tips else None
    need_new_tip = not management_tips or last_date != today_str
    if need_new_tip and MISTRAL_AVAILABLE and _get_mistral_api_key():
        _generate_management_tip_with_ai(silent=True)


def _save_management_tips() -> None:
    """Write the global management_tips list to file."""
    try:
        with open(MANAGEMENT_TIPS_FILE, "w", encoding="utf-8") as f:
            json.dump(management_tips, f, indent=2)
    except OSError as e:
        print(f"Could not save management tips: {e}", file=sys.stderr)


def _get_latest_management_tip() -> str:
    """Return the most recent management tip text, or a placeholder if none."""
    if management_tips:
        return management_tips[-1]["text"]
    return "No tip yet. Generate one from Mistral AI."


def _normalize_tip_for_comparison(tip: str) -> str:
    """Normalize tip text for duplicate check: lowercase, single spaces, no leading/trailing space."""
    return " ".join(tip.lower().split())


def _is_duplicate_management_tip(text: str) -> bool:
    """Return True if the tip text is effectively a duplicate of any existing tip in management_tips."""
    if not text:
        return False
    normalized_new = _normalize_tip_for_comparison(text)
    for entry in management_tips:
        if _normalize_tip_for_comparison(entry["text"]) == normalized_new:
            return True
    return False


def _generate_management_tip_with_ai(*, silent: bool = False) -> bool:
    """Generate one daily management tip using Mistral AI; append and save. Returns True on success.
    If the suggested tip is a duplicate of an existing one, requests a different tip (up to a few retries).
    If silent is True, do not print success message (e.g. when seeding on startup)."""
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
    try:
        client = Mistral(api_key=api_key)
        for attempt in range(max_attempts):
            avoid_all = [e["text"] for e in management_tips[-20:]]
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
            if _is_duplicate_management_tip(text):
                continue
            management_tips.append({"date": date.today().isoformat(), "text": text})
            _save_management_tips()
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
    """Print all management tips grouped by date (oldest first)."""
    _clear_screen()
    print("\n--- Management Tips by Date ---\n")
    if not management_tips:
        print("No tips yet.")
        return
    for entry in management_tips:
        print(f"  {entry['date']}:  {entry['text']}")
    print()


# ============================================================================
# MILESTONE REMINDERS
# ============================================================================

def _view_milestone_reminders() -> None | bool:
    """Show upcoming birthdays and anniversaries for direct reports."""
    today = date.today()

    def _print_upcoming(range_days: int) -> None:
        _clear_screen()
        print("\n--- Milestone Reminders ---\n")
        print(f"Showing the next {range_days} days.\n")
        upcoming = []
        for r in direct_reports:
            # Birthday
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
                        upcoming.append((days_until, f"Birthday: {r['first_name']} {r['last_name']} on {next_bd.strftime('%Y-%m-%d')} ({days_until} days)", bd_date))
                except Exception:
                    pass
            # Work anniversary
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
                        years = (anniv.year - hd_date.year)
                        upcoming.append((days_until, f"Anniversary: {r['first_name']} {r['last_name']} ({years} years) on {anniv.strftime('%Y-%m-%d')} ({days_until} days)", hd_date))
                except Exception:
                    pass
        if not upcoming:
            print(f"No upcoming birthdays or anniversaries in the next {range_days} days.")
        else:
            upcoming.sort()
            for _, msg, _ in upcoming:
                print(msg)

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
# MENUS: Main Menu
# ============================================================================

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
            "",
            "",
            (
                "Instructions For Dr. Riskas:",
                " You can navigate to either 'Administer Direct Reports' or 'View Management Tips by Date'"
                "(select red options) to see file operations in action. There are two files direct_reports.json"
                " and management_tips.json that store the data for the direct reports and management tips respectively. "
                "Management tips are generated by Mistral AI daily and are stored in the management_tips.json file. "
                "When a direct report is added or deleted, the data is persisted to direct_reports.json. "  
                "Both files are read back in when the program starts up for persistence. If one or both files are missing, "
                "the program will function as normal."
                ,
            ),
            "",
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


# ============================================================================
# MENUS: Developer Menu
# ============================================================================

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


# ============================================================================
# MENUS: Project Creation & Estimation
# ============================================================================

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


# ============================================================================
# MENUS: People Management & Coaching
# ============================================================================

PEOPLE_MENU = _menu_box(
    "           People Management & Coaching",
    [
        ("  1. Upload 1:1 recording (summarize & action items)", False),
        ("  2. View 1:1 trends analysis", False),
        ("  3. Get suggested follow-up topics", False),
        ("  4. View milestone reminders (anniversaries, birthdays)", True),
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
            1: lambda: print("\n[Placeholder] Upload 1:1 recording — not yet implemented."),
            2: lambda: print("\n[Placeholder] View 1:1 trends — not yet implemented."),
            3: lambda: print("\n[Placeholder] Suggested follow-up topics — not yet implemented."),
            4: _view_milestone_reminders,
            5: run_direct_reports_menu,
            6: _print_management_tips_by_date,
        },
    )


# ============================================================================
# MENUS: Administer Direct Reports
# ============================================================================

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
# AUTHENTICATION
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
