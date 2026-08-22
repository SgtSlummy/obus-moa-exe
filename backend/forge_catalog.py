"""Arcana Forge curated GitHub project catalog."""
from __future__ import annotations


def item(id: str, name: str, repo: str, category: str, description: str, capabilities: list[str],
         integration: str, windows_mode: str, risk: str = "low", status_binary: str | None = None,
         installer: str | None = None, package: str | None = None, recommended: bool = False) -> dict:
    return {
        "id": id, "name": name, "repo": repo, "url": f"https://github.com/{repo}",
        "category": category, "description": description, "capabilities": capabilities,
        "integration": integration, "windows_mode": windows_mode, "risk": risk,
        "status_binary": status_binary, "installer": installer, "package": package,
        "recommended": recommended,
    }


FORGE_NAME = "Arcana Forge"
PROJECTS = [
    item("vllm", "vLLM", "vllm-project/vllm", "inference", "High-throughput GPU model serving; use WSL2 or Docker on Windows.", ["inference", "gpu", "serving", "openai_api"], "service", "wsl_or_docker", "medium", recommended=True),
    item("gptcache", "GPTCache", "zilliztech/gptcache", "optimization", "Semantic response cache for repeated LLM requests.", ["cache", "semantic_search", "latency", "cost"], "python_library", "isolated_venv", "low", package="gptcache", recommended=True),
    item("llmlingua", "LLMLingua", "microsoft/llmlingua", "optimization", "Prompt and KV-cache compression for lower token use.", ["compression", "context", "prompt", "tokens"], "python_library", "isolated_venv", "low", package="llmlingua", recommended=True),
    item("codeburn", "Codeburn", "getagentseal/codeburn", "observability", "Local token usage and cost telemetry for coding agents.", ["observability", "tokens", "cost", "coding"], "cli", "native", "low", "codeburn", recommended=True),
    item("caveman", "Caveman", "JuliusBrussee/caveman", "optimization", "Agent context compression and token-minimization suite.", ["compression", "tokens", "memory", "coding"], "plugin_suite", "review_required", "medium"),
    item("gortex", "Gortex", "zzet/gortex", "code_intelligence", "Local code graph and MCP context engine.", ["code", "graph", "mcp", "retrieval"], "mcp", "native_or_source", "low", status_binary="gortex", recommended=True),
    item("headroom", "Headroom", "headroomlabs-ai/headroom", "optimization", "Compress tool output, logs, files, and RAG chunks.", ["compression", "tools", "rag", "tokens"], "mcp", "native", "low", "headroom", recommended=True),
    item("outlines", "Outlines", "dottxt-ai/outlines", "structured_output", "Schema-constrained structured generation.", ["json", "schema", "structured_output", "validation"], "python_library", "isolated_venv", "low", package="outlines"),
    item("rtk", "RTK", "rtk-ai/rtk", "optimization", "Token-saving proxy for common developer commands.", ["compression", "cli", "coding", "tokens"], "cli", "native", "low", "rtk", recommended=True),
    item("ponytail-skills", "Karpathy Ponytail Skills", "AbdullahHameedKhan/karpathy-ponytail-skills", "skills", "Coding discipline and simplicity skill pack.", ["skills", "coding", "planning", "review"], "skill_pack", "manual_review", "medium"),
    item("superpowers", "Superpowers", "obra/superpowers", "skills", "Agentic software-development methodology and skills.", ["skills", "tdd", "debugging", "planning"], "skill_pack", "plugin_review", "medium"),
    item("ragflow", "RAGFlow", "infiniflow/ragflow", "rag", "Full RAG and agent context service.", ["rag", "agents", "retrieval", "documents"], "service", "docker", "high"),
    item("haiku-rag", "Haiku RAG", "ggozad/haiku.rag", "rag", "Local hybrid and multimodal RAG with MCP.", ["rag", "mcp", "documents", "multimodal"], "mcp_service", "isolated_venv", "medium"),
    item("agent-reach", "Agent Reach", "Panniantong/Agent-Reach", "research", "Internet search and reading router for agents.", ["research", "web", "github", "media"], "cli", "native", "low", "agent-reach", recommended=True),
    item("opennews", "OpenNews MCP", "6551Team/opennews-mcp", "research", "News aggregation, ratings, signals, and updates.", ["news", "research", "mcp", "monitoring"], "mcp_service", "isolated_venv", "medium"),
    item("deeptutor", "DeepTutor", "HKUDS/DeepTutor", "education", "Personalized tutoring and deep-research multi-agent system.", ["education", "research", "agents", "rag"], "service", "docker", "high"),
    item("oh-my-hermes", "Oh My Hermes", "rlaope/oh-my-hermes", "orchestration", "Hermes-native skills, memory, subagents, and MoA harness.", ["orchestration", "skills", "memory", "agents"], "hermes_plugin", "native", "medium", recommended=True),
    item("pinchtab", "PinchTab", "pinchtab/pinchtab", "browser", "Browser automation and MCP tooling.", ["browser", "automation", "mcp", "research"], "mcp", "native", "low", "pinchtab", recommended=True),
    item("lightpanda", "Lightpanda Browser", "lightpanda-io/browser", "browser", "Headless browser designed for AI automation.", ["browser", "automation", "performance"], "service", "wsl_or_docker", "medium"),
    item("infinite-bookshelf", "Infinite Bookshelf", "Bklieger/infinite-bookshelf", "creative", "Book-generation application using Groq and Llama.", ["creative", "books", "writing"], "standalone_app", "isolated_venv", "medium"),
    item("penecho", "Penecho", "penecho/penecho", "creative", "Spatial canvas for handwriting, diagrams, and reasoning.", ["canvas", "visual", "reasoning", "education"], "standalone_app", "node_source", "medium"),
    item("llmfit", "LLMFit", "AlexsJones/llmfit", "inference", "Hardware-aware local model and runtime recommendations.", ["hardware", "models", "inference", "optimization"], "cli", "native", "low", "llmfit", recommended=True),
    item("ghost-downloader", "Ghost Downloader 3", "XiaoYouChR/Ghost-Downloader-3", "utility", "General download manager; catalog-only for OBus.", ["downloads"], "standalone_app", "catalog_only", "high"),
    item("open-design", "Open Design", "nexu-io/open-design", "creative", "Local-first design engine and coding-agent plugin.", ["design", "ui", "slides", "media"], "plugin_suite", "node_source", "medium"),
    item("public-apis", "Public APIs", "public-apis/public-apis", "reference", "Curated public API directory.", ["reference", "apis", "research"], "knowledge_catalog", "no_install", "low"),
    item("refine", "Refine", "refinedev/refine", "ui", "React framework for admin panels and internal tools.", ["ui", "react", "dashboard", "crud"], "development_framework", "node_source", "low"),
    item("olmocr", "olmOCR", "allenai/olmocr", "documents", "GPU document OCR pipeline.", ["ocr", "documents", "vision", "gpu"], "python_service", "wsl_or_docker", "high"),
    item("crewai", "CrewAI", "crewAIInc/crewAI", "orchestration", "Role-based multi-agent orchestration framework.", ["agents", "orchestration", "planning", "tools"], "python_library", "isolated_venv", "medium", package="crewai"),
    item("mempalace", "MemPalace", "MemPalace/mempalace", "memory", "Local-first verbatim AI memory with semantic retrieval and MCP.", ["memory", "retrieval", "mcp", "agents"], "uv_tool", "native", "low", status_binary="mempalace", installer="uv_tool", package="mempalace", recommended=True),
]

PROJECT_BY_ID = {project["id"]: project for project in PROJECTS}
assert len(PROJECTS) == 29
