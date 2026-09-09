"use strict";

const { app, BrowserWindow, dialog, shell } = require("electron");
const http = require("http");
const path = require("path");
const { spawn } = require("child_process");

const DEFAULT_OBUS_URL = "http://127.0.0.1:38173/";
const BACKEND_READY_TIMEOUT_MS = 20_000;
let mainWindow = null;
let activeTarget = null;

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
      let body = "";
      response.on("data", (chunk) => { body += chunk; if (body.length > 8192) request.destroy(); });
      response.on("end", () => {
        try { const state = JSON.parse(body); resolve(response.statusCode === 200 && state.service === "obus-moa" && state.status === "ok"); }
        catch { resolve(false); }
      });
    });
    request.on("error", () => resolve(false));
    request.on("timeout", () => { request.destroy(); resolve(false); });
  });
}

function bundledBackendPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, "backend", "OBus.exe")
    : path.resolve(__dirname, path.basename(__dirname) === "electron_app" ? ".." : ".", "dist", "OBus.exe");
}

async function backendSupportsCurrentDesktopRuntime(target) {
  return new Promise((resolve) => {
    const request = http.request(
      new URL("/api/providers/local-ollama/auto-aid", target),
      { method: "OPTIONS", timeout: 1_500 },
      (response) => {
        response.resume();
        // A registered FastAPI route responds to OPTIONS/405; a missing legacy
        // route responds 404. Do not silently bind the desktop shell to v97.
        resolve(response.statusCode === 405 || response.statusCode === 200 || response.statusCode === 204);
      },
    );
    request.once("timeout", () => request.destroy());
    request.once("error", () => resolve(false));
    request.end();
  });
}

async function startBundledBackend(target) {
  const executable = bundledBackendPath();
  const port = new URL(target).port;
  const sourceLauncher = process.env.OBUS_LAUNCHER;
  const command = sourceLauncher && process.env.OBUS_PYTHON ? process.env.OBUS_PYTHON : executable;
  const args = sourceLauncher && process.env.OBUS_PYTHON ? [sourceLauncher, "--headless"] : ["--headless"];
  let spawnError = null;
  const backend = spawn(command, args, {
    cwd: path.dirname(executable),
    env: { ...process.env, OBUS_PORT: port, OBUS_HOST: "127.0.0.1" },
    windowsHide: true,
    detached: true,
    stdio: "ignore",
  });
  backend.on("error", (error) => { spawnError = error; });
  backend.unref();
  const deadline = Date.now() + BACKEND_READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (await backendHealthy(target) && await backendSupportsCurrentDesktopRuntime(target)) return target;
    if (spawnError) throw spawnError;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`OBus backend did not become ready: ${executable}`);
}

async function ensureBackend(target) {
  if (await backendHealthy(target)) {
    if (await backendSupportsCurrentDesktopRuntime(target)) return target;
    throw new Error(`Update the shared OBus backend at ${target}; it is incompatible with this desktop.`);
  }
  if (target !== DEFAULT_OBUS_URL) {
    throw new Error(`OBUS_URL is unavailable: ${target}`);
  }
  return startBundledBackend(target);
}

function createWindow(target = activeTarget || obusUrl()) {
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
      activeTarget = await ensureBackend(target);
      createWindow(activeTarget);
    } catch (error) {
      dialog.showErrorBox("OBus could not start", String(error.message || error));
      app.quit();
    }
  });
  app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
  app.on("activate", () => { if (mainWindow === null) createWindow(); });
}

module.exports = { DEFAULT_OBUS_URL, isLoopbackUrl, obusUrl, ensureBackend, backendHealthy };
