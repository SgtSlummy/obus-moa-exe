"""Bounded, secret-free local event stream for OBus AUI consumers."""
from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from copy import deepcopy
from typing import Any, Iterator

from backend.secret_safety import redact_value, safe_route_id


class RouteEventHub:
    """Thread-safe bounded event history with a polling and streaming view."""

    def __init__(self, max_events: int = 256) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max(20, int(max_events)))
        self._condition = threading.Condition()

    def publish(self, route_id: str, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "id": f"evt-{uuid.uuid4().hex[:16]}",
            "created_at": time.time(),
            "route_id": safe_route_id(route_id),
            "type": str(event_type),
            "payload": redact_value(payload or {}),
        }
        with self._condition:
            self._events.append(event)
            self._condition.notify_all()
        return deepcopy(event)

    def contains_id(self, event_id: str) -> bool:
        with self._condition:
            return any(event["id"] == event_id for event in self._events)

    def snapshot(self, route_id: str | None = None, limit: int = 50, since: str | None = None) -> list[dict[str, Any]]:
        with self._condition:
            events = list(self._events)
        if since:
            cursor_index = next((index for index, event in enumerate(events) if event["id"] == since), None)
            if cursor_index is None:
                return []
            events = events[cursor_index + 1 :]
        if route_id:
            events = [event for event in events if event["route_id"] == route_id]
        return deepcopy(events[-max(1, min(int(limit), 100)) :])

    def stream(self, route_id: str | None = None, since: str | None = None, heartbeat_seconds: float = 10.0) -> Iterator[str]:
        cursor = since
        while True:
            if cursor and not self.contains_id(cursor):
                yield "event: route.cursor_reset\ndata: {\"reset\":true}\n\n"
                cursor = None
            events = self.snapshot(route_id=route_id, since=cursor, limit=100)
            if events:
                for event in events:
                    cursor = event["id"]
                    yield f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event, separators=(',', ':'), ensure_ascii=False)}\n\n"
                continue
            with self._condition:
                self._condition.wait(timeout=heartbeat_seconds)
            yield ": heartbeat\n\n"


ROUTE_EVENTS = RouteEventHub()
