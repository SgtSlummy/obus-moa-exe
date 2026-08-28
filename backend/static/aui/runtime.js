"use strict";

(function installObusRuntime(root) {
  const OBusRuntime = {
    create({api, state, $, $$, escapeHtml, toast, quantumPollInterval, loadRooms, loadThreads} = {}) {
      const cardName = (id) => state.dashboard?.cards.find((card) => card.id === id)?.name || id;
      const schedulerTime = (value) => {
        const timestamp = Number(value || 0);
        if (!Number.isFinite(timestamp) || timestamp <= 0) return "not scheduled";
        return new Date(timestamp * 1000).toLocaleString();
      };
      const scheduleWorkspace = () => state.workspaceStatus?.valid ? state.workspaceStatus.root : null;
      const renderApprovalStatus = () => {
        const status = $("#harness-task-approval-status");
        if (!status) return;
        const approval = (state.harnessApprovals || []).find((item) => item.id === state.selectedHarnessApprovalId);
        if (!approval) {
          status.textContent = "Major-risk objectives create a local, one-time approval request. Nothing starts until you approve it.";
          return;
        }
        const label = String(approval.status || "pending");
        status.textContent = label === "approved"
          ? `Approved once · ${approval.id} · Run guarded task only for this exact request.`
          : label === "pending"
            ? `Pending local decision · ${approval.id} · Review the queue below before approval.`
            : `${label} · ${approval.id} · Create a new request if the task changes.`;
      };
      const retainedDraftMatchesApproval = (approvalId) => {
        const draft = state.pendingHarnessApprovalDraft;
        if (!draft?.applied || !draft.objective || draft.approval_id !== approvalId || state.selectedHarnessApprovalId !== approvalId) return false;
        return $("#harness-task-objective")?.value.trim() === draft.objective
          && scheduleWorkspace() === draft.workspace
          && $("#harness-task-provider")?.value === draft.provider
          && Number($("#harness-task-attempts")?.value) === draft.max_attempts
          && Number($("#harness-task-priority")?.value) === draft.priority;
      };
      const renderApprovals = () => {
        const list = $("#harness-approval-list");
        if (!list) return;
        const approvals = state.harnessApprovals || [];
        const pending = approvals.filter((item) => item.status === "pending").length;
        $("#harness-approval-count").textContent = `${pending} pending`;
        if (state.harnessApprovalsError) {
          list.innerHTML = `<div class="empty">Local approval queue is unavailable: ${escapeHtml(state.harnessApprovalsError)}</div>`;
          renderApprovalStatus();
          return;
        }
        list.innerHTML = approvals.length ? approvals.map((approval) => {
          const selected = approval.id === state.selectedHarnessApprovalId;
          const status = String(approval.status || "pending");
          const risks = Array.isArray(approval.risks) ? approval.risks.join(" · ") : "major risk";
          const canResume = status === "pending" && retainedDraftMatchesApproval(approval.id);
          const canDecide = status === "pending" && !state.approvalDecisionBusy;
          return `<article class="row harness-approval-card ${selected ? "selected" : ""}"><div><h4>${escapeHtml(status)} <span class="badge ${status === "approved" ? "ready" : status === "pending" ? "warn" : "risk"}">${escapeHtml(approval.id)}</span></h4><p class="context">${escapeHtml(approval.objective_preview || "Redacted objective")}</p><p class="hint">${escapeHtml(risks)} · ${escapeHtml(approval.provider || "provider")} · ${escapeHtml(approval.workspace || "workspace")}</p><p class="hint">${escapeHtml(String(approval.requested_at || "").replace("T", " ").replace(/\..*$/, "Z"))}${approval.task_id ? ` · task ${escapeHtml(approval.task_id)}` : ""}</p></div><div class="row-actions"><button class="button mini harness-approval-select" data-harness-approval="${escapeHtml(approval.id)}">${selected ? "Selected" : "Select"}</button><button class="button mini harness-approval-approve" data-harness-approval="${escapeHtml(approval.id)}" ${canDecide ? "" : "disabled"} title="${canResume ? "Approve and start this exact retained task" : "Approve this one-time local request"}">${canResume ? "Approve & start" : "Approve once"}</button><button class="button mini danger harness-approval-reject" data-harness-approval="${escapeHtml(approval.id)}" ${canDecide ? "" : "disabled"}>Reject</button></div></article>`;
        }).join("") : "<div class=\"empty\">No major-risk approvals are awaiting a local decision.</div>";
        $$(".harness-approval-select").forEach((button) => { button.onclick = () => { state.selectedHarnessApprovalId = button.dataset.harnessApproval; renderApprovals(); }; });
        $$(".harness-approval-approve").forEach((button) => { button.onclick = () => decideApproval(button.dataset.harnessApproval, "approve"); });
        $$(".harness-approval-reject").forEach((button) => { button.onclick = () => decideApproval(button.dataset.harnessApproval, "reject"); });
        renderApprovalStatus();
      };
      const loadApprovals = async () => {
        try {
          const output = await api("/api/harness/approvals?limit=50");
          state.harnessApprovals = output.approvals || [];
          state.harnessApprovalsError = null;
        } catch (error) {
          state.harnessApprovals = [];
          state.harnessApprovalsError = error.message;
        }
        renderApprovals();
        return state.harnessApprovals;
      };
      const decideApproval = async (approvalId, decision) => {
        if (!approvalId || state.approvalDecisionBusy) return;
        state.approvalDecisionBusy = true;
        renderApprovals();
        try {
          const approval = await api(`/api/harness/approvals/${encodeURIComponent(approvalId)}/${decision}`, {method: "POST", body: JSON.stringify({})});
          state.selectedHarnessApprovalId = approval.id;
          await loadApprovals();
          if (decision === "approve" && retainedDraftMatchesApproval(approval.id)) {
            toast("Local one-time approval recorded. Starting the exact guarded task…");
            await launchTask();
            return;
          }
          toast(decision === "approve" ? "Local one-time approval recorded. Run the exact guarded task when ready." : "Local approval request rejected. No task was started.");
        } catch (error) { toast(error.message, true); }
        finally {
          state.approvalDecisionBusy = false;
          renderApprovals();
        }
      };
      const stageMajorRiskApproval = async ({objective, detail} = {}) => {
        const approvalId = detail?.approval_id;
        if (!approvalId) return null;
        const configuration = detail?.approval || {};
        state.selectedHarnessApprovalId = approvalId;
        state.pendingHarnessApprovalDraft = {
          approval_id: approvalId, objective: String(objective || ""), workspace: configuration.workspace || null, provider: configuration.provider || null,
          max_attempts: Number(configuration.max_attempts || 3), priority: Number(configuration.priority || 50),
          applied: false,
        };
        await loadApprovals();
        return {approval_required: true, approval_id: approvalId};
      };
      const renderSchedules = () => {
        const list = $("#autonomy-job-list");
        if (!list) return;
        const providers = (state.autonomyProviders || []).filter((provider) => provider.available);
        const providerSelect = $("#autonomy-job-provider");
        const currentProvider = providerSelect.value || "codex";
        providerSelect.innerHTML = providers.length ? providers.map((provider) => `<option value="${escapeHtml(provider.id)}">${escapeHtml(provider.id)}${provider.models?.length ? ` · ${escapeHtml(provider.models[0])}` : ""}</option>`).join("") : '<option value="codex">Codex</option>';
        providerSelect.value = providers.some((provider) => provider.id === currentProvider) ? currentProvider : providerSelect.options[0]?.value || "codex";
        const workspace = scheduleWorkspace();
        $("#autonomy-job-workspace").textContent = workspace || "Choose a workspace root first";
        $("#autonomy-job-workspace").title = workspace || "";
        $("#autonomy-job-create").disabled = !workspace;
        const jobs = state.autonomyJobs || [];
        $("#autonomy-job-count").textContent = `${jobs.filter((job) => job.enabled).length} scheduled`;
        if (state.autonomyJobsError) {
          list.innerHTML = `<div class="empty">Autonomous jobs are unavailable: ${escapeHtml(state.autonomyJobsError)}</div>`;
          return;
        }
        list.innerHTML = jobs.length ? jobs.map((job) => `<div class="row autonomous-job-card"><div><h4>${escapeHtml(job.name)} <span class="badge ${job.enabled ? "ready" : "warn"}">${job.enabled ? "scheduled" : "paused"}</span></h4><p>${escapeHtml(job.provider)} · every ${Math.max(1, Math.round(Number(job.interval_seconds || 0) / 60))} min · next ${escapeHtml(schedulerTime(job.next_run_at))}</p><p class="context">${escapeHtml(job.objective)}</p><p class="hint">Workspace: ${escapeHtml(job.workspace)}${job.last_task_id ? ` · last task ${escapeHtml(job.last_task_id)}` : ""}</p>${job.last_error ? `<p class="risk-high">${escapeHtml(job.last_error)}</p>` : ""}</div><div class="row-actions"><button class="button mini autonomy-job-toggle" data-autonomy-job="${escapeHtml(job.id)}">${job.enabled ? "Pause" : "Resume"}</button><button class="button mini danger autonomy-job-delete" data-autonomy-job="${escapeHtml(job.id)}">Delete</button></div></div>`).join("") : "<div class=\"empty\">No scheduled jobs yet. Schedule an ordinary, local workspace objective to run it every 30 minutes.</div>";
        $$(".autonomy-job-toggle").forEach((button) => { button.onclick = () => scheduleAction(button.dataset.autonomyJob, "toggle"); });
        $$(".autonomy-job-delete").forEach((button) => { button.onclick = () => scheduleAction(button.dataset.autonomyJob, "delete"); });
      };
      const loadSchedules = async () => {
        try {
          const [scheduleData, providerData] = await Promise.all([api("/api/harness/objectives"), api("/api/harness/providers")]);
          state.autonomyJobs = scheduleData.objectives || [];
          state.autonomyProviders = providerData.providers || [];
          state.autonomyJobsError = null;
        } catch (error) {
          state.autonomyJobs = [];
          state.autonomyJobsError = error.message;
        }
        renderSchedules();
        return state.autonomyJobs;
      };
      const createSchedule = async () => {
        const objective = $("#autonomy-job-objective").value.trim();
        const workspace = scheduleWorkspace();
        if (!workspace) return toast("Choose a workspace root before scheduling autonomous work", true);
        if (!objective) return toast("Enter an ordinary workspace objective", true);
        const intervalMinutes = Math.round(Number($("#autonomy-job-interval").value));
        if (!Number.isFinite(intervalMinutes) || intervalMinutes < 5 || intervalMinutes > 525600) return toast("Choose an interval from 5 minutes to one year", true);
        const button = $("#autonomy-job-create");
        button.disabled = true;
        try {
          await api("/api/harness/objectives", {method: "POST", body: JSON.stringify({name: $("#autonomy-job-name").value.trim() || objective.slice(0, 80), objective, workspace, interval_seconds: intervalMinutes * 60, provider: $("#autonomy-job-provider").value, enabled: true})});
          $("#autonomy-job-name").value = "";
          $("#autonomy-job-objective").value = "";
          await loadSchedules();
          toast(`Local job scheduled every ${intervalMinutes} minutes`);
        } catch (error) { toast(error.message, true); } finally { button.disabled = !scheduleWorkspace(); }
      };
      const scheduleAction = async (jobId, actionName) => {
        const job = (state.autonomyJobs || []).find((item) => item.id === jobId);
        if (!job) return toast("Scheduled job is no longer available", true);
        try {
          if (actionName === "delete") await api(`/api/harness/objectives/${encodeURIComponent(jobId)}`, {method: "DELETE"});
          else await api(`/api/harness/objectives/${encodeURIComponent(jobId)}`, {method: "PATCH", body: JSON.stringify({enabled: !job.enabled})});
          await loadSchedules();
          toast(actionName === "delete" ? "Scheduled job deleted" : job.enabled ? "Scheduled job paused" : "Scheduled job resumed");
        } catch (error) { toast(error.message, true); }
      };
      const taskIsActive = (task) => !["succeeded", "failed", "cancelled", "interrupted"].includes(task.state);
      const taskTime = (value) => value ? String(value).replace("T", " ").replace(/\..*$/, "Z") : "not started";
      const stopTaskEventStream = () => {
        if (state.harnessTaskEventStream) state.harnessTaskEventStream.close();
        state.harnessTaskEventStream = null;
        state.harnessTaskStreamTaskId = null;
      };
      const taskEventSummary = (event) => {
        const payload = event.payload || {};
        if (event.event_type === "task.state") return `State changed to ${payload.state || "unknown"}.`;
        if (event.event_type === "task.interrupted") return "OBus stopped before completion; explicit review is required before any resume.";
        if (event.event_type === "task.resume_requested" || event.event_type === "task.resumed") return "Explicit safe resume requested; OBus will inspect before continuing.";
        if (event.event_type === "checkpoint.created") return `Workspace checkpoint created · ${payload.files ?? 0} files protected.`;
        if (event.event_type === "workspace.verified") return `Workspace verification ${payload.status || "recorded"}.`;
        if (event.event_type === "workflow.stage") return `Workflow · ${payload.stage || "stage"} · ${payload.status || "recorded"}.`;
        if (event.event_type === "provider.started") return `${payload.provider || "Provider"} started${payload.model ? ` · ${payload.model}` : ""}.`;
        if (event.event_type === "provider.tool") return `${payload.provider || "Provider"} ${payload.status || "used"} ${payload.tool || "a workspace tool"}.`;
        if (event.event_type === "provider.verification") return `Verification ${payload.status || "recorded"}.`;
        if (event.event_type === "task.completed") return "Task completed; final result is available above.";
        return JSON.stringify(payload).slice(0, 900) || "Activity recorded.";
      };
      const renderTaskTimeline = () => {
        const list = $("#harness-task-timeline");
        const status = $("#harness-task-timeline-status");
        if (!list || !status) return;
        const events = state.harnessTaskEvents || [];
        if (!state.selectedHarnessTask) {
          status.textContent = "Select an active task to follow its redacted activity live.";
          list.innerHTML = '<div class="empty">Task events will appear here as the selected task works.</div>';
          return;
        }
        status.textContent = state.harnessTaskEventStream ? "Live local task feed · polling remains available as a fallback." : "Saved task activity · refresh remains available.";
        list.innerHTML = events.length ? events.slice(-40).reverse().map((event) => `<div class="row harness-task-event"><div><h4>${escapeHtml(event.event_type || "activity")}</h4><p class="hint">${escapeHtml(taskTime(event.created_at))}</p><p>${escapeHtml(taskEventSummary(event))}</p></div></div>`).join("") : '<div class="empty">No redacted task events have been recorded yet.</div>';
      };
      const startTaskEventStream = (taskId, after = 0) => {
        stopTaskEventStream();
        if (!root.EventSource || !taskId) return;
        const source = new EventSource(`/api/harness/tasks/${encodeURIComponent(taskId)}/events/stream?after=${Math.max(0, after)}`);
        state.harnessTaskEventStream = source;
        state.harnessTaskStreamTaskId = taskId;
        const receive = (message) => {
          if (state.selectedHarnessTask !== taskId) return stopTaskEventStream();
          try {
            const event = JSON.parse(message.data || "{}");
            const events = state.harnessTaskEvents || [];
            if (!events.some((item) => item.sequence === event.sequence)) state.harnessTaskEvents = [...events, event].slice(-40);
            renderTaskTimeline();
            api(`/api/harness/tasks/${encodeURIComponent(taskId)}`).then((task) => {
              if (state.selectedHarnessTask !== taskId) return;
              $("#harness-task-detail-title").textContent = `Task ${String(task.id || "").slice(0, 12)} · ${task.state}`;
              const outcome = task.error ? `Error\n${task.error}` : task.result ? `Result\n${task.result}` : "No final result yet.";
              $("#harness-task-detail").textContent = outcome;
              if (!taskIsActive(task)) stopTaskEventStream();
              loadTasks().catch(() => {});
            }).catch(() => {});
          } catch (_) {}
        };
        ["task.created", "task.state", "task.interrupted", "task.resume_requested", "task.resumed", "checkpoint.created", "workspace.verified", "workflow.stage", "provider.started", "provider.tool", "provider.verification", "task.completed", "repair.required", "action.started", "action.finished", "lesson.promoted", "approval.consumed"].forEach((kind) => source.addEventListener(kind, receive));
        source.onerror = () => { if (source.readyState === EventSource.CLOSED && state.harnessTaskEventStream === source) { stopTaskEventStream(); renderTaskTimeline(); } };
        renderTaskTimeline();
      };
      const populateTaskProviders = () => {
        const select = $("#harness-task-provider");
        if (!select) return;
        const providers = (state.autonomyProviders || []).filter((provider) => provider.available);
        const current = select.value || "codex";
        select.innerHTML = providers.length ? providers.map((provider) => `<option value="${escapeHtml(provider.id)}">${escapeHtml(provider.id)}${provider.models?.length ? ` · ${escapeHtml(provider.models[0])}` : ""}</option>`).join("") : '<option value="codex">Codex</option>';
        select.value = providers.some((provider) => provider.id === current) ? current : select.options[0]?.value || "codex";
      };
      const renderTasks = () => {
        const list = $("#harness-task-list");
        if (!list) return;
        populateTaskProviders();
        const workspace = scheduleWorkspace();
        $("#harness-task-workspace").textContent = workspace || "Choose a workspace root first";
        $("#harness-task-workspace").title = workspace || "";
        $("#harness-task-submit").disabled = !workspace;
        const pendingDraft = state.pendingHarnessApprovalDraft;
        if (pendingDraft && !pendingDraft.applied) {
          $("#harness-task-objective").value = pendingDraft.objective;
          const provider = $("#harness-task-provider");
          if (pendingDraft.provider && [...provider.options].some((option) => option.value === pendingDraft.provider)) provider.value = pendingDraft.provider;
          $("#harness-task-attempts").value = String(Math.max(1, Math.min(10, pendingDraft.max_attempts || 3)));
          $("#harness-task-priority").value = String(Math.max(0, Math.min(100, pendingDraft.priority || 50)));
          state.pendingHarnessApprovalDraft = {...pendingDraft, applied: true};
        }
        const quickButton = $("#harness-task-quick");
        const readyProviders = (state.autonomyProviders || []).filter((provider) => provider.available);
        if (quickButton) quickButton.disabled = !workspace || !readyProviders.length;
        const quickSummary = $("#harness-task-quick-summary");
        if (quickSummary) quickSummary.textContent = workspace
          ? `Quick Start uses this workspace, ${readyProviders[0]?.id || "the best ready provider"}, three repair attempts, and normal priority. Major-risk work always needs the explicit path below.`
          : "Choose a workspace to enable Quick Start. Major-risk work always needs explicit local approval.";
        const tasks = state.harnessTasks || [];
        $("#harness-task-count").textContent = `${tasks.length} task${tasks.length === 1 ? "" : "s"}`;
        if (state.harnessTasksError) {
          list.innerHTML = `<div class="empty">Task queue is unavailable: ${escapeHtml(state.harnessTasksError)}</div>`;
          return;
        }
        list.innerHTML = tasks.length ? tasks.map((task) => `<div class="row harness-task-card"><div><h4>${escapeHtml(task.state)} <span class="badge ${task.state === "succeeded" ? "ready" : taskIsActive(task) ? "warn" : "risk"}">${escapeHtml(task.provider || "codex")}</span></h4><p>${escapeHtml(task.source || "local")} · attempt ${escapeHtml(task.attempt || 0)}/${escapeHtml(task.max_attempts || 1)} · ${escapeHtml(taskTime(task.updated_at))}</p><p class="context">${escapeHtml(task.objective)}</p><p class="hint">Workspace: ${escapeHtml(task.workspace || "")}</p>${task.state === "interrupted" ? "<p class=\"hint\">Inspect the checkpoint and history before choosing the explicit safe resume.</p>" : ""}${task.error ? `<p class="risk-high">${escapeHtml(task.error)}</p>` : ""}</div><div class="row-actions"><button class="button mini harness-task-inspect" data-harness-task="${escapeHtml(task.id)}">Inspect</button><button class="button mini harness-task-resume" data-harness-task="${escapeHtml(task.id)}" ${task.state === "interrupted" ? "" : "disabled"}>Resume safely</button><button class="button mini danger harness-task-cancel" data-harness-task="${escapeHtml(task.id)}" ${taskIsActive(task) ? "" : "disabled"}>Cancel</button></div></div>`).join("") : "<div class=\"empty\">No autonomous tasks yet. Configure a workspace root, then start a focused task.</div>";
        $$(".harness-task-inspect").forEach((button) => { button.onclick = () => inspectTask(button.dataset.harnessTask); });
        $$(".harness-task-cancel").forEach((button) => { button.onclick = () => cancelTask(button.dataset.harnessTask); });
        $$(".harness-task-resume").forEach((button) => { button.onclick = () => resumeTask(button.dataset.harnessTask); });
        renderApprovalStatus();
        clearTimeout(state.harnessTaskPolling);
        if (tasks.some(taskIsActive)) state.harnessTaskPolling = setTimeout(() => loadTasks().catch((error) => toast(error.message, true)), quantumPollInterval());
      };
      const loadTasks = async () => {
        try {
          const output = await api("/api/harness/tasks?limit=50");
          state.harnessTasks = output.tasks || [];
          state.harnessTasksError = null;
        } catch (error) {
          state.harnessTasks = [];
          state.harnessTasksError = error.message;
        }
        renderTasks();
        return state.harnessTasks;
      };
      const renderTaskChanges = () => {
        const list = $("#harness-task-change-list");
        if (!list) return;
        const summary = $("#harness-task-change-summary");
        const changes = state.harnessTaskChanges;
        if (!changes?.task_id) {
          summary.textContent = "Select a task to inspect the checkpoint-bound workspace changes.";
          list.innerHTML = "<div class=\"empty\">Change review is read-only and becomes available after a task creates its checkpoint.</div>";
          return;
        }
        if (!changes.checkpoint) {
          summary.textContent = changes.reason || "This task has not created a checkpoint yet.";
          list.innerHTML = `<div class="empty">${escapeHtml(changes.reason || "No checkpoint is available yet.")}</div>`;
          return;
        }
        const counts = Object.entries(changes.counts || {}).map(([kind, count]) => `${count} ${kind}`).join(" · ");
        summary.textContent = `${changes.checkpoint.status} checkpoint · ${counts || "no safe changes"}${changes.truncated ? " · list truncated" : ""}`;
        const files = changes.changes || [];
        list.innerHTML = files.length ? files.map((change) => `<div class="row harness-task-change"><div><h4>${escapeHtml(change.path)} <span class="badge ${change.status === "modified" ? "warn" : change.status === "added" ? "ready" : "risk"}">${escapeHtml(change.status)}</span></h4><p class="hint">${change.before_size ?? "new"} → ${change.after_size ?? "deleted"} bytes${change.reason ? ` · ${escapeHtml(change.reason)}` : ""}</p></div><div class="row-actions"><button class="button mini harness-task-change-inspect" data-harness-change="${escapeHtml(change.path)}">${change.diff_available ? "Inspect diff" : "Why unavailable"}</button></div></div>`).join("") : `<div class="empty">${escapeHtml(changes.reason || "No safe, bounded workspace changes were found.")}</div>`;
        $$(".harness-task-change-inspect").forEach((button) => { button.onclick = () => inspectTaskChange(button.dataset.harnessChange); });
      };
      const loadTaskChanges = async (taskId = state.selectedHarnessTask) => {
        if (!taskId) {
          state.harnessTaskChanges = null;
          renderTaskChanges();
          return null;
        }
        try {
          state.harnessTaskChanges = await api(`/api/harness/tasks/${encodeURIComponent(taskId)}/changes`);
          $("#harness-task-change-diff").textContent = "Select a changed file to inspect its bounded, redacted diff.";
        } catch (error) {
          state.harnessTaskChanges = {task_id: taskId, checkpoint: null, changes: [], reason: error.message};
        }
        renderTaskChanges();
        return state.harnessTaskChanges;
      };
      const inspectTaskChange = async (relativePath) => {
        const taskId = state.selectedHarnessTask;
        if (!taskId || !relativePath) return;
        const encodedPath = String(relativePath).split("/").map(encodeURIComponent).join("/");
        try {
          const output = await api(`/api/harness/tasks/${encodeURIComponent(taskId)}/changes/${encodedPath}`);
          $("#harness-task-change-diff").textContent = output.diff_available
            ? (output.diff || "No textual diff was produced.")
            : (output.reason || "No safe text diff is available.");
        } catch (error) { toast(error.message, true); }
      };
      const inspectTask = async (taskId) => {
        if (!taskId) return;
        try {
          const [task, eventData] = await Promise.all([api(`/api/harness/tasks/${encodeURIComponent(taskId)}`), api(`/api/harness/tasks/${encodeURIComponent(taskId)}/events`)]);
          state.selectedHarnessTask = taskId;
          state.harnessTaskEvents = (eventData.events || []).slice(-40);
          $("#harness-task-detail-title").textContent = `Task ${String(task.id || "").slice(0, 12)} · ${task.state}`;
          const outcome = task.error ? `Error\n${task.error}` : task.result ? `Result\n${task.result}` : "No final result yet.";
          $("#harness-task-detail").textContent = outcome;
          renderTaskTimeline();
          if (taskIsActive(task)) startTaskEventStream(taskId, Number(state.harnessTaskEvents.at(-1)?.sequence || 0));
          else stopTaskEventStream();
          await loadTaskChanges(taskId);
        } catch (error) { toast(error.message, true); }
      };
      const launchQuickTask = async ({objective: requestedObjective, button: requestedButton, clearObjective = true, startedMessage} = {}) => {
        const objective = String(requestedObjective ?? $("#harness-task-objective").value).trim();
        if (!scheduleWorkspace()) return toast("Choose a workspace root before starting autonomous work", true);
        if (!objective) return toast("Enter a focused task objective", true);
        const button = requestedButton || $("#harness-task-quick");
        const buttonLabel = button.textContent;
        button.disabled = true;
        button.textContent = "Starting…";
        try {
          const task = await api("/api/desktop/quick-task", {method: "POST", body: JSON.stringify({objective})});
          if (clearObjective) $("#harness-task-objective").value = "";
          await loadTasks();
          await inspectTask(task.id);
          toast(startedMessage || `Quick task started · ${task.defaults?.provider || "local provider"} · 3 attempts`);
          return task;
        } catch (error) {
          const handoff = await stageMajorRiskApproval({objective, detail: error?.obusDetail});
          if (handoff) {
            toast("Local approval request created. The exact task is ready in Runtime; no task was started.");
            return handoff;
          }
          toast(error.message, true);
        }
        finally { button.textContent = buttonLabel; renderTasks(); }
      };
      const launchTask = async () => {
        const objective = $("#harness-task-objective").value.trim();
        const workspace = scheduleWorkspace();
        if (!workspace) return toast("Choose a workspace root before starting autonomous work", true);
        if (!objective) return toast("Enter a focused task objective", true);
        const attempts = Math.round(Number($("#harness-task-attempts").value));
        const priority = Math.round(Number($("#harness-task-priority").value));
        if (!Number.isFinite(attempts) || attempts < 1 || attempts > 10) return toast("Choose 1 to 10 repair attempts", true);
        if (!Number.isFinite(priority) || priority < 0 || priority > 100) return toast("Choose a priority from 0 to 100", true);
        const button = $("#harness-task-submit");
        button.disabled = true;
        try {
          const body = {objective, workspace, provider: $("#harness-task-provider").value, max_attempts: attempts, priority};
          if (state.selectedHarnessApprovalId) body.approval_id = state.selectedHarnessApprovalId;
          const task = await api("/api/harness/tasks", {method: "POST", body: JSON.stringify(body)});
          $("#harness-task-objective").value = "";
          state.selectedHarnessApprovalId = null;
          state.pendingHarnessApprovalDraft = null;
          await Promise.all([loadTasks(), loadApprovals()]);
          await inspectTask(task.id);
          toast("Guarded workspace task started");
        } catch (error) {
          const handoff = await stageMajorRiskApproval({objective, detail: error?.obusDetail});
          if (handoff) {
            toast("Local approval request created. Review its risks, then approve it explicitly before running.");
          } else toast(error.message, true);
        } finally { button.disabled = !scheduleWorkspace(); }
      };
      const cancelTask = async (taskId) => {
        try {
          const task = await api(`/api/harness/tasks/${encodeURIComponent(taskId)}`, {method: "DELETE"});
          await loadTasks();
          await inspectTask(task.id);
          toast("Task cancellation requested; its checkpoint will be rolled back if it is running");
        } catch (error) { toast(error.message, true); }
      };
      const resumeTask = async (taskId) => {
        try {
          const task = await api(`/api/harness/tasks/${encodeURIComponent(taskId)}/resume`, {method: "POST"});
          await loadTasks();
          await inspectTask(task.id);
          toast("Task resumed. OBus will re-inspect the workspace before continuing.");
        } catch (error) { toast(error.message, true); }
      };
      const ledgerIsActive = (ledger) => ["planning", "running"].includes(String(ledger?.status || "").toLowerCase());
      const ledgerTime = (value) => value ? String(value).replace("T", " ").replace(/\..*$/, "Z") : "not started";
      const renderLedgers = () => {
        const list = $("#runtime-ledger-list");
        const detail = $("#runtime-ledger-detail");
        if (!list || !detail) return;
        const ledgers = state.runtimeLedgers || [];
        if (state.selectedTeamLedger && !ledgers.some((ledger) => ledger.id === state.selectedTeamLedger)) state.selectedTeamLedger = null;
        list.innerHTML = ledgers.length ? ledgers.map((ledger) => {
          const active = ledgerIsActive(ledger);
          const selected = ledger.id === state.selectedTeamLedger;
          const findingCount = (ledger.findings || []).length;
          const workerLimit = Number(ledger.parallelism?.worker_limit || (ledger.agent_ids || []).length || 1);
          const sharedEvidence = ledger.context_policy?.shared_redacted_findings !== false;
          return `<div class="row runtime-ledger ${selected ? "selected" : ""}" data-runtime-ledger="${escapeHtml(ledger.id)}" role="button" tabindex="0" style="width:100%;text-align:left"><div><h4>${escapeHtml(ledger.kind === "planned-team" ? "Planned team" : "Orchestrated team")} <span class="badge ${ledger.status === "complete" ? "ready" : active ? "warn" : "risk"}">${escapeHtml(ledger.status || "unknown")}</span></h4><p>${escapeHtml(ledger.objective || "Untitled team")}</p><p class="hint">${(ledger.agent_ids || []).length} agents · ${workerLimit} worker slots · ${sharedEvidence ? "private contexts + redacted evidence" : "fully private contexts"} · ${findingCount} findings · updated ${escapeHtml(ledgerTime(ledger.updated_at))}</p></div><div class="row-actions"><span class="badge">Inspect</span>${active ? `<button class="button mini danger" data-runtime-ledger-stop="${escapeHtml(ledger.id)}" type="button">Stop team</button>` : ""}</div></div>`;
        }).join("") : "<div class=\"empty\">No parallel teams launched yet. Review a plan, then launch its team.</div>";
        $$("[data-runtime-ledger]").forEach((button) => { button.onclick = () => inspectLedger(button.dataset.runtimeLedger); });
        $$("[data-runtime-ledger-stop]").forEach((button) => { button.onclick = async (event) => { event.stopPropagation(); const ledger = ledgers.find((item) => item.id === button.dataset.runtimeLedgerStop); const agentIds = new Set(ledger?.agent_ids || []); const activeAgents = (state.runtimeAgents || []).filter((agent) => agentIds.has(agent.id) && ['queued', 'running', 'stopping'].includes(agent.status)); if (!activeAgents.length) return toast('This team has no active agents to stop.'); button.disabled = true; try { await Promise.all(activeAgents.map((agent) => api(`/api/runtime/agents/${encodeURIComponent(agent.id)}/stop`, {method: 'POST', body: JSON.stringify({})}))); await load(); toast(`Stop requested for ${activeAgents.length} team agent${activeAgents.length === 1 ? '' : 's'}.`); } catch (error) { toast(error.message, true); } finally { button.disabled = false; } }; });
        const ledger = ledgers.find((item) => item.id === state.selectedTeamLedger);
        if (!ledger) {
          detail.textContent = "Select a team to inspect its bounded findings and synthesis.";
          return;
        }
        const findings = (ledger.findings || []).slice(-20).map((finding, index) => [
          `${index + 1}. ${finding.agent_name || "Agent"} · step ${finding.step || "?"} · ${finding.created_at || ""}`,
          finding.output || "No visible finding.",
        ].join("\n"));
        const synthesis = ledger.synthesis || (ledger.status === "running" ? "Waiting for all active agents before local synthesis…" : "No synthesis was produced.");
        const workerLimit = Number(ledger.parallelism?.worker_limit || (ledger.agent_ids || []).length || 1);
        const sharedEvidence = ledger.context_policy?.shared_redacted_findings !== false;
        const contexts = Object.entries(ledger.context_windows || {}).map(([agentId, context]) => `${agentId}: ${Number(context?.window || 0).toLocaleString()} tokens · ${Number(context?.input_tokens_estimate || 0).toLocaleString()} estimated input`).join("\n");
        detail.textContent = [
          `Team ${ledger.id} · ${ledger.status || "unknown"}`,
          `Objective\n${ledger.objective || "Untitled team"}`,
          `Parallel execution\n${workerLimit} shared worker slot${workerLimit === 1 ? "" : "s"} · each agent keeps a separate history${sharedEvidence ? "; only bounded redacted findings can cross to siblings or synthesis." : "; sibling evidence sharing is disabled."}`,
          `Per-agent context\n${contexts || "Agent context capacity will appear after each worker begins."}`,
          `Synthesis\n${synthesis}`,
          `Redacted findings\n${findings.join("\n\n────\n\n") || "No completed findings yet."}`,
        ].join("\n\n");
      };
      const inspectLedger = async (ledgerId) => {
        if (!ledgerId) return;
        state.selectedTeamLedger = ledgerId;
        try {
          const ledger = await api(`/api/runtime/task-ledgers/${encodeURIComponent(ledgerId)}`);
          const current = state.runtimeLedgers || [];
          state.runtimeLedgers = [ledger, ...current.filter((item) => item.id !== ledger.id)];
        } catch (error) { toast(error.message, true); }
        renderLedgers();
      };
      const populateSelectors = () => {
        if (!state.dashboard) return;
        const setOptions = (selector, options, current) => {
          $(selector).innerHTML = options;
          if (current) $(selector).value = current;
        };
        setOptions("#runtime-spawn-card", state.dashboard.cards.map((card) => `<option value="${escapeHtml(card.id)}">${escapeHtml(card.name)} · ${escapeHtml(card.agent_type)}</option>`).join(""), $("#runtime-spawn-card").value);
        setOptions("#runtime-spawn-key", `<option value="auto">Auto · best Ready provider</option>${state.dashboard.providers.filter((key) => key.connected).map((key) => `<option value="${escapeHtml(key.id)}">${escapeHtml(key.name)} · ${escapeHtml(key.model)}</option>`).join("")}`, $("#runtime-spawn-key").value);
        setOptions("#runtime-spawn-room", `<option value="">None</option>${state.rooms.filter((room) => room.status !== "archived").map((room) => `<option value="${escapeHtml(room.id)}">${escapeHtml(room.name)}</option>`).join("")}`, $("#runtime-spawn-room").value);
        setOptions("#runtime-spawn-forum", `<option value="">None</option>${state.threads.map((thread) => `<option value="${escapeHtml(thread.id)}">${escapeHtml(thread.title)}</option>`).join("")}`, $("#runtime-spawn-forum").value);
      };
      const render = () => {
        if (!$("#runtime-agent-list")) return;
        populateSelectors();
        renderSchedules();
        renderTasks();
        renderLedgers();
        const running = state.runtimeAgents.filter((agent) => agent.status === "running").length;
        const queued = state.runtimeAgents.filter((agent) => agent.status === "queued").length;
        const completed = state.runtimeAgents.filter((agent) => agent.status === "complete").length;
        const parallelLimit = Number(state.settings?.max_parallel_agents) || 5;
        $("#runtime-count").textContent = `${state.runtimeAgents.length} / 30 · ${running}/${parallelLimit} live`;
        $("#runtime-running-count").textContent = String(running);
        $("#runtime-queued-count").textContent = String(queued);
        $("#runtime-parallel-limit").textContent = String(parallelLimit);
        $("#runtime-complete-count").textContent = String(completed);
        $("#runtime-event-log").textContent = state.runtimeEvents.length
          ? state.runtimeEvents.slice(-30).map((event) => `${event.created_at} · ${event.kind}${event.agent_id ? ` · ${event.agent_id}` : ""}\n${event.message}`).join("\n\n")
          : "No runtime events yet.";
        $("#runtime-agent-list").innerHTML = state.runtimeAgents.length ? state.runtimeAgents.map((agent, index) => {
          const active = ["queued", "running", "stopping"].includes(agent.status);
          const resumable = agent.status === "interrupted";
          const history = (agent.history || []).slice(-3);
          const visual = root.OBusAgentVisuals?.persistentMarkup(agent, cardName(agent.card_id), index) || `<div class="row"><h4>${escapeHtml(agent.name)}</h4><p>${escapeHtml(agent.objective)}</p></div>`;
          const interruption = agent.interruption?.at ? `Interrupted at ${String(agent.interruption.at).replace("T", " ").replace(/\..*$/, "Z")} · inspect before continuing.` : "";
          return `<div class="row agent-runtime-card"><div class="agent-runtime-main">${visual}<div class="agent-runtime-meta">${escapeHtml(agent.provider_mode)} provider · max ${agent.max_steps} steps · runs ${agent.run_count}${agent.current_provider ? ` · current ${escapeHtml(agent.current_provider)} / ${escapeHtml(agent.current_model || "")} · step ${agent.current_step || 0}` : ""}</div>${agent.last_error ? `<p class="risk-high">${escapeHtml(agent.last_error)}</p>` : ""}${interruption ? `<p class="hint">${escapeHtml(interruption)}</p>` : ""}${history.length ? `<details class="agent-runtime-history"><summary>Recent visible context (${agent.history.length})</summary>${history.map((item) => `<div class="deliberation-message"><div class="deliberation-head"><strong>${escapeHtml(item.provider || "provider")}</strong><span>run ${item.run} · step ${item.step}</span></div><div>${escapeHtml(item.output)}</div></div>`).join("")}</details>` : ""}</div><div class="row-actions"><button class="button mini runtime-run" data-agent="${escapeHtml(agent.id)}" data-action="${resumable ? "resume" : "run"}" ${active ? "disabled" : ""} title="${resumable ? "Inspect the persisted state before continuing; OBus never restarts interrupted work automatically." : "Start a new bounded run."}">${resumable ? "Resume safely" : "Run"}</button><button class="button mini runtime-stop" data-agent="${escapeHtml(agent.id)}" ${active ? "" : "disabled"}>Stop</button><button class="button mini danger runtime-delete" data-agent="${escapeHtml(agent.id)}" ${active ? "disabled" : ""}>Delete</button></div></div>`;
        }).join("") : "<div class=\"empty\">No persistent agents yet. Spawn one card persona or let local Ollama orchestrate a team.</div>";
        $$(".runtime-run").forEach((button) => { button.onclick = () => action(button.dataset.agent, button.dataset.action || "run"); });
        $$(".runtime-stop").forEach((button) => { button.onclick = () => action(button.dataset.agent, "stop"); });
        $$(".runtime-delete").forEach((button) => { button.onclick = () => action(button.dataset.agent, "delete"); });
        const active = state.runtimeAgents.some((agent) => ["queued", "running", "stopping"].includes(agent.status)) || (state.runtimeLedgers || []).some(ledgerIsActive);
        clearTimeout(state.runtimePolling);
        if (active) state.runtimePolling = setTimeout(() => load().catch((error) => toast(error.message, true)), quantumPollInterval());
      };
      const load = async () => {
        [state.runtimeAgents, state.runtimeEvents, state.runtimeLedgers] = await Promise.all([api("/api/runtime/agents"), api("/api/runtime/events"), api("/api/runtime/task-ledgers")]);
        await Promise.all([loadSchedules(), loadTasks(), loadApprovals()]);
        render();
        return state.runtimeAgents;
      };
      const action = async (agentId, actionName) => {
        try {
          if (actionName === "delete") await api(`/api/runtime/agents/${encodeURIComponent(agentId)}`, {method: "DELETE"});
          else await api(`/api/runtime/agents/${encodeURIComponent(agentId)}/${actionName}`, {method: "POST", body: JSON.stringify({})});
          await load();
          toast(`Agent ${actionName} requested`);
        } catch (error) { toast(error.message, true); }
      };
      const spawn = async () => {
        const objective = $("#runtime-spawn-objective").value.trim();
        if (!objective) return toast("Enter a persistent objective", true);
        const key = $("#runtime-spawn-key").value;
        const body = {name: $("#runtime-spawn-name").value.trim() || null, card_id: $("#runtime-spawn-card").value, objective, provider_mode: key === "auto" ? "auto" : "manual", key_id: key === "auto" ? null : key, room_id: $("#runtime-spawn-room").value || null, forum_thread_id: $("#runtime-spawn-forum").value || null, max_steps: Number($("#runtime-spawn-steps").value) || 1, auto_start: $("#runtime-spawn-autostart").checked};
        const button = $("#runtime-spawn-agent"); button.disabled = true;
        try { await api("/api/runtime/agents", {method: "POST", body: JSON.stringify(body)}); $("#runtime-spawn-name").value = ""; $("#runtime-spawn-objective").value = ""; await load(); toast("Persistent agent spawned"); }
        catch (error) { toast(error.message, true); } finally { button.disabled = false; }
      };
      const orchestrate = async () => {
        const objective = $("#runtime-orchestrator-objective").value.trim();
        if (!objective) return toast("Enter an orchestration objective", true);
        const button = $("#runtime-orchestrate"); button.disabled = true; button.textContent = "Ollama planning…";
        try { const output = await api("/api/runtime/orchestrate", {method: "POST", body: JSON.stringify({objective, max_agents: Number($("#runtime-orchestrator-max").value) || 6, execute: true})}); $("#runtime-event-log").textContent = `Created ${output.created_agents.length} agents, ${output.created_rooms.length} rooms, and ${output.created_forums.length} forums.\n\n${JSON.stringify(output.plan, null, 2)}`; await Promise.all([load(), loadRooms(), loadThreads()]); toast("Local Ollama orchestration executed"); }
        catch (error) { toast(error.message, true); } finally { button.disabled = false; button.textContent = "Let Ollama orchestrate"; }
      };
      return {load, render, action, spawn, orchestrate, loadSchedules, createSchedule, scheduleAction, loadTasks, loadApprovals, stageMajorRiskApproval, launchQuickTask, launchTask, inspectTask, cancelTask, resumeTask, loadTaskChanges, inspectTaskChange, inspectLedger};
    },
  };
  root.OBusRuntime = OBusRuntime;
})(window);
