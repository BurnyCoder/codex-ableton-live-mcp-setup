<!-- Global context: contribution workflow for changes to automation, documentation, tests, and pins. -->

# Contributing

Thank you for helping make the Windows setup safer and more reproducible.

## Start here

1. Read [`AGENTS.md`](AGENTS.md), especially the safety invariants.
2. Fork or clone the repository and create a focused branch.
3. Install the locked development environment:

   ```powershell
   uv sync --locked
   ```

4. Add a failing test for changed behavior before implementation.
5. Keep changes modular and update the relevant guide.

## Pull-request requirements

A pull request should explain the problem, safety impact, method, tests, and
rollback implications. Before opening it, run:

```powershell
uv run pytest
.\manage.ps1 doctor --json
.\manage.ps1 install --dry-run --accept-risk
```

Do not attach raw logs or configuration backups. Sanitize usernames, machine
names, absolute personal paths, Live object IDs, set signatures, process IDs,
tokens, and non-default set contents.

Changes to `config/versions.json` need an isolated pin-update pull request. Verify
the exact upstream commit, parent, and tree; run the complete pinned upstream
suite; update the affected documentation; and explain why the new source is
trusted.

## Code and documentation style

- Prefer standard-library features and small readable functions.
- Keep the PowerShell wrapper thin and platform-specific behavior behind named
  Python phases.
- Add a global-context header to every authored file and purpose/contract
  docstrings to functions.
- Cite primary sources for external behavior. Recheck Codex desktop UI steps
  against current official OpenAI documentation.
- Use forward-slash path examples inside `.env` and TOML.
- Avoid duplicating long instructions: link to the canonical guide.
- Keep logs complete locally and shared summaries concise and sanitized.

## Live testing

Automated CI cannot run Ableton Live. End-to-end testing requires an authorized
human checkpoint, an empty/default Live Set, sequential read-only probes, and the
[manual release checklist](docs/release-checklist.md). Never dismiss a modal or
mutate a contributor's set to make a test pass.

## Security reports

Do not open a normal issue for a sensitive vulnerability. Follow
[`SECURITY.md`](SECURITY.md).
