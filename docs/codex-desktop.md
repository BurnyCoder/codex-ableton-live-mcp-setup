<!-- Global context: current official setup path and permission boundaries for optional Computer Use and shared local MCP configuration. -->

# Codex desktop and Computer Use

Computer Use lets Codex inspect or operate Ableton's graphical interface. It is
optional: the Ableton MCP uses a structured STDIO/TCP path and does not depend on
Computer Use.

The steps below follow the current
[official OpenAI Computer Use documentation](https://learn.chatgpt.com/docs/computer-use).
Availability can vary by region, account, or workspace policy.

## Install or enable the plugin

1. Open the ChatGPT desktop app on Windows.
2. Select **Codex**, or select **ChatGPT** and switch to **Work**.
3. Open Settings (`Ctrl+,` on current Windows builds) and select
   **Plugins → Computer Use**. If the shortcut differs, use the app's Settings
   menu.
4. Select **Install plugin** if offered.
5. Select **Enable** if offered.
6. Turn on both the **Computer Use** server and skill toggles.
7. Select **Try now**.
8. Open **Settings → Computer use** and review app access.

The setup CLI diagnoses whether Computer Use appears available/enabled but does
not install it, change plugin toggles, or edit app permissions.

## First use with Ableton

1. Keep Ableton visible on the active Windows desktop.
2. Ask Codex for a narrowly scoped visual-only task, for example:

   ```text
   Use Computer Use only to inspect the visible Ableton Settings window. Report
   the selected Control Surface, Input, and Output. Do not click or type.
   ```

3. When prompted for Ableton access, review the displayed app identity.
4. Choose one-time access for the most conservative policy. Choose
   **Always allow** only if you want future Computer Use tasks to operate that
   exact app without repeating the app prompt.
5. Review or revoke saved decisions under **Settings → Computer use → Always
   allowed apps**.

On Windows, Computer Use operates the active desktop in the foreground. Expect it
to move the pointer and type, and do not use the same session interactively while
an authorized task is running. Keep the device unlocked and Ableton visible.

## Four separate permission layers

| Layer | Controls |
|---|---|
| Computer Use app approval | Which visible Windows apps Codex may operate. |
| MCP approval mode | Whether Codex prompts before invoking Ableton MCP tools. |
| Task sandbox/approvals | File, shell, and other task actions. |
| Ableton capability | What the Live edition and active Control Surface permit. |

An **Always allow** decision for Ableton in Computer Use does not approve MCP
tools. Likewise, `default_tools_approval_mode = "approve"` for this MCP does not
grant Computer Use access to Ableton.

Persistent Windows app decisions are stored by Codex using the app identifier
Computer Use reports. Do not guess an executable name or copy an identifier from
another machine; approve the observed app through the UI.

## Shared MCP configuration

OpenAI documents that ChatGPT desktop, Codex CLI, and the IDE extension share MCP
configuration for the same Codex host. The installer writes the global
`~/.codex/config.toml` entry and verifies it with the CLI. Restart any client that
was already running so it reloads the new server and tool schemas.

In desktop Settings, the server should appear under **MCP servers**. A manual
desktop install is unnecessary. In a task, `/mcp` can show connected servers.

## When not to use Computer Use

Prefer the MCP for repeatable structured reads and actions. Use Computer Use for
modal dialogs, Control Surface settings, or visual checks that structured tools
cannot answer. Never authorize it to dismiss a save/recovery dialog or to operate
an unrelated app merely to complete Ableton setup.
