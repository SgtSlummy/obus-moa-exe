"""Persisted, inspectable Flow Studio graphs for the local OBus desktop."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .execution_policy import classify_major_risk


NODE_TYPES = {"agent", "tool", "model", "memory", "router", "parallel", "guardrail", "approval", "output"}
EDGE_TYPES = {"data", "reasoning", "policy", "fallback", "tool"}
STAGES = {"observe", "reason", "act", "improve"}


class FlowDocument(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    nodes: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    edges: list[dict[str, Any]] = Field(default_factory=list, max_length=250)
    version: int = Field(ge=1)


class FlowCreate(BaseModel):
    title: str = Field(default="Untitled Flow", min_length=1, max_length=120)


class FlowClone(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)


class ProposalApply(BaseModel):
    base_version: int = Field(ge=1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path() -> Path:
    root = Path(os.environ.get("OBUS_STATE_DIR") or os.environ.get("LOCALAPPDATA") or Path.home() / ".obus")
    return root / "Obus" / "flow_studio.json"


def _node(node_id: str, node_type: str, label: str, description: str, stage: str, **config: Any) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "label": label, "description": description, "stage": stage, "config": config}


def _edge(source: str, target: str, edge_type: str = "data", label: str = "") -> dict[str, Any]:
    return {"source": source, "target": target, "type": edge_type, "label": label}


def _blueprint(flow_id: str, title: str, summary: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    timestamp = _now()
    return {"id": flow_id, "kind": "template", "title": title, "summary": summary, "nodes": nodes, "edges": edges,
            "version": 1, "created_at": timestamp, "updated_at": timestamp, "source_template": None}


def templates() -> list[dict[str, Any]]:
    """Built-in patterns: sequential, parallel, router, loop, and guarded automation."""
    return [
        _blueprint("template-parallel-research", "Resilient Parallel Research", "Parallel research, evaluation, synthesis, and review.", [
            _node("input", "agent", "Input", "User request or event", "observe"), _node("context", "memory", "Context Collector", "Gather bounded context", "observe"),
            _node("planner", "agent", "Planner", "Decompose the goal", "reason"), _node("research", "agent", "Research Agent", "Find relevant sources", "reason"),
            _node("evaluator", "agent", "Source Evaluator", "Check quality and relevance", "reason"), _node("synthesis", "agent", "Consensus & Evaluator", "Synthesize verified results", "reason"),
            _node("approval", "approval", "Human Approval", "Review consequential output", "act", scope="consequential actions"), _node("output", "output", "Output", "Deliver result", "act"), _node("memory", "memory", "Outcome Memory", "Store non-secret lessons", "improve")],
            [_edge("input", "context"), _edge("context", "planner"), _edge("planner", "research", "reasoning"), _edge("planner", "evaluator", "reasoning"), _edge("research", "synthesis", "reasoning"), _edge("evaluator", "synthesis", "reasoning"), _edge("synthesis", "approval", "policy"), _edge("approval", "output", "policy"), _edge("output", "memory")]),
        _blueprint("template-safe-task", "Safe Task Runner", "Plan, risk-check, ask, then perform bounded work.", [
            _node("input", "agent", "Task Request", "A scoped task", "observe"), _node("planner", "agent", "Task Planner", "Plan bounded steps", "reason"), _node("guard", "guardrail", "Risk Gate", "Classify destructive and hardware risk", "act"), _node("approval", "approval", "Explicit Approval", "Pause when approval is required", "act", scope="major risk"), _node("worker", "agent", "Bounded Worker", "Perform approved work", "act"), _node("output", "output", "Receipt", "Report result and checks", "act")],
            [_edge("input", "planner"), _edge("planner", "guard", "policy"), _edge("guard", "approval", "policy"), _edge("approval", "worker", "policy"), _edge("worker", "output")]),
        _blueprint("template-rag-router", "RAG Orchestrator", "Route through retrieval, ranking, and a grounded answer.", [
            _node("input", "agent", "Question", "Incoming question", "observe"), _node("router", "router", "Query Router", "Choose a retrieval route", "reason"), _node("retrieve", "tool", "Retriever", "Fetch bounded knowledge", "reason"), _node("rank", "agent", "Evidence Ranker", "Rank evidence and gaps", "reason"), _node("answer", "agent", "Grounded Answer", "Compose an answer", "act"), _node("output", "output", "Answer", "Deliver source-aware response", "act")],
            [_edge("input", "router"), _edge("router", "retrieve", "reasoning"), _edge("retrieve", "rank", "tool"), _edge("rank", "answer", "reasoning"), _edge("answer", "output")]),
        _blueprint("template-local-model", "Local Model Pipeline", "Local inference with bounded context and a retry loop.", [
            _node("input", "agent", "Input", "User request", "observe"), _node("context", "memory", "Bounded Context", "Select relevant context", "observe"), _node("model", "model", "Local Model", "Run local inference", "reason", provider="ollama"), _node("check", "guardrail", "Quality Check", "Inspect result before release", "act"), _node("output", "output", "Output", "Return reviewed result", "act")],
            [_edge("input", "context"), _edge("context", "model"), _edge("model", "check", "reasoning"), _edge("check", "output", "policy"), _edge("model", "context", "fallback", "smaller context")]),
        _blueprint("template-guarded-automation", "Guarded Automation", "Conservative automation with a local review point.", [
            _node("input", "agent", "Automation Request", "Scoped request", "observe"), _node("plan", "agent", "Planner", "Prepare visible plan", "reason"), _node("risk", "guardrail", "Safety Review", "Inspect permission and risk", "act"), _node("approval", "approval", "Human Approval", "Require local decision", "act", scope="automation execution"), _node("worker", "agent", "Automation Worker", "Perform approved work", "act"), _node("output", "output", "Receipt", "Report actions and checks", "act")],
            [_edge("input", "plan"), _edge("plan", "risk", "policy"), _edge("risk", "approval", "policy"), _edge("approval", "worker", "policy"), _edge("worker", "output"), _edge("risk", "output", "fallback", "decline or clarify")]),
    ]


def validate_graph(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str]]:
    errors, warnings = [], []
    identifiers: list[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict): errors.append(f"Tile {index + 1} must be an object."); continue
        node_id = str(node.get("id", "")); node_type, stage, label = node.get("type"), node.get("stage"), str(node.get("label", "")).strip()
        if not node_id or len(node_id) > 96: errors.append(f"Tile {index + 1} has an invalid ID.")
        elif node_id in identifiers: errors.append(f"Tile ID {node_id} is duplicated.")
        else: identifiers.append(node_id)
        if node_type not in NODE_TYPES: errors.append(f"Tile {node_id or index + 1} has an unsupported type.")
        if stage not in STAGES: errors.append(f"Tile {node_id or index + 1} has an unsupported stage.")
        if not label or len(label) > 120: errors.append(f"Tile {node_id or index + 1} needs a label.")
    known, seen = set(identifiers), set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict): errors.append(f"Connection {index + 1} must be an object."); continue
        source, target, kind = edge.get("source"), edge.get("target"), edge.get("type")
        if source not in known or target not in known: errors.append(f"Connection {source} → {target} refers to a missing tile.")
        elif source == target and kind != "fallback": errors.append(f"Connection {source} cannot point to itself unless it is fallback.")
        elif (source, target, kind) in seen: warnings.append(f"Duplicate connection {source} → {target}.")
        seen.add((source, target, kind))
        if kind not in EDGE_TYPES: errors.append(f"Connection {source} → {target} has an unsupported type.")
    if not nodes: warnings.append("Add tiles before this flow can run.")
    risks = classify_major_risk(json.dumps(nodes, ensure_ascii=False))
    if risks and not any(item.get("type") == "approval" for item in nodes if isinstance(item, dict)): warnings.append("Major-risk terms appear without an Approval tile. Runtime still requires local approval.")
    if nodes and not any(item.get("type") == "output" for item in nodes if isinstance(item, dict)): warnings.append("No Output tile is present.")
    warnings.append("Editing, saving, copying, and proposals never run a flow. Runtime submission is separate.")
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings)), risks


class FlowStore:
    def __init__(self, path: Path | None = None): self.path, self.lock = path or _path(), threading.RLock()
    def _read(self) -> dict[str, Any]:
        if not self.path.exists(): return {"schema_version": 1, "flows": templates()}
        try: value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): return {"schema_version": 1, "flows": templates()}
        return value if isinstance(value, dict) and value.get("schema_version") == 1 and isinstance(value.get("flows"), list) else {"schema_version": 1, "flows": templates()}
    def _write(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True); temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"); temporary.replace(self.path)
    @staticmethod
    def _find(value: dict[str, Any], flow_id: str) -> dict[str, Any]:
        for item in value["flows"]:
            if item.get("id") == flow_id: return item
        raise KeyError(flow_id)
    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            return [{key: item.get(key) for key in ("id", "kind", "title", "summary", "version", "created_at", "updated_at", "source_template")} | {"node_count":len(item.get("nodes", [])), "edge_count":len(item.get("edges", []))} for item in self._read()["flows"]]
    def get(self, flow_id: str) -> dict[str, Any]:
        with self.lock: return deepcopy(self._find(self._read(), flow_id))
    def create(self, title: str) -> dict[str, Any]:
        with self.lock:
            value, timestamp = self._read(), _now(); item = {"id":f"flow-{uuid4().hex}", "kind":"draft", "title":title, "summary":"Custom flow draft.", "nodes":[], "edges":[], "version":1, "created_at":timestamp, "updated_at":timestamp, "source_template":None}; value["flows"].append(item); self._write(value); return deepcopy(item)
    def clone(self, flow_id: str, title: str | None) -> dict[str, Any]:
        with self.lock:
            value, source = self._read(), None; source = self._find(value, flow_id); item, timestamp = deepcopy(source), _now()
            item.update({"id":f"flow-{uuid4().hex}", "kind":"draft", "title":title or f"{source['title']} Copy", "version":1, "created_at":timestamp, "updated_at":timestamp, "source_template":source.get("source_template") or source["id"]}); value["flows"].append(item); self._write(value); return deepcopy(item)
    def update(self, flow_id: str, draft: FlowDocument) -> dict[str, Any]:
        with self.lock:
            value, current = self._read(), None; current = self._find(value, flow_id)
            if current.get("kind") != "draft": raise PermissionError("Built-in templates are read-only. Copy one before changing it.")
            if current.get("version") != draft.version: raise RuntimeError("This draft changed elsewhere. Reload it before saving.")
            errors, _, _ = validate_graph(draft.nodes, draft.edges)
            if errors: raise ValueError("; ".join(errors))
            current.update({"title":draft.title.strip(), "nodes":draft.nodes, "edges":draft.edges, "version":draft.version + 1, "updated_at":_now()}); self._write(value); return deepcopy(current)
    def validate(self, flow_id: str) -> dict[str, Any]:
        flow = self.get(flow_id); errors, warnings, risks = validate_graph(flow["nodes"], flow["edges"])
        return {"flow_id":flow_id, "version":flow["version"], "valid":not errors, "errors":errors, "warnings":warnings, "major_risks":risks, "execution":"requires explicit local run"}
    def propose_split(self, flow_id: str) -> dict[str, Any]:
        flow = self.get(flow_id)
        if not any(item.get("label", "").casefold() == "research agent" for item in flow["nodes"]): raise ValueError("This flow has no Research Agent to split.")
        return {"id":"split-research-agent", "flow_id":flow_id, "base_version":flow["version"], "summary":"Split Research Agent into Web Search Agent and Source Evaluator.", "changes":["replace Research Agent", "add two specialist agents", "preserve graph links"], "apply_requires":"explicit apply to this draft"}
    def apply_split(self, flow_id: str, base_version: int) -> dict[str, Any]:
        with self.lock:
            value, flow = self._read(), None; flow = self._find(value, flow_id)
            if flow.get("kind") != "draft": raise PermissionError("Copy a built-in template before applying an OBus proposal.")
            if flow.get("version") != base_version: raise RuntimeError("This draft changed after the proposal was previewed. Preview it again.")
            old = next((item for item in flow["nodes"] if item.get("label", "").casefold() == "research agent"), None)
            if not old: raise ValueError("Research Agent is no longer present in this draft.")
            suffix, old_id = uuid4().hex[:8], old["id"]; web = f"web-search-{suffix}"
            evaluator = next((item for item in flow["nodes"] if item.get("label", "").casefold() == "source evaluator" and item["id"] != old_id), None)
            evaluate = evaluator["id"] if evaluator else f"source-evaluator-{suffix}"
            additions = [_node(web,"agent","Web Search Agent","Find relevant sources","reason")]
            if not evaluator: additions.append(_node(evaluate,"agent","Source Evaluator","Check quality and conflicts","reason"))
            flow["nodes"] = [item for item in flow["nodes"] if item["id"] != old_id] + additions
            updated = []
            for edge in flow["edges"]:
                if edge["target"] == old_id:
                    updated.append({**edge,"target":web})
                    if not evaluator: updated.append({**edge,"target":evaluate})
                elif edge["source"] == old_id: updated.append({**edge,"source":evaluate})
                else: updated.append(edge)
            deduplicated, edge_keys = [], set()
            for edge in updated + [_edge(web,evaluate,"reasoning","sources")]:
                key = (edge["source"],edge["target"],edge["type"],edge.get("label", ""))
                if key not in edge_keys: deduplicated.append(edge); edge_keys.add(key)
            flow["edges"] = deduplicated; flow["version"] += 1; flow["updated_at"] = _now(); self._write(value); return deepcopy(flow)


def compile_runtime_objective(flow: dict[str, Any]) -> str:
    graph = {key: flow[key] for key in ("title", "version", "nodes", "edges")}
    return "Execute this user-authored Flow Studio graph as a bounded OBus task. The graph is not independent authorization: follow existing workspace, secret, approval, and major-risk policies. Stop and request explicit local approval before major destructive or hardware-risk work.\n\n" + json.dumps(graph, indent=2, ensure_ascii=False)
