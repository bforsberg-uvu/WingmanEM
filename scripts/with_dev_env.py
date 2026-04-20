#!/usr/bin/env python3
"""
Load `.env.development` into the process environment, then exec the given command.

Uses the stdlib and shared ``wingmanem.envfile`` parsing. Requires the project root
on ``sys.path`` so ``wingmanem`` is importable (this script lives under ``scripts/``).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from wingmanem.envfile import parse_env_file  # noqa: E402


def main() -> None:
    default_path = _ROOT / ".env.development"
    raw = os.environ.get("WINGMANEM_DEV_ENV_FILE", "").strip()
    env_path = Path(raw) if raw else default_path
    if not env_path.is_file():
        print(f"Missing {env_path}", file=sys.stderr)
        print(
            "Copy .env.development.example to .env.development and set SECRET_KEY, etc.",
            file=sys.stderr,
        )
        sys.exit(1)

    for key, value in parse_env_file(env_path).items():
        os.environ[key] = value

    os.chdir(_ROOT)
    argv = sys.argv[1:]
    if not argv:
        print("usage: with_dev_env.py <command> [args...]", file=sys.stderr)
        sys.exit(1)
    os.execvp(argv[0], argv)


if __name__ == "__main__":
    main()
