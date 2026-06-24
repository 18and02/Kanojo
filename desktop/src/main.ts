import { app, BrowserWindow, Notification, ipcMain, session } from "electron";
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
