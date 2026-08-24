"use strict";

(function installObusRooms(root) {
  const OBusRooms = {
    create({api, state, $, $$, escapeHtml, toast, quantumPollInterval, roomCardName} = {}) {
      const renderRooms = () => {
        const element = $("#room-list");
        if (!element) return;
        element.innerHTML = state.rooms.length ? state.rooms.map((room) => {
          const archived = room.status === "archived";
          const selected = room.id === state.selectedRoom;
          return `<div class="row ${selected ? "selected" : ""}"><div><h4>${escapeHtml(room.name)} <span class="badge ${room.status === "complete" ? "ready" : "warn"}">${escapeHtml(room.status)}</span></h4><p>${room.card_ids.length} seats · ${escapeHtml(room.mode)} · Chymeria: ${escapeHtml(roomCardName(room.chymeria.card_id))} · revision ${room.revision}</p>${room.status === "running" ? `<p class="context">Phase: ${escapeHtml(room.current_phase || "starting")} · ${room.progress_count || 0} messages</p>` : ""}</div><div class="row-actions"><button class="button mini room-open" data-room="${escapeHtml(room.id)}">Open</button>${archived ? "<span class=\"badge warn\">Archived</span>" : `<button class="button mini room-archive" data-room="${escapeHtml(room.id)}">Archive</button>`}</div></div>`;
        }).join("") : "<div class=\"empty\">No rooms yet. Create a hand/spread to start an isolated council.</div>";
        $$(".room-open").forEach((button) => { button.onclick = () => selectRoom(button.dataset.room, false); });
        $$(".room-archive").forEach((button) => { button.onclick = async () => { try { await api(`/api/rooms/${encodeURIComponent(button.dataset.room)}`, {method: "DELETE"}); if (state.selectedRoom === button.dataset.room) state.selectedRoom = null; await loadRooms(); toast("Room archived"); } catch (error) { toast(error.message, true); } }; });
      };
      const renderRoomDetail = (room, messages, preserveTask = true) => {
        state.selectedRoom = room.id;
        $("#room-detail-title").textContent = room.name;
        $("#room-detail-meta").textContent = `${room.mode} · revision ${room.revision} · Chymeria: ${roomCardName(room.chymeria.card_id)}`;
        $("#room-progress").textContent = room.status === "running" ? `${room.current_phase || "starting"} · ${room.progress_count || messages.length} messages` : room.status;
        $("#room-progress").className = `badge ${room.status === "complete" ? "ready" : "warn"}`;
        $("#room-seats").innerHTML = room.card_ids.map((id, index) => root.OBusAgentVisuals?.faceButtonMarkup({id: `room-seat-${room.id}-${id}`, kind: "room", role: roomCardName(id), status: room.status === "running" ? "running" : "idle", stage: id === room.chymeria.card_id ? "Chymeria seat" : "council seat", context: `${room.mode} room · revision ${room.revision}`}, index) || `<span class="badge ${id === room.chymeria.card_id ? "ready" : ""}">${escapeHtml(roomCardName(id))}${id === room.chymeria.card_id ? " · Chymeria" : ""}</span>`).join("");
        if (!preserveTask || !$("#room-task-input").value) $("#room-task-input").value = room.last_prompt || "";
        $("#room-run-deliberation").disabled = room.status === "archived" || room.status === "running";
        $("#room-refresh-deliberation").disabled = false;
        $("#room-deliberation").className = `result ${messages.length ? "" : "empty"}`;
        $("#room-deliberation").innerHTML = messages.length ? messages.map((message, index) => `<div class="deliberation-message ${message.author_type === "chymeria" ? "chymeria" : ""}"><div class="deliberation-head"><span class="room-message-agent">${root.OBusAgentVisuals?.faceButtonMarkup({id: `room-message-${room.id}-${message.id || index}`, kind: "room", role: roomCardName(message.author_id), status: room.status === "running" ? "running" : "complete", stage: message.phase, output: message.body, context: message.body}, index) || ""}</span><strong>${escapeHtml(roomCardName(message.author_id))}${message.author_type === "chymeria" ? " · Chymeria" : ""}</strong><span>${escapeHtml(message.phase)} · ${escapeHtml(message.created_at || "")}</span></div><div>${escapeHtml(message.body)}</div></div>`).join("") : "No deliberation yet. Enter a task and run the room.";
        const packet = room.last_packet;
        $("#room-decision").className = `result ${packet ? "" : "empty"}`;
        $("#room-decision").textContent = packet ? `${packet.position}\n\nConfidence: ${packet.confidence}\nStatus: ${packet.status}${packet.rationale ? `\n\nRationale: ${packet.rationale}` : ""}` : "The final Chymeria decision will appear after deliberation.";
        $("#room-deliberation").scrollTop = $("#room-deliberation").scrollHeight;
        renderRooms();
      };
      const selectRoom = async (roomId, preserveTask = true) => {
        const [room, messages] = await Promise.all([api(`/api/rooms/${encodeURIComponent(roomId)}`), api(`/api/rooms/${encodeURIComponent(roomId)}/messages`)]);
        renderRoomDetail(room, messages, preserveTask);
        if (room.status === "running") scheduleRoomPoll();
        return room;
      };
      const scheduleRoomPoll = () => {
        clearTimeout(state.roomPolling);
        state.roomPolling = setTimeout(async () => { if (!state.selectedRoom) return; try { const room = await selectRoom(state.selectedRoom, true); if (room.status === "running") scheduleRoomPoll(); } catch (error) { toast(error.message, true); } }, quantumPollInterval());
      };
      const loadRooms = async () => {
        state.rooms = await api("/api/rooms");
        if (!state.selectedRoom && state.rooms.length) state.selectedRoom = (state.rooms.find((room) => room.status !== "archived") || state.rooms[0]).id;
        renderRooms();
        if (state.selectedRoom && state.rooms.some((room) => room.id === state.selectedRoom)) await selectRoom(state.selectedRoom, true);
        return state.rooms;
      };
      const syncRoomChymeriaOptions = () => {
        const selected = [...$("#room-card-picker").selectedOptions].map((option) => option.value);
        const current = $("#room-chymeria").value;
        $("#room-chymeria").innerHTML = selected.map((id) => { const card = state.dashboard.cards.find((item) => item.id === id); return `<option value="${escapeHtml(id)}">${escapeHtml(card?.name || id)}</option>`; }).join("");
        $("#room-chymeria").value = selected.includes(current) ? current : (selected[0] || "");
      };
      const openRoomDialog = () => {
        if (!state.dashboard) return toast("Dashboard is still loading", true);
        $("#room-card-picker").innerHTML = state.dashboard.cards.map((card) => `<option value="${escapeHtml(card.id)}">${escapeHtml(card.name)} · ${escapeHtml(card.agent_type)}</option>`).join("");
        $("#room-chymeria").innerHTML = ""; $("#room-name").value = ""; $("#room-prompt").value = ""; $("#room-dialog").showModal();
      };
      const saveRoom = async () => {
        const selected = [...$("#room-card-picker").selectedOptions].map((option) => option.value);
        if (!selected.length) throw new Error("Choose at least one Tarot seat");
        const body = {name: $("#room-name").value.trim(), card_ids: selected, mode: $("#room-mode").value, chymeria_card_id: $("#room-chymeria").value || selected[0]};
        const prompt = $("#room-prompt").value.trim();
        const room = await api("/api/rooms", {method: "POST", body: JSON.stringify(body)});
        $("#room-dialog").close(); state.selectedRoom = room.id; await loadRooms(); await selectRoom(room.id, false);
        if (prompt) { $("#room-task-input").value = prompt; await runSelectedRoom(); }
        toast(`${room.name} created`);
      };
      const runSelectedRoom = async () => {
        if (!state.selectedRoom) return toast("Select a room first", true);
        const prompt = $("#room-task-input").value.trim(); if (!prompt) return toast("Enter a room task first", true);
        const button = $("#room-run-deliberation"); button.disabled = true; button.textContent = "Deliberating…"; $("#room-progress").textContent = "starting"; $("#room-deliberation").className = "result empty"; $("#room-deliberation").textContent = "The room council is starting…"; scheduleRoomPoll();
        try { await api(`/api/rooms/${encodeURIComponent(state.selectedRoom)}/run`, {method: "POST", body: JSON.stringify({prompt})}); await loadRooms(); await selectRoom(state.selectedRoom, true); toast("Room deliberation complete"); }
        catch (error) { await selectRoom(state.selectedRoom, true).catch(() => {}); toast(error.message, true); }
        finally { clearTimeout(state.roomPolling); button.disabled = false; button.textContent = "Run deliberation"; }
      };
      const renderThreads = () => {
        const element = $("#forum-thread-list"); if (!element) return;
        element.innerHTML = state.threads.length ? state.threads.map((thread) => `<button class="row" data-thread="${escapeHtml(thread.id)}" style="width:100%;text-align:left"><div><h4>${escapeHtml(thread.title)}</h4><p>${thread.room_ids.length} rooms · revision ${thread.revision} · ${escapeHtml(thread.status)}</p></div><span class="badge">${thread.messages.length} messages</span></button>`).join("") : "<div class=\"empty\">No forum threads yet. Add two or more rooms first.</div>";
        $$('[data-thread]').forEach((button) => { button.onclick = () => selectThread(button.dataset.thread).catch((error) => toast(error.message, true)); });
      };
      const loadThreads = async () => { state.threads = await api("/api/forum/threads"); renderThreads(); return state.threads; };
      const selectThread = async (threadId) => { state.selectedThread = threadId; const thread = await api(`/api/forum/threads/${encodeURIComponent(threadId)}`); $("#forum-round").disabled = false; $("#send-forum-message").disabled = false; $("#forum-message-list").className = "result"; $("#forum-message-list").textContent = thread.messages.length ? thread.messages.map((message) => `${message.author_type} · ${message.room_id} · ${message.kind}\n${message.body}\n`).join("\n---\n") : "No public Chymeria messages yet."; return thread; };
      const createForumThread = async () => {
        const activeRooms = state.rooms.filter((room) => room.status !== "archived"); if (activeRooms.length < 2) return toast("Create at least two active rooms first", true);
        const title = root.prompt("Forum thread title", "Shared decision"); if (!title) return; const prompt = root.prompt("Forum question", "Compare the rooms’ recommendations"); if (!prompt) return;
        try { await api("/api/forum/threads", {method: "POST", body: JSON.stringify({title, prompt, room_ids: activeRooms.map((room) => room.id)})}); await loadThreads(); toast("Forum thread created"); } catch (error) { toast(error.message, true); }
      };
      const runForumRound = async () => { if (!state.selectedThread) return; $("#forum-round").disabled = true; try { await api(`/api/forum/threads/${encodeURIComponent(state.selectedThread)}/round`, {method: "POST"}); await Promise.all([loadThreads(), loadRooms()]); await selectThread(state.selectedThread); toast("Forum round complete"); } catch (error) { toast(error.message, true); } finally { $("#forum-round").disabled = false; } };
      const sendForumMessage = async () => { if (!state.selectedThread || !$("#forum-composer").value.trim()) return; try { const thread = await api(`/api/forum/threads/${encodeURIComponent(state.selectedThread)}`); await api(`/api/forum/threads/${encodeURIComponent(state.selectedThread)}/messages`, {method: "POST", body: JSON.stringify({room_id: thread.room_ids[0], kind: "question", body: $("#forum-composer").value.trim()})}); $("#forum-composer").value = ""; await loadThreads(); await selectThread(state.selectedThread); toast("Public question posted"); } catch (error) { toast(error.message, true); } };
      return {loadRooms, renderRooms, renderRoomDetail, selectRoom, scheduleRoomPoll, syncRoomChymeriaOptions, openRoomDialog, saveRoom, runSelectedRoom, loadThreads, renderThreads, selectThread, createForumThread, runForumRound, sendForumMessage};
    },
  };
  root.OBusRooms = OBusRooms;
})(window);
