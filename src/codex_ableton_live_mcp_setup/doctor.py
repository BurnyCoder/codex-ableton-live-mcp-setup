"""Global context: inspect prerequisites, ports, legacy integration, and Computer Use without mutation."""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import tomllib
from typing import Any

from .configuration import Settings
from .manifest import VersionManifest
from .process import Runner
from .remote_script import inventory_existing_integration
from .state import load_state
from .upstream import checkout_status


def port_status(host: str, port: int, timeout: float = 0.2) -> dict[str, Any]:
    """Probe a loopback TCP listener without sending application data."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        listening = client.connect_ex((host, port)) == 0
    return {"host": host, "port": port, "listening": listening}


def computer_use_status(settings: Settings, runner: Runner) -> dict[str, Any]:
    """Read plugin-level CLI/config state; desktop-only server and skill toggles remain manual."""
    codex = shutil.which("codex")
    if not codex:
        return {"installed": False, "enabled": False, "error": "codex not found"}
    result = runner.run([codex, "plugin", "list", "--json"], check=False)
    if result.returncode != 0:
        return {"installed": False, "enabled": False, "error": result.stderr.strip() or result.stdout.strip()}
    try:
        payload = json.loads(result.stdout)
        plugin = next(
            (item for item in payload.get("installed", []) if item.get("pluginId") == "computer-use@openai-bundled"),
            None,
        )
    except (json.JSONDecodeError, AttributeError) as exc:
        return {"installed": False, "enabled": False, "error": f"invalid plugin JSON: {exc}"}
    configured = None
    if settings.codex_config_path.is_file():
        try:
            with settings.codex_config_path.open("rb") as handle:
                configured = tomllib.load(handle).get("plugins", {}).get("computer-use@openai-bundled", {}).get("enabled")
        except (OSError, tomllib.TOMLDecodeError):
            configured = None
    return {
        "installed": bool(plugin and plugin.get("installed")),
        "enabled": bool(plugin and plugin.get("enabled") and configured is not False),
        "version": plugin.get("version") if plugin else None,
        "desktop_server_skill_toggles": "verify_manually",
    }


def checkout_destination_status(settings: Settings, checkout: dict[str, Any]) -> dict[str, Any]:
    """Check that acquisition can safely reuse the path or create it under a writable parent."""
    candidate = settings.checkout
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    writable = candidate.exists() and os.access(candidate, os.W_OK)
    reusable = not settings.checkout.exists() or bool(
        checkout.get("present") and checkout.get("origin_current") and not checkout.get("dirty") and not checkout.get("error")
    )
    return {
        "ok": bool(writable and reusable),
        "path_exists": settings.checkout.exists(),
        "nearest_existing_parent": str(candidate),
        "nearest_parent_writable": bool(writable),
        "existing_path_reusable": bool(reusable),
    }


def doctor(settings: Settings, manifest: VersionManifest, runner: Runner) -> dict[str, Any]:
    """Gather a structured read-only health report and core installation readiness."""
    commands = {name: shutil.which(name) for name in ("git", "uv", "codex")}
    python_probe = None
    if commands["uv"]:
        probe = runner.run([commands["uv"], "python", "find", settings.python_version], check=False)
        python_probe = probe.stdout.strip() if probe.returncode == 0 else None
    windows = platform.system() == "Windows"
    checkout = checkout_status(settings, manifest, runner)
    destination = checkout_destination_status(settings, checkout)
    managed_state = load_state(settings.state_path)
    active_matching_state = bool(
        managed_state
        and not managed_state.get("rolled_back")
        and managed_state.get("settings", {}).get("checkout") == str(settings.checkout)
    )
    requested_port = port_status(settings.host, settings.port)
    port_conflict = bool(requested_port["listening"] and not (active_matching_state and checkout.get("commit_current") and checkout.get("tree_current")))
    result = {
        "ok": windows and all(commands.values()) and python_probe is not None and settings.user_library.is_dir() and destination["ok"] and not port_conflict,
        "platform": {"system": platform.system(), "release": platform.release(), "windows_supported": windows},
        "commands": commands,
        "python": {"requested": settings.python_version, "resolved": python_probe},
        "user_library": {"path": str(settings.user_library), "exists": settings.user_library.is_dir()},
        "checkout": checkout,
        "checkout_destination": destination,
        "ports": {
            str(settings.port): requested_port,
            "9877": port_status(settings.host, 9877),
        },
        "port_conflict": port_conflict,
        "port_listener_justified_by_managed_state": bool(requested_port["listening"] and not port_conflict),
        "legacy_ableton_mcp": inventory_existing_integration(settings),
        "computer_use": computer_use_status(settings, runner),
    }
    return result
