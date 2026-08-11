"""Global context: allow ``python -m codex_ableton_live_mcp_setup`` to run the CLI."""

from .cli import main

raise SystemExit(main())
