"""
Reconstruct HTTP request text for debug / teaching pages (e.g. goal admin).

Uses Werkzeug/Flask request objects; no Flask app import required.
"""

from __future__ import annotations

from typing import Any


def headers_for_display(headers: Any) -> dict[str, str]:
    """Return headers safe for display (redacts sensitive values)."""
    redacted: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in {"cookie", "authorization"}:
            redacted[k] = "[redacted]"
        else:
            redacted[k] = v
    return redacted


def raw_http_request_for_display(req: Any, body_text: str = "") -> str:
    """Best-effort reconstructed raw HTTP request (not a wire capture)."""
    proto = req.environ.get("SERVER_PROTOCOL", "HTTP/1.1")
    full_path = req.full_path
    if full_path.endswith("?"):
        full_path = full_path[:-1]
    request_line = f"{req.method} {full_path} {proto}"
    hdrs = headers_for_display(req.headers)
    header_lines = "\n".join([f"{k}: {v}" for k, v in hdrs.items()])
    if body_text:
        return f"{request_line}\n{header_lines}\n\n{body_text}"
    return f"{request_line}\n{header_lines}"
