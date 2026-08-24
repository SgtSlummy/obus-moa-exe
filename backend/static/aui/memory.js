"use strict";

(function installObusMemory(root) {
  const OBusMemory = {
    create({api, state, $, $$, escapeHtml, toast, refresh} = {}) {
      const render = (data) => {
        state.memories = data?.items || [];
        const element = $("#memory-local-list");
        if (!element) return;
        element.innerHTML = state.memories.length ? state.memories.slice().reverse().map((item) => `<div class="row"><div><h4>${escapeHtml((item.tags || []).join(", ") || "Memory")}</h4><p>${escapeHtml(item.text)}</p><p class="context">${escapeHtml(item.created_at || "")} · ${escapeHtml(item.source || "manual")}</p></div><button class="button mini danger memory-delete" data-memory="${escapeHtml(item.id)}">Delete</button></div>`).join("") : "<div class=\"empty\">No local memories yet. Add a stable fact or preference above.</div>";
        $$(".memory-delete").forEach((button) => { button.onclick = () => deleteMemory(button.dataset.memory); });
      };
      const load = async () => { const data = await api("/api/memory"); render(data); return data; };
      const add = async () => {
        const text = $("#memory-input").value.trim(); if (!text) return toast("Enter something to remember", true);
        const tags = $("#memory-tags").value.split(",").map((tag) => tag.trim()).filter(Boolean); const button = $("#add-memory"); button.disabled = true;
        try { const item = await api("/api/memory", {method: "POST", body: JSON.stringify({text, tags})}); $("#memory-input").value = ""; $("#memory-tags").value = ""; await Promise.all([load(), refresh()]); toast(item.deduplicated ? "That memory already exists" : "Memory saved and available to RAG"); }
        catch (error) { toast(error.message, true); } finally { button.disabled = false; }
      };
      const deleteMemory = async (id) => { try { await api(`/api/memory/${encodeURIComponent(id)}`, {method: "DELETE"}); await Promise.all([load(), refresh()]); toast("Memory deleted"); } catch (error) { toast(error.message, true); } };
      const search = async () => {
        const query = $("#memory-search").value.trim(); if (!query) return toast("Enter a memory search", true);
        const output = await api(`/api/memory/search?query=${encodeURIComponent(query)}&limit=20`); const element = $("#memory-search-results"); element.className = `result ${output.results.length ? "" : "empty"}`;
        element.innerHTML = output.results.length ? output.results.map((item) => `<div class="deliberation-message"><div class="deliberation-head"><strong>${escapeHtml(item.source || "memory")}</strong><span>${escapeHtml(item.path || item.id || "")}</span></div><div>${escapeHtml(item.text || "")}</div></div>`).join("") : "No matching memory found.";
      };
      const renderHub = (data) => {
        const hub = data?.memory_hub || {}; const labels = {obus: "OBus local memory", hermes: "Hermes native memory", mempalace: "MemPalace", mem0: "Mem0", tarot_rag: "Tarot Router RAG", mythos_router: "Mythos Router SWD", moa_router: "MoA router"};
        const element = $("#memory-hub-list"); if (!element) return;
        element.innerHTML = Object.entries(hub).map(([key, value]) => { const ready = value.status === "ready"; const detail = value.chunks !== undefined ? `${value.chunks} chunks` : value.messages !== undefined ? `${value.messages} messages` : value.indexed !== undefined ? (value.indexed ? "indexed" : "not indexed") : value.ollama_connected !== undefined ? (value.ollama_connected ? "Ollama connected" : "Ollama offline") : value.mcp_boundary !== undefined ? (value.mcp_boundary ? "MCP boundary available" : "CLI/source partial") : value.present ? "present" : "not present"; return `<div class="row"><div><h4>${escapeHtml(labels[key] || key)}</h4><p>${escapeHtml(value.path || value.source || value.palace || "Local integration")}</p></div><span class="badge ${ready ? "ready" : "warn"}">${escapeHtml(value.status || "unknown")} · ${escapeHtml(detail)}</span></div>`; }).join("");
      };
      return {load, render, add, deleteMemory, search, renderHub};
    },
  };
  root.OBusMemory = OBusMemory;
})(window);
