# Integrate Understand Anything into OBus UI

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Attach the open‑source Understand‑Anything toolchain to the existing OBus UI, enriching it with automatic code‑analysis dashboards, a comfy UI prompt entry, local LLM agent support for coding assistance, and elevated code‑execution capabilities for user‑level agents.

**Architecture:**
- **Front‑end**: Extend the current OBus UI (React/TS) with the Understand‑Anything dashboard as an embedded module or micro‑service.
- **Back‑end**: Add an Express/Node‑JS microservice (or a lightweight FastAPI) that hosts the Understand‑Anything core logic, exposing REST endpoints for graph generation, diff analysis, and chat commands.
- **LLM**: Wire the local LLM (Ollama / OpenAI local model) as the Understand‑Anything plugin’s backend model.
- **Agent Layer**: Extend the OBus agent runtime to launch a local LLM agent that can invoke the Understand‑Anything service and run arbitrary code with admin privileges via a sandboxed Exec service.

**Tech Stack:**
- Node.js (>=18) + pnpm, TypeScript
- Understand‑Anything monorepo (core, dashboard, plugin)
- React + Vite (for dashboard), Zustand, TailwindCSS
- Warp (open‑source terminal UI library) for console UI components in OBus
- Local LLM via Ollama (GGUF) served in Docker
- Agent runtime (existing OBus) with capability to spawn child Node processes

---

## Proposed Approach

1. **Package the Understand‑Anything service** – build and containerize the core into a lightweight image.
2. **Expose REST API** for OBus UI to fetch graph data, run `understand` commands, and retrieve chat responses.
3. **Embed or iframe the dashboard** in OBus UI as a dedicated tab, providing visual representation of the codebase.
4. **Add a comfy prompt entry** using Warp UI components, leveraging the local LLM to interpret prompts and generate code snippets.
5. **Implement a code‑execution microservice** that accepts agent commands and runs them with admin rights, sanitizing paths and commands.
6. **Hook everything into OBus agents** – new agent types: `code-helper`, `code-executor`, and `analysis-agent`.

## Step‑by‑Step Plan

### Task 1: Prepare Understand‑Anything Workspace
**Objective:** Build the Understand‑Anything core and dashboard for local use.

**Files to Create/Modify:**
- `understand-anything/package.json` (ensure `pnpm` lockfile exists)
- `understand-anything/README.md` (add a brief usage guide)

**Commands:**
```bash
cd Understand-Anything
pnpm i
pnpm --filter @understand-anything/core build
pnpm --filter @understand-anything/skill build
```
**Validation:**
- Run `pnpm test` to confirm tests pass.
- Start dev dashboard with `pnpm dev:dashboard` and verify the UI loads.

---

### Task 2: Containerize the Core Service
**Objective:** Create a Docker image that serves the core logic via HTTP.

**Files to Add:**
- `understand-anything/Dockerfile`
- `understand-anything/server.ts` (simple Express wrapper around core)
- `understand-anything/.dockerignore`

**Commands:**
```bash
# From root of Understand-Anything
# Build backend
node server.ts --build  # ensures dist built
# Build Docker image
docker build -t understand-anything:latest .
```
**Validation:**
- Run container locally and hit `/status` endpoint.
- Ensure it accepts `POST /understand` with a prompt.

---

### Task 3: Add OBus Integration Layer
**Objective:** Extend OBus backend to communicate with the Understand‑Anything service.

**Files to Modify/Add:**
- `src/agents/analysis-agent.ts` – new agent definition.
- `src/services/understand-service.ts` – HTTP client.
- `src/routes/understand.ts` – Express route to proxy requests.
- `src/ui/components/UnderstandDashboard.tsx` – UI wrapper for dashboard iframe.

**Commands to run locally for testing:**
```bash
# In OBus root
npm run build
npm start
# Visit http://localhost:3000/understand to load dashboard
```
**Validation:**
- Verify agent logs show successful request to Understand service.
- Dashboard renders graph correctly.

