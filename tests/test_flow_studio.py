from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import flow_studio_api
from backend.flow_studio import FlowDocument, FlowStore


def test_templates_are_copied_then_persisted(tmp_path: Path):
    store = FlowStore(tmp_path / "flow_studio.json")
    template = store.list()[0]
    draft = store.clone(template["id"], None)
    assert draft["kind"] == "draft" and draft["source_template"] == template["id"]
    saved = store.update(draft["id"], FlowDocument(title="Research Copy", nodes=draft["nodes"], edges=draft["edges"], version=draft["version"]))
    assert saved["version"] == 2
    assert FlowStore(tmp_path / "flow_studio.json").get(draft["id"])["title"] == "Research Copy"


def test_proposal_is_versioned_and_changes_a_draft_only(tmp_path: Path):
    store = FlowStore(tmp_path / "flow_studio.json")
    draft = store.clone("template-parallel-research", None)
    proposal = store.propose_split(draft["id"])
    changed = store.apply_split(draft["id"], proposal["base_version"])
    assert {"Web Search Agent", "Source Evaluator"} <= {item["label"] for item in changed["nodes"]}
    assert sum(item["label"] == "Source Evaluator" for item in changed["nodes"]) == 1
    try:
        store.apply_split(draft["id"], proposal["base_version"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("stale proposal was accepted")


def test_local_api_clones_and_blocks_template_mutation(tmp_path: Path):
    original, flow_studio_api.flow_store = flow_studio_api.flow_store, FlowStore(tmp_path / "flow_studio.json")
    app = FastAPI(); app.include_router(flow_studio_api.api_router)
    try:
        client = TestClient(app)
        template_id = client.get("/api/flow-studio/flows").json()["flows"][0]["id"]
        draft = client.post(f"/api/flow-studio/flows/{template_id}/clone", json={})
        assert draft.status_code == 201
        assert client.post(f"/api/flow-studio/flows/{draft.json()['id']}/validate").status_code == 200
        assert client.put(f"/api/flow-studio/flows/{template_id}", json={"title":"Nope","nodes":[],"edges":[],"version":1}).status_code == 403
        assert client.post(f"/api/flow-studio/flows/{template_id}/run", json={}).status_code == 409
    finally:
        flow_studio_api.flow_store = original


def test_page_route_and_dashboard_launch_target_exist(tmp_path: Path):
    original, flow_studio_api.flow_store = flow_studio_api.flow_store, FlowStore(tmp_path / "flow_studio.json")
    app = FastAPI(); app.include_router(flow_studio_api.api_router); app.include_router(flow_studio_api.page_router)
    try:
        response = TestClient(app).get("/flow-studio")
        assert response.status_code == 200 and "OBus Flow Studio" in response.text
        dashboard = (Path(__file__).parents[1] / "backend" / "static" / "index.html").read_text(encoding="utf-8")
        assert 'href="/flow-studio"' in dashboard
    finally:
        flow_studio_api.flow_store = original


def test_flow_studio_cannot_bypass_runtime_major_risk_approval_queue(tmp_path: Path):
    original, flow_studio_api.flow_store = flow_studio_api.flow_store, FlowStore(tmp_path / "flow_studio.json")
    app = FastAPI(); app.include_router(flow_studio_api.api_router)
    try:
        client = TestClient(app)
        template_id = client.get("/api/flow-studio/flows").json()["flows"][0]["id"]
        draft = client.post(f"/api/flow-studio/flows/{template_id}/clone", json={}).json()
        draft["nodes"][0]["description"] = "Raise the GPU power limit for a benchmark."
        saved = client.put(f"/api/flow-studio/flows/{draft['id']}", json={
            "title": draft["title"], "nodes": draft["nodes"], "edges": draft["edges"], "version": draft["version"],
        })
        assert saved.status_code == 200
        blocked = client.post(f"/api/flow-studio/flows/{draft['id']}/run", json={"major_risk_approved": True})
        assert blocked.status_code == 409
        assert "cannot bypass the local approval queue" in blocked.json()["detail"]["message"]
    finally:
        flow_studio_api.flow_store = original
