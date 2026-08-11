<!-- Global context: attribution and licensing boundaries for source fetched or referenced by this companion project. -->

# Third-party notices

## Ableton Live MCP

This companion project fetches—but does not vendor—source from:

- Project: [`bschoepke/ableton-live-mcp`](https://github.com/bschoepke/ableton-live-mcp)
- Reviewed base: `70f7df9192b78d9bd9405f369c9e046c88f1610e`
- License: MIT, as published in the upstream repository
- Copyright: retained by the upstream contributors

The Windows STDIO fix is attributed to AxidentDK through upstream
[pull request #15](https://github.com/bschoepke/ableton-live-mcp/pull/15):

- Commit: `a93d223440b275feda2fb08cdf814238c1270e00`
- Purpose: UTF-8 Windows pipes, LF-only JSON framing, and JSON-RPC parse-error
  recovery

The setup verifies the public base, PR commit, parent relationship, and expected
patched tree before installation. The upstream MIT license applies to that
upstream source and change. This file is attribution, not a relicensing of either.

## Runtime dependencies

Companion dependencies are resolved by `uv` from this repository's
`pyproject.toml` and committed `uv.lock`; they retain their own licenses. The
separate upstream checkout has no upstream lockfile at the reviewed commit, so
its editable `.[dev]` installation resolves versions allowed by upstream at
installation time. That extra currently includes pytest, Pillow, and
platform-specific visual-capture packages. Inspect each installed package's
metadata for the resulting upstream-environment inventory and license terms.

## Product names

Ableton and Live are trademarks of Ableton AG. Codex and ChatGPT are products of
OpenAI. GitHub is a trademark of GitHub, Inc. Python is a trademark of the Python
Software Foundation. `uv` is maintained by Astral. Product names identify
compatibility only; no endorsement or affiliation is implied.
