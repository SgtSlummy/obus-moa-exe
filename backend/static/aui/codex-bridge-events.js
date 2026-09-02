"use strict";

(function installCodexBridgeEventRenderer(root) {
  const compact = (value, limit = 600) => {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    return text.length > limit ? `${text.slice(0, limit - 1)}…` : text;
  };

  const eventText = (params) => {
    const item = params?.item && typeof params.item === "object" ? params.item : {};
    return [params?.delta, params?.text, params?.message, params?.command, params?.reason, item.delta, item.text, item.message]
      .find((value) => typeof value === "string" && value.trim()) || "";
  };

  const line = (event) => {
    const method = String(event?.method || "app-server/message");
    const params = event?.params && typeof event.params === "object" ? event.params : {};
    const timestamp = new Date((Number(event?.at) || 0) * 1000).toLocaleTimeString();
    const text = compact(eventText(params));
    if (method === "item/agentMessage/delta") return `${timestamp} · Codex · ${text || "thinking…"}`;
    if (method === "item/commandExecution/outputDelta") return `${timestamp} · Command output · ${text || "updated"}`;
    if (method === "item/commandExecution/terminalInteraction") return `${timestamp} · Terminal interaction · ${text || "updated"}`;
    if (method === "approval/required" || method.includes("requestApproval")) return `${timestamp} · Approval required · ${text || "review locally before proceeding"}`;
    if (method === "approval/auto-accepted") return `${timestamp} · Ordinary workspace command allowed · ${text || "local policy"}`;
    if (method === "turn/completed") return `${timestamp} · Turn completed · ${compact(params?.turn?.status || params?.status || "review the result")}`;
    if (method === "turn/started" || method === "turn/submitted") return `${timestamp} · Codex turn started`;
    if (method === "app-server/ready") return `${timestamp} · Codex App Server ready · local stdio`;
    if (method === "app-server/stopped" || method === "app-server/exited") return `${timestamp} · Codex App Server stopped`;
    return `${timestamp} · ${method}${text ? ` · ${text}` : ""}`;
  };

  root.addEventListener("DOMContentLoaded", () => {
    root.codexBridgeEventLine = line;
  });
})(window);
