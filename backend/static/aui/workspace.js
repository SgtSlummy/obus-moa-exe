"use strict";

(function installObusWorkspace(root) {
  const OBusWorkspace = {
    create({api, state, $, $$, escapeHtml, persist, toast} = {}) {
      const preview = () => $("#workspace-file");
      const editor = () => $("#workspace-editor");
      const changeReview = () => $("#workspace-change-review");
      const changeList = () => $("#workspace-change-list");
      const resetDraft = () => {
        state.workspaceDraft = null;
        preview().hidden = false;
        editor().hidden = true;
        editor().value = "";
        $("#workspace-edit").hidden = false;
        $("#workspace-save").hidden = true;
        $("#workspace-discard").hidden = true;
        $("#workspace-save").disabled = true;
        $("#workspace-discard").disabled = true;
        $("#workspace-risk-approval").hidden = true;
        $("#workspace-major-risk-approved").checked = false;
      };
      const updateEditorAvailability = (file) => {
        const editable = Boolean(file?.editable && file?.sha256 && file?.editor_content !== null && file?.editor_content !== undefined);
        $("#workspace-edit").disabled = !editable;
        $("#workspace-edit-hint").textContent = editable
          ? "Open a local draft, then explicitly save it. OBus checks for on-disk conflicts before writing."
          : (file?.binary ? "Binary files cannot be edited here." : "Editing is disabled for truncated or secret-like file content.");
      };
      const refreshNativePicker = async () => {
        const button = $("#workspace-root-picker");
        if (!button) return null;
        try {
          const capabilities = await api("/api/desktop/capabilities");
          const picker = capabilities?.native_workspace_picker || {};
          state.nativeWorkspacePicker = picker;
          button.hidden = !picker.available;
          button.disabled = !picker.available;
          button.title = picker.reason || "Choose a local workspace folder";
          return picker;
        } catch (_error) {
          button.hidden = true;
          return null;
        }
      };
      const workspaceLabel = (root) => {
        const compact = String(root || "").replace(/[\\/]+$/, "");
        return compact.split(/[\\/]/).pop() || compact || "Local project";
      };
      const renderRecentWorkspaces = (items) => {
        const panel = $("#workspace-recents");
        const list = $("#workspace-recent-list");
        if (!panel || !list) return;
        const entries = Array.isArray(items) ? items : [];
        panel.hidden = !entries.length;
        list.innerHTML = entries.map((item) => {
          const root = String(item?.root || "");
          return `<div class="workspace-recent-entry"><button class="workspace-recent-open" type="button" data-recent-workspace="${escapeHtml(root)}" title="Reopen ${escapeHtml(root)}"><strong>${escapeHtml(workspaceLabel(root))}</strong><small>${escapeHtml(root)}</small></button><button class="workspace-recent-remove" type="button" data-forget-workspace="${escapeHtml(root)}" aria-label="Forget ${escapeHtml(workspaceLabel(root))}" title="Forget this local history entry">×</button></div>`;
        }).join("");
        $$('[data-recent-workspace]').forEach((button) => {
          button.onclick = () => selectRecentWorkspace(button.dataset.recentWorkspace);
        });
        $$('[data-forget-workspace]').forEach((button) => {
          button.onclick = () => forgetRecentWorkspace(button.dataset.forgetWorkspace);
        });
      };
      const loadRecentWorkspaces = async () => {
        try {
          const recent = await api("/api/workspace/recent");
          state.recentWorkspaces = Array.isArray(recent?.items) ? recent.items : [];
          renderRecentWorkspaces(state.recentWorkspaces);
          return state.recentWorkspaces;
        } catch (_error) {
          state.recentWorkspaces = [];
          renderRecentWorkspaces([]);
          return [];
        }
      };
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
      const renderChanges = (value) => {
        const panel = changeReview();
        const list = changeList();
        if (!panel || !list) return;
        panel.hidden = false;
        const summary = $("#workspace-change-summary");
        if (!value?.available) {
          summary.textContent = "Unavailable";
          list.innerHTML = `<div class="empty">${escapeHtml(value?.reason || "A local Git change review is not available for this workspace.")}</div>`;
          return;
        }
        const counts = Object.entries(value.counts || {}).map(([kind, count]) => `${count} ${kind}`).join(" · ");
        summary.textContent = `${counts || "clean"}${value.truncated ? " · list truncated" : ""}${value.skipped ? ` · ${value.skipped} protected path${value.skipped === 1 ? "" : "s"} omitted` : ""}`;
        const changes = value.changes || [];
        list.innerHTML = changes.length ? changes.map((change) => `<div class="row workspace-change"><div><h4>${escapeHtml(change.path)} <span class="badge ${change.status === "modified" ? "warn" : change.status === "deleted" ? "risk" : "ready"}">${escapeHtml(change.status)}</span></h4><p class="hint">${change.previous_path ? `renamed from ${escapeHtml(change.previous_path)}` : change.reviewable ? "Select to inspect the bounded local diff." : "Deleted files cannot be opened from the current workspace."}</p></div><div class="row-actions"><button class="button mini workspace-change-inspect" data-workspace-change="${escapeHtml(change.path)}" data-workspace-change-reviewable="${change.reviewable ? "true" : "false"}">${change.reviewable ? "Inspect diff" : "Why unavailable"}</button></div></div>`).join("") : "<div class=\"empty\">No safe local Git changes were found.</div>";
        $$(".workspace-change-inspect").forEach((button) => {
          button.onclick = () => inspectWorkspaceChange(button.dataset.workspaceChange, button.dataset.workspaceChangeReviewable === "true");
        });
      };
      const load = async () => {
        await Promise.all([refreshNativePicker(), loadRecentWorkspaces()]);
        const status = await api("/api/workspace/status");
        state.workspaceStatus = status;
        $("#workspace-status").textContent = status.valid ? "Ready · read-only" : "Not configured";
        $("#workspace-status").className = `badge ${status.valid ? "ready" : "warn"}`;
        $("#workspace-root").value = status.root || "";
        if (!status.valid) {
          $("#workspace-tree").innerHTML = `<div class="empty">${escapeHtml(status.reason || "Choose a local workspace root to inspect files.")}</div>`;
          $("#workspace-review-all").disabled = true;
          changeReview().hidden = true;
          return status;
        }
        $("#workspace-review-all").disabled = false;
        const tree = await api("/api/workspace/tree");
        state.workspaceTree = tree;
        renderTree(tree);
        return status;
      };
      const loadWorkspaceChanges = async () => {
        try {
          const value = await api("/api/workspace/changes");
          state.workspaceChanges = value;
          renderChanges(value);
          return value;
        } catch (error) {
          state.workspaceChanges = {available: false, reason: error.message, changes: []};
          renderChanges(state.workspaceChanges);
          throw error;
        }
      };
      const selectFile = async (path) => {
        try {
          const value = await api(`/api/workspace/file?path=${encodeURIComponent(path)}`);
          state.workspaceFile = value;
          state.workspaceDiff = null;
          resetDraft();
          $("#workspace-file-title").textContent = value.path;
          preview().textContent = value.binary ? "Binary file · content withheld" : (value.content || "");
          $("#workspace-use-context").disabled = Boolean(value.binary) || !value.content;
          $("#workspace-show-diff").disabled = Boolean(value.binary) || !value.content;
          $("#workspace-show-diff").textContent = "Review changes";
          preview().dataset.workspacePath = value.path;
          updateEditorAvailability(value);
        } catch (error) {
          toast(error.message, true);
        }
      };
      const showDiff = async () => {
        const file = state.workspaceFile;
        if (!file?.path || file.binary) return toast("Select a text file first", true);
        try {
          const value = await api(`/api/workspace/diff?path=${encodeURIComponent(file.path)}`);
          state.workspaceDiff = value;
          resetDraft();
          $("#workspace-file-title").textContent = `${value.path} · local Git review`;
          preview().textContent = value.diff_available
            ? (value.diff || value.reason || "No changes against HEAD.")
            : (value.reason || "A local Git diff is not available for this file.");
          $("#workspace-show-diff").textContent = value.diff_available && value.changed ? "Changes shown" : "Review changes";
          preview().dataset.workspacePath = value.path;
          updateEditorAvailability(file);
        } catch (error) {
          toast(error.message, true);
        }
      };
      const inspectWorkspaceChange = async (path, reviewable) => {
        if (!reviewable) {
          resetDraft();
          $("#workspace-file-title").textContent = `${path} · workspace change`;
          preview().textContent = "This file was deleted from the workspace, so there is no current file to open. Its path remains listed for review.";
          return;
        }
        await selectFile(path);
        await showDiff();
      };
      const editDraft = () => {
        const file = state.workspaceFile;
        if (!file?.editable || !file?.sha256 || file?.editor_content === null || file?.editor_content === undefined) return toast("This selected file cannot be safely edited here", true);
        state.workspaceDraft = {path: file.path, expected_sha256: file.sha256};
        preview().hidden = true;
        editor().hidden = false;
        editor().value = file.editor_content;
        $("#workspace-file-title").textContent = `${file.path} · local draft`;
        $("#workspace-edit").hidden = true;
        $("#workspace-save").hidden = false;
        $("#workspace-discard").hidden = false;
        $("#workspace-save").disabled = false;
        $("#workspace-discard").disabled = false;
        $("#workspace-risk-approval").hidden = false;
        $("#workspace-edit-hint").textContent = "Saving writes only this file after a conflict and safety check. Nothing is sent outside this computer.";
        editor().focus();
      };
      const discardDraft = () => {
        const file = state.workspaceFile;
        resetDraft();
        if (file) {
          $("#workspace-file-title").textContent = file.path;
          preview().textContent = file.binary ? "Binary file · content withheld" : (file.content || "");
          updateEditorAvailability(file);
        }
      };
      const saveDraft = async () => {
        const draft = state.workspaceDraft;
        if (!draft) return toast("Open a local draft first", true);
        try {
          const result = await api("/api/workspace/file", {
            method: "PUT",
            body: JSON.stringify({
              path: draft.path,
              content: editor().value,
              expected_sha256: draft.expected_sha256,
              major_risk_approved: $("#workspace-major-risk-approved").checked,
            }),
          });
          await selectFile(result.path);
          toast(result.changed ? "Local file draft saved" : "No local file changes to save");
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
      const pickRoot = async () => {
        const button = $("#workspace-root-picker");
        if (!button || button.disabled) return;
        button.disabled = true;
        button.textContent = "Opening…";
        try {
          const result = await api("/api/desktop/select-workspace", {method: "POST"});
          if (!result.selected) {
            toast("Folder selection cancelled");
            return;
          }
          await refresh();
          await load();
          toast("Workspace root configured from the native folder picker");
        } finally {
          button.textContent = "Choose folder…";
          button.disabled = false;
        }
      };
      const selectRecentWorkspace = async (rootPath) => {
        if (!rootPath) return;
        const result = await api("/api/workspace/recent/select", {method: "POST", body: JSON.stringify({root: rootPath})});
        if (!result.selected) return;
        await refresh();
        await load();
        toast("Recent workspace reopened after local validation");
      };
      const forgetRecentWorkspace = async (rootPath) => {
        if (!rootPath) return;
        const result = await api("/api/workspace/recent", {method: "DELETE", body: JSON.stringify({root: rootPath})});
        state.recentWorkspaces = Array.isArray(result?.items) ? result.items : [];
        renderRecentWorkspaces(state.recentWorkspaces);
        if (result.removed) toast("Recent workspace removed from local history");
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
      return {load, renderTree, renderChanges, loadWorkspaceChanges, selectFile, showDiff, inspectWorkspaceChange, editDraft, discardDraft, saveDraft, saveRoot, pickRoot, selectRecentWorkspace, forgetRecentWorkspace, useContext};
    },
  };
  root.OBusWorkspace = OBusWorkspace;
})(window);
