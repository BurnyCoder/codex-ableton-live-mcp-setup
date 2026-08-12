<!-- Global context: maintainer checklist for a public release whose CI is offline and whose Live acceptance requires an authorized Windows workstation. -->

# Manual release checklist

CI cannot run Ableton Live, so a release needs both Windows CI and a separately
signed-off Live acceptance run. Record only sanitized evidence.

## Source and repository

- [ ] `main` is clean and the release branch contains only intended files.
- [ ] `config/versions.json` has reviewed base, PR, parent/tree, package version,
      tool count, and accepted failure node IDs.
- [ ] `uv.lock` is current and `uv sync --locked` succeeds.
- [ ] No upstream source, PR patch, local `.env`, nested checkout, raw log, Codex
      config backup, credential, or personal path is tracked.
- [ ] MIT `LICENSE` and `THIRD_PARTY_NOTICES.md` are present.
- [ ] One correctness/security/maintainability/reliability/design review is done.

## Automated Windows checks

- [ ] Companion unit suite passes.
- [ ] `manage.ps1 doctor --json` returns valid structured output.
- [ ] Install/update/rollback dry runs make no state changes.
- [ ] Pin identity fails closed under SHA, parent, and tree mismatch tests.
- [ ] TOML upsert/restore tests preserve unrelated content/comments.
- [ ] Existing `AbletonMCP`, exact-target ReadOnly remediation, port conflict,
      redaction, and idempotent rollback tests pass.
- [ ] Complete pinned upstream suite has zero failures or exactly the manifest's
      two accepted test-only failures.
- [ ] The run deselecting exactly those two node IDs passes all remaining tests.
- [ ] `ableton-live-mcp-validate --skip-live` passes.
- [ ] STDIO returns 37 unique valid schemas, preserves UTF-8/LF, returns `-32700`
      for malformed JSON, and recovers for the next request.
- [ ] Secret/personal-path scan, Markdown links, and locked dependency checks
      pass.

## Authorized Live acceptance

- [ ] Tester saved/closed important sets and opened a disposable/default set.
- [ ] Existing `AbletonMCP` inventory, when present, is unchanged before/after.
- [ ] `Ableton Live MCP` is the second Control Surface; Input/Output are `None`.
- [ ] Port 8765 is Live-owned; 9877 is checked only when previously detected.
- [ ] Full validator exits zero with current installed files,
      `runtime_current: true`, and `live_mutations_safe: true`.
- [ ] Visual dependencies work and an Ableton-only capture is nonblank.
- [ ] The inspected capture contains no private or non-default set material.
- [ ] Recent Live log contains no relevant Remote Script/Python startup error.
- [ ] Fresh Codex process runs read-only `live_ping` and `live_set_summary`.
- [ ] Codex desktop sees the server after restart.
- [ ] Optional Computer Use instructions match current official OpenAI Docs and
      availability/permission boundaries are still accurate.

## Published documentation

- [ ] Any published PNG is Ableton-only, nonblank, visually inspected, and
      metadata-checked.
- [ ] README and version-specific guidance match the current manifest and the
      signed-off Live validation result.
- [ ] Source links resolve and unstable UI claims have an access/review date.
- [ ] Release notes state Windows-only validation, allow-all risk, and Live
      Intro/Standard M4L limitation.

## GitHub publication

- [ ] Draft PR CI passes; findings are resolved; PR is marked ready and merged
      while preserving meaningful commits.
- [ ] Feature branch is deleted after merge.
- [ ] Repository is public with the approved description and topics.
- [ ] Issues and dependency/security alerts are enabled.
- [ ] Wiki, Projects, and Discussions are disabled; automatic branch deletion is
      enabled.
- [ ] `main` protection requires a pull request and the Windows CI check for
      future changes.
- [ ] The release tag, notes, and intended assets match the reviewed merge.
- [ ] No fork, upstream branch, or upstream pull request was created.

Release sign-off should record date, companion commit, manifest identities,
Windows/Live/Codex versions, CI URL, and sanitized manual result—never the tester's
username, machine name, home path, process IDs, or Live object IDs.
