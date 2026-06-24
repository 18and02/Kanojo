import { app, BrowserWindow, Notification, ipcMain, session } from "electron";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

app.setAppUserModelId("AI Memory Card");

ipcMain.handle(
  "kanojo:notify",
  (_event, payload: { title?: string; body?: string }) => {
    if (!Notification.isSupported()) {
      return { delivered: false, reason: "notifications unsupported" };
    }
    const notification = new Notification({
      title: payload.title || "AI Memory Card",
      body: payload.body || ""
    });
    notification.show();
    return { delivered: true };
  }
);

ipcMain.handle(
  "kanojo:apply-peer-config",
  (_event, payload: { peerBaseUrl?: string }) => {
    const peerBaseUrl = payload.peerBaseUrl?.trim();
    if (!peerBaseUrl) {
      return { applied: false, reason: "peerBaseUrl is required" };
    }
    try {
      const url = new URL(peerBaseUrl);
      if (!["http:", "https:"].includes(url.protocol)) {
        return { applied: false, reason: "peerBaseUrl must use http or https" };
      }
    } catch {
      return { applied: false, reason: "peerBaseUrl is not a valid URL" };
    }

    const envFile = findBackendEnvFile();
    if (!envFile) {
      return {
        applied: false,
        reason: "backend/.env not found",
        value: peerBaseUrl
      };
    }
    const result = writeEnvValue(envFile, "KANOJO_PEER_BASE_URL", peerBaseUrl);
    return {
      applied: true,
      key: "KANOJO_PEER_BASE_URL",
      value: peerBaseUrl,
      env_file: envFile,
      backup_file: result.backupFile
    };
  }
);

function findBackendEnvFile() {
  const candidates = [
    process.env.KANOJO_BACKEND_ENV_FILE,
    path.resolve(process.cwd(), "backend", ".env"),
    path.resolve(process.cwd(), "..", "backend", ".env"),
    path.resolve(app.getAppPath(), "..", "backend", ".env"),
    path.resolve(app.getAppPath(), "..", "..", "backend", ".env"),
    path.resolve(__dirname, "..", "..", "..", "backend", ".env")
  ].filter((candidate): candidate is string => Boolean(candidate));
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? null;
}

function writeEnvValue(envFile: string, key: string, value: string) {
  const content = fs.readFileSync(envFile, "utf8");
  const eol = content.includes("\r\n") ? "\r\n" : "\n";
  const backupFile = `${envFile}.bak-${timestampForFilename()}`;
  fs.copyFileSync(envFile, backupFile);

  const body = content.replace(/\r?\n$/, "");
  const lines = body ? body.split(/\r?\n/) : [];
  let replaced = false;
  const nextLines = lines.map((line) => {
    if (line.startsWith(`${key}=`)) {
      replaced = true;
      return `${key}=${value}`;
    }
    return line;
  });
  if (!replaced) {
    nextLines.push(`${key}=${value}`);
  }
  fs.writeFileSync(envFile, `${nextLines.join(eol)}${eol}`, "utf8");
  return { backupFile };
}

function timestampForFilename() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\..+$/, "Z");
}

const createWindow = () => {
  const window = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 860,
    minHeight: 620,
    title: "AI Memory Card",
    webPreferences: {
      preload: path.join(__dirname, "../preload/preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      backgroundThrottling: false
    }
  });

  if (process.env.ELECTRON_RENDERER_URL) {
    window.loadURL(process.env.ELECTRON_RENDERER_URL);
  } else {
    window.loadFile(path.join(__dirname, "../renderer/index.html"));
  }
};

app.whenReady().then(() => {
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback, details) => {
    if (permission === "media") {
      const mediaDetails = details as { mediaTypes?: string[] };
      callback(mediaDetails.mediaTypes?.includes("audio") ?? true);
      return;
    }
    callback(false);
  });
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
