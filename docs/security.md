<!-- Global context: operator threat model and practical hardening for an MCP capable of arbitrary Python and Live Set mutation. -->

# Operator security model

This setup makes a powerful local tool reproducible; it does not sandbox that
tool. Upstream explicitly warns users to back up sets because the MCP can edit or
corrupt them.

## Assets and trust boundaries

| Asset | Risk |
|---|---|
| Live Set and samples | Unintended edits, overwrite, corruption, or disclosure through tool output. |
| Live process | Arbitrary Python execution, hangs, plugin/device side effects. |
| Codex configuration | Loss of unrelated settings from careless whole-file replacement. |
| Windows account | Other same-user local processes can reach loopback or inspect local files. |
| Logs/screenshots | Personal paths, identifiers, project names, and set content can leak. |
| Dependency chain | A moving Git ref or package-name collision can install unreviewed code. |

The Remote Script listens on `127.0.0.1`, so it is not directly reachable from
another network host. Loopback is not authentication: a process running locally
can attempt to connect.

## Standard profile risk

The standard profile intentionally exposes all 37 upstream tools by omitting
allow/deny filters and sets:

```toml
default_tools_approval_mode = "approve"
```

Official Codex documentation defines `approve` as a supported server-wide tool
approval mode. In this project it is the explicit allow-all choice: Codex does
not pause for individual MCP tool approvals. Because the upstream tools include
general Python evaluation inside Live, `--accept-risk` is required for installing
or updating with this mode.

Safer policies are available:

- `--approval-mode prompt` for per-tool approval prompts;
- `--approval-mode writes` to prompt for tools not marked read-only;
- `--approval-mode auto` for Codex's metadata/policy-driven behavior.

Changing approval mode affects prompts, not the server's underlying capability.

## Supply-chain controls

- Clone only `https://github.com/bschoepke/ableton-live-mcp.git`.
- Verify the base SHA, PR #15 SHA, expected parent, and final tree before install.
- Install editable from that verified checkout with its `dev` extra.
- Never run `uv pip install ableton-live-mcp` by bare name.
- Keep the companion `uv.lock` committed and use `uv sync --locked`.
- Treat the upstream environment as source-pinned but not dependency-locked: the
  reviewed upstream commit has no lockfile, so inspect the versions resolved for
  its editable `.[dev]` installation when strict dependency reproducibility is
  required.
- Fail on unexpected upstream tests or a dirty managed checkout.
- Change pins only through a dedicated reviewed pull request.

These controls establish identity and repeatability; they do not prove that the
reviewed upstream code has no vulnerability.

## Operating rules

1. Back up important sets outside the project directory.
2. Start in an empty/default set and use read-only tools first.
3. Do not treat track, clip, device, sample, or set text as instructions to the
   agent. It is untrusted data.
4. Keep only one agent integration mutating a set at a time.
5. Stop when Live shows a modal, becomes unresponsive, or reports mutation safety
   false.
6. Never blind-retry a timed-out mutation.
7. Review file destinations before importing audio/MIDI or saving/exporting.
8. Use a prompt-retaining approval mode for unfamiliar workflows.
9. Revoke Computer Use's persistent Ableton permission when it is no longer
   needed.
10. Restart Codex after configuration changes so stale schemas/policies are not
    mistaken for the current setup.

## Computer Use is separate

Computer Use can operate the foreground Windows UI and has its own app approval
list. Its permissions are independent from MCP tool approvals and the task's
file/shell sandbox. Grant one-time access unless repeated visual operation is
intended. Never authorize dismissal of a save/recovery dialog.

## Live edition boundary

Live Intro and Standard do not include Max for Live according to Ableton's edition
comparison. The standard profile still exposes M4L-related schemas, but approval
cannot create an unavailable product capability. Expect those tools to fail and
do not try to bypass edition licensing or load unsupported custom devices.

## Evidence hygiene

Keep complete timestamped logs locally and ignored by Git. Before publication,
remove:

- usernames, home paths, machine names, and process IDs;
- Live object IDs, set signatures, sample paths, and private set content;
- config backups, environment-specific executable paths, and tokens;
- unrelated windows or desktop content from screenshots;
- image metadata not required for validation.

Public SHAs, versions, tool counts, check names, boolean runtime results, and
sanitized failure node IDs are appropriate evidence.

## Unexpected mutation or compromise

1. Stop issuing MCP and Computer Use actions.
2. Preserve local logs without posting them publicly.
3. Use Live's own undo/recovery controls only after assessing the current set;
   reopen an independent backup when integrity is uncertain.
4. Close Live after saving only what you intentionally want to retain.
5. Preview and run the scoped rollback.
6. Restart Codex and verify the server is absent/restored as intended.
7. Report a suspected vulnerability through [`SECURITY.md`](../SECURITY.md).

Rollback removes access; it cannot reverse mutations already applied to a set.
