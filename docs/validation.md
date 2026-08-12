<!-- Global context: test stages, expected evidence, and pass/fail criteria for the companion and pinned upstream setup. -->

# Validation and acceptance criteria

Validation is deliberately sequential. Offline checks must pass before Live is
launched, and Live checks must pass before a fresh Codex client is trusted.

## Stage 1: doctor

```powershell
.\manage.ps1 doctor
.\manage.ps1 doctor --json
```

`doctor` is read-only. It reports prerequisites, selected/discovered paths,
checkout state, selected port, Codex availability, an existing `AbletonMCP`
integration, and Computer Use status when discoverable.

Pass when all required prerequisites and exactly one User Library are resolved,
the selected port is available for a new install, and no target path is unsafe.
Computer Use may be unavailable because it is optional.

## Stage 2: mutation preview

```powershell
.\manage.ps1 install --dry-run --accept-risk
```

Pass when the report names only the intended upstream checkout,
`Ableton_Live_MCP` target, scoped Codex MCP entry, and timestamped backup/state
locations. A dry run must not change Git state, create a virtual environment,
write Remote Script files, or edit Codex configuration.

## Stage 3: pre-Live validation

```powershell
.\manage.ps1 validate pre-live
.\manage.ps1 validate pre-live --json
```

The preceding `install` or `update` command must have verified:

- upstream base, PR commit, parent, and patched tree match
  `config/versions.json`;
- the checkout is clean and package version is `0.1.1`;
- the complete upstream test suite has either zero failures or exactly the two
  accepted Windows path assertion node IDs;
- a second suite run deselecting exactly those two node IDs passes everything.

The explicit `validate pre-live` command rechecks the following fast pre-Live
contract without rerunning the complete upstream suite:

- `ableton-live-mcp-validate --skip-live` exits successfully;
- installed Remote Script files are current;
- Pillow and the Windows visual-capture backend are available;
- STDIO initialize succeeds and `tools/list` returns 37 unique tools with valid
  object schemas;
- a non-ASCII request/response round trip remains valid UTF-8 with LF-only JSON
  records;
- malformed JSON returns JSON-RPC `-32700`, after which the server still handles
  a valid request.

The two accepted test-only failures are documented in upstream
[PR #14](https://github.com/bschoepke/ableton-live-mcp/pull/14):

- `test_agent_audio_tap_builds_amxd_container`
- `test_agent_m4l_host_patch_contains_runtime_and_role_io`

They compare raw Windows backslash paths with the forward-slash paths production
code intentionally emits for Max. They are not a license to accept any other
failure. If PR #14 or an equivalent fix becomes part of a future reviewed pin,
the manifest and expected result must be updated together.

## Stage 4: post-Live validation

Complete the [manual Live checkpoint](ableton-activation.md), then run:

```powershell
.\manage.ps1 validate post-live
.\manage.ps1 validate post-live --json
```

Pass only when all of these are true:

| Evidence | Required result |
|---|---|
| New listener | The selected loopback port accepts a connection and the upstream validator confirms the Live bridge/runtime, default 8765. |
| Existing listener | Port 9877 remains listening only when preinstall inventory found the older integration; process ownership remains a manual release check. |
| File currency | Installed Remote Script source hashes match the checkout. |
| Runtime currency | `runtime_current: true`. |
| Mutation gate | `live_mutations_safe: true`. |
| Visual dependencies | Pillow and Windows capture backend available. |
| Visual evidence | Ableton-only PNG is nonblank and visibly shows Live, not another app. |
| Live log | No recent Remote Script/Python startup error for `Ableton_Live_MCP`. |

Do not treat `runtime_current: false` as a warning. It means the running Control
Surface loaded different code and must be reinstalled/reloaded before testing.
Do not mutate Live when `live_mutations_safe` is false.

## Stage 5: fresh Codex client

1. Confirm registration:

   ```powershell
   codex mcp list
   codex mcp get ableton-live-mcp --json
   ```

2. Restart Codex desktop or start a new CLI process.
3. Use [`prompts/read-only-live-validation.md`](../prompts/read-only-live-validation.md).
4. Require successful `live_ping` and `live_set_summary` only.

This proves the actual configured STDIO command and schema loading without
introducing a destructive regression test. Never use a set mutation merely to
prove that `approve` suppresses approval prompts.

## Logs and shared summaries

Every command streams timestamped subprocess command, stdout, and stderr to the
terminal and an ignored local log without truncation. When an LLM prompt is used,
store the complete prompt and output in the same timestamped evidence session.

Raw logs are private because they may contain usernames, machine names, absolute
paths, process IDs, Live object IDs, set signatures, and set contents. Published
summaries may include versions, public SHAs, counts, booleans, failure node IDs,
and high-level results after redaction.

Never publish a screenshot until it has been visually inspected, limited to an
Ableton window, checked for non-default set content, and stripped/checked for
metadata.

## Structured-output stability

`--json` is intended for CI and diagnostic tooling. Consumers should treat a
nonzero exit code or explicit failed check as failure; they should not infer
success from the presence of partial diagnostic fields. Human logs remain the
source for untruncated subprocess detail.
