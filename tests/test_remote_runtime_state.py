"""Global context: prove hashing, legacy preservation, safe move-based rollback, and atomic state."""

import os
import stat
from pathlib import Path

import pytest

from codex_ableton_live_mcp_setup.configuration import Settings
from codex_ableton_live_mcp_setup.errors import SetupError
from codex_ableton_live_mcp_setup.logging_utils import SetupLogger
from codex_ableton_live_mcp_setup.process import Runner
from codex_ableton_live_mcp_setup.remote_script import assert_safe_managed_tree, clear_readonly, hash_tree, install_remote_script, inventory_existing_integration, rollback_remote_script, tree_fingerprint
from codex_ableton_live_mcp_setup.runtime import configure_runtime
from codex_ableton_live_mcp_setup.state import load_state, new_state, save_state


def settings_for(tmp_path: Path) -> Settings:
    return Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library", state_dir=tmp_path / "state", codex_home=tmp_path / "codex")


def test_hash_tree_ignores_bytecode_and_is_content_sensitive(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("one", encoding="utf-8")
    (tmp_path / "a.pyc").write_bytes(b"ignored")
    first = hash_tree(tmp_path)
    assert list(first) == ["a.py"]
    (tmp_path / "a.py").write_text("two", encoding="utf-8")
    assert hash_tree(tmp_path)["a.py"] != first["a.py"]


def test_inventory_reads_but_does_not_modify_legacy_integration(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    legacy_file = settings.remote_scripts_dir / "AbletonMCP" / "bridge.py"
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_text("legacy", encoding="utf-8")
    before = legacy_file.read_bytes()
    result = inventory_existing_integration(settings)
    assert result["present"] is True and result["file_count"] == 1
    assert legacy_file.read_bytes() == before


def test_readonly_remediation_is_exact_target_only(tmp_path: Path) -> None:
    target = tmp_path / "target"
    outside = tmp_path / "outside.txt"
    target.mkdir()
    inside = target / "inside.txt"
    inside.write_text("x", encoding="utf-8")
    outside.write_text("y", encoding="utf-8")
    os.chmod(inside, stat.S_IREAD)
    os.chmod(outside, stat.S_IREAD)
    clear_readonly(target)
    assert inside.stat().st_mode & stat.S_IWRITE
    assert not outside.stat().st_mode & stat.S_IWRITE
    os.chmod(outside, stat.S_IWRITE)


def test_runtime_env_written_and_locally_excluded(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    exclude = settings.checkout / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True)
    runner = Runner(SetupLogger(tmp_path / "log.txt"))
    configure_runtime(settings, runner)
    assert settings.runtime_env_path.is_file()
    assert exclude.read_text(encoding="utf-8").splitlines().count(".env") == 1
    configure_runtime(settings, runner)
    assert exclude.read_text(encoding="utf-8").splitlines().count(".env") == 1


def test_remote_rollback_moves_managed_target_and_restores_original(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    target = settings.remote_script_target
    target.mkdir(parents=True)
    (target / "managed.py").write_text("managed", encoding="utf-8")
    original = settings.state_dir / "backups" / "original"
    original.mkdir(parents=True)
    (original / "original.py").write_text("original", encoding="utf-8")
    state = new_state()
    state["settings"] = {"user_library": str(settings.user_library)}
    original_fingerprint = tree_fingerprint(original)
    state["remote_script"] = {
        "target": str(target),
        "preexisting": True,
        "original_backup": str(original),
        "original_file_count": original_fingerprint["file_count"],
        "original_sha256": original_fingerprint["sha256"],
    }
    save_state(settings.state_path, state)
    result = rollback_remote_script(state, settings.state_path, Runner(SetupLogger(tmp_path / "log.txt")))
    assert (target / "original.py").is_file()
    assert Path(result["moved_to"]).joinpath("managed.py").is_file()
    assert load_state(settings.state_path, required=True)["remote_script"]["rollback_moved_to"] == result["moved_to"]
    assert rollback_remote_script(state, settings.state_path, Runner(SetupLogger(tmp_path / "log2.txt")))["already_complete"] is True


def test_remote_rollback_checks_original_before_moving_target(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    target = settings.remote_script_target
    target.mkdir(parents=True)
    marker = target / "managed.py"
    marker.write_text("managed", encoding="utf-8")
    state = new_state()
    state["settings"] = {"user_library": str(settings.user_library)}
    state["remote_script"] = {"target": str(target), "preexisting": True, "original_backup": str(tmp_path / "missing")}
    save_state(settings.state_path, state)
    with pytest.raises(SetupError, match="snapshot is missing"):
        rollback_remote_script(state, settings.state_path, Runner(SetupLogger(tmp_path / "log.txt")))
    assert marker.is_file()


def test_update_rejects_corrupted_original_rollback_snapshot(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    (settings.checkout / settings.remote_script_name).mkdir(parents=True)
    original = settings.state_dir / "backups" / "original"
    original.mkdir(parents=True)
    (original / "original.py").write_text("original", encoding="utf-8")
    fingerprint = tree_fingerprint(original)
    state = new_state()
    state["remote_script"] = {
        "target": str(settings.remote_script_target),
        "preexisting": True,
        "original_backup": str(original),
        "original_file_count": fingerprint["file_count"],
        "original_sha256": fingerprint["sha256"],
    }
    (original / "original.py").write_text("corrupted", encoding="utf-8")
    with pytest.raises(SetupError, match="integrity check"):
        install_remote_script(settings, Runner(SetupLogger(tmp_path / "log.txt"), dry_run=True), state)


def test_managed_target_symlink_is_rejected(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "Ableton_Live_MCP"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("Windows symlink privilege is unavailable")
    with pytest.raises(SetupError, match="reparse point"):
        assert_safe_managed_tree(link)


def test_install_rejects_target_symlink_before_snapshot(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    (settings.checkout / settings.remote_script_name).mkdir(parents=True)
    actual = tmp_path / "outside"
    actual.mkdir()
    settings.remote_scripts_dir.mkdir(parents=True)
    try:
        settings.remote_script_target.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("Windows symlink privilege is unavailable")
    state = new_state()
    with pytest.raises(SetupError, match="reparse point"):
        install_remote_script(settings, Runner(SetupLogger(tmp_path / "log.txt"), dry_run=True), state)
    assert "remote_script" not in state


def test_update_refuses_missing_original_rollback_snapshot(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    (settings.checkout / settings.remote_script_name).mkdir(parents=True)
    state = new_state()
    state["remote_script"] = {"target": str(settings.remote_script_target), "preexisting": True, "original_backup": str(tmp_path / "missing")}
    with pytest.raises(SetupError, match="snapshot is missing"):
        install_remote_script(settings, Runner(SetupLogger(tmp_path / "log.txt"), dry_run=True), state)


def test_install_checks_target_safety_before_creating_snapshot(monkeypatch, tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    source = settings.checkout / settings.remote_script_name
    source.mkdir(parents=True)
    target = settings.remote_script_target
    target.mkdir(parents=True)
    import codex_ableton_live_mcp_setup.remote_script as remote_module
    original_check = remote_module.is_reparse_point
    monkeypatch.setattr(remote_module, "is_reparse_point", lambda path: path == target or original_check(path))
    state = new_state()
    with pytest.raises(SetupError, match="reparse point"):
        install_remote_script(settings, Runner(SetupLogger(tmp_path / "log.txt"), dry_run=True), state)
    assert "remote_script" not in state