---

### Task 4: Implement Comfy Prompt Entry with Warp UI
**Objective:** Replace legacy prompt textarea with a Warp‑powered terminal‑style console.

**Files to Add/Modify:**
- `src/ui/components/PromptConsole.tsx` – Warp UI component.
- Update `src/ui/App.tsx` to use `PromptConsole` instead of old `<textarea>`.
- Add CSS for consistent styling.

**Notes:**
- Warp UI provides scrollable, line‑numbered input, syntax‑highlighting.
- Capture input on `Enter` and forward to OBus agent via WebSocket.

**Validation:**
- In browser, type a prompt and confirm that the agent receives it.
- Check console logs for prompt parsing.

---

### Task 5: Enable Code Execution at Agent Level
**Objective:** Provide an API that lets OBus agents run arbitrary shell commands with admin rights.

**Files to Add/Modify:**
- `src/services/exec-service.ts` – secure shell executor.
- `src/routes/exec.ts` – route exposing `/api/exec`.
- Update `agent.config.json` to grant `exec` permission to `analysis-agent`.

**Security:**
- Whitelist allowed command patterns.
- Run inside Docker container with least privilege, mapping only necessary volumes.
- Log all executions.

**Validation:**
- Use test agent to run `echo "hello"` and match output.
- Verify no unintended files modified.

---

### Task 6: Wire Local LLM for Code Assistance
**Objective:** Let agents generate code snippets using the local LLM via Understand‑Anything.

**Files to Modify:**
- `src/agents/code-helper.ts` – agent using Understand service.
- `src/services/llm-service.ts` – wrapper around Ollama local endpoint.

**Commands:**
```bash
# Run Ollama locally (example)
odamola serve -m ./models/ggml-large.bin
```
**Validation:**
- Agent receives prompt, forwards to `/understand`, receives JSON with code snippet.
- Agent inserts snippet into designated file.

---

## Files Likely to Change
- `Understand-Anything/` files (Dockerfile, server.ts)
- `src/agents/` (analysis-agent.ts, code-helper.ts)
- `src/services/` (understand-service.ts, exec-service.ts, llm-service.ts)
- `src/ui/` (UnderstandDashboard.tsx, PromptConsole.tsx, App.tsx)
- `src/routes/` (understand.ts, exec.ts)
- `.hermes/plans/` (this plan file)
- `docker-compose.yml` (add understand service)

## Tests / Validation
- `pnpm test` within Understand-Anything repo.
- Unit tests for `understand-service` and `exec-service` (write Jest tests).
- E2E test: OBus -> Execute prompt → Generates code → Agent writes file.
- Dashboard smoke test: `curl http://localhost:4000/health`.

## Risks & Trade‑offs
- **Dependency bloat:** Adding Node ecosystem may conflict with existing OBus Go or Rust components.
- **Security:** Running admin‑level code execution requires strict sandboxing.
- **Performance:** Understand‑Anything graph build can be heavy; consider caching.
- **UI integration:** Embedding React dashboard inside existing UI may cause style clashes; use CSS isolation.
- **LLM orchestration:** Needs robust fallback for network outages when pulling local models.

## Open Questions
- Should the Understand service run as a separate Docker container or co‑process with OBus? Docker offers isolation but adds complexity to dev ops.
- How to best expose visual dashboards? Full iframe or micro‑frontend injection?
- Which admin privileges are truly necessary? Should we use `runas` or `sudo` inside container?
- Is Warp UI the best terminal component for the prompt area, or should we use xterm.js?

## Next Steps
1. Create the Dockerfile and server wrapper.
2. Write minimal test suites for new services.
3. Commit plan file.
4. Kick off implementation via subagent-driven-development.

---

**Plan saved to:** `.hermes/plans/20260823_212422-integrate-understand-anything.md`

