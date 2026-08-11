<!-- Global context: fresh-client acceptance prompt constrained to two read-only Ableton MCP tools. -->

# Agent prompt: fresh-client read-only validation

```text
Use only the ableton-live-mcp server. Call live_ping once, then call
live_set_summary once. Do not call any other tool, do not use Computer Use, do not
change transport or selection, and do not mutate or save the Live Set.

Report whether both calls succeeded, the Live version, runtime-current/safety
signals if returned, and a compact count-only set summary. Omit object IDs, set
signatures, absolute paths, and other machine-specific values.
```
