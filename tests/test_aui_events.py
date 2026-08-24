import unittest

from fastapi.testclient import TestClient

import backend.main as backend
from backend.aui_events import RouteEventHub


class AUIEventTests(unittest.TestCase):
    def test_event_hub_redacts_secret_shaped_payloads(self):
        hub = RouteEventHub()
        event = hub.publish("route-test", "route.started", {"model": "local", "api_key": "secret-value", "detail": "Bearer credential-value"})
        self.assertNotIn("api_key", event["payload"])
        self.assertNotIn("secret-value", str(event))
        self.assertNotIn("Bearer", str(event))
        self.assertNotIn("credential-value", str(event))

    def test_route_events_endpoint_returns_bounded_events(self):
        backend.ROUTE_EVENTS.publish("route-test", "route.started", {"status": "planning"})
        response = TestClient(backend.app).get("/api/route/events?route_id=route-test")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_ui_exposes_optional_event_stream_with_polling_compatible_fallback(self):
        html = TestClient(backend.app).get("/").text
        self.assertIn('/static/aui/route-events.js', html)
        self.assertIn('startRouteEventStream', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
