"use strict";

(function installObusAuiLayout(root) {
  const DEFAULT_SPLIT = 62;
  const MIN_SPLIT = 45;
  const MAX_SPLIT = 75;
  const PRESETS = {
    focus: {split: 62, density: "comfortable", sidebarCollapsed: false},
    review: {split: 55, density: "comfortable", sidebarCollapsed: false},
    deck: {split: 62, density: "compact", sidebarCollapsed: false},
    studio: {split: 50, density: "spacious", sidebarCollapsed: false},
  };
  const clamp = (value, minimum, maximum) => Math.min(maximum, Math.max(minimum, value));

  const OBusAuiLayout = {
    create({densitySelect, sidebarToggle, presetSelect, resetButton, runSplitter, runWorkbench, announce} = {}) {
      const storedSplit = Number(root.localStorage?.getItem("obus-aui-split-run"));
      if (!Number.isFinite(storedSplit) || storedSplit < MIN_SPLIT || storedSplit > MAX_SPLIT) {
        root.localStorage?.removeItem("obus-aui-split-run");
      }
      const storedPreset = root.localStorage?.getItem("obus-aui-preset");
      const prefs = {
        density: root.localStorage?.getItem("obus-aui-density") || "comfortable",
        sidebarCollapsed: root.localStorage?.getItem("obus-aui-sidebar") === "true",
        preset: PRESETS[storedPreset] ? storedPreset : "focus",
        runSplit: Number.isFinite(storedSplit) && storedSplit >= MIN_SPLIT && storedSplit <= MAX_SPLIT ? storedSplit : DEFAULT_SPLIT,
      };
      const notify = (message) => { if (typeof announce === "function") announce(message); };
      const setSplit = (value, {persist = true} = {}) => {
        prefs.runSplit = clamp(Number(value) || DEFAULT_SPLIT, MIN_SPLIT, MAX_SPLIT);
        const ratio = prefs.runSplit / (100 - prefs.runSplit);
        runWorkbench?.style.setProperty("--run-primary-fr", ratio.toFixed(4));
        runWorkbench?.style.setProperty("--run-secondary-fr", "1");
        runSplitter?.setAttribute("aria-valuenow", String(Math.round(prefs.runSplit)));
        if (persist) root.localStorage?.setItem("obus-aui-split-run", String(prefs.runSplit));
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
          root.localStorage?.setItem("obus-aui-preset", prefs.preset);
          root.localStorage?.setItem("obus-aui-density", prefs.density);
          root.localStorage?.setItem("obus-aui-sidebar", String(prefs.sidebarCollapsed));
        }
        apply();
        if (emit && root.CustomEvent) root.dispatchEvent(new root.CustomEvent("obus-layout-preset", {detail: {preset: prefs.preset}}));
        notify(`Layout preset set to ${prefs.preset}`);
      };
      const bindResizablePane = () => {
        if (!runSplitter || !runWorkbench) return;
        let dragging = false;
        const updateFromPointer = (event) => {
          if (!dragging) return;
          const bounds = runWorkbench.getBoundingClientRect();
          if (!bounds.width) return;
          setSplit(((event.clientX - bounds.left) / bounds.width) * 100);
        };
        runSplitter.addEventListener("pointerdown", (event) => {
          if (event.button !== 0) return;
          dragging = true;
          runSplitter.setPointerCapture?.(event.pointerId);
          updateFromPointer(event);
        });
        runSplitter.addEventListener("pointermove", updateFromPointer);
        const stopDragging = (event) => {
          if (!dragging) return;
          dragging = false;
          runSplitter.releasePointerCapture?.(event.pointerId);
          notify(`Run workbench split set to ${Math.round(prefs.runSplit)} percent`);
        };
        runSplitter.addEventListener("pointerup", stopDragging);
        runSplitter.addEventListener("pointercancel", stopDragging);
        runSplitter.addEventListener("keydown", (event) => {
          const step = event.shiftKey ? 5 : 1;
          let next = null;
          if (event.key === "ArrowLeft") next = prefs.runSplit - step;
          else if (event.key === "ArrowRight") next = prefs.runSplit + step;
          else if (event.key === "Home") next = DEFAULT_SPLIT;
          else if (event.key === "End") next = MAX_SPLIT;
          if (next === null) return;
          event.preventDefault();
          setSplit(next);
          notify(`Run workbench split set to ${Math.round(prefs.runSplit)} percent`);
        });
      };
      densitySelect?.addEventListener("change", (event) => {
        prefs.density = event.target.value;
        root.localStorage?.setItem("obus-aui-density", prefs.density);
        apply();
        notify(`Density set to ${prefs.density}`);
      });
      sidebarToggle?.addEventListener("click", () => {
        prefs.sidebarCollapsed = !prefs.sidebarCollapsed;
        root.localStorage?.setItem("obus-aui-sidebar", String(prefs.sidebarCollapsed));
        apply();
        notify(prefs.sidebarCollapsed ? "Sidebar collapsed" : "Sidebar expanded");
      });
      presetSelect?.addEventListener("change", (event) => applyPreset(event.target.value));
      resetButton?.addEventListener("click", () => {
        for (const key of ["obus-aui-split-run", "obus-aui-preset", "obus-aui-density", "obus-aui-sidebar"]) {
          root.localStorage?.removeItem(key);
        }
        prefs.density = "comfortable";
        prefs.sidebarCollapsed = false;
        prefs.preset = "focus";
        prefs.runSplit = DEFAULT_SPLIT;
        apply();
        notify("Workspace layout reset");
      });
      bindResizablePane();
      apply();
      updateViewport(root.document.documentElement.clientWidth);
      let observer = null;
      if (root.ResizeObserver) {
        observer = new root.ResizeObserver((entries) => updateViewport(entries[0]?.contentRect?.width || root.document.documentElement.clientWidth));
        observer.observe(root.document.documentElement);
      } else {
        root.addEventListener("resize", () => updateViewport(root.document.documentElement.clientWidth));
      }
      return {apply, applyPreset, bindResizablePane, setSplit, updateViewport, observer};
    },
  };
  root.OBusAuiLayout = OBusAuiLayout;
})(window);
