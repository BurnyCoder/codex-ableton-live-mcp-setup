<!-- Global context: reusable user prompt for a staged Windows setup that preserves human checkpoints and requires explicit allow-all acknowledgement. -->

# Agent prompt: install through the companion

```text
Set up the pinned Ableton Live MCP for Codex on this Windows machine using the
current codex-ableton-live-mcp-setup repository.

First run doctor and show me the selected checkout, User Library, port, existing
AbletonMCP inventory, and Codex server name. Then run install as a dry run and
review every target. Do not install the bare same-named PyPI package. Do not alter
the existing AbletonMCP folder, Control Surface, or port 9877.

Use the standard all-37-tools approval profile. I understand that it can execute
arbitrary Python in Live, auto-approves MCP tools, and can mutate or corrupt a
set; after the dry-run review, use --accept-risk for installation.

Run pre-Live validation. Stop on any failure other than exactly the two accepted
Windows path assertion failures recorded in config/versions.json, and require the
second deselected test run to pass.

Do not restart or close Live, dismiss a save/recovery/update dialog, or change a
Control Surface for me. Pause at the documented Live checkpoint so I can save my
work, restart Live, select Ableton Live MCP as a second Control Surface, and set
Input/Output to None.

After I confirm that checkpoint, run sequential read-only post-Live validation.
Do not mutate my set. Preserve complete local logs but report only sanitized
versions, public SHAs, counts, booleans, and check results.
```
