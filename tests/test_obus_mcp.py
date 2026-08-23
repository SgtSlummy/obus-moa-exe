import json
import unittest
from unittest.mock import patch

import obus_mcp_server as mcp


class OBusMcpTests(unittest.TestCase):
    def test_mcp_lists_connected_rag_memory_and_route_tools(self):
        names = {tool["name"] for tool in mcp.tool_catalog()}
        self.assertTrue({"obus_status", "obus_memory_search", "obus_memory_add", "obus_route_plan", "obus_route_run", "obus_connection", "obus_tentacle_status", "obus_tentacle_run"} <= names)

    def test_mcp_calls_backend_without_returning_secret_values(self):
        with patch.object(mcp, "request_json", return_value={"provider": "obus", "base_url": "http://127.0.0.1:38174/v1", "api_key_env": "OCCULTBUS_API_KEY"}) as request:
            result = mcp.call_tool("obus_connection", {})
        self.assertEqual(request.call_args.args[0], "/api/provider/connection")
        serialized = json.dumps(result).lower()
        self.assertNotIn('"api_key":', serialized)
        self.assertEqual(result["api_key_env"], "OCCULTBUS_API_KEY")

    def test_mcp_initialize_and_tools_list_protocol(self):
        initialized = mcp.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")
        listed = mcp.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertGreaterEqual(len(listed["result"]["tools"]), 6)
    def test_mcp_transport_ascii_escapes_unicode_tarot_and_kawaii(self):
        encoded = mcp.serialize_message({"symbol": "🃏", "face": "(◕‿◕✿)"})
        encoded.encode("ascii")
        self.assertIn("\\ud83c", encoded)

    def test_packaged_launcher_exposes_stdio_mcp_mode(self):
        root = __import__("pathlib").Path(__file__).parents[1]
        self.assertIn('"--mcp"', (root / "obus_launcher.py").read_text(encoding="utf-8"))
        self.assertIn('"obus_mcp_server"', (root / "OBus.spec").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
