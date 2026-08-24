"use strict";

(function installObusRouteEvents(root) {
  const OBusRouteEvents = {
    create({url = "/api/route/events/stream", eventTypes = [], onEvent, onError} = {}) {
      if (!root.EventSource) return null;
      const source = new root.EventSource(url);
      const handle = (event) => {
        let payload = {};
        try {
          payload = JSON.parse(event.data || "{}");
        } catch (_) {
          payload = {type: event.type, payload: {}};
        }
        if (typeof onEvent === "function") onEvent(payload, event);
      };
      eventTypes.forEach((type) => source.addEventListener(type, handle));
      source.onerror = (event) => {
        if (typeof onError === "function") onError(event, source);
      };
      return source;
    },
  };

  root.OBusRouteEvents = OBusRouteEvents;
})(window);
