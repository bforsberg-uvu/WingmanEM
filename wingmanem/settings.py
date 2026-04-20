"""
Environment-driven configuration.

Loads optional env files from the **project root** (parent of the ``wingmanem``
package), not only the process cwd — so ``MISTRAL_API_KEY`` and friends work when
running ``python web_app.py`` or Gunicorn from any working directory.

Parsing is done by ``wingmanem.envfile`` (stdlib only), so keys load even when you
run the system ``python3`` without activating a venv.

Files are loaded in order. A variable is only skipped if it is **already set to a
non-empty value** in the process environment (so real deployment secrets win). An
empty or whitespace-only value does **not** block loading from the file.

1. ``.env.development`` — local dev secrets (gitignored)
2. ``.env`` — generic local overrides

See ``.env.example`` and ``scripts/with_dev_env.sh``.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from wingmanem.envfile import parse_env_file


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _env_nonempty(name: str) -> bool:
    v = os.environ.get(name)
    return v is not None and str(v).strip() != ""


def _load_dotenv_files() -> None:
    root = _project_root()
    for name in (".env.development", ".env"):
        path = root / name
        if not path.is_file():
            continue
        for key, value in parse_env_file(path).items():
            if _env_nonempty(key):
                continue
            os.environ[key] = value


_load_dotenv_files()


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def _env_str_optional(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    return str(raw).strip()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip(), 10)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


# --- Data paths (defaults: project cwd) ---
DATABASE_PATH = _env_str("WINGMANEM_DATABASE_PATH", "wingmanem.db")
DIRECT_REPORTS_FILE = _env_str("WINGMANEM_DIRECT_REPORTS_FILE", "direct_reports.json")
MANAGEMENT_TIPS_FILE = _env_str("WINGMANEM_MANAGEMENT_TIPS_FILE", "management_tips.json")
DIRECT_REPORT_GOALS_FILE = _env_str("WINGMANEM_DIRECT_REPORT_GOALS_FILE", "direct_report_goals.json")
DIRECT_REPORT_COMP_DATA_FILE = _env_str(
    "WINGMANEM_DIRECT_REPORT_COMP_DATA_FILE", "direct_report_comp_data.json"
)
LEGACY_DIRECT_REPORT_COMP_DATA_FILE = _env_str(
    "WINGMANEM_LEGACY_EMPLOYEE_COMP_DATA_FILE", "employee_comp_data.json"
)


def flask_secret_key() -> str:
    """Flask signing key: ``SECRET_KEY`` env, or a random per-process value if unset."""
    explicit = _env_str_optional("SECRET_KEY")
    if explicit:
        return explicit
    return secrets.token_hex(32)


def max_upload_bytes() -> int:
    mb = _env_int("WINGMANEM_MAX_UPLOAD_MB", 32)
    if mb < 1:
        mb = 1
    return mb * 1024 * 1024


def web_host() -> str:
    return _env_str("WINGMANEM_WEB_HOST", "127.0.0.1")


def web_port() -> int:
    return _env_int("WINGMANEM_WEB_PORT", 5000)


def web_debug() -> bool:
    return _env_bool("WINGMANEM_WEB_DEBUG", False)


def mistral_api_key() -> str | None:
    return _env_str_optional("MISTRAL_API_KEY")


def cli_expected_password() -> str:
    """Optional CLI ``authenticate()`` password (``WINGMANEM_PASSWORD``)."""
    return (os.environ.get("WINGMANEM_PASSWORD") or "").strip()
