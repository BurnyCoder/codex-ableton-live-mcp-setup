"""Global context: prove active installation scope and legacy preservation fail before mutation."""

from pathlib import Path

import pytest

from codex_ableton_live_mcp_setup.configuration import Settings
from codex_ableton_live_mcp_setup.errors import SetupError
from codex_ableton_live_mcp_setup.logging_utils import SetupLogger
from codex_ableton_live_mcp_setup.manifest import load_manifest
from codex_ableton_live_mcp_setup.process import Runner
from codex_ableton_live_mcp_setup.remote_script import tree_fingerprint
from codex_ableton_live_mcp_setup.state import load_state, new_state, save_state
from codex_ableton_live_mcp_setup.workflow import assert_legacy_unchanged, install_or_update, rollback_workflow, validate_workflow


def test_active_scope_drift_fails_before_acquisition(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "new-library", approval_mode="prompt", state_dir=tmp_path / "state")
    state = new_state()
    state["settings"] = {"checkout": str(settings.checkout), "user_library": str(tmp_path / "old-library"), "port": 8765, "server_name": settings.server_name}
    state["legacy_ableton_mcp"] = {"present": False, "file_count": 0, "sha256": None}
    save_state(settings.state_path, state)
    monkeypatch.setattr("codex_ableton_live_mcp_setup.workflow.doctor", lambda *args: {"ok": True})
    called = {"acquire": False}
    monkeypatch.setattr("codex_ableton_live_mcp_setup.workflow.acquire_checkout", lambda *args, **kwargs: called.update(acquire=True))
    with pytest.raises(SetupError, match="rollback before changing scope"):
        install_or_update(settings, load_manifest(), Runner(SetupLogger(tmp_path / "log.txt")), accepted_risk=False, update=False)
    assert called["acquire"] is False


def test_legacy_hash_drift_blocks_claim(tmp_path: Path) -> None:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library")
    legacy = settings.remote_scripts_dir / "AbletonMCP"
    legacy.mkdir(parents=True)
    (legacy / "bridge.py").write_text("changed", encoding="utf-8")
    state = {"legacy_ableton_mcp": {"present": True, "file_count": 1, "sha256": "not-current"}}
    with pytest.raises(SetupError, match="changed unexpectedly"):
        assert_legacy_unchanged(settings, state)


def test_validation_rejects_nonreviewed_checkout_before_protocol_calls(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library")
    monkeypatch.setattr(
        "codex_ableton_live_mcp_setup.workflow.checkout_status",
        lambda *args: {"present": True, "origin_current": True, "commit_current": False, "tree_current": True, "dirty": False},
    )
    called = {"stdio": False}
    monkeypatch.setattr(
        "codex_ableton_live_mcp_setup.workflow.stdio_smoke",
        lambda *args: called.update(stdio=True),
    )
    with pytest.raises(SetupError, match="exact reviewed upstream"):
        validate_workflow(settings, load_manifest(), Runner(SetupLogger(tmp_path / "log.txt")), "pre-live")
    assert called["stdio"] is False


def test_rollback_retries_after_remote_phase_fault(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library", state_dir=tmp_path / "state", codex_home=tmp_path / "codex")
    settings.codex_home.mkdir(parents=True)
    settings.codex_config_path.write_text('[mcp_servers."ableton-live-mcp"]\ncommand="managed"\n', encoding="utf-8")
    target = settings.remote_script_target
    target.mkdir(parents=True)
    (target / "managed.py").write_text("managed", encoding="utf-8")
    original = settings.state_dir / "backups" / "original"
    original.mkdir(parents=True)
    (original / "original.py").write_text("original", encoding="utf-8")
    original_fingerprint = tree_fingerprint(original)
    state = new_state()
    state["settings"] = {"user_library": str(settings.user_library)}
    state["codex"] = {"config_path": str(settings.codex_config_path), "server_name": settings.server_name, "prior_server_blocks": []}
    state["remote_script"] = {
        "target": str(target),
        "preexisting": True,
        "original_backup": str(original),
        "original_file_count": original_fingerprint["file_count"],
        "original_sha256": original_fingerprint["sha256"],
    }
    save_state(settings.state_path, state)
    import codex_ableton_live_mcp_setup.workflow as workflow_module
    actual_remote = workflow_module.rollback_remote_script
    monkeypatch.setattr(workflow_module, "rollback_remote_script", lambda *args, **kwargs: (_ for _ in ()).throw(SetupError("injected")))
    with pytest.raises(SetupError, match="injected"):
        rollback_workflow(settings, Runner(SetupLogger(tmp_path / "first.log")))
    assert load_state(settings.state_path, required=True)["codex"]["rollback_complete"] is True
    monkeypatch.setattr(workflow_module, "rollback_remote_script", actual_remote)
    result = rollback_workflow(settings, Runner(SetupLogger(tmp_path / "second.log")))
    assert result["codex"]["already_complete"] is True
    assert (target / "original.py").is_file()
