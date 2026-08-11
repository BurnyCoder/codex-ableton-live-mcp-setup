<!-- Global context: catalog of sanitized prompts used for repeatable setup and validation while raw prompt/output evidence remains local. -->

# Prompt catalog

These prompts define authorization boundaries for agent-assisted workflows:

- [`install-with-companion.md`](install-with-companion.md) asks an agent to use
  this repository's staged installer rather than improvising upstream setup.
- [`read-only-live-validation.md`](read-only-live-validation.md) limits fresh
  client acceptance to two read-only MCP calls.

When a prompt is used, preserve its complete text and the agent's complete output
in an ignored timestamped local log. Before publishing a report, redact personal
paths, machine names, process/Live object IDs, set signatures/content, config
backups, tokens, and unrelated app data.

Prompts grant only the actions they state. A request to validate does not
authorize restarting Live, dismissing dialogs, mutating a set, changing Computer
Use permissions, publishing a repository, or restoring a whole Codex config.
