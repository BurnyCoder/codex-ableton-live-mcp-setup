<!-- Global context: preflight requirements for reproducing the verified Windows installation without modifying the machine unexpectedly. -->

# Prerequisites

The first release is verified on Windows 11. The upstream project may work on
macOS, but the automation and acceptance criteria here are Windows-specific.

## Required software

| Component | Requirement | Check |
|---|---|---|
| Windows | Windows 11; Windows 10 is not part of this project's tested matrix | `winver` |
| PowerShell | PowerShell 7 recommended | `$PSVersionTable.PSVersion` |
| Git | Current Git for Windows | `git --version` |
| `uv` | Current release with Python 3.14 support | `uv --version` |
| Codex | Desktop app and CLI signed in to the same local Codex host | `codex --version` |
| Ableton Live | Live 12 installed and authorized | Help → About Live |

`uv` can download a compatible Python automatically. The verified baseline used
Python 3.14.2 and `uv` 0.11.27; those patch versions are evidence, not hard
minimums. Astral documents both the Windows installer and managed Python behavior
in its [`uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/)
and [Python guide](https://docs.astral.sh/uv/guides/install-python/).

GitHub CLI is needed only for maintainers publishing releases, not for a normal
installation.

## Required access and disk locations

- The Windows account must be able to write the chosen checkout directory, the
  Ableton User Library, and the local Codex configuration directory.
- Live's User Library must be enabled. Ableton documents the default Windows
  location as `C:/Users/USERNAME/Documents/Ableton/User Library` and requires a
  `Remote Scripts` child directory for third-party scripts.
- Port 8765 must be free unless you deliberately choose another loopback port in
  `.env` or with a command-line override.
- The setup needs outbound HTTPS access to GitHub and the Python package indexes
  during installation. Live-to-MCP traffic stays on `127.0.0.1`.

If more than one plausible User Library is found, the setup fails with candidates
instead of guessing. Put the intended path in `.env`, using quotes and forward
slashes:

```dotenv
ABLETON_USER_LIBRARY="D:/Music/Ableton/User Library"
```

## Protect your work first

Before any install or update:

1. Save the current Live Set.
2. Make a copy outside the working project directory.
3. Close any set that cannot safely be inspected by an agent.
4. Plan to use Live's default empty set for first validation.

The upstream MCP can execute arbitrary Python inside Live. A successful installer
does not make Live mutations reversible or safe.

## Optional Computer Use

Computer Use is not required for MCP transport. It is useful for inspecting Live
dialogs and settings that have no structured interface. Availability depends on
the user's region/account. Set it up only after reading the
[Codex desktop guide](codex-desktop.md); its app permissions are independent of
the MCP approval mode.

## Continue

Proceed to the [complete Windows installation](installation.md).
