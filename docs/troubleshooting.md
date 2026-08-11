<!-- Global context: safe diagnosis and recovery guidance that avoids destructive Git, Codex, Live, or filesystem actions. -->

# Troubleshooting

Start with read-only evidence:

```powershell
.\manage.ps1 doctor --json
.\manage.ps1 validate pre-live --json
```

Run `validate post-live --json` only after Live is manually activated. Preserve
the full local log; publish only a redacted excerpt.

## Common failures

| Symptom | Likely cause | Safe next action |
|---|---|---|
| `uv`, Git, or Codex missing | Prerequisite not on `PATH` | Install/update from the official source, open a new PowerShell session, rerun `doctor`. |
| More than one User Library candidate | Custom or synchronized Documents location | Set the exact `ABLETON_USER_LIBRARY` in `.env`; do not choose by guess. |
| Port 8765 already listening | Another local service or earlier MCP instance | Identify the owner; stop only a process you recognize, or choose a new `ABLETON_MCP_PORT` before installation. |
| Commit, parent, or tree mismatch | Upstream PR changed, wrong ref, or checkout tampering | Stop. Do not bypass the pin. Compare against `config/versions.json` and open a pin-review PR if an upgrade is intended. |
| Checkout is dirty during update | Local edits in the managed upstream checkout | Inspect `git status` and preserve the work elsewhere. Do not use `git reset --hard`. |
| Exactly two documented path tests fail | Known PR #14 test-only defect | Confirm the exact node IDs, then require the second deselected run to pass. |
| Any other upstream test fails | Regression, environment incompatibility, or bad checkout | Block installation/update and investigate the first unexpected failure. |
| `--skip-live` says Remote Script stale | Installed files differ from checkout | Close Live, rerun the idempotent install/update, then repeat pre-Live validation. |
| `Ableton Live MCP` absent from picker | Wrong User Library, extra folder nesting, or Live not restarted | Check `User Library/Remote Scripts/Ableton_Live_MCP/__init__.py`, rerun pre-Live validation, relaunch Live. |
| Bridge not listening | Control Surface not selected, startup error, or different port | Confirm the second Control Surface row and Input/Output `None`; inspect the validator's recent Live-log summary. |
| `runtime_current: false` | Live loaded an older installed script | Stop mutations, close/relaunch Live after reinstalling, and require the full validator to pass. |
| `live_mutations_safe: false` | Modal, stalled Live main thread, or runtime mismatch | Inspect Live visually. Do not queue more calls or lengthen timeouts blindly. |
| Tool schema is missing/stale | Codex client started before config/server change | Restart the desktop app or CLI process and verify `/mcp`/`codex mcp list`. |
| Non-ASCII data is corrupted or JSON uses CRLF | PR #15 fix not active | Verify the exact patched tree and configured executable. Treat as failed installation. |
| One malformed JSON line kills tools | PR #15 fix not active | Stop; verify pin/tree and repeat protocol recovery test. |
| Ableton-only screenshot is blank | Locked/sleeping display, invisible Live window, or capture backend issue | Unlock/wake the active desktop, make Live visible, and retry once; do not broaden capture to the desktop. |
| Computer Use cannot see Ableton | App permission missing or Ableton not on active desktop | Bring Live forward, review Settings → Computer use, and approve the exact reported app when prompted. |
| M4L tools fail on Intro/Standard | Edition lacks Max for Live | Use core Live/visual tools. Exposure/approval does not add the missing Live capability. |

## Inspect a port without killing anything

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

Use Task Manager or `Get-Process -Id <PID>` only to identify the owner. Do not
terminate an unknown process. A configured alternative must still bind to
`127.0.0.1`.

## Live dialogs and hangs

A save, recovery, crash, plugin scan, or update modal can block Live's main
thread while the socket still exists. If validation classifies a Live-main-thread
timeout or hang:

1. stop all MCP mutations;
2. inspect only the Ableton window;
3. let the user resolve the modal;
4. restart/reload Live only after the user's work is safe;
5. rerun full post-Live validation before any mutation.

Never blind-retry a mutation after a response timeout. Its status may be unknown,
and a retry can duplicate clips, devices, or automation.

## Codex config problems

The installer validates TOML semantically and preserves unrelated text/comments.
If Codex cannot parse the result, use the setup's timestamped backup and saved
prior managed section. Prefer `rollback` over replacing the entire config with an
older copy, because a full restore can erase settings added later.

```powershell
.\manage.ps1 rollback --dry-run
```

Review the target, close Live, then follow
[Updates and rollback](updates-and-rollback.md).

## Ask for help safely

Include companion/upstream versions, public SHAs, command exit codes, failed
check names, and a redacted error. Exclude usernames, machine names, full paths,
set names/content, IDs, signatures, config backups, tokens, and raw screenshots.
Use the private process in [`SECURITY.md`](../SECURITY.md) for vulnerabilities.
