"use strict";

(function installObusAgentVisuals(root) {
  const PHI = 1.61803398875;
  const metaRegistry = new Map();
  const faceLibrary = {
    default: ["(｡•́‿•̀｡)", "(づ｡◕‿‿◕｡)づ", "(◕‿◕✿)", "(≧◡≦)", "(｡•̀ᴗ-)✧", "(๑˃̵ᴗ˂̵)و"],
    coding: ["(•̀ᴗ•́)و", "(⌐■_■)", "(ง'̀-'́)ง", "(｡•̀ᴗ-)✧", "(¬‿¬)", "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧"],
    research: ["(｡•́‿•̀｡)✎", "(¬_¬)", "(◔_◔)", "(•̀ᴗ•́)و", "(⊙_⊙)", "( ˘▽˘)っ♨"],
    creative: ["(✿◠‿◠)", "(づ￣ ³￣)づ", "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧", "(｡♥‿♥｡)", "(≧▽≦)", "(☆▽☆)"],
    analysis: ["(•̀ᴗ•́)و", "(¬‿¬)", "(｡•́‿•̀｡)", "(⊙_⊙)", "(⌐■_■)", "(￣ー￣)"],
    security: ["(•̀ᴗ•́)و🛡", "(ง •̀_•́)ง", "(¬‿¬)", "(ಠ_ಠ)", "(⌐■_■)", "(•̀ᴗ•́)و"],
    planning: ["(｡•́‿•̀｡)✦", "(•̀ᴗ•́)و", "(￣▽￣)ノ", "(◕‿◕)", "(｡•̀ᴗ-)✧", "(づ｡◕‿‿◕｡)づ"],
    writing: ["(｡•́‿•̀｡)✎", "(✿◠‿◠)", "(≧◡≦)", "(￣▽￣)ノ", "(｡♥‿♥｡)", "(◕‿◕✿)"],
    tools: ["(•̀ᴗ•́)و🔧", "(⌐■_■)", "(ง'̀-'́)ง", "(｡•̀ᴗ-)✧", "(¬‿¬)", "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧"]
  };
  const statusFaces = {
    queued: ["(｡•́‿•̀｡)⏳", "(づ｡◕‿‿◕｡)づ…"],
    planned: ["(｡•́‿•̀｡)✦", "(◕‿◕)⌁"],
    running: ["(•̀ᴗ•́)و", "(ง'̀-'́)ง", "(｡•̀ᴗ-)✧"],
    complete: ["(^‿^)", "(≧◡≦)", "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧"],
    failed: ["(｡•́︿•̀｡)", "(╥﹏╥)", "(ಠ╭╮ಠ)"],
    stopped: ["(－_ლ)", "(｡•́︿•̀｡)"],
    idle: ["(｡•́‿•̀｡)", "(◕‿◕✿)"]
  };
  const statusIcons = {
    queued: ["◌", "◌", "◌"],
    planned: ["◇", "·", "◇"],
    running: ["◐", "◓", "◑", "◒"],
    complete: ["✦", "✧", "✦"],
    failed: ["×", "·", "×"],
    stopped: ["Ⅱ", "·", "Ⅱ"],
    idle: ["·", "·", "·"]
  };
  const groupAliases = {
    coding: "coding", code: "coding", developer: "coding", research: "research", investigator: "research",
    creative: "creative", design: "creative", analysis: "analysis", analyst: "analysis", security: "security",
    planning: "planning", strategy: "planning", writing: "writing", tools: "tools", tool: "tools"
  };

  const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;"}[char]));
  const normalizedStatus = (meta = {}) => {
    const status = String(meta.status || meta.phase || "idle").toLowerCase().replaceAll(" ", "_");
    return ["queued", "planned", "running", "complete", "failed", "stopped", "idle"].includes(status) ? status : "idle";
  };
  const capabilityGroup = (meta = {}) => {
    const words = `${meta.role || ""} ${meta.persona || ""} ${(meta.capabilities || []).join(" ")}`.toLowerCase().split(/[^a-z]+/);
    return words.map((word) => groupAliases[word]).find(Boolean) || "default";
  };
  const faceFor = (meta = {}, index = 0) => {
    const status = normalizedStatus(meta);
    const options = statusFaces[status] || faceLibrary[capabilityGroup(meta)] || faceLibrary.default;
    return options[index % options.length];
  };
  const iconStream = (status, index = 0) => {
    const icons = statusIcons[status] || statusIcons.idle;
    return [0, 1, 2].map((offset) => icons[(index + offset) % icons.length]).join(" ");
  };
  const keyFor = (meta, index) => {
    const key = String(meta.id || meta.agentId || `${meta.kind || "agent"}-${index}`);
    metaRegistry.set(key, {...meta, id: key});
    return key;
  };
  const metaForElement = (element) => metaRegistry.get(element?.dataset?.agentVisualKey) || {
    id: element?.dataset?.agentVisualKey || "agent",
    role: element?.dataset?.agentRole || "Agent",
    status: element?.dataset?.agentStatus || "idle",
    model: element?.dataset?.agentModel || "unassigned",
    kind: element?.dataset?.agentKind || "route",
    output: element?.dataset?.agentOutput || ""
  };
  const faceButtonMarkup = (meta = {}, index = 0) => {
    const status = normalizedStatus(meta);
    const key = keyFor(meta, index);
    const label = meta.role || meta.name || "Agent";
    const compactClass = meta.compact ? " agent-card-face" : "";
    return `<button type="button" class="kawaii-face agent-face-button agent-face-${status}${compactClass}" data-agent-face data-agent-visual-key="${esc(key)}" aria-label="Inspect ${esc(label)} working context" title="Click to inspect ${esc(label)} · right-click for quick info"><span class="agent-face-glyph" aria-hidden="true">${esc(faceFor(meta, index))}</span><span class="agent-face-spark" aria-hidden="true">${esc(iconStream(status, index))}</span></button>`;
  };
  const formatTokenCount = (value) => {
    const count = Math.max(0, Math.round(Number(value) || 0));
    return count >= 1000000 ? `${(count / 1000000).toFixed(1)}M` : count >= 1000 ? `${Math.round(count / 1000)}K` : String(count);
  };
  const contextMeterMarkup = (meta = {}) => {
    const capacity = Math.max(0, Math.round(Number(meta.context_window) || 0));
    if (!capacity) return "";
    const used = Math.min(capacity, Math.max(0, Math.round(Number(meta.context_input_tokens_estimate) || 0)));
    const percent = Math.min(100, Math.round((used / capacity) * 100));
    const tone = percent >= 90 ? "risk" : percent >= 70 ? "warn" : "ready";
    const summary = `${formatTokenCount(used)} / ${formatTokenCount(capacity)} tokens · ${percent}%`;
    return `<div class="agent-context-meter" title="A local estimate from the sanitized prompt; provider tokenizer counts are not exposed."><div class="agent-context-meter-label"><span>Context estimate</span><span>${esc(summary)}</span></div><div class="agent-context-meter-track" role="progressbar" aria-label="Estimated context use: ${esc(summary)}" aria-valuemin="0" aria-valuemax="${capacity}" aria-valuenow="${used}"><span class="${tone}" style="width:${percent}%"></span></div></div>`;
  };
  const contextWindowMarkup = (meta = {}, index = 0) => {
    const status = normalizedStatus(meta);
    const key = keyFor(meta, index);
    const role = meta.role || meta.name || "Agent";
    const context = meta.context || meta.output || meta.objective || "Waiting for visible working context…";
    const stage = meta.stage || (meta.kind === "persistent" ? "persistent agent" : "route stage");
    const voice = meta.kind === "route" && index === 0
      ? `<button type="button" class="button mini" id="voice-toggle" data-route-voice>Voice</button><span class="voice-state" id="voice-status" data-route-voice-status>Checking local voice…</span>`
      : "";
    return `<section class="agent-context-window" data-agent-context-window="${esc(key)}" aria-label="${esc(role)} context window"><div class="agent-context-head"><strong>${esc(stage)}</strong><span class="agent-icon-stream" aria-hidden="true">${esc(iconStream(status, index))}</span></div><p class="agent-context-text">${esc(context)}</p>${contextMeterMarkup(meta)}<div class="agent-context-actions">${voice}<button type="button" class="button mini agent-inspect" data-agent-inspect="${esc(key)}" data-agent-visual-key="${esc(key)}">Inspect</button><button type="button" class="button mini agent-copy" data-agent-copy="${esc(key)}" data-agent-visual-key="${esc(key)}">Copy</button></div></section>`;
  };
  const stageMarkup = (meta = {}, index = 0) => {
    const status = normalizedStatus(meta);
    const key = keyFor(meta, index);
    const role = meta.role || meta.name || `Agent ${index + 1}`;
    const model = meta.model || "unassigned";
    return `<article class="agent-stage agent-visual-stage ${esc(status)}" data-agent-card data-agent-visual-key="${esc(key)}"><div class="agent-visual-layout"><div class="agent-face-column">${faceButtonMarkup({...meta, id:key}, index)}<span class="agent-face-caption">${esc(status)}</span></div>${contextWindowMarkup({...meta, id:key, role, model, status}, index)}</div><div class="agent-stage-details"><h4>${esc(role)}</h4><div class="stage-meta">${esc(meta.stage || "specialist")} · ${esc(model)} · ${esc(status)}</div></div></article>`;
  };
  const persistentMarkup = (agent = {}, cardLabel = "Tarot persona", index = 0) => stageMarkup({
    id: agent.id, kind: "persistent", role: agent.name || cardLabel, status: agent.status, stage: cardLabel,
    model: agent.current_model || "waiting for provider", objective: agent.objective,
    context: agent.last_output || agent.objective || "No visible working context yet.", output: agent.last_output || "",
    context_window: agent.context_window, context_input_tokens_estimate: agent.context_input_tokens_estimate
  }, index);

  const dialog = () => root.document?.querySelector("#agent-monologue-dialog");
  const setText = (selector, value) => { const element = root.document?.querySelector(selector); if (element) element.textContent = String(value ?? ""); };
  const renderMessage = (parent, heading, detail, body) => {
    const article = root.document.createElement("article"); article.className = "agent-monologue-entry";
    const header = root.document.createElement("div"); header.className = "agent-monologue-entry-head";
    const strong = root.document.createElement("strong"); strong.textContent = heading;
    const small = root.document.createElement("span"); small.textContent = detail;
    header.append(strong, small);
    const pre = root.document.createElement("pre"); pre.textContent = String(body ?? "");
    article.append(header, pre); parent.append(article);
  };
  // Inner monologue viewer: only visible, sanitized working context is shown.
  const openMonologue = async (meta = {}) => {
    const target = dialog(); if (!target) return;
    const key = meta.id || meta.agentId || "agent";
    const latest = metaRegistry.get(String(key)) || meta;
    setText("#agent-monologue-title", latest.role || latest.name || "Agent working context");
    setText("#agent-monologue-subtitle", "Visible working context · hidden chain-of-thought is never exposed");
    setText("#agent-monologue-status", `${normalizedStatus(latest)} · ${latest.model || "unassigned"}`);
    const body = root.document.querySelector("#agent-monologue-body"); body.replaceChildren();
    renderMessage(body, "Objective", "persistent brief", latest.objective || latest.context || "No objective supplied.");
    if (latest.kind === "persistent" && latest.id) {
      try {
        const token = root.sessionStorage?.getItem("obus-access-token");
        const response = await root.fetch(`/api/runtime/agents/${encodeURIComponent(latest.id)}`, token ? {headers: {"X-OBus-Access": token}} : {});
        if (!response.ok) throw new Error(`Agent context unavailable (${response.status})`);
        const agent = await response.json();
        setText("#agent-monologue-status", `${normalizedStatus(agent)} · ${agent.current_model || latest.model || "provider pending"}`);
        (agent.history || []).slice(-12).forEach((item) => renderMessage(body, item.provider || "provider", `run ${item.run || "?"} · step ${item.step || "?"} · ${item.created_at || ""}`, item.output || ""));
        if (!(agent.history || []).length) renderMessage(body, "Current context", "no completed steps", agent.last_output || agent.objective || "Waiting for the first provider result…");
      } catch (error) { renderMessage(body, "Context request", "unavailable", error.message); }
    } else {
      renderMessage(body, latest.stage || "Route stage", latest.status || "visible output", latest.output || latest.context || "Waiting for output…");
    }
    if (!target.open) target.showModal();
  };
  const infoPopover = () => root.document?.querySelector("#agent-info-popover");
  const showInfo = (meta, x, y) => {
    const popover = infoPopover(); if (!popover) return;
    const latest = metaRegistry.get(String(meta.id || meta.agentId)) || meta;
    popover.replaceChildren();
    const title = root.document.createElement("strong"); title.textContent = latest.role || latest.name || "Agent";
    const detail = root.document.createElement("span"); detail.textContent = `${normalizedStatus(latest)} · ${latest.model || "unassigned"}`;
    const hint = root.document.createElement("small"); hint.textContent = "Click face to inspect visible working context.";
    const inspect = root.document.createElement("button"); inspect.className = "button mini"; inspect.type = "button"; inspect.textContent = "Inspect"; inspect.onclick = () => { popover.hidden = true; openMonologue(latest); };
    popover.append(title, detail, hint, inspect); popover.hidden = false;
    popover.style.left = `${Math.min(Math.max(10, x), root.innerWidth - 290)}px`;
    popover.style.top = `${Math.min(Math.max(10, y), root.innerHeight - 150)}px`;
  };
  const hideInfo = () => { const popover = infoPopover(); if (popover) popover.hidden = true; };
  const metaFromEvent = (event) => {
    const element = event.target.closest?.("[data-agent-face], [data-agent-inspect], [data-agent-card]");
    return element ? metaForElement(element) : null;
  };
  root.document?.addEventListener("click", (event) => {
    const face = event.target.closest?.("[data-agent-face]");
    const inspect = event.target.closest?.("[data-agent-inspect]");
    const copy = event.target.closest?.("[data-agent-copy]");
    if (face || inspect) { event.preventDefault(); openMonologue(metaForElement(face || inspect)); return; }
    if (copy) {
      const meta = metaForElement(copy); const text = meta.output || meta.context || meta.objective || "";
      root.navigator.clipboard?.writeText(text).then(() => root.document.querySelector("#toast") && (root.document.querySelector("#toast").textContent = "Agent context copied"));
    } else if (!event.target.closest?.("#agent-info-popover")) hideInfo();
  });
  root.document?.addEventListener("contextmenu", (event) => {
    const meta = metaFromEvent(event); if (!meta) return;
    event.preventDefault(); showInfo(meta, event.clientX, event.clientY);
  });
  root.document?.addEventListener("pointerover", (event) => {
    const face = event.target.closest?.("[data-agent-face]");
    if (!face || (event.relatedTarget && face.contains(event.relatedTarget))) return;
    showInfo(metaForElement(face), event.clientX + 12, event.clientY + 12);
  });
  root.document?.addEventListener("pointerout", (event) => {
    const face = event.target.closest?.("[data-agent-face]");
    if (face && (!event.relatedTarget || !face.contains(event.relatedTarget))) hideInfo();
  });
  root.OBusAgentVisuals = {PHI, faceFor, faceButtonMarkup, contextMeterMarkup, contextWindowMarkup, stageMarkup, persistentMarkup, openMonologue, showInfo};
})(window);
