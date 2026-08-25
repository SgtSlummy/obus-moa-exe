# Contributing to Obus

## Development setup

Create an isolated Python environment, install `requirements.txt`, and run the server on loopback. Keep runtime data outside the checkout with `OCCULTBUS_HOME`.

## Before submitting a change

```powershell
python -m compileall -q backend tools scripts
python -m pytest -q
python -m pytest -q tools/obus_launcher/test_obus_launcher.py
python -m pip_audit
git diff --check
```

Run the Windows non-installing production build for launcher, packaging, dependency or static-asset changes.

## Change expectations

- Preserve explicit persisted provider choices; Codex remains the default for new implicit state.
- Keep optional integrations out of the health-critical startup path.
- Add or update tests for behavior, migrations, API contracts and security boundaries.
- Keep APIs and state migrations backward compatible or document the migration.
- Use atomic persistence and bounded input/output behavior.
- Return actionable errors without leaking tokens, credentials, machine paths or private workspace content.
- Do not commit virtual environments, build artifacts, local state, `.env`, credentials or generated reports.

## Pull requests

Describe the user-visible outcome, architectural impact, verification commands and results, security considerations, startup impact, and rollback plan. Keep unrelated worktree changes out of the pull request.

## Security reports

Do not open a public issue containing credentials or an exploitable secret. Remove exposed credentials immediately, rotate them with the provider, and report the issue privately to the repository owner with reproduction steps and affected versions.
