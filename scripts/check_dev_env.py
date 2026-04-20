#!/usr/bin/env python3
"""Print safe diagnostics for local env loading (no secret values). Run from project root."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    import wingmanem.app as app
    import wingmanem.settings as s
    from wingmanem.envfile import parse_env_file

    dev = root / ".env.development"
    env = root / ".env"
    print("settings module:", Path(s.__file__).resolve())
    print("project root:", s._project_root())
    print(".env.development exists:", dev.is_file(), f"({dev})")
    print(".env exists:", env.is_file(), f"({env})")

    raw = __import__("os").environ.get("MISTRAL_API_KEY", "")
    print("MISTRAL_API_KEY in os.environ (non-empty):", bool(raw and raw.strip()))
    k = s.mistral_api_key()
    print("mistral_api_key() resolved (non-empty):", bool(k))
    print("mistralai importable (MISTRAL_AVAILABLE):", bool(app.MISTRAL_AVAILABLE))
    if app.MISTRAL_IMPORT_ERROR:
        print("MISTRAL_IMPORT_ERROR:", app.MISTRAL_IMPORT_ERROR)
    if k and not app.MISTRAL_AVAILABLE:
        print(
            "Hint: API key is set but the Mistral SDK did not import in this interpreter. "
            "Start the app with the same Python as: which python && pip install -r requirements.txt"
        )
    if k:
        print("mistral_api_key length:", len(k))
    else:
        if dev.is_file():
            parsed = parse_env_file(dev)
            mk = (parsed.get("MISTRAL_API_KEY") or "").strip()
            print("MISTRAL_API_KEY in parsed .env.development (non-empty):", bool(mk))
            if not mk:
                print("Hint: add a line MISTRAL_API_KEY=your_key (no spaces around =).")
        else:
            print("Hint: create .env.development from .env.development.example in the project root.")


if __name__ == "__main__":
    main()
