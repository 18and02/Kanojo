import { app, BrowserWindow, Notification, ipcMain, session } from "electron";
import { spawn } from "node:child_process";
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

ipcMain.handle("kanojo:restart-backend", async () => {
  const script = findProjectFile(path.join("scripts", "start_backend.ps1"));
  if (!script) {
    return { restarted: false, reason: "scripts/start_backend.ps1 not found" };
  }
  const result = await runPowerShellScript(script, [
    "-Restart",
    "-BindAddress",
    "0.0.0.0",
    "-Port",
    "8787"
  ]);
  return {
    restarted: result.exitCode === 0,
    exit_code: result.exitCode,
    stdout: result.stdout,
    stderr: result.stderr,
    reason: result.exitCode === 0 ? undefined : "backend restart failed"
  };
});

function findBackendEnvFile() {
  return findProjectFile(path.join("backend", ".env"), process.env.KANOJO_BACKEND_ENV_FILE);
}

function findProjectFile(relativePath: string, explicitPath?: string) {
  const candidates = [
    explicitPath,
    path.resolve(process.cwd(), relativePath),
    path.resolve(process.cwd(), "..", relativePath),
    path.resolve(app.getAppPath(), "..", relativePath),
    path.resolve(app.getAppPath(), "..", "..", relativePath),
    path.resolve(__dirname, "..", "..", "..", relativePath)
  ].filter((candidate): candidate is string => Boolean(candidate));
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? null;
}

function runPowerShellScript(script: string, args: string[]) {
  return new Promise<{ exitCode: number; stdout: string; stderr: string }>((resolve) => {
    const child = spawn(
      "powershell.exe",
      ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, ...args],
      {
        cwd: path.dirname(path.dirname(script)),
        windowsHide: true
      }
    );
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      resolve({ exitCode: 1, stdout, stderr: error.message });
    });
    child.on("close", (code) => {
      resolve({ exitCode: code ?? 1, stdout, stderr });
    });
  });
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
