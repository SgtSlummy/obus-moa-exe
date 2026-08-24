import unittest

from fastapi.testclient import TestClient

import backend.main as backend


class RouteBlockActionTests(unittest.TestCase):
    def test_route_block_exposes_reinput_and_retry_actions(self):
        html = TestClient(backend.app).get("/").text
        for control_id in ("reinput-latest", "retry-latest"):
            self.assertIn(f'id="{control_id}"', html)
        for marker in ("reinputLatestPrompt", "retryLatestRoute", "route.reinput_latest", "route.retry_latest"):
            self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
