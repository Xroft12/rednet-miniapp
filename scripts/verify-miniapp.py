#!/usr/bin/env python3
"""Smoke checks for the RedNET Telegram MiniApp."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
MANIFEST = ROOT / "manifest.webmanifest"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not INDEX.exists():
        fail("index.html missing")
    if not MANIFEST.exists():
        fail("manifest.webmanifest missing")

    html = INDEX.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    required = [
        "https://telegram.org/js/telegram-web-app.js",
        "window.Telegram?.WebApp",
        "sendData",
        'source: "rednet-miniapp"',
        'type: "command"',
        'type: "secret_transfer"',
        "secretPayload",
        "secretClearBtn",
        "adminActionIds",
        "safety",
    ]
    missing = [marker for marker in required if marker not in html]
    if missing:
        fail("missing required markers: " + ", ".join(missing))

    command_count = len(re.findall(r'\{\s*id:\s*"[a-z0-9-]+"', html))
    if command_count < 25:
        fail(f"too few commands detected: {command_count}")

    scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, flags=re.S | re.I)
    if not scripts:
        fail("no inline script blocks found")

    with tempfile.TemporaryDirectory() as td:
        js_path = Path(td) / "inline.js"
        js_path.write_text("\n;\n".join(scripts), encoding="utf-8")
        result = subprocess.run(["node", "--check", str(js_path)], text=True, capture_output=True)
        if result.returncode != 0:
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            fail("node --check failed")

    print("OK: RedNET MiniApp smoke check passed")
    print(f"commands: {command_count}")
    print(f"manifest: {manifest.get('name')} / {manifest.get('display')}")
    print(f"index_bytes: {INDEX.stat().st_size}")


if __name__ == "__main__":
    main()
