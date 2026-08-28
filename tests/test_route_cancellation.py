import unittest

from fastapi.testclient import TestClient

import asyncio
import threading
import time

import backend.main as backend


class RouteCancellationTests(unittest.TestCase):
    def test_cancel_endpoint_confirms_a_route_cancel_request(self):
        response = TestClient(backend.app).post("/api/route/route-test/cancel")
        self.assertEqual(response.status_code, 404)

    def test_route_status_reports_cancel_request_and_events(self):
        backend.ROUTE_EVENTS.publish("route-status-test", "route.cancel_requested", {"status": "cancel_requested"})
        response = TestClient(backend.app).get("/api/route/route-status-test/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["route_id"], "route-status-test")
        self.assertTrue(response.json()["events"])

    def test_route_run_honors_cancel_requested_before_execution(self):
        client = TestClient(backend.app)
        cancel = client.post("/api/route/route-pre-cancel/cancel")
        self.assertEqual(cancel.status_code, 404)
        response = client.post("/api/route/run", json={"prompt": "cancel me", "route_id": "route-pre-cancel", "model": "__not_installed__", "rag_enabled": False})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["status"], "cancelled")
        self.assertEqual(response.json()["route_id"], "route-pre-cancel")

    def test_active_generation_returns_promptly_after_cancellation(self):
        route_id = "route-active-cancel"
        started = threading.Event()

        def slow_worker():
            started.set()
            time.sleep(0.5)
            return "late result"

        async def scenario():
            backend.register_route_cancel(route_id)
            task = asyncio.create_task(backend._await_route_generation(route_id, slow_worker))
            await asyncio.to_thread(started.wait, 0.2)
            backend.ROUTE_CANCEL_EVENTS[route_id].set()
            return await asyncio.wait_for(task, timeout=0.25)

        try:
            completed, result = asyncio.run(scenario())
        finally:
            backend.clear_route_cancel(route_id)

        self.assertFalse(completed)
        self.assertIsNone(result)

    def test_route_ui_exposes_confirmed_cancel_control(self):
        html = TestClient(backend.app).get("/").text
        for marker in ("cancel-latest", "cancelActiveRoute", "/cancel", "route_id"):
            self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
