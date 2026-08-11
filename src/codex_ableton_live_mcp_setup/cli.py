"""Global context: parse the public PowerShell/Python command surface and dispatch one workflow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .configuration import APPROVAL_MODES, Settings, load_settings
from .doctor import doctor
from .errors import SetupError
from .logging_utils import new_logger, print_result
from .manifest import load_manifest
from .process import Runner
from .workflow import install_or_update, rollback_workflow, validate_workflow


def add_common_settings(parser: argparse.ArgumentParser) -> None:
    """Add identical post-subcommand overrides so documentation and shell completion stay simple."""
    parser.add_argument("--env-file", type=Path, help="Companion .env path (default: repository-root .env).")
    parser.add_argument("--checkout", type=Path, help="Pinned upstream checkout path.")
    parser.add_argument("--user-library", type=Path, help="Ableton User Library path.")
    parser.add_argument("--python", dest="python_version", help="uv Python version (default: 3.14).")
    parser.add_argument("--port", type=int, help="Loopback Ableton bridge port (default: 8765).")
    parser.add_argument("--server-name", help="Global Codex MCP server name.")
    parser.add_argument("--startup-timeout", type=int, help="Codex MCP startup timeout seconds.")
    parser.add_argument("--tool-timeout", type=int, help="Codex MCP tool timeout seconds.")
    parser.add_argument("--approval-mode", choices=APPROVAL_MODES, help="Codex MCP approval mode.")


def build_parser() -> argparse.ArgumentParser:
    """Build the decision-complete public CLI grammar."""
    parser = argparse.ArgumentParser(prog="codex-ableton-live-mcp-setup")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor_parser = commands.add_parser("doctor", help="Inspect prerequisites without changing anything.")
    add_common_settings(doctor_parser)
    doctor_parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    for name in ("install", "update"):
        command = commands.add_parser(name, help=f"{name.title()} the pinned integration.")
        add_common_settings(command)
        command.add_argument("--accept-risk", action="store_true", help="Acknowledge arbitrary Python and Live Set mutation risk.")
        command.add_argument("--dry-run", action="store_true", help="Log mutations without performing them.")
        command.add_argument("--json", action="store_true", help="Emit structured JSON.")
    validate_parser = commands.add_parser("validate", help="Validate before or after activating Live.")
    validate_parser.add_argument("stage", choices=("pre-live", "post-live"))
    add_common_settings(validate_parser)
    validate_parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    rollback_parser = commands.add_parser("rollback", help="Move managed files aside and restore prior state.")
    add_common_settings(rollback_parser)
    rollback_parser.add_argument("--dry-run", action="store_true", help="Log mutations without performing them.")
    rollback_parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    """Convert only supported CLI overrides into the shared precedence resolver."""
    keys = ("checkout", "user_library", "python_version", "port", "server_name", "startup_timeout", "tool_timeout", "approval_mode")
    overrides = {key: getattr(args, key, None) for key in keys}
    return load_settings(overrides, getattr(args, "env_file", None))


def dispatch(args: argparse.Namespace) -> tuple[dict[str, Any], Settings, Runner]:
    """Resolve dependencies and dispatch exactly one top-level operation."""
    settings = settings_from_args(args)
    logger = new_logger()
    runner = Runner(logger, dry_run=bool(getattr(args, "dry_run", False)))
    manifest = load_manifest()
    if args.command == "doctor":
        result = doctor(settings, manifest, runner)
    elif args.command in {"install", "update"}:
        result = install_or_update(settings, manifest, runner, accepted_risk=args.accept_risk, update=args.command == "update")
    elif args.command == "validate":
        result = validate_workflow(settings, manifest, runner, args.stage)
    elif args.command == "rollback":
        result = rollback_workflow(settings, runner)
    else:
        raise SetupError(f"Unsupported command: {args.command}")
    return result, settings, runner


def main(argv: list[str] | None = None) -> int:
    """Run the CLI, returning stable exit codes and concise expected errors."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result, settings, runner = dispatch(args)
        print_result(result, bool(getattr(args, "json", False)), Path.home())
        runner.logger.log(f"completed command={args.command} ok={result.get('ok', False)}")
        return 0 if result.get("ok") else 1
    except SetupError as exc:
        if bool(getattr(args, "json", False)):
            print_result({"ok": False, "error": str(exc)}, True, Path.home())
            return 2
        print(f"error: {exc}", file=sys.stderr)
        return 2
