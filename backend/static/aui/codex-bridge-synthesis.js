"use strict";

(function installCodexBridgeSynthesis(root) {
  const api = async (path, options = {}) => {
    let token = "";
    try { token = root.sessionStorage?.getItem("obus-access-token") || ""; } catch (_) {}
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (token) headers["X-OBus-Access"] = token;
    const response = await root.fetch(path, { ...options, headers });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body?.detail?.message || body?.detail || "Codex synthesis is unavailable.");
    return body;
  };

  const workerIds = () => Array.from(root.document.querySelectorAll("#codex-bridge-parallel-roster .hint"))
    .map((node) => node.textContent.split("·").map((part) => part.trim())[1])
    .filter((value, index, values) => value && values.indexOf(value) === index)
    .slice(0, 4);

  const report = (message) => {
    const output = root.document.querySelector("#codex-bridge-output");
    if (!output) return;
    output.textContent += `\n${message}`;
    output.scrollTop = output.scrollHeight;
  };

  root.addEventListener("DOMContentLoaded", () => {
    const parallel = root.document.querySelector("#codex-bridge-parallel");
    if (!parallel || root.document.querySelector("#codex-bridge-synthesize")) return;
    const button = root.document.createElement("button");
    button.id = "codex-bridge-synthesize";
    button.type = "button";
    button.className = "button";
    button.textContent = "Synthesize findings";
    button.title = "Starts a separate read-only synthesis from selected worker findings";
    parallel.insertAdjacentElement("afterend", button);
    const promote = root.document.createElement("button");
    promote.id = "codex-bridge-promote";
    promote.type = "button";
    promote.className = "button primary";
    promote.textContent = "Start reviewed task";
    promote.title = "Promotes the completed read-only synthesis into ordinary workspace work";
    promote.disabled = true;
    button.insertAdjacentElement("afterend", promote);
    const sync = () => {
      const cards = Array.from(root.document.querySelectorAll("#codex-bridge-parallel-roster .harness-task-card"));
      const active = cards.some((card) => /\b(starting|working|running|interrupting)\b/i.test(card.textContent || ""));
      const count = workerIds().length;
      button.disabled = count < 2 || active;
      button.title = active
        ? "Wait for the read-only workers to finish before synthesizing"
        : count < 2
          ? "Start at least two isolated read-only workers first"
          : "Starts a separate read-only synthesis from completed worker findings";
    };
    new root.MutationObserver(sync).observe(root.document.querySelector("#codex-bridge-parallel-roster"), { childList: true, subtree: true, characterData: true });
    sync();
    button.addEventListener("click", async () => {
      const ids = workerIds();
      if (ids.length < 2) {
        report("Synthesis needs at least two completed read-only workers.");
        return;
      }
      button.disabled = true;
      const original = button.textContent;
      button.textContent = "Synthesizing…";
      try {
        const model = root.document.querySelector("#codex-bridge-model")?.value.trim() || null;
        const result = await api("/api/codex-bridge/parallel/synthesize", {
          method: "POST",
          body: JSON.stringify({ worker_thread_ids: ids, model }),
        });
        promote.dataset.synthesisThread = result.thread?.id || "";
        promote.disabled = !promote.dataset.synthesisThread;
        report(`Read-only synthesis started from ${result.worker_count || ids.length} selected worker findings. Review it before explicitly starting any workspace changes.`);
      } catch (error) {
        report(`Synthesis not started: ${error?.message || "Codex synthesis failed."}`);
      } finally {
        button.disabled = false;
        button.textContent = original;
        sync();
      }
    });
    promote.addEventListener("click", async () => {
      const threadId = promote.dataset.synthesisThread;
      if (!threadId) return;
      promote.disabled = true;
      const original = promote.textContent;
      promote.textContent = "Starting reviewed task…";
      try {
        const model = root.document.querySelector("#codex-bridge-model")?.value.trim() || null;
        await api(`/api/codex-bridge/threads/${encodeURIComponent(threadId)}/promote`, {
          method: "POST",
          body: JSON.stringify({ model }),
        });
        report("Reviewed task started in the selected workspace. Network remains disabled; destructive and hardware-risk actions still require approval.");
        promote.dataset.synthesisThread = "";
      } catch (error) {
        report(`Reviewed task not started: ${error?.message || "The handoff was blocked."}`);
      } finally {
        promote.disabled = true;
        promote.textContent = original;
      }
    });
  });
})(window);
