# WingmanEM — running locally and in production

## Configuration overview

- **Production:** set environment variables on the host, process manager, or container (never commit secrets). At minimum, set **`SECRET_KEY`** to a long random string so sessions and cookies remain valid across workers and restarts.
- **Development:** keep real keys in **`.env.development`** (gitignored). Use **`scripts/with_dev_env.sh`** to load that file and run commands. The shell script delegates to **`scripts/with_dev_env.py`**, which uses **`wingmanem.envfile`** to parse the file and updates **`os.environ`** before **`exec`**, so **`SECRET_KEY`** and other values are always visible to **Gunicorn** and its workers.

Variable reference: **`.env.example`**. Development template with placeholders: **`.env.development.example`**.

To see why a variable might be missing (paths, which files exist, whether the key resolved, whether **`mistralai`** imported—**no secrets printed**):

```bash
python3 scripts/check_dev_env.py
```

## Mistral AI (optional)

- Set **`MISTRAL_API_KEY`** in **`.env.development`** or the process environment (see **`.env.example`**).
- Install the SDK with the **same virtualenv** you use to run the web app: **`pip install -r requirements.txt`** (includes **`mistralai`**).
- The code supports **mistralai v1** (`from mistralai import Mistral`) and **v2** (`from mistralai.client import Mistral`). If the UI shows a flash about the client not loading, run **`check_dev_env.py`** and read **`MISTRAL_IMPORT_ERROR`** (if present).

## Local development

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create **`.env.development`** from the example and add your keys:

   ```bash
   cp .env.development.example .env.development
   # Edit .env.development: set SECRET_KEY and MISTRAL_API_KEY
   ```

   Generate a stable dev `SECRET_KEY`:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. Activate your venv whenever you run **`gunicorn`** or **`python`** so the same environment resolves both the loader and the server.

4. Run the Flask dev server (working directory should be the project root):

   ```bash
   chmod +x scripts/with_dev_env.sh
   ./scripts/with_dev_env.sh python web_app.py
   ```

   To use a different env file path:

   ```bash
   WINGMANEM_DEV_ENV_FILE=/path/to/.env.development ./scripts/with_dev_env.sh python web_app.py
   ```

5. Run the CLI with the same environment:

   ```bash
   ./scripts/with_dev_env.sh python -m wingmanem.app
   ```

If you run **`python web_app.py`** or **Gunicorn** without the script, **`wingmanem.settings`** still loads **`.env.development`** and then **`.env`** from the **project root** (next to the `wingmanem` package), regardless of the shell’s current working directory. That loader uses **`wingmanem.envfile`** (stdlib only), so **`MISTRAL_API_KEY`** is available even when you use system `python3` without activating your venv. Process environment variables always override those files.

## Production with Gunicorn

Run from the **project root** so SQLite and JSON paths resolve correctly.

1. Set **`SECRET_KEY`** and any other variables (see `.env.example`) in the environment of the service user.

2. Install dependencies (same `requirements.txt`).

3. Start Gunicorn using the **`wsgi:app`** entrypoint:

   ```bash
   gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
   ```

   Common options:

   - **`-w`:** worker count (often `2 * CPUs + 1` as a starting point).
   - **`-b`:** bind address and port.
   - **`--timeout 120`:** increase if large uploads (1:1 audio) hit worker timeouts.

4. Put Gunicorn behind **nginx** or another reverse proxy for TLS and static files in real deployments.

The app initializes data on the first request per worker (`before_request`); no separate `init_data` call is required for Gunicorn.

## Gunicorn vs `python web_app.py`

| Mode | Command | Typical use |
|------|---------|-------------|
| Flask built-in | `./scripts/with_dev_env.sh python web_app.py` | Local debugging (`WINGMANEM_WEB_DEBUG=true`) |
| Gunicorn | `./scripts/with_dev_env.sh gunicorn -w 2 -b 127.0.0.1:8000 wsgi:app` | Closer to production; use without debug in shared environments |

## Dependencies

See **`requirements.txt`** (Flask, Gunicorn, SQLAlchemy, **mistralai**, etc.). Environment files under the project root are loaded by **`wingmanem.settings`** via **`wingmanem.envfile`**.
