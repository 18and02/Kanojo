const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

function argValue(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const baseUrl = argValue("--url", "http://127.0.0.1:5173");
const outDir = path.resolve(argValue("--out", "exports-showcase"));
const browserPath = argValue("--browser", process.env.BROWSER_PATH);
const remotePort = Number(argValue("--remote-port", "9222"));
const viewport = {
  width: Number(argValue("--width", "1440")),
  height: Number(argValue("--height", "960"))
};

const shots = [
  { name: "01-control", label: "控制", clicks: ["控制"] },
  { name: "02-memory-card", label: "记忆名片", clicks: ["记忆", "名片"] },
  { name: "03-memory-audit", label: "记忆审计", clicks: ["记忆", "审计"] },
  { name: "04-debug-node", label: "调试节点", clicks: ["调试"] }
];

class CdpSession {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 1;
    this.pending = new Map();
    socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data);
      if (payload.id && this.pending.has(payload.id)) {
        const { resolve, reject } = this.pending.get(payload.id);
        this.pending.delete(payload.id);
        if (payload.error) {
          reject(new Error(payload.error.message || JSON.stringify(payload.error)));
        } else {
          resolve(payload.result);
        }
      }
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`${url} returned HTTP ${response.status}`);
  }
  return response.json();
}

async function waitForCdp() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      return await fetchJson(`http://127.0.0.1:${remotePort}/json/version`);
    } catch {
      await sleep(250);
    }
  }
  throw new Error(`Chrome DevTools did not become ready on port ${remotePort}`);
}

async function connectPage(url) {
  await fetchJson(`http://127.0.0.1:${remotePort}/json/new?${encodeURIComponent(url)}`, {
    method: "PUT"
  });
  const pages = await fetchJson(`http://127.0.0.1:${remotePort}/json/list`);
  const page = pages.find((item) => item.type === "page" && item.url.startsWith(url)) ?? pages[0];
  if (!page?.webSocketDebuggerUrl) {
    throw new Error("No debuggable page target found.");
  }
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    socket.addEventListener("open", resolve, { once: true });
    socket.addEventListener("error", reject, { once: true });
  });
  return new CdpSession(socket);
}

async function clickButtonText(session, text) {
  const expression = `
(() => {
  const nodes = Array.from(document.querySelectorAll("button, [role=button]"));
  const node = nodes.find((item) => (item.textContent || "").includes(${JSON.stringify(text)}));
  if (!node) return false;
  node.click();
  return true;
})()
`;
  const result = await session.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true
  });
  if (!result.result?.value) {
    throw new Error(`Could not find clickable text: ${text}`);
  }
  await sleep(650);
}

async function waitForApp(session) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const result = await session.send("Runtime.evaluate", {
      expression: `Boolean(document.querySelector("#root")?.textContent?.trim())`,
      returnByValue: true
    });
    if (result.result?.value) {
      return;
    }
    await sleep(250);
  }
  throw new Error("Renderer did not render app content.");
}

async function screenshot(session, file) {
  const result = await session.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: true
  });
  fs.writeFileSync(file, Buffer.from(result.data, "base64"));
}

async function main() {
  if (!browserPath) {
    throw new Error("Browser path is required. Pass --browser or set BROWSER_PATH.");
  }
  fs.mkdirSync(outDir, { recursive: true });
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "kanojo-cdp-"));
  const browser = childProcess.spawn(
    browserPath,
    [
      "--headless=new",
      "--disable-gpu",
      "--disable-dev-shm-usage",
      `--remote-debugging-port=${remotePort}`,
      `--user-data-dir=${userDataDir}`,
      "about:blank"
    ],
    { stdio: "ignore" }
  );

  try {
    await waitForCdp();
    const session = await connectPage(baseUrl);
    await session.send("Page.enable");
    await session.send("Runtime.enable");
    await session.send("Emulation.setDeviceMetricsOverride", {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: 1,
      mobile: false
    });
    await waitForApp(session);
    await sleep(1500);

    const manifest = [];
    for (const shot of shots) {
      for (const text of shot.clicks) {
        await clickButtonText(session, text);
      }
      const file = path.join(outDir, `${shot.name}.png`);
      await screenshot(session, file);
      manifest.push({
        name: shot.name,
        label: shot.label,
        file,
        bytes: fs.statSync(file).size
      });
    }

    const manifestFile = path.join(outDir, "showcase-screenshots.json");
    fs.writeFileSync(manifestFile, JSON.stringify({ baseUrl, viewport, shots: manifest }, null, 2));
    console.log(JSON.stringify({ outDir, manifestFile, count: manifest.length }, null, 2));
  } finally {
    if (process.platform === "win32") {
      childProcess.spawnSync("taskkill.exe", ["/PID", String(browser.pid), "/T", "/F"], {
        stdio: "ignore"
      });
    } else {
      browser.kill();
    }
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
