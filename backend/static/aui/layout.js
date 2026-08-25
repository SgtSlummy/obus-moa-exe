"use strict";

(function installObusAuiLayout(root) {
  const DEFAULT_SPLIT = 61.803398875;
  const MIN_SPLIT = 45;
  const MAX_SPLIT = 75;
  const PRESETS = {
    focus: {split: 61.803398875, density: "comfortable", sidebarCollapsed: false},
    review: {split: 55, density: "comfortable", sidebarCollapsed: false},
    deck: {split: 62, density: "compact", sidebarCollapsed: false},
    studio: {split: 50, density: "spacious", sidebarCollapsed: false},
  };
  const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));
  const createSafeStorage = () => {
    let storage = null;
    try { storage = root.localStorage; } catch { storage = null; }
    return {
      getItem(key) { try { return storage?.getItem(key) ?? null; } catch { return null; } },
      setItem(key, value) { try { storage?.setItem(key, value); } catch {} },
      removeItem(key) { try { storage?.removeItem(key); } catch {} },
    };
  };

  const OBusAuiLayout = {
    create({densitySelect, sidebarToggle, presetSelect, resetButton, runSplitter, runWorkbench, mobileDrawers = [], announce} = {}) {
      const safeStorage = createSafeStorage();
      const cleanup = [];
      let splitterBound = false;
      let observer = null;
      const listen = (target, type, handler) => {
        if (!target) return;
        target.addEventListener(type, handler);
        cleanup.push(() => target.removeEventListener(type, handler));
      };
      const storedSplit = Number(safeStorage.getItem("obus-aui-split-run"));
      if (!Number.isFinite(storedSplit) || storedSplit < MIN_SPLIT || storedSplit > MAX_SPLIT) {
        safeStorage.removeItem("obus-aui-split-run");
      }
      const storedPreset = safeStorage.getItem("obus-aui-preset");
      const prefs = {
        density: safeStorage.getItem("obus-aui-density") || "comfortable",
        sidebarCollapsed: safeStorage.getItem("obus-aui-sidebar") === "true",
        preset: PRESETS[storedPreset] ? storedPreset : "focus",
        runSplit: Number.isFinite(storedSplit) && storedSplit >= MIN_SPLIT && storedSplit <= MAX_SPLIT ? storedSplit : DEFAULT_SPLIT,
      };
      const notify = (message) => { if (typeof announce === "function") announce(message); };
      const setSplit = (value, {persist = true} = {}) => {
        prefs.runSplit = clamp(Number(value) || DEFAULT_SPLIT, MIN_SPLIT, MAX_SPLIT);
        const ratio = prefs.runSplit / (100 - prefs.runSplit);
        runWorkbench?.style.setProperty("--run-primary-fr", `${ratio.toFixed(4)}fr`);
        runWorkbench?.style.setProperty("--run-secondary-fr", "1fr");
        runSplitter?.setAttribute("aria-valuenow", String(Math.round(prefs.runSplit)));
        if (persist) safeStorage.setItem("obus-aui-split-run", String(prefs.runSplit));
      };
      const apply = () => {
        const density = ["compact", "comfortable", "spacious"].includes(prefs.density) ? prefs.density : "comfortable";
        root.document.body.dataset.density = density;
        root.document.body.dataset.sidebarCollapsed = String(Boolean(prefs.sidebarCollapsed));
        root.document.body.dataset.layoutPreset = prefs.preset;
        if (densitySelect) densitySelect.value = density;
        if (presetSelect) presetSelect.value = prefs.preset;
        if (sidebarToggle) {
          sidebarToggle.setAttribute("aria-pressed", String(Boolean(prefs.sidebarCollapsed)));
          sidebarToggle.textContent = prefs.sidebarCollapsed ? "▣" : "☰";
        }
        setSplit(prefs.runSplit, {persist: false});
      };
      const mobileMedia = root.matchMedia?.("(max-width: 720px)") || null;
      const syncMobileDrawers = () => mobileDrawers.filter(Boolean).forEach((drawer) => { drawer.open = !mobileMedia?.matches; });
      const updateViewport = (width) => {
        root.document.body.dataset.viewportMode = width < 720 ? "phone" : width < 960 ? "narrow" : width < 1280 ? "medium" : width < 1600 ? "wide" : "ultrawide";
      };
      const applyPreset = (name, {persist = true, emit = true} = {}) => {
        const preset = PRESETS[name] || PRESETS.focus;
        prefs.preset = PRESETS[name] ? name : "focus";
        prefs.density = preset.density;
        prefs.sidebarCollapsed = preset.sidebarCollapsed;
        setSplit(preset.split, {persist});
        if (persist) {
          safeStorage.setItem("obus-aui-preset", prefs.preset);
          safeStorage.setItem("obus-aui-density", prefs.density);
          safeStorage.setItem("obus-aui-sidebar", String(prefs.sidebarCollapsed));
        }
        apply();
        if (emit && root.CustomEvent) root.dispatchEvent(new root.CustomEvent("obus-layout-preset", {detail: {preset: prefs.preset}}));
        notify(`Layout preset set to ${prefs.preset}`);
      };
      const bindResizablePane = () => {
        if (!runSplitter || !runWorkbench || splitterBound) return;
        splitterBound = true;
        let dragging = false;
        const updateFromPointer = (event) => {
          if (!dragging) return;
          const bounds = runWorkbench.getBoundingClientRect();
          if (!bounds.width) return;
          setSplit(((event.clientX - bounds.left) / bounds.width) * 100);
        };
        const pointerDown = (event) => {
          if (event.button !== 0) return;
          dragging = true;
          runSplitter.setPointerCapture?.(event.pointerId);
          updateFromPointer(event);
        };
        const stopDragging = (event) => {
          if (!dragging) return;
          dragging = false;
          runSplitter.releasePointerCapture?.(event.pointerId);
          notify(`Run workbench split set to ${Math.round(prefs.runSplit)} percent`);
        };
        const keyDown = (event) => {
          const step = event.shiftKey ? 5 : 1;
          let next = null;
          if (event.key === "ArrowLeft") next = prefs.runSplit - step;
          else if (event.key === "ArrowRight") next = prefs.runSplit + step;
          else if (event.key === "Home") next = MIN_SPLIT;
          else if (event.key === "End") next = MAX_SPLIT;
          if (next === null) return;
          event.preventDefault();
          setSplit(next);
          notify(`Run workbench split set to ${Math.round(prefs.runSplit)} percent`);
        };
        listen(runSplitter, "pointerdown", pointerDown);
        listen(runSplitter, "pointermove", updateFromPointer);
        listen(runSplitter, "pointerup", stopDragging);
        listen(runSplitter, "pointercancel", stopDragging);
        listen(runSplitter, "lostpointercapture", stopDragging);
        listen(runSplitter, "keydown", keyDown);
      };
      listen(densitySelect, "change", (event) => {
        prefs.density = event.target.value;
        safeStorage.setItem("obus-aui-density", prefs.density);
        apply();
        notify(`Density set to ${prefs.density}`);
      });
      listen(sidebarToggle, "click", () => {
        prefs.sidebarCollapsed = !prefs.sidebarCollapsed;
        safeStorage.setItem("obus-aui-sidebar", String(prefs.sidebarCollapsed));
        apply();
        notify(prefs.sidebarCollapsed ? "Sidebar collapsed" : "Sidebar expanded");
      });
      listen(presetSelect, "change", (event) => applyPreset(event.target.value));
      listen(resetButton, "click", () => {
        for (const key of ["obus-aui-split-run", "obus-aui-preset", "obus-aui-density", "obus-aui-sidebar"]) {
          safeStorage.removeItem(key);
        }
        prefs.density = "comfortable";
        prefs.sidebarCollapsed = false;
        prefs.preset = "focus";
        prefs.runSplit = DEFAULT_SPLIT;
        apply();
        notify("Workspace layout reset");
      });
      bindResizablePane();
      syncMobileDrawers();
      listen(mobileMedia, "change", syncMobileDrawers);
      apply();
      updateViewport(root.document.documentElement.clientWidth);
      if (root.ResizeObserver) {
        observer = new root.ResizeObserver((entries) => updateViewport(entries[0]?.contentRect?.width || root.document.documentElement.clientWidth));
        observer.observe(root.document.documentElement);
      } else {
        listen(root, "resize", () => updateViewport(root.document.documentElement.clientWidth));
      }
      const destroy = () => {
        observer?.disconnect?.();
        observer = null;
        cleanup.splice(0).forEach((remove) => remove());
        splitterBound = false;
      };
      return {apply, applyPreset, bindResizablePane, destroy, setSplit, syncMobileDrawers, updateViewport, observer};
    },
  };
  root.OBusAuiLayout = OBusAuiLayout;
})(window);
