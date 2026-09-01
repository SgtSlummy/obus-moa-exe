---
name: desktop-electron-wrapper
description: > 
  Minimal Electron wrapper for OBus, no browser needed.


tags:
  - electron
  - node
  - python
  - obus
---

## Purpose

Provide a tiny Electron app that (1) launches the OBus `uvicorn` backend and (2) opens the web UI in a native window, eliminating the need to manually open a browser.

## What is installed

* `electron_app/package.json` – npm meta, declares Electron as a dependency.
* `electron_app/main.js` – Electron entry point that loads `http://127.0.0.1:8000`.
* `electron_app/start‑obus‑desktop.bat` – Windows helper that starts the backend and opens Electron.

## Usage

1. Copy the `electron_app` directory into your repo.
2. `cd electron_app && npm install`.
3. Run `start‑obus‑desktop.bat`.

The OBus UI will appear in a desktop window.

## Reference files

* `references/usage-guide.md` – detailed usage scenarios and tips.
* `references/desktop-launch-cmd.md` – quick batch launch for Windows.

## Optional extensions

* Modify `main.js` to change window size.
* Change port in the bat and `main.js` if you run on a custom port.

## Troubleshooting

* If the window is blank, verify the backend is listening on port 8000.
* Ensure `node` and `npm` are in PATH.
