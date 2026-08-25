import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const SOURCE = readFileSync(new URL("../backend/static/aui/layout.js", import.meta.url), "utf8");

class FakeTarget {
  constructor() {
    this.listeners = new Map();
    this.attributes = new Map();
    this.style = {setProperty() {}};
    this.value = "";
    this.textContent = "";
  }
  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(handler);
  }
  removeEventListener(type, handler) { this.listeners.get(type)?.delete(handler); }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getBoundingClientRect() { return {left: 0, width: 1000}; }
  listenerCount(type) { return this.listeners.get(type)?.size || 0; }
  setPointerCapture() {}
  releasePointerCapture() {}
}

function loadLayout({throwingStorage = false} = {}) {
  const storageValues = new Map();
  const storage = {
    getItem(key) { return storageValues.get(key) ?? null; },
    setItem(key, value) { storageValues.set(key, String(value)); },
    removeItem(key) { storageValues.delete(key); },
  };
  const observers = [];
  class FakeResizeObserver {
    constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
    observe() {}
    disconnect() { this.disconnected = true; }
  }
  const root = new FakeTarget();
  Object.defineProperty(root, "localStorage", {
    get() {
      if (throwingStorage) throw new DOMException("denied", "SecurityError");
      return storage;
    },
  });
  root.document = {
    body: {dataset: {}},
    documentElement: {clientWidth: 1440},
  };
  root.ResizeObserver = FakeResizeObserver;
  root.CustomEvent = class { constructor(type, options) { this.type = type; this.detail = options?.detail; } };
  vm.runInNewContext(SOURCE, {window: root, DOMException});
  return {root, observers};
}

test("layout creation survives unavailable localStorage", () => {
  const {root} = loadLayout({throwingStorage: true});
  assert.doesNotThrow(() => root.OBusAuiLayout.create());
  assert.equal(root.document.body.dataset.density, "comfortable");
});

test("splitter binding is idempotent and destroy removes listeners", () => {
  const {root, observers} = loadLayout();
  const splitter = new FakeTarget();
  const workbench = new FakeTarget();
  const controller = root.OBusAuiLayout.create({runSplitter: splitter, runWorkbench: workbench});
  assert.equal(splitter.listenerCount("pointerdown"), 1);
  controller.bindResizablePane();
  assert.equal(splitter.listenerCount("pointerdown"), 1);
  controller.destroy();
  for (const type of ["pointerdown", "pointermove", "pointerup", "pointercancel", "keydown"]) {
    assert.equal(splitter.listenerCount(type), 0);
  }
  assert.equal(observers[0].disconnected, true);
});

test("auxiliary pane splitters bind once and share teardown", () => {
  const {root} = loadLayout();
  const splitter = new FakeTarget();
  const container = new FakeTarget();
  const controller = root.OBusAuiLayout.create({
    resizablePanes: [{key: "rooms", label: "Rooms", splitter, container}],
  });
  assert.equal(splitter.listenerCount("pointerdown"), 1);
  assert.equal(splitter.attributes.get("aria-valuenow"), "62");
  controller.destroy();
  assert.equal(splitter.listenerCount("pointerdown"), 0);
});
