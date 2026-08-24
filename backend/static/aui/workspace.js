"use strict";

(function installObusWorkspace(root) {
  const OBusWorkspace = {
    create({api, state, $, $$, escapeHtml, persist, toast} = {}) {
      const renderTree = (tree) => {
        const element = $("#workspace-tree");
        const needle = String(state.workspaceFilter || "").trim().toLowerCase();
        const entries = (tree?.entries || []).filter((item) => !needle || String(item.path || "").toLowerCase().includes(needle));
        if (!entries.length) {
          element.innerHTML = `<div class="empty">${needle ? "No safe files match this filter." : "No safe files found under this root."}</div>`;
          return;
        }
        element.innerHTML = entries.map((item) => item.kind === "directory"
          ? `<div class="row"><div><strong>▸ ${escapeHtml(item.path)}</strong><p>directory</p></div></div>`
          : `<button class="row workspace-file-entry" data-workspace-path="${escapeHtml(item.path)}" style="width:100%;text-align:left"><div><strong>▹ ${escapeHtml(item.path)}</strong><p>${Number(item.size || 0).toLocaleString()} bytes</p></div><span class="badge">read-only</span></button>`
        ).join("");
        $$(".workspace-file-entry").forEach((button) => {
          button.onclick = () => selectFile(button.dataset.workspacePath);
        });
      };
      const load = async () => {
        const status = await api("/api/workspace/status");
        state.workspaceStatus = status;
        $("#workspace-status").textContent = status.valid ? "Ready · read-only" : "Not configured";
        $("#workspace-status").className = `badge ${status.valid ? "ready" : "warn"}`;
        $("#workspace-root").value = status.root || "";
        if (!status.valid) {
          $("#workspace-tree").innerHTML = `<div class="empty">${escapeHtml(status.reason || "Choose a local workspace root to inspect files.")}</div>`;
          return status;
        }
        const tree = await api("/api/workspace/tree");
        state.workspaceTree = tree;
        renderTree(tree);
        return status;
      };
      const selectFile = async (path) => {
        try {
          const value = await api(`/api/workspace/file?path=${encodeURIComponent(path)}`);
          state.workspaceFile = value;
          $("#workspace-file-title").textContent = value.path;
          $("#workspace-file").textContent = value.binary ? "Binary file · content withheld" : (value.content || "");
          $("#workspace-use-context").disabled = Boolean(value.binary) || !value.content;
          $("#workspace-file").dataset.workspacePath = value.path;
        } catch (error) {
          toast(error.message, true);
        }
      };
      const saveRoot = async () => {
        const rootPath = $("#workspace-root").value.trim();
        try {
          await persist({workspace_root: rootPath || null});
          await load();
          toast(rootPath ? "Workspace root configured" : "Workspace root cleared");
        } catch (error) {
          toast(error.message, true);
        }
      };
      const useContext = () => {
        const value = state.workspaceFile;
        if (!value?.content) return toast("Select a text file first", true);
        const input = $("#route-input");
        const context = `\n\n[Local workspace context: ${value.path}]\n${value.content.slice(0, 12000)}\n[/Local workspace context]`;
        input.value = `${input.value}${context}`.trim();
        input.dispatchEvent(new Event("input"));
        input.focus();
        toast("Bounded file context added to the next route");
      };
      return {load, renderTree, selectFile, saveRoot, useContext};
    },
  };
  root.OBusWorkspace = OBusWorkspace;
})(window);
