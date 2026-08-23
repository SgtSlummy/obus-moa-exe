import json
import os
import tempfile
import threading
import time
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
        self.assertNotIn("data-build", html)
        self.assertNotIn("build obus", html.lower())
        self.assertIn("Local → GPT 5.6 Luna", html)
        for control_id in (
            'rag-toggle', 'refresh-btn', 'route-btn', 'clear-memory',
            'provider-list', 'agent-list', 'deck-list', 'result-output', 'memory-hub-list',
            'quantum-inference-status', 'quantum-refresh'
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
        self.assertNotIn("build", payload)
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

    def test_quantum_inference_initializes_and_updates_only_for_missing_information(self):
        state = backend.normalize_state({"settings": {"selected_model": "gpt-oss:20b", "selected_deck": "auto"}})
        initial, changed = backend.update_quantum_inference(state, now=60)
        self.assertTrue(changed)
        self.assertTrue(initial["setup_complete"])
        self.assertEqual(initial["chosen_variable"], "ui_poll_interval_ms")
        self.assertIn(initial["ui_poll_interval_ms"], backend.QUANTUM_POLL_INTERVALS_MS)
        self.assertFalse(initial["quantum_hardware"])
        held, changed = backend.update_quantum_inference(state, now=120)
        self.assertFalse(changed)
        self.assertEqual(held["flow_state"], "holding-present-information")
        self.assertEqual(initial["ui_poll_interval_ms"], held["ui_poll_interval_ms"])
        state["settings"]["selected_model"] = ""
        follow_up, changed = backend.update_quantum_inference(state, now=180)
        self.assertTrue(changed)
        self.assertEqual(follow_up["missing_items"], ["selected_model"])
        self.assertNotEqual(initial["ui_poll_interval_ms"], follow_up["ui_poll_interval_ms"])
        self.assertEqual(state["runtime_settings"]["max_parallel"], 8)

    def test_quantum_inference_api_is_visible_and_secret_safe(self):
        dashboard = self.client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("quantum_inference", dashboard.json())
        response = self.client.get("/api/quantum-inference")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["chosen_variable"], "ui_poll_interval_ms")
        self.assertNotIn("api_key", json.dumps(payload).lower())

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
        self.assertEqual(obus_launcher.APP_PORT, 38173)
        self.assertEqual(obus_launcher.APP_URL, "http://127.0.0.1:38173/")
        self.assertEqual(obus_launcher.HEALTH_URL, "http://127.0.0.1:38173/health")
        launcher_source = (Path(__file__).parents[1] / "obus_launcher.py").read_text(encoding="utf-8")
        self.assertNotIn("8080", launcher_source)
        self.assertNotIn("?build=", launcher_source)
        with patch.object(obus_launcher.urllib.request, "urlopen") as open_mock:
            open_mock.side_effect = [OSError("not ready"), object()]
            self.assertTrue(obus_launcher.wait_for_server(obus_launcher.HEALTH_URL, attempts=2, delay=0))
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
        self.assertIn("Test &amp; enable", html)
        self.assertIn("Ready — set automatically after successful live test", html)
        self.assertIn("Configured:", html)
        self.assertIn("Verified:", html)
        self.assertIn('data-page="providers">⌘ Keys</button>', html)
        self.assertIn("Solomon’s Key registry", html)
        self.assertNotIn(">⌘ Providers</button>", html)
        self.assertNotIn("Provider readiness", html)
        self.assertNotIn('name="api_key"', html)

    def test_key_live_test_promotes_staged_to_ready_atomically(self):
        secret = "unit-test-secret-that-must-never-leak"
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": secret}, clear=False), patch.object(
            backend, "probe_key_live", return_value={"success": True, "message": "Live model-list probe succeeded", "status_code": 200}
        ):
            response = self.client.post("/api/providers/key-anthropic/test")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["state"], "ready")
        self.assertTrue(payload["verified"])
        self.assertNotIn(secret, json.dumps(payload))
        persisted = next(item for item in json.loads(self.state_file.read_text(encoding="utf-8"))["keys"] if item["id"] == "key-anthropic")
        self.assertEqual(persisted["state"], "ready")
        self.assertTrue(persisted["verified"])
        self.assertTrue(persisted["approved"])
        self.assertTrue(persisted["active"])
        self.assertTrue(persisted["verified_at"])

    def test_failed_live_test_demotes_ready_key_and_redacts_credentials(self):
        secret = "invalid-secret-that-must-never-leak"
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": secret}, clear=False), patch.object(
            backend, "probe_key_live", return_value={"success": True, "message": "Initial live probe succeeded", "status_code": 200}
        ):
            promoted = self.client.post("/api/providers/key-anthropic/test").json()
        self.assertEqual(promoted["state"], "ready")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": secret}, clear=False), patch.object(
            backend, "probe_key_live", return_value={"success": False, "message": "Authentication rejected", "status_code": 401, "reason": "authentication_rejected"}
        ):
            response = self.client.post("/api/providers/key-anthropic/test")
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["state"], "staged")
        self.assertFalse(payload["verified"])
        self.assertEqual(payload["reason"], "authentication_rejected")
        self.assertNotIn(secret, json.dumps(payload))

    def test_successful_test_keeps_disabled_key_disabled(self):
        self.client.put("/api/keys/key-anthropic", json={"state": "disabled"})
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-only"}, clear=False), patch.object(
            backend, "probe_key_live", return_value={"success": True, "message": "Live probe succeeded", "status_code": 200}
        ):
            payload = self.client.post("/api/providers/key-anthropic/test").json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["state"], "disabled")
        self.assertTrue(payload["verified"])
        self.assertFalse(payload["connected"])

    def test_missing_authorization_reference_never_calls_live_probe(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_API_KEY", None)
            with patch.object(backend, "probe_key_live") as probe:
                payload = self.client.post("/api/providers/key-google-gemini/test").json()
        self.assertFalse(payload["success"])
        self.assertEqual(payload["reason"], "missing_reference")
        self.assertEqual(payload["state"], "staged")
        probe.assert_not_called()

    def test_manual_ready_cannot_bypass_live_verification(self):
        response = self.client.put("/api/keys/key-google-gemini", json={"state": "ready"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Test & enable", response.json()["detail"])

    def test_builtin_keys_use_distinct_public_domain_solomon_seals(self):
        dashboard = self.client.get("/api/dashboard").json()
        providers = [item for item in dashboard["providers"] if item["id"] in backend.BUILTIN_KEY_IDS]
        self.assertEqual(len(providers), 16)
        self.assertEqual(len({item["solomon_seal"] for item in providers}), 16)
        self.assertEqual(len({item["solomon_seal_number"] for item in providers}), 16)
        manifest_path = Path(__file__).resolve().parents[1] / "backend" / "static" / "art" / "keys" / "solomon-key-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["keys"]), 16)
        self.assertTrue(all(item["license"] == "Public domain" for item in manifest["keys"]))
        self.assertTrue(all(item["source_page"].startswith("https://commons.wikimedia.org/wiki/File:") for item in manifest["keys"]))
        self.assertEqual({item["key_id"] for item in manifest["keys"]}, {item["id"] for item in providers})
        hashes = set()
        for provider in providers:
            response = self.client.get(provider["sigil"])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/svg+xml")
            self.assertIn(provider["solomon_seal"].upper().encode(), response.content.upper())
            hashes.add(__import__("hashlib").sha256(response.content).hexdigest())
        self.assertEqual(len(hashes), 16)

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

    def test_complete_deck_uses_distinct_public_domain_hand_drawn_webp_art(self):
        from io import BytesIO
        from PIL import Image
        cards = self.client.get("/api/dashboard").json()["cards"]
        manifest_path = Path(__file__).resolve().parents[1] / "backend" / "static" / "art" / "cards" / "generation-manifest.json"
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["provider"], "Wikimedia Commons public-domain scans")
        self.assertEqual(manifest["artist"], "Pamela Colman Smith")
        self.assertEqual(manifest["style"], "restored-public-domain-hand-drawn-watercolor")
        self.assertEqual(len(manifest["cards"]), 78)
        self.assertGreaterEqual(len(manifest["research_sources"]), 7)
        self.assertTrue(all(record["license"] == "Public domain" for record in manifest["cards"]))
        self.assertTrue(all(record["source_page"].startswith("https://commons.wikimedia.org/wiki/File:") for record in manifest["cards"]))
        hashes = set()
        for card in cards:
            self.assertEqual(card["art_style"], "restored-public-domain-hand-drawn-watercolor")
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

    def test_default_state_contains_empty_room_and_forum_collections(self):
        state = backend.load_state()
        self.assertEqual(state["rooms"], [])
        self.assertEqual(state["forum_threads"], [])
        self.assertEqual(state["room_messages"], [])

    def test_create_room_validates_cards_and_selects_one_chymeria(self):
        cards = backend.load_state()["cards"]
        selected = [cards[0]["id"], cards[1]["id"]]
        response = self.client.post("/api/rooms", json={
            "name": "Security hand",
            "card_ids": selected,
            "mode": "adversarial",
        })
        self.assertEqual(response.status_code, 200)
        room = response.json()
        self.assertTrue(room["id"].startswith("room-"))
        self.assertEqual(room["card_ids"], selected)
        self.assertEqual(room["mode"], "adversarial")
        self.assertIn("card_id", room["chymeria"])
        self.assertIn("key_id", room["chymeria"])

        duplicate = self.client.post("/api/rooms", json={
            "name": "Bad hand", "card_ids": [selected[0], selected[0]],
        })
        self.assertEqual(duplicate.status_code, 422)

    def test_room_council_plan_has_collaborative_and_adversarial_phases(self):
        room = {
            "id": "room-test", "name": "Test", "card_ids": ["card-hermit", "card-devil"],
            "mode": "collaborative", "chymeria": {"card_id": "card-hermit", "key_id": "key-local-ollama"},
        }
        collaborative = backend.build_room_council_plan(room, "Design a secure service")
        self.assertEqual([phase["name"] for phase in collaborative["phases"]], ["draft", "improve", "synthesize"])
        room["mode"] = "adversarial"
        adversarial = backend.build_room_council_plan(room, "Stress-test room isolation")
        self.assertEqual([phase["name"] for phase in adversarial["phases"]], ["draft", "triage", "attack", "verdict"])

    def test_simple_room_prompt_short_circuits_council(self):
        room = {
            "id": "room-test", "name": "Test", "card_ids": ["card-hermit"],
            "mode": "collaborative", "chymeria": {"card_id": "card-hermit", "key_id": "key-local-ollama"},
        }
        plan = backend.build_room_council_plan(room, "What is 2 + 2?")
        self.assertTrue(plan["short_circuit"])

    def test_room_run_persists_one_public_chymeria_decision(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": True, "models": ["llama3.2:latest"]}):
            created = self.client.post("/api/rooms", json={
                "name": "Room Alpha", "card_ids": ["card-hermit", "card-magician"],
            })
            self.assertEqual(created.status_code, 200)
            room_id = created.json()["id"]

            def fake_complete(**kwargs):
                phase = kwargs["phase"]
                return json.dumps({
                    "position": f"{phase} position",
                    "confidence": "high",
                    "rationale": "deterministic test result",
                    "evidence_refs": [],
                    "unresolved_questions": [],
                    "requested_responses": [],
                    "status": "approved" if phase in {"synthesize", "verdict"} else "provisional",
                })

            with patch.object(backend, "ROOM_COMPLETE", side_effect=fake_complete):
                response = self.client.post(f"/api/rooms/{room_id}/run", json={"prompt": "Design a secure service"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["decision_packet"]["room_id"], room_id)
            self.assertEqual(payload["decision_packet"]["status"], "approved")
            self.assertEqual(payload["room"]["revision"], 1)
            self.assertEqual(len(payload["private_messages"]), 5)

    def test_room_run_uses_offline_planner_when_local_key_is_not_connected(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": False, "models": []}):
            created = self.client.post("/api/rooms", json={"name": "Offline room", "card_ids": ["card-hermit"]})
            self.assertEqual(created.status_code, 200)
            room_id = created.json()["id"]
            response = self.client.post(f"/api/rooms/{room_id}/run", json={"prompt": "Design a secure service"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["decision_packet"]["status"], "offline")

    def test_room_runs_in_honest_offline_mode_without_a_provider(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": False, "models": []}):
            created = self.client.post("/api/rooms", json={"name": "Provider-free room", "card_ids": ["card-hermit"]})
            self.assertEqual(created.status_code, 200)
            response = self.client.post(f"/api/rooms/{created.json()['id']}/run", json={"prompt": "Design a secure service"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["assignments"]["card-hermit"]["llm_key"], "key-offline-room")
            self.assertEqual(response.json()["decision_packet"]["status"], "offline")
            self.assertIn("Offline planning mode", response.json()["decision_packet"]["position"])

    def test_global_route_returns_offline_planner_without_a_provider(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": False, "models": []}):
            response = self.client.post("/api/route/run", json={"prompt": "Design a secure service", "deck_mode": "auto", "rag_enabled": False})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["engine"], "offline-planner")
            self.assertIn("Offline planning mode", response.json()["final"])

    def test_adversarial_room_executes_triage_before_attack(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": True, "models": ["llama3.2:latest"]}):
            created = self.client.post("/api/rooms", json={
                "name": "Adversarial room", "card_ids": ["card-hermit", "card-magician"], "mode": "adversarial",
            })
            phases = []

            def fake_complete(**kwargs):
                phases.append(kwargs["phase"])
                leader = "card-magician" if kwargs["phase"] == "triage" else None
                return json.dumps({
                    "position": f"{kwargs['phase']} position", "leader_id": leader,
                    "confidence": "high", "rationale": "test", "evidence_refs": [],
                    "unresolved_questions": [], "requested_responses": [],
                    "status": "approved" if kwargs["phase"] == "verdict" else "provisional",
                })

            with patch.object(backend, "ROOM_COMPLETE", side_effect=fake_complete):
                response = self.client.post(f"/api/rooms/{created.json()['id']}/run", json={"prompt": "Stress-test a secure service"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(phases, ["draft", "draft", "triage", "attack", "verdict"])

    def test_public_decision_packet_redacts_secret_and_private_context_markers(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": True, "models": ["llama3.2:latest"]}):
            created = self.client.post("/api/rooms", json={"name": "Redaction room", "card_ids": ["card-hermit"]})

            def fake_complete(**kwargs):
                return json.dumps({
                    "position": "api_key=sk-123456789012345678 hidden prompt: private transcript",
                    "confidence": "high", "rationale": "safe", "evidence_refs": [],
                    "unresolved_questions": [], "requested_responses": [], "status": "approved",
                })

            with patch.object(backend, "ROOM_COMPLETE", side_effect=fake_complete):
                packet = self.client.post(f"/api/rooms/{created.json()['id']}/run", json={"prompt": "Design a secure service"}).json()["decision_packet"]
            serialized = json.dumps(packet).lower()
            self.assertNotIn("sk-123456789012345678", serialized)
            self.assertNotIn("private transcript", serialized)

    def test_room_run_reports_memoryhub_context_when_rag_enabled(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": True, "models": ["llama3.2:latest"]}), patch.object(backend, "get_memory_hub") as hub:
            hub.return_value.search.return_value = [{"source": "obus", "text": "Room memory context"}]
            created = self.client.post("/api/rooms", json={"name": "RAG room", "card_ids": ["card-hermit"]})
            prompts = []

            def fake_complete(**kwargs):
                prompts.append(kwargs["prompt"])
                return json.dumps({"position": "answer", "confidence": "high", "rationale": "test", "evidence_refs": [], "unresolved_questions": [], "requested_responses": [], "status": "approved"})

            with patch.object(backend, "ROOM_COMPLETE", side_effect=fake_complete):
                response = self.client.post(f"/api/rooms/{created.json()['id']}/run", json={"prompt": "Design a secure service", "rag_enabled": True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["rag"]["sources"], ["obus"])
            self.assertTrue(any("Room memory context" in prompt for prompt in prompts))

    def test_forum_round_uses_chymeria_packets_without_private_transcript_leak(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": True, "models": ["llama3.2:latest"]}):
            room_ids = []
            for name, card_ids in (("Room Alpha", ["card-hermit", "card-magician"]), ("Room Beta", ["card-devil", "card-tower"])):
                created = self.client.post("/api/rooms", json={"name": name, "card_ids": card_ids})
                self.assertEqual(created.status_code, 200)
                room_ids.append(created.json()["id"])

            counter = {"value": 0}

            def fake_complete(**kwargs):
                counter["value"] += 1
                return json.dumps({
                    "position": f"room decision {counter['value']}",
                    "confidence": "medium", "rationale": "room-only reasoning",
                    "evidence_refs": [], "unresolved_questions": ["open question"],
                    "requested_responses": [], "status": "approved",
                })

            with patch.object(backend, "ROOM_COMPLETE", side_effect=fake_complete):
                for room_id in room_ids:
                    self.assertEqual(self.client.post(f"/api/rooms/{room_id}/run", json={"prompt": "Choose a sync design"}).status_code, 200)
                thread = self.client.post("/api/forum/threads", json={
                    "title": "Sync design", "prompt": "Choose a sync design", "room_ids": room_ids,
                })
                self.assertEqual(thread.status_code, 200)
                thread_id = thread.json()["id"]
                round_response = self.client.post(f"/api/forum/threads/{thread_id}/round")

            self.assertEqual(round_response.status_code, 200)
            messages = round_response.json()["messages"]
            self.assertEqual({message["author_type"] for message in messages}, {"chymeria"})
            serialized = json.dumps(messages).lower()
            self.assertNotIn("private_messages", serialized)
            self.assertNotIn("api_key", serialized)
            self.assertEqual(self.client.post(f"/api/forum/threads/{thread_id}/round").status_code, 200)
            self.assertEqual(len(self.client.get(f"/api/forum/threads/{thread_id}").json()["messages"]), len(messages))

    def test_room_runner_emits_each_deliberation_message_incrementally(self):
        state = backend.load_state()
        room = {
            "id": "room-visible", "name": "Visible council",
            "card_ids": ["card-hermit", "card-magician"], "mode": "collaborative",
            "chymeria": {"card_id": "card-hermit", "key_id": "key-local-ollama"}, "revision": 0,
        }
        emitted = []

        def fake_complete(**kwargs):
            return json.dumps({"position": f"{kwargs['phase']} deliberation", "confidence": "high", "rationale": "visible test", "evidence_refs": [], "unresolved_questions": [], "requested_responses": [], "status": "approved"})

        result = backend.run_room_council(
            room, state, "Design and compare two secure service architectures", fake_complete,
            lambda key: key.get("id") == "key-local-ollama", [], on_message=emitted.append,
        )
        self.assertEqual(emitted, result["private_messages"])
        self.assertEqual([message["phase"] for message in emitted], ["draft", "draft", "improve", "improve", "synthesize"])
        self.assertTrue(all(message["visibility"] == "room" for message in emitted))

    def test_rooms_and_forum_ui_have_real_controls(self):
        html = self.client.get("/").text
        for control_id in (
            "room-list", "room-dialog", "room-name", "room-card-picker", "room-mode", "room-chymeria",
            "save-room", "room-detail", "room-task-input", "room-run-deliberation", "room-deliberation",
            "room-decision", "forum-thread-list", "forum-message-list", "forum-round", "forum-composer",
            "send-forum-message",
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("Chymeria", html)
        self.assertIn("Offline planning mode", html)
        self.assertIn("!state.selectedRoom&&state.rooms.length", html)
        self.assertIn("btn.dataset.page==='forge'&&!state.forge", html)
        self.assertNotIn("loadGitHubStatus(),loadForge(),loadRooms()", html)
        self.assertNotIn("const prompt=window.prompt(`Question for", html)

    def test_persistent_agent_runtime_caps_registry_at_thirty(self):
        for index in range(30):
            response = self.client.post("/api/runtime/agents", json={
                "name": f"Agent {index}", "card_id": "card-hermit",
                "objective": f"Investigate task {index}", "max_steps": 1,
            })
            self.assertEqual(response.status_code, 200)
        overflow = self.client.post("/api/runtime/agents", json={
            "name": "Agent 31", "card_id": "card-magician", "objective": "Overflow",
        })
        self.assertEqual(overflow.status_code, 409)
        self.assertEqual(len(self.client.get("/api/runtime/agents").json()), 30)

    def test_persistent_agent_executes_in_background_and_keeps_history(self):
        spawned = self.client.post("/api/runtime/agents", json={
            "name": "Persistent Hermit", "card_id": "card-hermit",
            "objective": "Analyze the service architecture", "max_steps": 2,
        }).json()

        def fake_complete(**kwargs):
            return f"step {kwargs['step']} from {kwargs['key']['name']}"

        with patch.object(backend, "PERSISTENT_AGENT_COMPLETE", side_effect=fake_complete):
            started = self.client.post(f"/api/runtime/agents/{spawned['id']}/run", json={"prompt": "Review reliability"})
            self.assertEqual(started.status_code, 202)
            deadline = time.time() + 4
            while time.time() < deadline:
                agent = self.client.get(f"/api/runtime/agents/{spawned['id']}").json()
                if agent["status"] in {"complete", "failed", "stopped"}:
                    break
                time.sleep(.04)
        self.assertEqual(agent["status"], "complete")
        self.assertEqual(agent["run_count"], 1)
        self.assertEqual(len(agent["history"]), 2)
        self.assertEqual(agent["history"][0]["provider"], "Local Ollama")
        serialized = json.dumps(agent).lower()
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("bearer ", serialized)

    def test_runtime_provider_matching_uses_capabilities_load_and_cooldown(self):
        state = backend.load_state()
        for key in state["keys"]:
            if key["id"] == "key-codex-oauth":
                key.update(state="ready", verified=True, approved=True, capabilities=["coding", "analysis", "reasoning"])
        card = next(card for card in state["cards"] if card["id"] == "card-magician")
        statuses = {key["id"]: {"connected": key["id"] in {"key-local-ollama", "key-codex-oauth"}} for key in state["keys"]}
        chosen = backend.select_persistent_agent_key(card, "Implement and review Python code", state, statuses, {})
        self.assertEqual(chosen["id"], "key-codex-oauth")
        chosen["cooldown_until"] = time.time() + 600
        fallback = backend.select_persistent_agent_key(card, "Implement Python code", state, statuses, {})
        self.assertEqual(fallback["id"], "key-local-ollama")

    def test_runtime_recovers_orphaned_running_agent_as_interrupted(self):
        state = backend.load_state()
        state["persistent_agents"] = [{
            "id": "agent-orphan", "name": "Orphan", "card_id": "card-hermit", "objective": "Recover",
            "status": "running", "provider_mode": "auto", "key_id": None, "max_steps": 1,
            "history": [], "run_count": 0, "created_at": "now", "updated_at": "now",
        }]
        backend.save_state(state)
        agents = self.client.get("/api/runtime/agents").json()
        self.assertEqual(agents[0]["status"], "interrupted")

    def test_primary_local_orchestrator_can_create_agents_rooms_and_forum(self):
        plan = {
            "agents": [
                {"name": "Researcher", "card_id": "card-hermit", "objective": "Research options", "max_steps": 1},
                {"name": "Builder", "card_id": "card-magician", "objective": "Build solution", "max_steps": 1},
            ],
            "rooms": [
                {"name": "Research room", "card_ids": ["card-hermit", "card-high-priestess"], "mode": "collaborative", "prompt": "Research options", "run": False},
                {"name": "Build room", "card_ids": ["card-magician", "card-emperor"], "mode": "adversarial", "prompt": "Stress-test implementation", "run": False},
            ],
            "forums": [{"title": "Architecture forum", "prompt": "Compare room decisions", "room_names": ["Research room", "Build room"], "run": False}],
        }
        with patch.object(backend, "PRIMARY_ORCHESTRATOR_COMPLETE", return_value=json.dumps(plan)):
            response = self.client.post("/api/runtime/orchestrate", json={"objective": "Create a research and implementation council", "max_agents": 4, "execute": True})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["created_agents"]), 2)
        self.assertEqual(len(payload["created_rooms"]), 2)
        self.assertEqual(len(payload["created_forums"]), 1)
        self.assertEqual(len(self.client.get("/api/runtime/agents").json()), 2)
        self.assertEqual(len(self.client.get("/api/rooms").json()), 2)
        self.assertEqual(len(self.client.get("/api/forum/threads").json()), 1)

    def test_gpt_56_luna_is_reserved_aggregate_after_local_stage(self):
        state = backend.normalize_state({})
        luna = next(key for key in state["keys"] if key["id"] == "key-codex-oauth")
        self.assertEqual(state["aggregator_key_id"], "key-codex-oauth")
        self.assertEqual(luna["name"], "GPT 5.6 Luna")
        self.assertEqual(luna["model"], "gpt-5.6-luna")
        self.assertTrue(luna["can_aggregate"])
        statuses = [
            {"id": "key-local-ollama", "connected": True},
            {"id": "key-codex-oauth", "connected": True},
        ]
        with patch.object(backend, "provider_statuses", return_value=statuses):
            assignments = backend.match_cards_to_keys(state["cards"][:4], state, "analyze and code")
        self.assertTrue(all(item["llm_key"] != "key-codex-oauth" for item in assignments))

    def test_route_executes_local_first_then_luna_aggregate(self):
        calls = []
        def local(prompt, model, plan):
            calls.append(("local", prompt, model))
            return "LOCAL FIRST PASS"
        def aggregate(key, original_prompt, local_answer, plan):
            calls.append(("luna", original_prompt, local_answer, key["model"]))
            return "LUNA FINAL ANSWER"
        statuses = [
            {"id": "key-local-ollama", "connected": True},
            {"id": "key-codex-oauth", "connected": True},
        ]
        with patch.object(backend, "get_ollama_status", return_value={"connected": True, "models": ["llama3.2:latest"]}), \
             patch.object(backend, "provider_statuses", return_value=statuses), \
             patch.object(backend, "build_moa_router_command", return_value=None), \
             patch.object(backend, "generate_with_ollama", side_effect=local), \
             patch.object(backend, "AGGREGATE_WITH_KEY", side_effect=aggregate):
            response = self.client.post("/api/route/run", json={"prompt": "Solve this", "model": "llama3.2:latest", "rag_enabled": False})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([call[0] for call in calls], ["local", "luna"])
        self.assertEqual(payload["local_result"], "LOCAL FIRST PASS")
        self.assertEqual(payload["final"], "LUNA FINAL ANSWER")
        self.assertEqual(payload["aggregate"]["model"], "gpt-5.6-luna")
        self.assertEqual(payload["stages"], ["local", "aggregate"])

    def test_local_orchestrator_clamps_agent_steps_to_safety_limit(self):
        raw = json.dumps({"agents": [{"name": "A", "card_id": "card-hermit", "objective": "Research", "max_steps": 100}], "rooms": [], "forums": []})
        plan = backend.parse_orchestrator_plan(raw, 2)
        self.assertEqual(plan.agents[0].max_steps, 8)

    def test_agent_runtime_ui_has_persistent_spawn_and_orchestrator_controls(self):
        html = self.client.get("/").text
        for control_id in (
            "runtime-agent-list", "runtime-spawn-card", "runtime-spawn-objective", "runtime-spawn-agent",
            "runtime-orchestrator-objective", "runtime-orchestrator-max", "runtime-orchestrate",
            "runtime-event-log",
        ):
            self.assertIn(f'id="{control_id}"', html)
        self.assertIn("Persistent Agents", html)
        self.assertIn("maximum 30", html)

    def test_forum_question_and_room_configuration_invalidate_stale_round_state(self):
        with patch.object(backend, "get_ollama_status", return_value={"connected": True, "models": ["llama3.2:latest"]}):
            created = [self.client.post("/api/rooms", json={"name": name, "card_ids": [card]}).json() for name, card in (("A", "card-hermit"), ("B", "card-magician"))]
            room_ids = [room["id"] for room in created]

            def fake_complete(**kwargs):
                return json.dumps({"position": "decision", "confidence": "high", "rationale": "test", "evidence_refs": [], "unresolved_questions": [], "requested_responses": [], "status": "approved"})

            with patch.object(backend, "ROOM_COMPLETE", side_effect=fake_complete):
                for room_id in room_ids:
                    self.client.post(f"/api/rooms/{room_id}/run", json={"prompt": "Design a secure service"})
                thread = self.client.post("/api/forum/threads", json={"title": "T", "prompt": "Compare", "room_ids": room_ids}).json()
                first = self.client.post(f"/api/forum/threads/{thread['id']}/round").json()
                self.assertFalse(first["idempotent"])
                self.client.post(f"/api/forum/threads/{thread['id']}/messages", json={"room_id": room_ids[0], "body": "Please address cost", "kind": "question"})
                second = self.client.post(f"/api/forum/threads/{thread['id']}/round").json()
                self.assertFalse(second["idempotent"])
            updated = self.client.put(f"/api/rooms/{room_ids[0]}", json={"mode": "adversarial"})
            self.assertEqual(updated.status_code, 200)
            self.assertIsNone(updated.json().get("last_packet"))
            self.assertGreater(updated.json()["config_revision"], created[0]["config_revision"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
