# OBus–Codex comparison matrix

`data/obus-codex-comparison-manifest.json` is the release-facing definition of
the OBus-versus-Codex comparison. It keeps the comparison honest by making
fixtures, weights, safety gates, and the performance threshold versioned
source rather than an informal checklist.

## What is compared

Each product gets the same fixture, baseline worktree, verifier rubric, and
environment record. The recorded environment includes the operating system,
hardware, sandbox, approval policy, network setting, model, product version,
and baseline worktree hash. OBus and Codex must use separate clean worktrees;
one product's changes must never become input to the other product's run.

The matrix measures desktop lifecycle, thread cancellation, terminal control,
scoped code edits, major-risk approval, context isolation, parallel work,
receipts/recovery, local-model operation, performance, installation, and
release reporting. Critical fixtures cannot pass without recorded explicit
approval. A release report requires all fixtures to be measured and passed,
an OBus weighted score of at least 85%, no domain below 70%, and no critical
blockers.

## Use

The default command is safe and plan-only. It neither opens a terminal nor
starts either agent:

```powershell
python scripts/obus_codex_comparison.py --plan
```

Generate the normalized receipt shape for an adapter or verifier:

```powershell
python scripts/obus_codex_comparison.py --template obus
python scripts/obus_codex_comparison.py --template codex
```

After a paired run has produced two completed, redacted receipts, score them:

```powershell
python scripts/obus_codex_comparison.py `
  --obus-receipt .\artifacts\obus-receipt.json `
  --codex-receipt .\artifacts\codex-receipt.json `
  --output .\artifacts\comparison.json `
  --markdown-output .\artifacts\comparison.md
```

The command exits with code `0` only when all release gates pass; it returns
`2` for a failed, incomplete, or invalid comparison. Receipts contain metadata,
scores, metrics, approval facts, and evidence paths only. Do not insert raw
prompts, command output, tokens, or provider credentials.

## Adapter boundary

The Codex adapter must use `backend.codex_policy.build_codex_exec_command`,
which uses `codex exec --approve-for-me` and rejects unrestricted bypass flags.
The OBus adapter submits the equivalent objective to `POST /api/harness/tasks`
in an isolated worktree and waits for a terminal task state. Completion alone
does not assign a passing score: the same verifier records the 0–5 score for
both products.
