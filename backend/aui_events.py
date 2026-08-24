"""Bounded, secret-free local event stream for OBus AUI consumers."""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from collections import deque
from copy import deepcopy
from typing import Any, Iterator

_SECRET_KEYS = {"api_key", "apikey", "token", "access_token", "refresh_token", "password", "secret", "private_key", "credential"}
_SECRET_VALUE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+|\bsk-[A-Za-z0-9_-]{12,}|\bgh[opusr]_[A-Za-z0-9_]{12,}")


def _safe_value(value: Any, key: str | None = None) -> Any:
    if key and key.casefold() in _SECRET_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(child_key): _safe_value(child, str(child_key)) for child_key, child in value.items() if str(child_key).casefold() not in _SECRET_KEYS}
    if isinstance(value, list):
        return [_safe_value(child) for child in value[:20]]
    if isinstance(value, str):
        return _SECRET_VALUE.sub("[REDACTED]", value[:2000])
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:500]


class RouteEventHub:
    """Thread-safe bounded event history with a polling and streaming view."""

    def __init__(self, max_events: int = 256) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max(20, int(max_events)))
        self._condition = threading.Condition()

    def publish(self, route_id: str, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "id": f"evt-{uuid.uuid4().hex[:16]}",
            "created_at": time.time(),
            "route_id": str(route_id),
            "type": str(event_type),
            "payload": _safe_value(payload or {}),
        }
        with self._condition:
            self._events.append(event)
            self._condition.notify_all()
        return deepcopy(event)

    def snapshot(self, route_id: str | None = None, limit: int = 50, since: str | None = None) -> list[dict[str, Any]]:
        with self._condition:
            events = list(self._events)
        if route_id:
            events = [event for event in events if event["route_id"] == route_id]
        if since:
            for index, event in enumerate(events):
                if event["id"] == since:
                    events = events[index + 1 :]
                    break
        return deepcopy(events[-max(1, min(int(limit), 100)) :])

    def stream(self, route_id: str | None = None, since: str | None = None, heartbeat_seconds: float = 10.0) -> Iterator[str]:
        cursor = since
        while True:
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
