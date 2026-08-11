"""Global context: public package metadata for the reproducible Ableton MCP setup CLI."""

from __future__ import annotations

__version__ = "1.0.0"


def main() -> int:
    """Delegate legacy imports to the canonical CLI entry point."""
    from .cli import main as cli_main

    return cli_main()
