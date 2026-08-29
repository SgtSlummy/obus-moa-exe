"use strict";

(function installObusRouteEvents(root) {
  const OBusRouteEvents = {
    create({url = "/api/route/events/stream", pollUrl = "/api/route/events", pollCursorParam = "since", eventTypes = [], onEvent, onError, pollIntervalMs = 1200} = {}) {
      const knownTypes = ["route.started", "route.plan_ready", "route.local_started", "route.local_complete", "route.cancel_requested", "route.deliberation_started", "route.deliberation_complete", "route.deliberation_failed", "route.complete", "route.failed", "route.cancelled", "route.cursor_reset"];
      const effectiveTypes = eventTypes.length ? eventTypes : knownTypes;
      const allowed = new Set(effectiveTypes);
      let lastEventId = "";
      const startPolling = (initialSince = lastEventId) => {
        let closed = false;
        let since = initialSince;
        const fallback = {readyState: 1, _pollingFallback: true, close() { closed = true; this.readyState = 2; }};
        const poll = async () => {
          if (closed) return;
          try {
            const separator = pollUrl.includes("?") ? "&" : "?";
            const headers = {};
            try { const token = root.sessionStorage?.getItem("obus-access-token"); if (token) headers["X-OBus-Access"] = token; } catch (_) {}
            const response = await root.fetch(`${pollUrl}${since ? `${separator}${encodeURIComponent(pollCursorParam)}=${encodeURIComponent(since)}` : ""}`, {headers});
            if (response.status === 410) { since = ""; }
            if (response.status !== 410 && !response.ok) throw new Error(`route event polling failed (${response.status})`);
            const payload = response.status === 410 ? [] : await response.json();
            const events = Array.isArray(payload) ? payload : Array.isArray(payload?.events) ? payload.events : [];
            events.forEach((payload) => {
              const type = payload.type || payload.event_type || "";
              const normalized = payload.type ? payload : {...payload, type};
              since = payload.id || payload.sequence || since;
              if (!allowed.size || allowed.has(type)) { if (typeof onEvent === "function") onEvent(normalized, {type}); }
            });
          } catch (error) { if (typeof onError === "function") onError(error, fallback); }
          if (!closed) root.setTimeout(poll, pollIntervalMs);
        };
        poll();
        return fallback;
      };
      let accessToken = "";
      try { accessToken = root.sessionStorage?.getItem("obus-access-token") || ""; } catch (_) {}
      if (accessToken) return startPolling();
      if (root.EventSource) {
        const source = new root.EventSource(url);
        const handle = (event) => {
          let payload = {};
          try { payload = JSON.parse(event.data || "{}"); } catch (_) { payload = {type: event.type, payload: {}}; }
          const type = payload.type || payload.event_type || event.type || "";
          if (!payload.type) payload = {...payload, type};
          if ((!allowed.size || allowed.has(type)) && typeof onEvent === "function") onEvent(payload, event);
          lastEventId = payload.id || payload.sequence || event.lastEventId || lastEventId;
        };
        new Set([...knownTypes, ...effectiveTypes]).forEach((type) => source.addEventListener(type, handle));
        let fallback = null;
        source.onerror = (event) => {
          if (!fallback) { source.close(); fallback = startPolling(lastEventId); }
          if (typeof onError === "function") onError(event, fallback);
        };
        return source;
      }
      return startPolling();
    },
  };

  root.OBusRouteEvents = OBusRouteEvents;
})(window);
