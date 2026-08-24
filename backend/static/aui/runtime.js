"use strict";

(function installObusRuntime(root) {
  const OBusRuntime = {
    create({api, state, $, $$, escapeHtml, toast, quantumPollInterval, loadRooms, loadThreads} = {}) {
      const cardName = (id) => state.dashboard?.cards.find((card) => card.id === id)?.name || id;
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
        $("#runtime-count").textContent = `${state.runtimeAgents.length} / 30`;
        $("#runtime-event-log").textContent = state.runtimeEvents.length
          ? state.runtimeEvents.slice(-30).map((event) => `${event.created_at} · ${event.kind}${event.agent_id ? ` · ${event.agent_id}` : ""}\n${event.message}`).join("\n\n")
          : "No runtime events yet.";
        $("#runtime-agent-list").innerHTML = state.runtimeAgents.length ? state.runtimeAgents.map((agent) => {
          const active = ["queued", "running", "stopping"].includes(agent.status);
          const history = (agent.history || []).slice(-3);
          return `<div class="row"><div><h4>${escapeHtml(agent.name)} <span class="badge ${agent.status === "complete" ? "ready" : "warn"}">${escapeHtml(agent.status)}</span></h4><p>${escapeHtml(cardName(agent.card_id))} · ${escapeHtml(agent.provider_mode)} provider · max ${agent.max_steps} steps · runs ${agent.run_count}</p><p class="context">${escapeHtml(agent.objective)}</p>${agent.current_provider ? `<p>Current: ${escapeHtml(agent.current_provider)} · ${escapeHtml(agent.current_model || "")} · step ${agent.current_step || 0}</p>` : ""}${agent.last_error ? `<p class="risk-high">${escapeHtml(agent.last_error)}</p>` : ""}${history.length ? `<details><summary>Recent history (${agent.history.length})</summary>${history.map((item) => `<div class="deliberation-message"><div class="deliberation-head"><strong>${escapeHtml(item.provider || "provider")}</strong><span>run ${item.run} · step ${item.step}</span></div><div>${escapeHtml(item.output)}</div></div>`).join("")}</details>` : ""}</div><div class="row-actions"><button class="button mini runtime-run" data-agent="${escapeHtml(agent.id)}" ${active ? "disabled" : ""}>Run</button><button class="button mini runtime-stop" data-agent="${escapeHtml(agent.id)}" ${active ? "" : "disabled"}>Stop</button><button class="button mini danger runtime-delete" data-agent="${escapeHtml(agent.id)}" ${active ? "disabled" : ""}>Delete</button></div></div>`;
        }).join("") : "<div class=\"empty\">No persistent agents yet. Spawn one card persona or let local Ollama orchestrate a team.</div>";
        $$(".runtime-run").forEach((button) => { button.onclick = () => action(button.dataset.agent, "run"); });
        $$(".runtime-stop").forEach((button) => { button.onclick = () => action(button.dataset.agent, "stop"); });
        $$(".runtime-delete").forEach((button) => { button.onclick = () => action(button.dataset.agent, "delete"); });
        const active = state.runtimeAgents.some((agent) => ["queued", "running", "stopping"].includes(agent.status));
        clearTimeout(state.runtimePolling);
        if (active) state.runtimePolling = setTimeout(() => load().catch((error) => toast(error.message, true)), quantumPollInterval());
      };
      const load = async () => {
        [state.runtimeAgents, state.runtimeEvents] = await Promise.all([api("/api/runtime/agents"), api("/api/runtime/events")]);
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
      return {load, render, action, spawn, orchestrate};
    },
  };
  root.OBusRuntime = OBusRuntime;
})(window);
