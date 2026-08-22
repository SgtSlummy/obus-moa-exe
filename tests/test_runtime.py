import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as backend
import obus_launcher


class RuntimeContractTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(backend.app)
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.tempdir.name) / "obus_state.json"
        self.memory_file = Path(self.tempdir.name) / "memory.json"
        self.state_patch = patch.object(backend, "STATE_FILE", self.state_file)
        self.memory_patch = patch.object(backend, "MEMORY_FILE", self.memory_file, create=True)
        self.state_patch.start()
        self.memory_patch.start()

    def tearDown(self):
        self.memory_patch.stop()
        self.state_patch.stop()
        self.tempdir.cleanup()

    def test_modern_ui_exposes_real_controls_not_simulated_alerts(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('data-build="obus-modern-8"', html)
        for control_id in (
            'rag-toggle', 'refresh-btn', 'route-btn', 'clear-memory',
            'provider-list', 'agent-list', 'deck-list', 'result-output', 'memory-hub-list'
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertNotIn('simulated', html.lower())

    def test_dashboard_reports_memory_hub_integrations(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        hub = response.json()["memory_hub"]
        self.assertIn("hermes", hub)
        self.assertIn("mempalace", hub)
        self.assertIn("mem0", hub)
        self.assertIn("tarot_rag", hub)
        self.assertIn("mythos_router", hub)
        self.assertIn("moa_router", hub)

    def test_memory_hub_search_endpoint_is_local_and_secret_safe(self):
        self.memory_file.write_text(json.dumps([{"id": "x", "text": "OBus integration memory"}]), encoding="utf-8")
        response = self.client.get("/api/memory/search", params={"query": "integration"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.json()["results"][0]["source"], {"obus", "mempalace", "tarot_rag"})
        self.assertNotIn("api_key", json.dumps(response.json()).lower())

    def test_moa_router_command_uses_local_endpoint_without_credentials(self):
        command = backend.build_moa_router_command("test task", "llama3.2:latest")
        if command is not None:
            serialized = " ".join(command)
            self.assertIn("moa_router.py", serialized)
            self.assertIn("http://127.0.0.1:11434/v1", serialized)
            self.assertNotIn("api_key", serialized.lower())

    def test_route_plan_includes_shared_memory_hub_context(self):
        response = self.client.post("/api/route/plan", json={
            "prompt": "Paris memory context",
            "deck_mode": "auto", "rag_enabled": True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("hub_results", response.json()["rag"])

    def test_dashboard_reports_live_ollama_and_provider_state(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("ollama", payload)
        self.assertIsInstance(payload["ollama"]["connected"], bool)
        self.assertIn("providers", payload)
        self.assertGreaterEqual(len(payload["providers"]), 4)
        self.assertIn("settings", payload)
        self.assertIn("rag_enabled", payload["settings"])

    def test_rag_toggle_persists_through_settings_endpoint(self):
        response = self.client.put("/api/settings", json={"rag_enabled": False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["rag_enabled"])
        persisted = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertFalse(persisted["settings"]["rag_enabled"])

    def test_clear_memory_is_a_real_backend_operation(self):
        self.memory_file.write_text(json.dumps([{"text": "temporary"}]), encoding="utf-8")
        response = self.client.delete("/api/memory")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["chunks"], 0)
        self.assertEqual(json.loads(self.memory_file.read_text(encoding="utf-8")), [])

    def test_post_route_plan_matches_frontend_contract(self):
        response = self.client.post(
            "/api/route/plan",
            json={"prompt": "Design a secure service", "deck_mode": "auto", "rag_enabled": True},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["prompt"], "Design a secure service")
        self.assertIn("selected_deck", payload)
        self.assertIn("dynamic_assignments", payload["agents"])

    def test_launcher_waits_for_server_before_opening_browser(self):
        with patch.object(obus_launcher.urllib.request, "urlopen") as open_mock:
            open_mock.side_effect = [OSError("not ready"), object()]
            self.assertTrue(obus_launcher.wait_for_server("http://127.0.0.1:8080/health", attempts=2, delay=0))
            self.assertEqual(open_mock.call_count, 2)

    def test_spec_packages_static_files_beside_backend_module(self):
        spec = (Path(__file__).parents[1] / "OBus.spec").read_text(encoding="utf-8")
        self.assertIn('"backend/static', spec.replace('\\\\', '/'))

    def test_create_edit_and_delete_reference_only_solomons_key(self):
        created = self.client.post("/api/keys", json={
            "name": "Test Local Key",
            "provider": "ollama",
            "model": "llama3.2:latest",
            "base_url": "http://127.0.0.1:11434",
            "env_var": None,
            "capabilities": ["coding", "reasoning"],
            "state": "ready",
            "local": True,
            "can_aggregate": True,
        })
        self.assertEqual(created.status_code, 200)
        key = created.json()
        self.assertTrue(key["id"].startswith("key-"))
        self.assertNotIn("api_key", key)
        self.assertNotIn("token", key)

        edited = self.client.put(f"/api/keys/{key['id']}", json={
            "name": "Edited Local Key",
            "model": "llama3.2:latest",
            "capabilities": ["coding", "tools", "reasoning"],
        })
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["name"], "Edited Local Key")
        self.assertIn("tools", edited.json()["capabilities"])

        deleted = self.client.delete(f"/api/keys/{key['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["success"])
        self.assertFalse(any(item["id"] == key["id"] for item in self.client.get("/api/keys").json()))

    def test_card_can_switch_between_auto_and_manual_key_pairing(self):
        cards = self.client.get("/api/cards").json()
        card_id = cards[0]["id"]
        keys = self.client.get("/api/keys").json()
        key_id = keys[0]["id"]

        manual = self.client.put(f"/api/cards/{card_id}", json={
            "assignment_mode": "manual",
            "key_id": key_id,
        })
        self.assertEqual(manual.status_code, 200)
        self.assertEqual(manual.json()["assignment_mode"], "manual")
        self.assertEqual(manual.json()["assigned_key_id"], key_id)

        automatic = self.client.put(f"/api/cards/{card_id}", json={"assignment_mode": "auto"})
        self.assertEqual(automatic.status_code, 200)
        self.assertEqual(automatic.json()["assignment_mode"], "auto")
        self.assertIsNone(automatic.json()["assigned_key_id"])

    def test_key_management_ui_has_guided_workflow_and_pairing_controls(self):
        html = self.client.get("/").text
        for control_id in ("add-key", "key-dialog", "key-provider", "key-name", "key-model", "key-env-var", "save-key"):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("pairing-select", html)
        self.assertNotIn('name="api_key"', html)

    def test_dashboard_lists_full_key_catalog_with_context_windows_and_unique_sigils(self):
        dashboard = self.client.get("/api/dashboard").json()
        providers = dashboard["providers"]
        self.assertGreaterEqual(len(providers), 12)
        sigils = []
        for provider in providers:
            self.assertGreater(provider["max_context_tokens"], 0)
            self.assertTrue(provider["sigil"].startswith("/static/art/keys/"))
            sigils.append(provider["sigil"])
        self.assertEqual(len(sigils), len(set(sigils)))

    def test_every_tarot_card_has_unique_bundled_detailed_art(self):
        cards = self.client.get("/api/dashboard").json()["cards"]
        images = [card["image"] for card in cards]
        self.assertEqual(len(images), len(set(images)))
        for image in images:
            self.assertTrue(image.startswith("/static/art/cards/"))
            response = self.client.get(image)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/webp")

    def test_complete_deck_uses_distinct_fantasy_realistic_webp_art(self):
        from io import BytesIO
        from PIL import Image
        cards = self.client.get("/api/dashboard").json()["cards"]
        manifest_path = Path(__file__).resolve().parents[1] / "backend" / "static" / "art" / "cards" / "generation-manifest.json"
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["provider"], "Pollinations legacy Flux anonymous")
        self.assertEqual(len(manifest["cards"]), 78)
        self.assertGreaterEqual(len(manifest["research_sources"]), 7)
        hashes = set()
        for card in cards:
            self.assertEqual(card["art_style"], "fantasy-realistic-painterly")
            self.assertTrue(card["image"].endswith(".webp"))
            response = self.client.get(card["image"])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/webp")
            self.assertGreater(len(response.content), 30000)
            image = Image.open(BytesIO(response.content)).convert("RGB")
            self.assertEqual(image.size, (720, 1120))
            center = __import__("numpy").asarray(image.crop((80, 120, 640, 920)))
            self.assertGreater(float(center.mean()), 18.0)
            self.assertGreater(float(center.std()), 18.0)
            hashes.add(__import__("hashlib").sha256(response.content).hexdigest())
        self.assertEqual(len(hashes), 78)

    def test_full_tarot_deck_exposes_78_distinct_agent_personas(self):
        cards = self.client.get("/api/dashboard").json()["cards"]
        self.assertEqual(len(cards), 78)
        self.assertEqual(len({card["id"] for card in cards}), 78)
        self.assertEqual(len({card["image"] for card in cards}), 78)
        for card in cards:
            self.assertIn(card["arcana"], {"major", "minor"})
            self.assertTrue(card["capabilities"])
            self.assertTrue(card["agent_type"])

    def test_github_app_configuration_persists_references_only(self):
        response = self.client.put("/api/integrations/github-app", json={
            "app_id": "12345",
            "installation_id": "67890",
            "owner": "example-owner",
            "repo": "shared-memory",
            "branch": "main",
            "memory_path": "obus/memory.json",
            "private_key_path": "C:/secure/github-app.pem",
            "app_slug": "obus-memory",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["owner"], "example-owner")
        serialized = json.dumps(payload).lower()
        self.assertNotIn("private_key", serialized.replace("private_key_path", ""))
        persisted = json.loads(self.state_file.read_text(encoding="utf-8"))["github_memory"]
        self.assertEqual(persisted["private_key_path"], "C:/secure/github-app.pem")

        rejected = self.client.put("/api/integrations/github-app", json={
            "app_id": "1", "installation_id": "2", "owner": "o", "repo": "r",
            "private_key_path": "-----BEGIN PRIVATE KEY-----secret",
        })
        self.assertEqual(rejected.status_code, 400)

    def test_memory_merge_deduplicates_shared_github_chunks(self):
        local = [{"id": "a", "text": "local"}, {"id": "same", "text": "old"}]
        remote = [{"id": "b", "text": "remote"}, {"id": "same", "text": "new"}]
        merged = backend.merge_memory_chunks(local, remote)
        self.assertEqual([item["id"] for item in merged], ["a", "same", "b"])
        self.assertEqual(next(item for item in merged if item["id"] == "same")["text"], "new")

    def test_codex_status_endpoint_uses_real_cli_contract(self):
        response = self.client.get("/api/integrations/codex/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("available", payload)
        self.assertIn("logged_in", payload)
        self.assertNotIn("token", json.dumps(payload).lower())

    def test_codex_device_output_parser_extracts_clickable_url_and_code(self):
        output = (
            "Open this link in your browser and sign in to your account\r\n"
            "https://auth.openai.com/codex/device"
            "2. Enter this one-time code(expires in 15 minutes)\r\n"
            "5M9U-MSRFVContinue only if you started this login in Codex."
        )
        parsed = backend.parse_codex_device_output(output)
        self.assertEqual(parsed["verification_url"], "https://auth.openai.com/codex/device")
        self.assertEqual(parsed["user_code"], "5M9U-MSRFV")

    def test_integrations_ui_has_github_app_sync_and_codex_login_controls(self):
        html = self.client.get("/").text
        for control_id in (
            "codex-login", "codex-status", "github-app-form", "github-app-id",
            "github-installation-id", "github-private-key-path", "github-memory-push",
            "github-memory-pull", "github-app-test", "codex-device-link",
            "codex-device-code", "codex-open-login"
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("window.open('https://auth.openai.com/codex/device'", html)

    def test_arcana_forge_catalog_contains_all_curated_projects(self):
        response = self.client.get("/api/forge/catalog")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["name"], "Arcana Forge")
        self.assertEqual(len(payload["projects"]), 29)
        ids = {item["id"] for item in payload["projects"]}
        self.assertTrue({"vllm", "gptcache", "llmlingua", "mempalace", "llmfit", "crewai"} <= ids)
        for project in payload["projects"]:
            self.assertIn(project["risk"], {"low", "medium", "high"})
            self.assertTrue(project["url"].startswith("https://github.com/"))

    def test_arcana_forge_selection_grants_tools_to_compatible_agents(self):
        cards = self.client.get("/api/cards").json()
        agent_ids = [cards[0]["id"], next(card["id"] for card in cards if card["id"] == "card-hermit")]
        response = self.client.put("/api/forge/selection", json={
            "project_ids": ["headroom", "mempalace", "codeburn"],
            "agent_ids": agent_ids,
            "auto_assign": True,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload["selected_projects"]), {"headroom", "mempalace", "codeburn"})
        updated = {card["id"]: card for card in self.client.get("/api/cards").json()}
        self.assertTrue(updated[agent_ids[0]]["tool_ids"])
        self.assertIn("mempalace", updated["card-hermit"]["tool_ids"])

    def test_arcana_forge_returns_safe_install_plans_and_blocks_catalog_only_tools(self):
        plan = self.client.get("/api/forge/install/mempalace/plan")
        self.assertEqual(plan.status_code, 200)
        self.assertEqual(plan.json()["argv"][:3], ["uv", "tool", "install"])
        self.assertNotIsInstance(plan.json()["argv"], str)
        blocked = self.client.get("/api/forge/install/ghost-downloader/plan")
        self.assertEqual(blocked.status_code, 400)

    def test_arcana_forge_hardware_recommendation_uses_local_machine_stack(self):
        response = self.client.get("/api/forge/recommend")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("projects", payload)
        ids = {item["id"] for item in payload["projects"]}
        self.assertTrue({"llmfit", "vllm", "gptcache", "llmlingua", "mempalace"} <= ids)

    def test_arcana_forge_setup_ui_is_agent_selectable(self):
        html = self.client.get("/").text
        for control_id in ("forge-catalog", "forge-agent-list", "forge-apply", "forge-recommend", "forge-search", "forge-status"):
            self.assertIn(f'id="{control_id}"', html)

    def test_arcana_forge_reports_operational_evidence_and_blockers(self):
        projects = {item["id"]: item for item in self.client.get("/api/forge/catalog").json()["projects"]}
        for project in projects.values():
            self.assertIsInstance(project["operational"], bool)
            self.assertIsInstance(project["evidence"], list)
        self.assertTrue(projects["gptcache"]["operational"])
        self.assertTrue(projects["mempalace"]["operational"])
        self.assertFalse(projects["vllm"]["operational"])
        self.assertIn("CUDA", projects["vllm"]["blocker"])

    def test_router_selects_relevant_agents_from_full_78_card_deck(self):
        response = self.client.post("/api/route/plan", json={
            "prompt": "Investigate a security threat, contain the incident, debug the failure, and recover safely",
            "deck_mode": "auto", "rag_enabled": True,
        })
        self.assertEqual(response.status_code, 200)
        ids = {item["agent_id"] for item in response.json()["agents"]["dynamic_assignments"]}
        self.assertTrue(ids & {"card-devil", "card-tower", "card-strength", "card-hermit"}, ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
