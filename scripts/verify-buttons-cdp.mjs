#!/usr/bin/env node
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const EDGE = [
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
].find(existsSync);

if (!EDGE) {
  throw new Error("Edge/Chrome executable not found");
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function waitFor(url, timeoutMs = 12000) {
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
    await sleep(300);
  }
  throw lastError || new Error(`Timeout waiting for ${url}`);
}

function cdpClient(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    }
  });
  return new Promise((resolve, reject) => {
    ws.addEventListener("open", () => {
      resolve({
        send(method, params = {}) {
          const callId = ++id;
          ws.send(JSON.stringify({ id: callId, method, params }));
          return new Promise((callResolve, callReject) => pending.set(callId, { resolve: callResolve, reject: callReject }));
        },
        close() {
          ws.close();
        },
      });
    });
    ws.addEventListener("error", reject);
  });
}

async function openPage(browserPort, url) {
  await fetch(`http://127.0.0.1:${browserPort}/json/new?${encodeURIComponent(url)}`, { method: "PUT" }).catch(() => null);
  const list = await (await waitFor(`http://127.0.0.1:${browserPort}/json/list`)).json();
  const page = list.find((item) => item.type === "page" && item.webSocketDebuggerUrl);
  if (!page) throw new Error("No CDP page target");
  const cdp = await cdpClient(page.webSocketDebuggerUrl);
  await cdp.send("Runtime.enable");
  await cdp.send("Page.enable");
  await cdp.send("Page.navigate", { url });
  await sleep(1600);
  return cdp;
}

async function evalJs(cdp, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "Runtime exception");
  }
  return result.result.value;
}

async function main() {
  const localServer = spawn("python", ["local-chat/server.py", "--port", "8792", "--target", "http://127.0.0.1:8790"], {
    cwd: ROOT,
    windowsHide: true,
    stdio: "ignore",
  });
  const profile = mkdtempSync(path.join(tmpdir(), "rednet-miniapp-cdp-"));
  const browserPort = 9333 + Math.floor(Math.random() * 200);
  const browser = spawn(EDGE, [
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--disable-default-apps",
    `--remote-debugging-port=${browserPort}`,
    `--user-data-dir=${profile}`,
    "about:blank",
  ], { windowsHide: true, stdio: "ignore" });

  try {
    await waitFor("http://127.0.0.1:8792/health");
    await waitFor(`http://127.0.0.1:${browserPort}/json/version`);

    const rootUrl = pathToFileURL(path.join(ROOT, "index.html")).href;
    const root = await openPage(browserPort, rootUrl);
    const rootResult = await evalJs(root, `(async () => {
      document.querySelector("#localChatBtn").click();
      await new Promise((resolve) => setTimeout(resolve, 80));
      const localPayload = document.querySelector("#actionResult").textContent;
      [...document.querySelectorAll(".quick-card")].find((button) => button.innerText.includes("Позвать")).click();
      await new Promise((resolve) => setTimeout(resolve, 80));
      const callPayload = document.querySelector("#actionResult").textContent;
      document.querySelector("[data-palette]").click();
      await new Promise((resolve) => setTimeout(resolve, 80));
      const paletteOpen = document.querySelector("#palette").open;
      document.querySelector("#closePalette").click();
      return {
        errors: window.__rednetErrors || [],
        localPayloadHasUrl: localPayload.includes("127.0.0.1:8792"),
        callPayloadHasPing: callPayload.includes("call-airin"),
        paletteOpen
      };
    })()`);
    root.close();

    const local = await openPage(browserPort, "http://127.0.0.1:8792/");
    const localResult = await evalJs(local, `(async () => {
      window.fetch = async (url, options = {}) => {
        const value = String(url);
        const json = (payload) => new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } });
        if (value.includes("/health")) return json({ ok: true, enabled: true, mode: "test", hot_off: false, queue: { held: 1, queued: 2 } });
        if (value.includes("/api/status")) return json({ ok: true, mode: "test", hot_off: false });
        if (value.includes("/api/history")) return json({ items: [{ sender: "airin", text: "тестовая связь", created_at: new Date().toISOString() }] });
        if (value.includes("/api/queue")) return json({ items: [] });
        if (value.includes("/api/chat")) return json({ ok: true });
        if (value.includes("/api/hotoff")) return json({ ok: true });
        return json({ ok: true });
      };
      await refresh();
      document.querySelector("#refreshBtn").click();
      await new Promise((resolve) => setTimeout(resolve, 80));
      const statusText = document.querySelector("#liveText").textContent;
      document.querySelector("#exportsBtn").click();
      const sheetOpen = document.querySelector("#sheet").classList.contains("show");
      document.querySelector("#loginPassword").value = "test-password";
      document.querySelector("#loginForm").requestSubmit();
      await new Promise((resolve) => setTimeout(resolve, 120));
      const operator = document.querySelector("#operatorText").textContent;
      document.querySelector("#callBtn").click();
      await new Promise((resolve) => setTimeout(resolve, 160));
      const notice = document.querySelector("#notice").textContent;
      document.querySelector("#holdBtn").click();
      await new Promise((resolve) => setTimeout(resolve, 160));
      return { statusText, sheetOpen, operator, notice, messageText: document.querySelector("#messages").innerText };
    })()`);
    local.close();

    const ok =
      rootResult.localPayloadHasUrl &&
      rootResult.callPayloadHasPing &&
      rootResult.paletteOpen &&
      !rootResult.errors.length &&
      localResult.statusText === "работает" &&
      localResult.sheetOpen &&
      localResult.operator === "ivan" &&
      localResult.messageText.includes("тестовая связь");

    if (!ok) {
      console.error(JSON.stringify({ rootResult, localResult }, null, 2));
      process.exit(1);
    }
    console.log("OK: button CDP check passed");
    console.log(JSON.stringify({ rootResult, localResult }, null, 2));
  } finally {
    browser.kill();
    localServer.kill();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
