"use strict";

(function installProjectSession(root) {
  const render = (session) => {
    const anchor = document.querySelector("#guided-project-access");
    if (!anchor) return;
    let summary = document.querySelector("#project-session-summary");
    if (!summary) {
      summary = document.createElement("span");
      summary.id = "project-session-summary";
      summary.className = "hint";
      anchor.insertAdjacentElement("afterend", summary);
    }
    const tasks = Array.isArray(session?.tasks) ? session.tasks : [];
    const review = tasks.filter((task) => ["failed", "interrupted"].includes(task?.state)).length;
    summary.textContent = session?.workspace
      ? ` · ${review ? `${review} task${review === 1 ? "" : "s"} to review · ` : ""}inspect-only session`
      : " · no project session";
    summary.title = session?.message || "No work is replayed automatically.";
  };

  const refresh = async () => {
    try {
      let accessToken = "";
      try { accessToken = root.sessionStorage?.getItem("obus-access-token") || ""; } catch (_) {}
      const headers = {Accept: "application/json"};
      if (accessToken) headers["X-OBus-Access"] = accessToken;
      const response = await root.fetch("/api/project-session", {headers});
      if (!response.ok) throw new Error("project session unavailable");
      render(await response.json());
    } catch (_) { render(null); }
  };

  root.addEventListener("DOMContentLoaded", () => {
    refresh();
    root.setInterval(refresh, 15_000);
  });
})(window);
