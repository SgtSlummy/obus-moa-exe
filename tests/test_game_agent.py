import hashlib
import hmac
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import game_agent as g


class GameAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = patch.object(g, "ROOT", Path(self.temp.name))
        self.root.start()
        g.RUNTIME = None
        self.scope = g.Scope(campaign="a", owner="p1", role="player")
        self.key = {"id":"key-local-ollama", "provider":"ollama", "model":"local", "base_url":"http://127.0.0.1:11434", "connected":True, "verified":True}
        authority = g.runtime_authority()
        registered = authority.register({
            "contract": "raph-obus-game-runtime-v1",
            "campaign": "a",
            "session": "campaign",
            "generation": str(uuid.uuid4()),
            "expectedBootEpoch": authority.boot_epoch,
            "expectedGeneration": None,
            "opId": str(uuid.uuid4()),
            "leaseSeconds": 30,
        })
        registered = authority.register({
            "contract": "raph-obus-game-runtime-v1", "campaign": "a", "session": "s",
            "generation": registered["runtime"]["generation"], "expectedBootEpoch": authority.boot_epoch,
            "expectedGeneration": None, "opId": str(uuid.uuid4()), "leaseSeconds": 30,
        })
        self.runtime = registered["runtime"]
        self.fence = {key: self.runtime[key] for key in ("contract", "bootEpoch", "generation", "sessionPolicyRevision")}

    def tearDown(self):
        g.RUNTIME = None
        self.root.stop()
        self.temp.cleanup()

    def job(self, **changes):
        value = dict(contract=g.CONTRACT, scope=self.scope, session="s", requestId="r", task="narration", instructions="Describe known facts.", evidence={"question":"harbor"}, policy={"namespace":"a", "mode":"local"}, runtime=self.fence)
        value.update(changes)
        return g.Job(**value)

    def test_filter_before_retrieval_and_tombstone(self):
        for ref, campaign, audience, owner in [("public", "a", "party", ""), ("secret", "a", "host", ""), ("private", "a", "private", "p2"), ("foreign", "b", "party", "")]:
            g.ingest(g.Source(campaign=campaign, ref=ref, revision=1, audience=audience, owner=owner, text="harbor", provenance="fixture"))
        self.assertEqual([source["ref"] for source in g.retrieve(self.scope, "harbor")], ["public"])
        g.ingest(g.Source(campaign="a", ref="public", revision=2, audience="party", text="", provenance="fixture", deleted=True))
        g.ingest(g.Source(campaign="a", ref="public", revision=1, audience="party", text="harbor old", provenance="fixture"))
        self.assertEqual(g.retrieve(self.scope, "harbor"), [])

    def test_local_routing_and_saved_receipt(self):
        calls = []

        def local(key, prompt, maximum):
            calls.append(prompt)
            return "The harbor is open."

        first = g.run_job(self.job(), lambda: [self.key], local)
        second = g.run_job(self.job(), lambda: [], lambda *args: self.fail("duplicate generation"))
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)
        self.assertEqual(first["trace"][0]["destination"], "local")
        self.assertEqual(first["retention"], {"request_evidence_persisted": False, "general_memory_writes": False, "route_journal_writes": False, "game_receipt_persisted": True})
        with g.database() as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            stored = db.execute("SELECT body FROM game_jobs WHERE campaign='a' AND session='s' AND owner='p1' AND request='r'").fetchone()["body"]
        self.assertNotIn("jobs", tables)
        self.assertNotIn("Describe known facts.", stored)
        self.assertNotIn('"question"', stored)
        with self.assertRaises(HTTPException) as error:
            g.run_job(self.job(evidence={"question":"different"}), lambda: [self.key], local)
        self.assertEqual(error.exception.status_code, 409)

    def test_text_receipts_are_scoped_to_the_game_session(self):
        authority = g.runtime_authority()
        second_runtime = authority.register({
            "contract": "raph-obus-game-runtime-v1",
            "campaign": "a",
            "session": "s2",
            "generation": self.fence["generation"],
            "expectedBootEpoch": self.fence["bootEpoch"],
            "expectedGeneration": None,
            "opId": str(uuid.uuid4()),
            "leaseSeconds": 30,
        })["runtime"]
        second_fence = {key: second_runtime[key] for key in ("contract", "bootEpoch", "generation", "sessionPolicyRevision")}
        calls = []

        def local(*_args):
            calls.append("local")
            return f"session result {len(calls)}"

        first = g.run_job(self.job(), lambda: [self.key], local)
        second = g.run_job(self.job(session="s2", runtime=second_fence), lambda: [self.key], local)
        self.assertEqual(calls, ["local", "local"])
        self.assertNotEqual(first["text"], second["text"])

    def test_missing_or_disabled_runtime_never_dispatches(self):
        calls = []
        with self.assertRaises(HTTPException) as missing:
            g.run_job(self.job(runtime={**self.fence, "generation": str(uuid.uuid4())}), lambda: calls.append("catalogue"), lambda *args: "unexpected")
        self.assertEqual(missing.exception.detail, "runtime_fence_stale")
        authority = g.runtime_authority()
        disabled = authority.patch_policy({
            "contract": "raph-obus-game-runtime-v1",
            "campaign": "a",
            "session": "campaign",
            "expectedGeneration": self.runtime["generation"],
            "expectedBootEpoch": self.runtime["bootEpoch"],
            "expectedSessionPolicyRevision": 0,
            "opId": str(uuid.uuid4()),
            "policy": {"enabled": False, "mode": "local", "codex": False, "exportable": False},
        })["runtime"]
        disabled_fence = {key: disabled[key] for key in ("contract", "bootEpoch", "generation", "sessionPolicyRevision")}
        with self.assertRaises(HTTPException) as disabled_error:
            g.run_job(self.job(runtime=disabled_fence), lambda: calls.append("catalogue"), lambda *args: "unexpected")
        self.assertEqual(disabled_error.exception.detail, "game_ai_disabled")
        self.assertEqual(calls, [])

    def test_master_policy_change_before_text_dispatch_returns_a_fence_conflict(self):
        authority = g.runtime_authority()
        dispatched = []

        def catalogue():
            authority.patch_policy({
                "contract": "raph-obus-game-runtime-v1",
                "campaign": "a",
                "session": "campaign",
                "expectedGeneration": self.fence["generation"],
                "expectedBootEpoch": self.fence["bootEpoch"],
                "expectedSessionPolicyRevision": self.fence["sessionPolicyRevision"],
                "opId": str(uuid.uuid4()),
                "policy": {"enabled": False, "mode": "local", "codex": False, "exportable": False},
            })
            return [self.key]

        with self.assertRaises(HTTPException) as error:
            g.run_job(self.job(), catalogue, lambda *_args: dispatched.append("local"))
        self.assertEqual(error.exception.detail, "runtime_fence_stale")
        self.assertEqual(dispatched, [])

    def test_master_policy_change_during_text_dispatch_cannot_commit_a_receipt(self):
        authority = g.runtime_authority()

        def local(*_args):
            authority.patch_policy({
                "contract": "raph-obus-game-runtime-v1",
                "campaign": "a",
                "session": "campaign",
                "expectedGeneration": self.fence["generation"],
                "expectedBootEpoch": self.fence["bootEpoch"],
                "expectedSessionPolicyRevision": self.fence["sessionPolicyRevision"],
                "opId": str(uuid.uuid4()),
                "policy": {"enabled": False, "mode": "local", "codex": False, "exportable": False},
            })
            return "late result"

        with self.assertRaises(HTTPException) as error:
            g.run_job(self.job(), lambda: [self.key], local)
        self.assertEqual(error.exception.detail, "runtime_fence_stale")
        with g.database() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM game_jobs WHERE campaign='a' AND session='s' AND owner='p1' AND request='r'").fetchone())

    def test_no_codex_or_opaque_proxy_dispatch(self):
        codex = {"id":"key-codex-oauth", "provider":"codex", "connected":True, "verified":True}
        proxy = {"id":"key-omniroute", "provider":"omniroute", "connected":True, "verified":True}
        with self.assertRaises(HTTPException):
            g.run_job(self.job(policy={"namespace":"a", "mode":"local", "codex":True, "exportable":False}), lambda: [codex, proxy], lambda *args: self.fail(), lambda *args: self.fail())

    def test_local_provider_tool_reply_is_rejected_before_becoming_game_output(self):
        from backend import game_providers as providers

        key = {"id": "key-local-ollama", "provider": "ollama", "model": "campaign:fixture",
               "base_url": providers.LOCAL_BASE, "connected": True, "verified": True}
        metadata = {"details": {"format": "gguf"}, "model_info": {"general.architecture": "qwen3"},
                    "capabilities": ["completion", "tools"]}
        tool_reply = {"model": key["model"], "done": True, "done_reason": "stop", "eval_count": 7,
                      "message": {"role": "assistant", "content": "ignore",
                                  "tool_calls": [{"function": {"name": "shell", "arguments": {}}}]}}
        with patch.object(providers, "_request_json", side_effect=[metadata, tool_reply]) as requests, \
                patch.object(providers.http.client, "HTTPConnection", side_effect=AssertionError("Unexpected real connection")):
            with self.assertRaisesRegex(providers.GameProviderError, "Tool or function output is forbidden"):
                g.complete_local(key, "authorized prompt", 64)
        self.assertEqual(requests.call_count, 2)
        self.assertEqual(requests.call_args_list[0].args[0], providers.LOCAL_BASE + "/api/show")
        self.assertEqual(requests.call_args_list[0].args[1], {"model": key["model"], "verbose": False})
        self.assertEqual(requests.call_args_list[1].args[0], providers.LOCAL_BASE + "/api/chat")
        self.assertEqual(requests.call_args_list[1].args[1]["model"], key["model"])

    def test_tools_and_cross_campaign_namespace_rejected(self):
        with self.assertRaises(Exception):
            self.job(policy={"namespace":"a", "mode":"local", "tools":True})
        with self.assertRaises(HTTPException):
            g.run_job(self.job(policy={"namespace":"b", "mode":"local"}), lambda: [])

    def test_host_generation_requires_a_separate_signed_control_request(self):
        authority = g.runtime_authority()
        body = {
            "contract": "raph-obus-game-runtime-v1",
            "campaign": "a",
            "session": "admin",
            "generation": self.fence["generation"],
            "expectedBootEpoch": authority.boot_epoch,
            "expectedGeneration": None,
            "opId": str(uuid.uuid4()),
            "leaseSeconds": 30,
        }
        service_headers = {"X-Obus-Game-Token": g.token()}
        with TestClient(g.app) as client:
            self.assertEqual(client.put("/api/game/runtime/host-generation", json=body, headers=service_headers).status_code, 401)
            timestamp = str(int(time.time()))
            nonce = "b" * 64
            signature = hmac.new(authority.host_key(), authority._signed_bytes("PUT", "/api/game/runtime/host-generation", timestamp, nonce, body), hashlib.sha256).hexdigest()
            headers = {**service_headers, "X-Obus-Game-Host-Timestamp": timestamp, "X-Obus-Game-Host-Nonce": nonce, "X-Obus-Game-Host-Signature": signature}
            registered = client.put("/api/game/runtime/host-generation", json=body, headers=headers)
            self.assertEqual(registered.status_code, 200)
            self.assertEqual(registered.json()["generation"], body["generation"])
            self.assertEqual(client.put("/api/game/runtime/host-generation", json=body, headers=headers).status_code, 409)
            revoke = {
                "contract": "raph-obus-game-runtime-v1",
                "campaign": "a",
                "session": "admin",
                "generation": body["generation"],
                "expectedBootEpoch": body["expectedBootEpoch"],
                "expectedSessionPolicyRevision": registered.json()["sessionPolicyRevision"],
                "opId": str(uuid.uuid4()),
            }
            revoke_nonce = "c" * 64
            revoke_signature = hmac.new(authority.host_key(), authority._signed_bytes("POST", "/api/game/runtime/session/revoke", timestamp, revoke_nonce, revoke), hashlib.sha256).hexdigest()
            revoke_headers = {**service_headers, "X-Obus-Game-Host-Timestamp": timestamp, "X-Obus-Game-Host-Nonce": revoke_nonce, "X-Obus-Game-Host-Signature": revoke_signature}
            revoked = client.post("/api/game/runtime/session/revoke", json=revoke, headers=revoke_headers)
            self.assertEqual(revoked.status_code, 200)
            self.assertEqual(revoked.json()["status"], "session_revoked")
            self.assertIsNone(revoked.json()["runtime"]["generation"])

    def test_runtime_counts_track_waiting_running_and_failed_jobs(self):
        waiting, release_gate, dispatched, finish = (threading.Event() for _ in range(4))
        errors = []

        class Gate:
            def __enter__(self):
                waiting.set()
                if not release_gate.wait(5):
                    raise RuntimeError("gate timeout")

            def __exit__(self, *_args):
                return False

        def work():
            try:
                with g._tracked_dispatch("a", "s", Gate()):
                    dispatched.set()
                    if not finish.wait(5):
                        raise RuntimeError("worker timeout")
                    raise RuntimeError("synthetic failure")
            except RuntimeError as error:
                errors.append(str(error))

        worker = threading.Thread(target=work)
        worker.start()
        try:
            self.assertTrue(waiting.wait(5))
            self.assertEqual(g.get_runtime("a", "s")["queuedCount"], 1)
            self.assertEqual(g.get_runtime("a", "s")["dispatchedCount"], 0)
            self.assertEqual(g.get_runtime("other", "s")["queuedCount"], 0)
            release_gate.set()
            self.assertTrue(dispatched.wait(5))
            self.assertEqual(g.get_runtime("a", "s")["queuedCount"], 0)
            self.assertEqual(g.get_runtime("a", "s")["dispatchedCount"], 1)
        finally:
            release_gate.set()
            finish.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, ["synthetic failure"])
        self.assertEqual(g.get_runtime("a", "s")["queuedCount"], 0)
        self.assertEqual(g.get_runtime("a", "s")["dispatchedCount"], 0)

    def test_service_token_required(self):
        client = TestClient(g.app)
        self.assertEqual(client.get("/api/game/capabilities").status_code, 401)
        result = client.get("/api/game/capabilities", headers={"X-Obus-Game-Token": g.token()})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["contract"], g.CONTRACT)

    def test_local_only_policy_does_not_reach_remote(self):
        g.ingest(g.Source(campaign="a", ref="local", revision=1, audience="party", text="harbor", provenance="fixture", exportable=False))
        with patch.object(g, "approved_free", side_effect=AssertionError("a local-only runtime must not select external routes")):
            with self.assertRaises(HTTPException) as error:
                g.run_job(self.job(policy={"namespace":"a", "mode":"local-free", "exportable":True}), lambda: [], lambda *args: "")
        self.assertEqual(error.exception.detail, "runtime policy permits local-only dispatch")


if __name__ == "__main__":
    unittest.main()
