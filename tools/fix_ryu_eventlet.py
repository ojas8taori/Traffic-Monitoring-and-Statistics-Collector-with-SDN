#!/usr/bin/env python3
"""
Patch Ryu's wsgi.py to work with Eventlet versions where
ALREADY_HANDLED was moved/removed from eventlet.wsgi.

This script is idempotent and safe to run multiple times.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

CLASS_START = "class _AlreadyHandledResponse(Response):"
CLASS_END_MARKER = "\n\ndef websocket("  # next symbol after class in Ryu 4.34
PATCH_MARKER = "return getattr(WSGI_LOCAL, 'already_handled', None)"

SAFE_CLASS = """class _AlreadyHandledResponse(Response):
    # XXX: Eventlet API should not be used directly.
    def __call__(self, environ, start_response):
        try:
            from eventlet.wsgi import ALREADY_HANDLED
            return ALREADY_HANDLED
        except ImportError:
            from eventlet.wsgi import WSGI_LOCAL
            return getattr(WSGI_LOCAL, 'already_handled', None)
"""


def locate_ryu_wsgi() -> Path:
    spec = importlib.util.find_spec("ryu")
    if spec is None or not spec.submodule_search_locations:
        raise RuntimeError("Ryu is not installed in the current Python environment.")

    ryu_root = Path(list(spec.submodule_search_locations)[0])
    wsgi_file = ryu_root / "app" / "wsgi.py"
    if not wsgi_file.exists():
        raise RuntimeError(f"Could not find Ryu wsgi file: {wsgi_file}")
    return wsgi_file


def patch_wsgi_file(path: Path) -> str:
    source = path.read_text(encoding="utf-8")

    if PATCH_MARKER in source:
        return "already_patched"

    start = source.find(CLASS_START)
    if start == -1:
        return "pattern_not_found"

    end = source.find(CLASS_END_MARKER, start)
    if end == -1:
        return "pattern_not_found"

    updated = source[:start] + SAFE_CLASS + source[end:]

    backup_path = path.with_suffix(path.suffix + ".bak")
    backup_path.write_text(source, encoding="utf-8")
    path.write_text(updated, encoding="utf-8")
    return "patched"


def main() -> int:
    try:
        wsgi_path = locate_ryu_wsgi()
        result = patch_wsgi_file(wsgi_path)

        if result == "patched":
            print(f"[OK] Patched Ryu Eventlet compatibility: {wsgi_path}")
            print(f"[OK] Backup created: {wsgi_path}.bak")
            return 0

        if result == "already_patched":
            print(f"[OK] Ryu compatibility patch already present: {wsgi_path}")
            return 0

        print(f"[WARN] Expected import line not found in: {wsgi_path}")
        return 1

    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
