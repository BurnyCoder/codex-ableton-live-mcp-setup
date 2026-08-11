<!-- Global context: canonical end-to-end Windows replication procedure from clone through fresh-client read-only acceptance. -->

# Complete Windows installation

This is the canonical replication path. Run commands in PowerShell 7. Stop if a
pin, test, or runtime-safety check differs from the documented acceptance result.

## 1. Back up Live work and close Live

Save important sets and copy them to an independent location. Close Ableton Live
before Remote Script installation. If Live presents a save, recovery, crash, or
update dialog at any later point, handle it yourself; do not ask an agent or the
installer to discard it.

## 2. Clone this companion repository

```powershell
git clone https://github.com/BurnyCoder/codex-ableton-live-mcp-setup.git
Set-Location codex-ableton-live-mcp-setup
git status --short
```

The last command should print nothing. This repository does not contain the
upstream Ableton MCP source; the verified source is acquired in a later phase.

## 3. Create the companion environment

```powershell
uv sync --locked
```

`uv` creates this repository's `.venv` and installs the exact locked companion
dependencies. It may download Python 3.14 if no compatible interpreter exists.
Astral documents that virtual environments isolate packages from the system
Python and that `uv` discovers a default `.venv` automatically.

## 4. Review optional configuration

```powershell
Copy-Item .env.example .env
notepad .env
```

All entries are comments, so the copied file initially uses discovery/defaults.
Uncomment only values you need. Supported non-secret keys are:

| Key | Meaning |
|---|---|
| `ABLETON_SETUP_CHECKOUT` | Destination for the pinned upstream checkout. |
| `ABLETON_USER_LIBRARY` | Exact Live User Library when discovery is ambiguous. |
| `ABLETON_SETUP_PYTHON` | Upstream environment Python request; default `3.14`. |
| `ABLETON_MCP_PORT` | New loopback bridge port; default `8765`. |
| `CODEX_MCP_SERVER_NAME` | Codex registration name; default `ableton-live-mcp`. |
| `CODEX_MCP_STARTUP_TIMEOUT_SEC` | MCP startup timeout; default `30`. |
| `CODEX_MCP_TOOL_TIMEOUT_SEC` | Per-tool timeout; default `120`. |
| `CODEX_MCP_APPROVAL_MODE` | `auto`, `prompt`, `writes`, or `approve`. |

Arguments supplied after a subcommand override `.env`; `.env` overrides automatic
discovery; discovery overrides defaults. Host `127.0.0.1`, Remote Script name
`Ableton_Live_MCP`, and UTF-8 Python I/O are fixed.

Do not put tokens in `.env`. It is ignored locally and is not an authentication
mechanism.

## 5. Run read-only diagnostics

```powershell
.\manage.ps1 doctor
.\manage.ps1 doctor --json
```

Resolve every error before installing. Warnings about unavailable Computer Use
may be accepted when you do not need visual app control. Confirm that:

- Git, `uv`, Python 3.14, and Codex are available;
- exactly one User Library is selected;
- the checkout destination is writable;
- port 8765 is free;
- any pre-existing `AbletonMCP` integration is reported as inventory only.

## 6. Preview every mutation

For the standard allow-all profile:

```powershell
.\manage.ps1 install --dry-run --accept-risk
```

Read the printed acquisition, environment, Remote Script, backup, and Codex
configuration targets. A dry run must not clone, install, edit Codex
configuration, or move files.

For a safer first-use policy, preview a mode that retains prompts:

```powershell
.\manage.ps1 install --dry-run --approval-mode writes
```

The `writes` mode prompts for tools not marked read-only. `prompt` asks for tool
approval. `approve` auto-approves all exposed tools and is the only mode requiring
`--accept-risk`. The supported values come from the
[official Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## 7. Install the pinned setup

Standard profile:

```powershell
.\manage.ps1 install --accept-risk
```

The command performs these named phases:

1. verifies prerequisites and selected paths;
2. clones `bschoepke/ableton-live-mcp` and verifies base
   `70f7df9192b78d9bd9405f369c9e046c88f1610e`;
3. fetches PR #15, verifies commit
   `a93d223440b275feda2fb08cdf814238c1270e00`, its expected parent, and patched
   tree `2d97d0b270f4d9058e2fd624af7e3b769e3493bd`;
4. creates the upstream checkout's own `.venv` with Python 3.14;
5. installs the verified checkout editable with `.[dev]`—not from PyPI;
6. writes a git-excluded runtime `.env` with loopback, port, User Library, and
   UTF-8 settings;
7. inventories/hashes a pre-existing `AbletonMCP`, if present;
8. installs `Ableton_Live_MCP` under the selected User Library with update-safe
   semantics;
9. creates a timestamped SHA-256 Codex config backup and saves only the prior
   managed section for rollback;
10. registers the STDIO command, 30/120-second timeouts, `required=false`, and
    the selected approval mode while preserving unrelated TOML text/comments;
11. resolves the result with Python `tomllib`, `codex mcp get --json`, and
    `codex mcp list`.

With the standard profile, no `enabled_tools` or `disabled_tools` keys are
written, so all 37 schemas remain exposed.

## 8. Validate before launching Live

```powershell
.\manage.ps1 validate pre-live
.\manage.ps1 validate pre-live --json
```

Confirm the completed install result reports that the full upstream suite had
zero failures, or exactly the two test-only Windows path assertions recorded in
`config/versions.json`, followed by a passing run with only those nodes
deselected. The explicit `validate pre-live` command then rechecks Remote Script
currency, visual dependencies, 37 schemas, Unicode, LF-only framing, and
malformed-JSON recovery without repeating the long upstream suite.

See [Validation](validation.md) for the full contract.

## 9. Complete the Live checkpoint manually

Follow [Live activation](ableton-activation.md). In summary:

1. launch Live and finish any update/recovery dialog yourself;
2. open **Settings → Link, Tempo & MIDI**;
3. add **Ableton Live MCP** as a second Control Surface;
4. set its Input and Output to **None**;
5. leave any existing `AbletonMCP` slot unchanged.

## 10. Validate the running bridge

With a default/empty set open:

```powershell
.\manage.ps1 validate post-live
.\manage.ps1 validate post-live --json
```

Require listener 8765, current installed/runtime files,
`runtime_current: true`, `live_mutations_safe: true`, working visual dependencies,
a nonblank Ableton-only capture, and no recent Remote Script/Python startup error.
Port 9877 is required only when `doctor` detected the older integration before
installation.

## 11. Confirm Codex and restart the desktop app

```powershell
codex mcp list
codex mcp get ableton-live-mcp --json
```

The ChatGPT desktop app, Codex CLI, and IDE extension share the local MCP
configuration, but running clients need a restart after server changes. Exit and
reopen Codex desktop.

Start a fresh Codex task with the
[read-only validation prompt](../prompts/read-only-live-validation.md). It must
call only `live_ping` and `live_set_summary`. Do not make a write call merely to
prove that approval mode works.

## 12. Optionally enable Computer Use

Follow [Codex desktop and Computer Use](codex-desktop.md). It is a separate
plugin and permission system; MCP works without it.

## Completion criteria

Installation is complete only when pre-Live validation, manual activation,
post-Live validation, semantic Codex registration, and fresh-client read-only
checks all pass. Preserve the timestamped local log. Publish only its sanitized
summary.
