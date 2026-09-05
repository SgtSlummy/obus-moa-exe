"use strict";

const { app, BrowserWindow, Menu, dialog, shell } = require("electron");
const http = require("http");
const { Tray, nativeImage } = require("electron");
const net = require("net");
const path = require("path");
const { spawn } = require("child_process");

const DEFAULT_OBUS_URL = "http://127.0.0.1:38173/";
const BACKEND_READY_TIMEOUT_MS = 20_000;
let mainWindow = null;
let tray = null;
let isQuitting = false;

app.on('second-instance', () => showMainWindow());
let ownedBackend = null;
let activeTarget = null;
let launchPromise = null;

function safeLoopbackUrl(value) {
  try {
    const parsed = new URL(value);
    const loopback = ["127.0.0.1", "localhost", "::1"].includes(parsed.hostname);
    return parsed.protocol === "http:" && loopback ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function obusUrl(value = process.env.OBUS_URL) {
  const requested = safeLoopbackUrl(value);
  if (value && !requested) console.warn("Ignoring unsafe OBUS_URL (not a loopback HTTP URL); starting OBus on its dedicated local endpoint.");
  return requested || DEFAULT_OBUS_URL;
}

function isLoopbackUrl(value) {
  return Boolean(safeLoopbackUrl(value));
}

function isSafeExternalUrl(value) {
  try {
    return new URL(value).protocol === "https:" || isLoopbackUrl(value);
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

async function backendSupportsDesktopRuntime(target) {
  return new Promise((resolve) => {
    const request = http.request(
      new URL("/api/providers/local-ollama/auto-aid", target),
      { method: "OPTIONS", timeout: 1500 },
      (response) => {
        response.resume();
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
    if (await backendHealthy(target) && await backendSupportsDesktopRuntime(target)) return target;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`OBus backend did not become ready: ${executable}`);
}

async function ensureBackend(target) {
  const requested = safeLoopbackUrl(process.env.OBUS_URL);
  if (requested) {
    if (!await backendHealthy(target) || !await backendSupportsDesktopRuntime(target)) {
      throw new Error(`OBUS_URL is unavailable or incompatible: ${target}`);
    }
    return target;
  }
  // The desktop owns a private backend, so a stale process on the default port
  // can never redirect the primary UI into a browser or an older runtime.
  return startBundledBackend(await reserveLoopbackTarget());
}

function stopOwnedBackend() {
  if (ownedBackend && !ownedBackend.killed) ownedBackend.kill();
  ownedBackend = null;
}

function dashboardUrl(route = "/") {
  return new URL(route, activeTarget || obusUrl()).toString();
}

async function showFirstTimeSetup() {
  const result = await dialog.showMessageBox(mainWindow ?? undefined, {
    type: "info",
    title: "First-time setup",
    message: "Get OBus ready in three steps",
    detail: "1. Open Settings and choose your workspace.\n2. Confirm a local model or provider is available.\n3. Start with a guided task or Flow Studio blueprint.\n\nYou can run self-diagnosis from File at any time.",
    buttons: ["Open Settings", "Close"],
    defaultId: 0,
    cancelId: 1,
  });
  if (result.response === 0) mainWindow?.loadURL(dashboardUrl("/?page=settings"));
}

async function runSelfDiagnosis() {
  const target = activeTarget || obusUrl();
  const ready = await backendHealthy(target) && await backendSupportsDesktopRuntime(target);
  const detail = ready
    ? "The local OBus desktop backend is ready. You can continue using OBus."
    : "OBus could not reach its dedicated local backend. Close duplicate OBus windows, reopen the OBus desktop shortcut, then run this check again. If it still fails, use First-time setup.";
  await dialog.showMessageBox(mainWindow ?? undefined, {
    type: ready ? "info" : "warning",
    title: "OBus self-diagnosis",
    message: ready ? "Everything looks ready." : "OBus needs attention.",
    detail,
    buttons: ["Close"],
  });
}

function installApplicationMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {
      label: "File",
      submenu: [
        { label: "First-time setup…", click: () => void showFirstTimeSetup() },
        { label: "Run self-diagnosis…", click: () => void runSelfDiagnosis() },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" }, { role: "redo" }, { type: "separator" },
        { role: "cut" }, { role: "copy" }, { role: "paste" }, { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" }, { role: "forceReload" }, { role: "toggleDevTools" }, { type: "separator" },
        { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" }, { type: "separator" }, { role: "togglefullscreen" },
      ],
    },
    { label: "Window", submenu: [{ role: "minimize" }, { role: "zoom" }, { role: "close" }] },
    { label: "Help", submenu: [{ label: "Open OBus home", click: () => mainWindow?.loadURL(activeTarget || obusUrl()) }] },
  ]));
}

function trayIcon() {
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#090c17"/><path d="M16 5c5.8 0 10.5 4.7 10.5 10.5S21.8 26 16 26 5.5 21.3 5.5 15.5 10.2 5 16 5Z" fill="#d9b35d"/><path d="M16 9v13M12 12.5h8M12 18h8" stroke="#090c17" stroke-width="2" stroke-linecap="round"/></svg>';
  return nativeImage.createFromDataURL(`data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}`);
}

function showMainWindow() {
  if (!mainWindow) {
    launchDesktop().catch((error) => console.error('Unable to restore OBus window:', error));
    return;
  }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function quitApplication() {
  isQuitting = true;
  app.quit();
}

function ensureTray() {
  if (tray) return;
  tray = new Tray(trayIcon());
  tray.setToolTip('OBus');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open OBus', click: showMainWindow },
    { type: 'separator' },
    { label: 'Quit OBus', click: quitApplication },
  ]));
  tray.on('click', showMainWindow);
}

function createWindow(target = activeTarget || obusUrl()) {
  ensureTray();
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1024,
    minHeight: 660,
    show: false,
    backgroundColor: "#090c17",
    title: "OBus",
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true },
  });
  mainWindow.once("ready-to-show", () => mainWindow?.show());
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow?.webContents.executeJavaScript(`
      (() => {
        if (document.getElementById('flow-studio-dialog')) return;
        const link = document.querySelector('a[href="/flow-studio"]');
        if (!link || link.dataset.electronFlowStudioBound) return;
        link.dataset.electronFlowStudioBound = 'true';
        link.addEventListener('click', (event) => {
          event.preventDefault();
          let dialog = document.getElementById('flow-studio-electron-dialog');
          if (!dialog) {
            dialog = document.createElement('dialog');
            dialog.id = 'flow-studio-electron-dialog';
            dialog.style.cssText = 'width:min(1440px,calc(100vw - 24px));height:min(920px,calc(100vh - 24px));max-width:none;max-height:none;margin:auto;padding:0;border:1px solid #3a4d72;border-radius:16px;background:#090c17;color:#f5f1e6;box-shadow:0 24px 80px rgba(0,0,0,.65)';
            dialog.innerHTML = '<header style="height:52px;display:flex;align-items:center;justify-content:space-between;padding:0 18px;border-bottom:1px solid #2b3855;background:#111827"><strong>Flow Studio</strong><button type="button">Back to command center</button></header><iframe title="Flow Studio editor" style="display:block;width:100%;height:calc(100% - 52px);border:0;background:#090c17"></iframe>';
            dialog.querySelector('button').addEventListener('click', () => dialog.close());
            dialog.querySelector('iframe').src = new URL('/flow-studio', window.location.origin).href;
            document.body.append(dialog);
          }
          dialog.showModal();
        });
      })();
    `).catch(() => {});
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isLoopbackUrl(url)) {
      mainWindow?.loadURL(url);
      return { action: "deny" };
    }
    if (isSafeExternalUrl(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!isLoopbackUrl(url)) event.preventDefault();
  });
  mainWindow.on('close', (event) => {
    if (isQuitting) return;
    event.preventDefault();
    mainWindow.hide();
  });
  mainWindow.loadURL(target);
  mainWindow.on("closed", () => { mainWindow = null; });
}

async function launchDesktop() {
  if (mainWindow) return;
  if (launchPromise) return launchPromise;
  launchPromise = (async () => {
    try {
      activeTarget = activeTarget || await ensureBackend(obusUrl());
      createWindow(activeTarget);
    } catch (error) {
      dialog.showErrorBox("OBus could not start", String(error.message || error));
      app.quit();
    } finally {
      launchPromise = null;
    }
  })();
  return launchPromise;
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return void launchDesktop();
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });
  app.whenReady().then(async () => {
    installApplicationMenu();
    await launchDesktop();
  });
  app.on("before-quit", stopOwnedBackend);
  app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
  app.on("activate", () => { if (mainWindow === null) void launchDesktop(); });
}

module.exports = {
  DEFAULT_OBUS_URL,
  backendHealthy,
  bundledBackendPath,
  isLoopbackUrl,
  isSafeExternalUrl,
  obusUrl,
  safeLoopbackUrl,
};
