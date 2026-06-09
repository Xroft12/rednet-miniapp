#!/usr/bin/env python3
"""Install RedNET MiniApp as the Telegram bot menu button.

Reads TELEGRAM_BOT_TOKEN from environment or Hermes .env. The token is never
printed. Usage:

    python scripts/install-telegram-menu.py https://example.com/rednet-miniapp/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def candidate_env_paths() -> list[Path]:
    paths: list[Path] = []
    for raw in [os.environ.get("HERMES_HOME")]:
        if raw:
            paths.append(Path(raw) / ".env")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        paths.append(Path(local) / "hermes" / ".env")
    user = os.environ.get("USERPROFILE") or os.environ.get("HOME")
    if user:
        paths.append(Path(user) / "AppData" / "Local" / "hermes" / ".env")
        paths.append(Path(user) / ".hermes" / ".env")
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            resolved = path.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def read_dotenv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def get_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        return token
    for env_path in candidate_env_paths():
        token = read_dotenv(env_path).get("TELEGRAM_BOT_TOKEN", "").strip()
        if token:
            return token
    raise RuntimeError("TELEGRAM_BOT_TOKEN was not found in environment or Hermes .env")


def telegram_api(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API HTTP {exc.code}: {text}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Telegram API network error: {exc}") from exc
    parsed = json.loads(text)
    if not parsed.get("ok"):
        raise RuntimeError("Telegram API returned ok=false: " + json.dumps(parsed, ensure_ascii=False))
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Install RedNET MiniApp as Telegram bot menu button")
    parser.add_argument("url", help="public HTTPS URL of the MiniApp")
    parser.add_argument("--text", default="Айрин ♥ RedNET", help="button text")
    parser.add_argument("--chat-id", default="", help="optional Telegram chat_id for chat-specific menu button")
    args = parser.parse_args()

    if not args.url.startswith("https://"):
        raise SystemExit("MiniApp URL must start with https://")

    token = get_token()
    payload: dict[str, Any] = {
        "menu_button": {
            "type": "web_app",
            "text": args.text,
            "web_app": {"url": args.url},
        }
    }
    verify_payload: dict[str, Any] = {}
    if args.chat_id:
        try:
            chat_id: int | str = int(args.chat_id)
        except ValueError:
            chat_id = args.chat_id
        payload["chat_id"] = chat_id
        verify_payload["chat_id"] = chat_id

    telegram_api(token, "setChatMenuButton", payload)
    verified = telegram_api(token, "getChatMenuButton", verify_payload)["result"]

    safe_result = {
        "type": verified.get("type"),
        "text": verified.get("text"),
        "url": (verified.get("web_app") or {}).get("url"),
    }
    print("OK: Telegram bot menu button installed")
    print(json.dumps(safe_result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - CLI should print concise failure
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
