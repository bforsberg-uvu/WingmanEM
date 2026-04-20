# WingmanEM

Engineering manager assistant: direct reports, goals, 1:1 summaries, management tips (optional **Mistral AI**), SQLite + JSON persistence.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

| What | Command |
|------|---------|
| **CLI** | `python app.py` or `python -m wingmanem` |
| **Web (Flask)** | `python web_app.py` or `./scripts/with_dev_env.sh python web_app.py` |
| **Web (Gunicorn)** | `gunicorn wsgi:app` (often with `./scripts/with_dev_env.sh` locally) |

Configuration, **`.env.development`**, Gunicorn, and **Mistral** troubleshooting are documented in **`DEPLOYMENT.md`**. Variable reference: **`.env.example`**.

Quick check (paths, key length, Mistral SDK import—**no secrets printed**):

```bash
python3 scripts/check_dev_env.py
```
