"""
WSGI entrypoint for production servers (e.g. Gunicorn).

    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app

See ``DEPLOYMENT.md`` for full run instructions.
"""

from web_app import app

__all__ = ["app"]
