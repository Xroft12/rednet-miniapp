#!/usr/bin/env node
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitFor(url, timeoutMs = 10000) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return response;
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(250);
  }
  throw lastError || new Error(`Timeout waiting for ${url}`);
}

function requireMarker(text, marker) {
  if (!text.includes(marker)) {
    throw new Error(`Missing marker: ${marker}`);
  }
}

async function main() {
  const index = readFileSync(path.join(ROOT, "index.html"), "utf8");
  const local = readFileSync(path.join(ROOT, "local-chat", "index.html"), "utf8");
  const server = readFileSync(path.join(ROOT, "local-chat", "server.py"), "utf8");

  for (const marker of [
    "LOCAL_BRIDGE_URLS",
    "sendViaLocalBridge",
    "НЕ ДОСТАВЛЕНО",
    "http://127.0.0.1:8792/api/command",
    "actionResult",
  ]) {
    requireMarker(index, marker);
  }
  for (const marker of ["Позвать", "Выгрузки", "/api/chat", "Hold"]) {
    requireMarker(local, marker);
  }
  for (const marker of ["def handle_command", "command_to_text", "api/chat"]) {
    requireMarker(server, marker);
  }

  const bridge = spawn("python", ["local-chat/server.py", "--port", "8792", "--target", "http://127.0.0.1:8790"], {
    cwd: ROOT,
    windowsHide: true,
    stdio: "ignore",
  });

  try {
    await waitFor("http://127.0.0.1:8792/health");
    const payload = {
      source: "rednet-miniapp-test",
      type: "command",
      id: "bridge-test",
      title: "Проверка bridge",
      command: "Айрин, это тест доставки MiniApp через локальный bridge. Ответ не обязателен.",
      safety: "safe",
      ts: new Date().toISOString(),
    };
    const response = await fetch("http://127.0.0.1:8792/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok || !body.ok || !body.delivered) {
      throw new Error(`Bridge delivery failed: ${JSON.stringify(body)}`);
    }
    console.log("OK: MiniApp bridge delivery check passed");
    console.log(JSON.stringify(body, null, 2));
  } finally {
    bridge.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
