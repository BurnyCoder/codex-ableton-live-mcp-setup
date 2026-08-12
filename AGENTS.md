<!-- Global context: repository-specific operating rules for human and automated contributors to this companion setup project. -->

# Repository agent guide

This repository automates a safety-sensitive bridge between Codex and Ableton
Live. Prefer the smallest practical implementation, fail closed on identity or
validation mismatches, and preserve user work.

## Authoritative contracts

- `config/versions.json` is the only authority for upstream SHAs, expected tree,
  package version, tool count, and accepted upstream-only test failures.
- `manage.ps1` is a thin entry point. Phase behavior belongs in the Python
  package, with orchestration separated from implementation details.
- Configuration precedence is CLI argument, `.env`, discovery, then default.
- Fixed values are loopback host `127.0.0.1`, Remote Script
  `Ableton_Live_MCP`, and UTF-8 Python I/O. The Codex server name defaults to
  `ableton-live-mcp` but can be overridden through the documented interface.
- Never install the bare `ableton-live-mcp` PyPI distribution. Install editable
  from the verified Git checkout.
- Never vendor upstream source or a PR patch in this repository.

## Safety invariants

- Require `--accept-risk` only when approval mode is `approve`.
- Omit `enabled_tools` and `disabled_tools` for the standard all-37-tools setup.
- Back up Codex configuration before editing it, preserve unrelated text and
  comments, and retain the prior managed section for scoped rollback.
- Never replace an entire newer `config.toml` during rollback.
- Never modify or remove `AbletonMCP`, its port 9877, or any unrelated Control
  Surface. Inventory it only when present.
- Install or update only the resolved `Ableton_Live_MCP` target. Clear Windows
  ReadOnly attributes only on explicitly resolved source/target directories.
- Move managed Remote Script content to a timestamped backup; never delete it.
- Never dismiss a Live save, recovery, crash, or update dialog. Stop for the user.
- Do not automate a Live restart or Control Surface change without explicit
  authorization. Post-Live validation is read-only.
- Do not run Live API probes concurrently.
- Redact usernames, machine names, absolute personal paths, process IDs, Live
  object IDs, set signatures, tokens, and raw configuration backups from public
  artifacts.

## Development method

1. Define the behavior and its failure cases in a test.
2. Implement one readable phase with a narrow interface.
3. Run the focused test, then the complete companion suite.
4. Exercise the wrapper exactly as a Windows user would, including `--dry-run`.
5. Inspect full timestamped logs for warnings, secrets, and inconsistent output.
6. Update the affected setup documentation when behavior changes.
7. Perform one correctness, security, maintainability, reliability, and design
   review before requesting merge.

Every authored source file needs a global-context header. Every public function
needs a purpose/contract docstring. Operational code should carry concise local
explanations where the reason is not evident, with primary-source links for
external formats or behavior. Avoid comments that merely restate syntax.

Use `apply_patch` for intentional text changes. Use formatters only after ensuring
they do not rewrite unrelated user work. Never put credentials in Git, logs,
fixtures, screenshots, or shared summaries.

## Required validation

Run from repository root:

```powershell
uv sync --locked
uv run pytest
.\manage.ps1 doctor --json
.\manage.ps1 install --dry-run --accept-risk
```

When a change affects upstream acquisition or validation, also run the pinned
offline integration workflow. Full upstream testing may have either zero failures
or exactly the two failure node IDs recorded in `config/versions.json`; any other
failure blocks completion. The second run must deselect exactly those two tests
and pass everything else.

Live end-to-end checks require a human-controlled disposable/default set. Require
`runtime_current: true`, `live_mutations_safe: true`, current installed files,
working visual dependencies, and a nonblank Ableton-only capture. Do not claim
end-to-end success from source tests alone.

## Documentation and local evidence

- Keep the README setup-first and concise; put extended operational detail in
  `docs/`.
- Use current primary documentation from upstream, OpenAI, Ableton, Astral,
  Python, GitHub, or Microsoft. Recheck unstable UI instructions before release.
- Preserve full local prompts and outputs in ignored timestamped logs. Publish
  only sanitized summaries.
- Do not publish screenshots unless they show only Ableton, have been inspected
  for hidden metadata/private content, and contain a disposable/default set.

## Release discipline

Pin updates require a dedicated pull request with reviewed source identity,
expected tests, and affected documentation updated together. Windows CI must
pass before merge. End-to-end Live acceptance remains a manual signed-off
checklist. Never create an upstream branch or PR from this companion repository.
