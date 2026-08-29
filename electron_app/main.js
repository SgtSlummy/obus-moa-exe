"use strict";

const { app, BrowserWindow, shell } = require("electron");

const DEFAULT_OBUS_URL = "http://127.0.0.1:38173/";
let mainWindow = null;

function obusUrl(value = process.env.OBUS_URL) {
  if (!value) return DEFAULT_OBUS_URL;
  try {
    const parsed = new URL(value);
    const loopback = parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost" || parsed.hostname === "::1";
    if (parsed.protocol !== "http:" || !loopback) throw new Error("not a loopback HTTP URL");
    return parsed.toString();
  } catch {
    console.warn("Ignoring unsafe OBUS_URL; using the local OBus endpoint.");
    return DEFAULT_OBUS_URL;
  }
}

function isLoopbackUrl(value) {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" && ["127.0.0.1", "localhost", "::1"].includes(parsed.hostname);
  } catch {
    return false;
  }
}

function createWindow() {
  const target = obusUrl();
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1024,
    minHeight: 660,
    show: false,
    backgroundColor: "#090c17",
    title: "OBus",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  mainWindow.once("ready-to-show", () => mainWindow?.show());
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!isLoopbackUrl(url)) event.preventDefault();
  });
  mainWindow.loadURL(target);
  mainWindow.on("closed", () => { mainWindow = null; });
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return createWindow();
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });
  app.whenReady().then(createWindow);
  app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
  app.on("activate", () => { if (mainWindow === null) createWindow(); });
}

module.exports = { DEFAULT_OBUS_URL, isLoopbackUrl, obusUrl };
