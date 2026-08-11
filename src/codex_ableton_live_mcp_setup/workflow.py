"""Global context: one readable wrapper composes the clearly named setup, validation, and rollback phases."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .codex_config import configure_codex, rollback_codex
from .configuration import Settings
from .doctor import doctor, port_status
from .errors import SetupError
from .manifest import VersionManifest
from .process import Runner
from .remote_script import clear_readonly, install_remote_script, inventory_existing_integration, rollback_remote_script
from .runtime import configure_runtime
from .state import load_state, new_state, save_state
from .upstream import acquire_checkout, checkout_status, create_environment, run_upstream_tests
from .validation import capture_ableton_evidence, scan_recent_live_log, stdio_smoke, validate_install


RISK_NOTICE = (
    "Approval mode 'approve' exposes and auto-approves all Ableton MCP tools. "
    "The server can execute arbitrary Python inside Ableton Live and can mutate or corrupt Live Sets."
)


def require_risk_acceptance(settings: Settings, accepted: bool) -> None:
    """Require explicit acknowledgement only for the plan's dangerous allow-all default."""
    if settings.approval_mode == "approve" and not accepted:
        raise SetupError(RISK_NOTICE + " Re-run with --accept-risk to continue.")


def install_or_update(
    settings: Settings,
    manifest: VersionManifest,
    runner: Runner,
    *,
    accepted_risk: bool,
    update: bool,
) -> dict[str, Any]:
    """Run ordered, idempotent phases and stop before the user's manual Live/Codex restart."""
    require_risk_acceptance(settings, accepted_risk)
    health = doctor(settings, manifest, runner)
    if not health["ok"]:
        raise SetupError("Preflight failed; run 'manage.ps1 doctor --json' and resolve missing Windows prerequisites or User Library")
    existing = load_state(settings.state_path, required=update)
    if existing and not existing.get("rolled_back"):
        state = existing
        stored_scope = state.get("settings", {})
        requested_scope = {
            "checkout": str(settings.checkout),
            "user_library": str(settings.user_library),
            "port": settings.port,
            "server_name": settings.server_name,
        }
        drift = {key: (stored_scope.get(key), value) for key, value in requested_scope.items() if stored_scope.get(key) != value}
        if drift:
            raise SetupError(f"Active installation scope differs from requested settings {drift}; rollback before changing scope")
    else:
        state = new_state()
        state["settings"] = {
            "checkout": str(settings.checkout),
            "user_library": str(settings.user_library),
            "port": settings.port,
            "server_name": settings.server_name,
        }
        state["legacy_ableton_mcp"] = inventory_existing_integration(settings)
        if not runner.dry_run:
            save_state(settings.state_path, state)
    acquisition = acquire_checkout(settings, manifest, runner, require_existing=update)
    environment = create_environment(settings, runner)
    runtime = configure_runtime(settings, runner)
    if runner.dry_run:
        tests = {"planned": True}
        stdio = {"planned": True}
    else:
        # copytree preserves Windows attributes; normalize only the exact packaged script before tests copy it.
        clear_readonly(settings.checkout / settings.remote_script_name)
        tests = run_upstream_tests(settings, manifest, runner)
        stdio = stdio_smoke(settings, manifest, runner.logger)
    remote = install_remote_script(settings, runner, state)
    legacy = assert_legacy_unchanged(settings, state)
    codex = configure_codex(settings, runner, state)
    validation = {"planned": True} if runner.dry_run else validate_install(settings, runner, "pre-live")
    state["last_operation"] = "update" if update else "install"
    state["last_completed_at"] = datetime.now(timezone.utc).isoformat()
    state["rolled_back"] = False
    if not runner.dry_run:
        save_state(settings.state_path, state)
    return {
        "ok": True,
        "operation": "update" if update else "install",
        "dry_run": runner.dry_run,
        "acquisition": acquisition,
        "environment": environment,
        "runtime": runtime,
        "upstream_tests": tests,
        "stdio": stdio,
        "remote_script": remote,
        "legacy_ableton_mcp": legacy,
        "codex": codex,
        "validation": validation,
        "manual_next_step": "Save Live Sets, restart Live without dismissing recovery dialogs, select Ableton Live MCP with Input/Output None, then restart Codex and run validate post-live.",
    }


def validate_workflow(settings: Settings, manifest: VersionManifest, runner: Runner, stage: str) -> dict[str, Any]:
    """Run offline STDIO for pre-Live validation and the strict upstream validator for both stages."""
    identity = checkout_status(settings, manifest, runner)
    required_identity = ("present", "origin_current", "commit_current", "tree_current")
    if not all(identity.get(key) for key in required_identity) or identity.get("dirty"):
        raise SetupError("Validation requires the clean, exact reviewed upstream commit and tree; run install/update first")
    result: dict[str, Any] = {
        "ok": True,
        "stage": stage,
        "checkout": {
            "commit": identity.get("head"),
            "tree": identity.get("tree"),
            "clean": not identity.get("dirty"),
        },
    }
    if stage == "pre-live":
        result["stdio"] = stdio_smoke(settings, manifest, runner.logger)
    else:
        listener = port_status(settings.host, settings.port)
        result["listener"] = listener
        if not listener["listening"]:
            raise SetupError(f"Required Ableton listener is not active on {settings.host}:{settings.port}")
        state = load_state(settings.state_path)
        legacy_was_present = bool(state and state.get("legacy_ableton_mcp", {}).get("present"))
        legacy_listener = port_status(settings.host, 9877)
        result["legacy_listener"] = {**legacy_listener, "required": legacy_was_present}
        if legacy_was_present and not legacy_listener["listening"]:
            raise SetupError("The preserved pre-existing AbletonMCP integration was detected, but its required listener on 127.0.0.1:9877 is not active")
        if state:
            result["legacy_ableton_mcp"] = assert_legacy_unchanged(settings, state)
        result["visual_capture"] = capture_ableton_evidence(settings, runner)
        result["live_log"] = scan_recent_live_log(evidence_dir=settings.state_dir / "evidence")
    result["validation"] = validate_install(settings, runner, stage)
    return result


def rollback_workflow(settings: Settings, runner: Runner) -> dict[str, Any]:
    """Use stored exact targets to move managed files aside and restore only prior Codex state."""
    state = load_state(settings.state_path, required=True)
    assert state is not None
    if state.get("rolled_back"):
        return {"ok": True, "operation": "rollback", "already_rolled_back": True, "dry_run": runner.dry_run}
    codex = rollback_codex(state, settings.state_path, runner)
    remote = rollback_remote_script(state, settings.state_path, runner)
    if not runner.dry_run:
        state["rolled_back"] = True
        state["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        save_state(settings.state_path, state)
    return {"ok": True, "operation": "rollback", "dry_run": runner.dry_run, "remote_script": remote, "codex": codex}


def assert_legacy_unchanged(settings: Settings, state: dict[str, Any]) -> dict[str, Any]:
    """Re-hash the pre-existing AbletonMCP integration and fail on any companion-caused drift."""
    expected = state.get("legacy_ableton_mcp")
    if not isinstance(expected, dict):
        raise SetupError("Installation state lacks the pre-install AbletonMCP inventory")
    current = inventory_existing_integration(settings)
    keys = ("present", "file_count", "sha256")
    drift = {key: (expected.get(key), current.get(key)) for key in keys if expected.get(key) != current.get(key)}
    if drift:
        raise SetupError(f"Preserved AbletonMCP integration changed unexpectedly: {drift}")
    return {"ok": True, **current}
