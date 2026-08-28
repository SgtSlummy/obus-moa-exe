"use strict";

const { app, BrowserWindow, dialog, shell } = require("electron");
const http = require("http");
const net = require("net");
const path = require("path");
const { spawn } = require("child_process");

const DEFAULT_OBUS_URL = "http://127.0.0.1:38173/";
const BACKEND_READY_TIMEOUT_MS = 20_000;
let mainWindow = null;
let ownedBackend = null;
let activeTarget = null;

function safeLoopbackUrl(value) {
  try {
    const parsed = new URL(value);
    const loopback = parsed.hostname === "127.0.0.1" || parsed.hostname === "localhost" || parsed.hostname === "::1";
    if (parsed.protocol !== "http:" || !loopback) return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

function latestStartupUrl(newerThan = 0) {
  const localAppData = process.env.LOCALAPPDATA;
  if (!localAppData) return null;
  try {
    const fs = require("node:fs");
    const path = require("node:path");
    const startupDir = path.join(localAppData, "OBus", "logs", "startup");
    const latest = fs.readdirSync(startupDir, {withFileTypes:true})
      .filter(entry => entry.isFile() && /^obus-startup-.*\.json$/i.test(entry.name))
      .map(entry => ({name:entry.name, modified:fs.statSync(path.join(startupDir, entry.name)).mtimeMs}))
      .sort((left, right) => right.modified - left.modified)[0];
    if (!latest || latest.modified < newerThan) return null;
    const receipt = JSON.parse(fs.readFileSync(path.join(startupDir, latest.name), "utf8"));
    const port = Number(receipt.app_port);
    return Number.isInteger(port) && port > 0 && port < 65536 ? safeLoopbackUrl(`http://127.0.0.1:${port}/`) : null;
  } catch (error) {
    console.warn("Unable to read the local OBus startup receipt:", error.message);
    return null;
  }
}

function obusUrl(value = process.env.OBUS_URL) {
  const requested = safeLoopbackUrl(value);
  if (value && !requested) console.warn("Ignoring unsafe OBUS_URL (not a loopback HTTP URL); using the local OBus endpoint.");
  return requested || latestStartupUrl() || DEFAULT_OBUS_URL;
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

function reserveLoopbackTarget() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      probe.close((error) => {
        if (error) return reject(error);
        resolve(`http://127.0.0.1:${address.port}/`);
      });
    });
  });
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
        resolve(response.statusCode !== 404);
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
  ownedBackend = spawn(executable, ["--headless"], {
    cwd: path.dirname(executable),
    env: { ...process.env, OBUS_PORT: port },
    windowsHide: true,
    stdio: "ignore",
  });
  const deadline = Date.now() + BACKEND_READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (await backendHealthy(target) && await backendSupportsCurrentDesktopRuntime(target)) return target;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`OBus backend did not become ready: ${executable}`);
}

async function ensureBackend(target) {
  if (process.env.OBUS_URL) {
    if (!await backendHealthy(target) || !await backendSupportsCurrentDesktopRuntime(target)) {
      throw new Error(`OBUS_URL is unavailable or incompatible: ${target}`);
    }
    return target;
  }
  // The packaged desktop owns a dedicated runtime. This prevents a legacy bridge
  // on the default port from becoming an accidental dependency of the UI.
  return startBundledBackend(await reserveLoopbackTarget());
}

function stopOwnedBackend() {
  if (ownedBackend && !ownedBackend.killed) ownedBackend.kill();
  ownedBackend = null;
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
  const retryWithFreshReceipt = () => {
    if (!mainWindow || Date.now() >= retryUntil) return;
    const freshTarget = latestStartupUrl(launchStartedAt);
    if (freshTarget && freshTarget !== target) {
      target = freshTarget;
      mainWindow.loadURL(target);
      return;
    }
    retryTimer = setTimeout(retryWithFreshReceipt, 500);
  };
  mainWindow.webContents.on("did-fail-load", (_event, _code, _description, url, isMainFrame) => {
    if (isMainFrame !== false && isLoopbackUrl(url)) retryWithFreshReceipt();
  });
  mainWindow.loadURL(target);
  mainWindow.on("closed", () => { if (retryTimer) clearTimeout(retryTimer); mainWindow = null; });
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
    let target = obusUrl();
  const launchStartedAt = Date.now();
  const retryUntil = launchStartedAt + 20_000;
  let retryTimer = null;
    try {
      activeTarget = await ensureBackend(target);
      createWindow(activeTarget);
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
