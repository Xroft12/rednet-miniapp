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
LOCAL_CHAT = ROOT / "local-chat" / "index.html"
LOCAL_CHAT_MANIFEST = ROOT / "local-chat" / "manifest.webmanifest"
LOCAL_CHAT_SW = ROOT / "local-chat" / "sw.js"
LOCAL_CHAT_SERVER = ROOT / "local-chat" / "server.py"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not INDEX.exists():
        fail("index.html missing")
    if not MANIFEST.exists():
        fail("manifest.webmanifest missing")
    for required_path in (LOCAL_CHAT, LOCAL_CHAT_MANIFEST, LOCAL_CHAT_SW, LOCAL_CHAT_SERVER, ROOT / "icon.svg"):
        if not required_path.exists():
            fail(f"{required_path.relative_to(ROOT)} missing")

    html = INDEX.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    local_html = LOCAL_CHAT.read_text(encoding="utf-8")
    local_manifest = json.loads(LOCAL_CHAT_MANIFEST.read_text(encoding="utf-8"))

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
        "actionResult",
        "openLocalChat",
        "sendViaLocalBridge",
        "LOCAL_BRIDGE_URLS",
        "НЕ ДОСТАВЛЕНО",
        "local-chat/server.py",
        "safety",
    ]
    missing = [marker for marker in required if marker not in html]
    if missing:
        fail("missing required markers: " + ", ".join(missing))

    command_count = len(re.findall(r'\{\s*id:\s*"[a-z0-9-]+"', html))
    if command_count < 25:
        fail(f"too few commands detected: {command_count}")

    local_required = [
        "class=\"app\"",
        "Позвать",
        "Выгрузки",
        "/api/chat",
        "/api/hotoff",
        "serviceWorker",
        "FaceID / TouchID",
    ]
    local_missing = [marker for marker in local_required if marker not in local_html]
    if local_missing:
        fail("missing local chat markers: " + ", ".join(local_missing))

    script_groups = [
        ("index", re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, flags=re.S | re.I)),
        ("local-chat", re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", local_html, flags=re.S | re.I)),
    ]
    if not any(scripts for _, scripts in script_groups):
        fail("no inline script blocks found")

    with tempfile.TemporaryDirectory() as td:
        for name, scripts in script_groups:
            if not scripts:
                continue
            js_path = Path(td) / f"{name}.js"
            js_path.write_text("\n;\n".join(scripts), encoding="utf-8")
            result = subprocess.run(["node", "--check", str(js_path)], text=True, capture_output=True)
            if result.returncode != 0:
                print(result.stdout, end="")
                print(result.stderr, end="", file=sys.stderr)
                fail(f"node --check failed for {name}")

    print("OK: RedNET MiniApp smoke check passed")
    print(f"commands: {command_count}")
    print(f"manifest: {manifest.get('name')} / {manifest.get('display')}")
    print(f"local_chat_manifest: {local_manifest.get('name')} / {local_manifest.get('display')}")
    print(f"index_bytes: {INDEX.stat().st_size}")
    print(f"local_chat_bytes: {LOCAL_CHAT.stat().st_size}")


if __name__ == "__main__":
    main()
