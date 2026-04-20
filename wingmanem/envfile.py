"""Parse simple ``KEY=value`` env files (stdlib only; UTF-8 BOM, CRLF, ``#`` comments)."""

from __future__ import annotations

from pathlib import Path


def parse_env_file(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig")
    out: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n").strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key] = value
    return out
