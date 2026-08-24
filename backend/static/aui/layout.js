"use strict";

(function installObusAuiLayout(root) {
  const OBusAuiLayout = {
    create({densitySelect, sidebarToggle, announce} = {}) {
      const prefs = {
        density: root.localStorage?.getItem("obus-aui-density") || "comfortable",
        sidebarCollapsed: root.localStorage?.getItem("obus-aui-sidebar") === "true",
      };
      const apply = () => {
        const density = ["compact", "comfortable", "spacious"].includes(prefs.density) ? prefs.density : "comfortable";
        root.document.body.dataset.density = density;
        root.document.body.dataset.sidebarCollapsed = String(Boolean(prefs.sidebarCollapsed));
        if (densitySelect) densitySelect.value = density;
        if (sidebarToggle) {
          sidebarToggle.setAttribute("aria-pressed", String(Boolean(prefs.sidebarCollapsed)));
          sidebarToggle.textContent = prefs.sidebarCollapsed ? "▣" : "☰";
        }
      };
      const updateViewport = (width) => {
        root.document.body.dataset.viewportMode = width < 720 ? "phone" : width < 960 ? "narrow" : width < 1280 ? "medium" : width < 1600 ? "wide" : "ultrawide";
      };
      const notify = (message) => { if (typeof announce === "function") announce(message); };
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
      apply();
      updateViewport(root.document.documentElement.clientWidth);
      let observer = null;
      if (root.ResizeObserver) {
        observer = new root.ResizeObserver((entries) => updateViewport(entries[0]?.contentRect?.width || root.document.documentElement.clientWidth));
        observer.observe(root.document.documentElement);
      } else {
        root.addEventListener("resize", () => updateViewport(root.document.documentElement.clientWidth));
      }
      return {apply, updateViewport, observer};
    },
  };
  root.OBusAuiLayout = OBusAuiLayout;
})(window);
