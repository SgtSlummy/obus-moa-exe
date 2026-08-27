"use strict";

const { app, BrowserWindow, dialog, shell } = require("electron");
const http = require("http");
const path = require("path");
const { spawn } = require("child_process");

const DEFAULT_OBUS_URL = "http://127.0.0.1:38173/";
const BACKEND_READY_TIMEOUT_MS = 20_000;
let mainWindow = null;
let ownedBackend = null;

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

function healthUrl(target) {
  return new URL("/health", target).toString();
}

function backendHealthy(target) {
  return new Promise((resolve) => {
    const request = http.get(healthUrl(target), { timeout: 1500 }, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.on("error", () => resolve(false));
    request.on("timeout", () => { request.destroy(); resolve(false); });
  });
}

function bundledBackendPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend", "OBus.exe")
    : path.resolve(__dirname, "..", "dist", "OBus.exe");
}

async function ensureBackend(target) {
  if (await backendHealthy(target)) return;
  if (process.env.OBUS_URL) {
    throw new Error(`OBUS_URL is unavailable: ${target}`);
  }
  const executable = bundledBackendPath();
  ownedBackend = spawn(executable, ["--headless"], { windowsHide: true, stdio: "ignore" });
  const deadline = Date.now() + BACKEND_READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (await backendHealthy(target)) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`OBus backend did not become ready: ${executable}`);
}

function stopOwnedBackend() {
  if (ownedBackend && !ownedBackend.killed) ownedBackend.kill();
  ownedBackend = null;
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
  app.whenReady().then(async () => {
    const target = obusUrl();
    try {
      await ensureBackend(target);
      createWindow();
    } catch (error) {
      dialog.showErrorBox("OBus could not start", String(error.message || error));
      app.quit();
    }
  });
  app.on("before-quit", stopOwnedBackend);
  app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
  app.on("activate", () => { if (mainWindow === null) createWindow(); });
}

module.exports = { DEFAULT_OBUS_URL, isLoopbackUrl, obusUrl };
