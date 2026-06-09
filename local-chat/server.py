#!/usr/bin/env python3
"""Локальный PWA/AJAX-прокси для резервного чата Айрин.

Сервер не меняет live runtime Айрин. Он только отдает PWA-файлы и
проксирует безопасные HTTP-запросы к уже работающему airin-local-chat.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
PROXY_PREFIXES = ("/health", "/api/")


class LocalChatHandler(BaseHTTPRequestHandler):
    target = "http://127.0.0.1:8790"

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[local-chat] " + fmt % args + "\n")

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store" if self.path.startswith(PROXY_PREFIXES) else "public, max-age=60")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith(PROXY_PREFIXES):
          self.proxy()
          return
        self.serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith(PROXY_PREFIXES):
            self.proxy()
            return
        self.send_json(404, {"ok": False, "error": "unknown endpoint"})

    def serve_static(self, path: str) -> None:
        if path in ("", "/", "/local-chat", "/local-chat/"):
            file_path = ROOT / "index.html"
        else:
            clean = path.removeprefix("/local-chat/").lstrip("/")
            file_path = ROOT / clean
        try:
            resolved = file_path.resolve()
            if ROOT not in resolved.parents and resolved != ROOT:
                raise ValueError("path escapes root")
            if not resolved.exists() or not resolved.is_file():
                raise FileNotFoundError(path)
            data = resolved.read_bytes()
        except Exception:
            self.send_json(404, {"ok": False, "error": "file not found"})
            return
        ctype = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        if resolved.suffix == ".webmanifest":
            ctype = "application/manifest+json"
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def proxy(self) -> None:
        body = b""
        if self.command in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length else b""
        target_url = urljoin(self.target.rstrip("/") + "/", self.path.lstrip("/"))
        headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
        request = Request(target_url, data=body or None, method=self.command, headers=headers)
        try:
            with urlopen(request, timeout=8) as response:
                data = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except HTTPError as error:
            data = error.read()
            self.send_response(error.code)
            self.send_header("Content-Type", error.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except URLError as error:
            self.send_json(502, {"ok": False, "error": f"target unavailable: {error.reason}"})

    def send_json(self, status: int, payload: dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="REDNET Airin local chat PWA proxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8792)
    parser.add_argument("--target", default="http://127.0.0.1:8790")
    args = parser.parse_args()
    LocalChatHandler.target = args.target
    server = ThreadingHTTPServer((args.host, args.port), LocalChatHandler)
    print(f"REDNET local chat PWA: http://{args.host}:{args.port}/ -> {args.target}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
