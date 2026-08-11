"""Global context: install only Ableton_Live_MCP while preserving all prior Remote Script state."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path
from typing import Any

from .configuration import Settings
from .errors import SetupError
from .process import Runner
from .state import save_state, timestamp_slug


IGNORED_SUFFIXES = {".pyc", ".pyo"}


def is_reparse_point(path: Path) -> bool:
    """Detect symlinks, Windows junctions, and other reparse points without following them."""
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def assert_safe_managed_tree(root: Path) -> None:
    """Reject any reparse point in the exact managed tree before recursive or destructive work."""
    if is_reparse_point(root):
        raise SetupError(f"Refusing managed Remote Script reparse point: {root}")
    if not root.exists():
        return
    for current, directories, files in os.walk(root, followlinks=False):
        for name in [*directories, *files]:
            candidate = Path(current) / name
            if is_reparse_point(candidate):
                raise SetupError(f"Refusing reparse point inside managed Remote Script: {candidate}")


def hash_tree(root: Path) -> dict[str, str]:
    """Hash deterministic relative file paths while ignoring Python bytecode caches."""
    if not root.is_dir():
        return {}
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if is_reparse_point(path) or not path.is_file() or "__pycache__" in path.parts or path.suffix in IGNORED_SUFFIXES:
            continue
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def tree_fingerprint(root: Path) -> dict[str, Any]:
    """Summarize one safe tree so rollback snapshots can be integrity-checked later."""
    hashes = hash_tree(root)
    aggregate = hashlib.sha256(
        "".join(f"{name}:{digest}\n" for name, digest in sorted(hashes.items())).encode("utf-8")
    ).hexdigest()
    return {"file_count": len(hashes), "sha256": aggregate}


def assert_original_snapshot_current(remote_state: dict[str, Any]) -> Path:
    """Require the immutable preinstall snapshot to match its recorded fingerprint."""
    original = Path(remote_state.get("original_backup", ""))
    if not original.is_dir():
        raise SetupError("Original Remote Script rollback snapshot is missing; refusing update or rollback")
    assert_safe_managed_tree(original)
    expected = {
        "file_count": remote_state.get("original_file_count"),
        "sha256": remote_state.get("original_sha256"),
    }
    current = tree_fingerprint(original)
    if None in expected.values() or current != expected:
        raise SetupError("Original Remote Script rollback snapshot failed its recorded integrity check")
    return original


def inventory_existing_integration(settings: Settings) -> dict[str, Any]:
    """Record the legacy AbletonMCP directory without ever modifying it or port 9877."""
    legacy = settings.remote_scripts_dir / "AbletonMCP"
    fingerprint = tree_fingerprint(legacy)
    if not legacy.is_dir():
        fingerprint["sha256"] = None
    return {"path": str(legacy), "present": legacy.is_dir(), **fingerprint}


def clear_readonly(root: Path) -> list[str]:
    """Clear ReadOnly only under the exact Remote Script source or target selected by setup."""
    changed: list[str] = []
    if not root.exists():
        return changed
    assert_safe_managed_tree(root)
    for path in [root, *root.rglob("*")]:
        try:
            mode = path.stat().st_mode
            file_attributes = getattr(path.stat(), "st_file_attributes", 0)
            windows_readonly = bool(file_attributes & getattr(stat, "FILE_ATTRIBUTE_READONLY", 1))
            writable = bool(mode & stat.S_IWRITE)
            if windows_readonly or not writable:
                os.chmod(path, mode | stat.S_IWRITE)
                changed.append(str(path))
        except OSError as exc:
            raise SetupError(f"Cannot clear ReadOnly on exact managed path {path}: {exc}") from exc
    return changed


def install_remote_script(settings: Settings, runner: Runner, state: dict[str, Any]) -> dict[str, Any]:
    """Snapshot a pre-existing target once, then invoke upstream's idempotent --update installer."""
    source = settings.checkout / settings.remote_script_name
    target = settings.remote_script_target
    # Validate before target.is_dir/copytree so a junction can never redirect the snapshot phase.
    assert_safe_managed_tree(source)
    assert_safe_managed_tree(target)
    remote_state = state.get("remote_script")
    if remote_state is not None:
        stored_target = Path(remote_state.get("target", ""))
        if os.path.abspath(stored_target) != os.path.abspath(target):
            raise SetupError(f"Active rollback state manages {stored_target}, not requested target {target}")
        if remote_state.get("preexisting"):
            assert_original_snapshot_current(remote_state)
    if remote_state is None:
        backup: Path | None = None
        preexisting = target.is_dir()
        original_fingerprint = tree_fingerprint(target) if preexisting else {"file_count": None, "sha256": None}
        if preexisting:
            backup = settings.state_dir / "backups" / f"remote-script-original-{timestamp_slug()}"
            if not runner.dry_run:
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(target, backup)
                if tree_fingerprint(backup) != original_fingerprint:
                    raise SetupError("Original Remote Script snapshot does not match the preinstall target")
        remote_state = {
            "target": str(target),
            "preexisting": preexisting,
            "original_backup": str(backup) if backup else None,
            "original_file_count": original_fingerprint["file_count"],
            "original_sha256": original_fingerprint["sha256"],
        }
        state["remote_script"] = remote_state
        if not runner.dry_run:
            save_state(settings.state_path, state)
    if runner.dry_run:
        runner.logger.log(f"DRY-RUN preserve/update Remote Script at {target}")
        return {"planned": True, "target": str(target)}
    if not source.is_dir():
        raise SetupError(f"Pinned checkout does not contain {settings.remote_script_name}: {source}")
    assert_safe_managed_tree(source)
    assert_safe_managed_tree(target)
    clear_readonly(source)
    clear_readonly(target)
    runner.run(
        [settings.installer_executable, "--target-dir", settings.remote_scripts_dir, "--update"],
        cwd=settings.checkout,
        mutating=True,
    )
    source_hashes = hash_tree(source)
    target_hashes = hash_tree(target)
    if not source_hashes or source_hashes != target_hashes:
        raise SetupError("Installed Ableton_Live_MCP files do not exactly match the pinned source")
    return {"planned": False, "target": str(target), "files": len(target_hashes), "current": True}


def rollback_remote_script(state: dict[str, Any], state_path: Path, runner: Runner) -> dict[str, Any]:
    """Move the managed target aside and restore the original snapshot, never deleting either."""
    remote = state.get("remote_script")
    if not isinstance(remote, dict) or not remote.get("target"):
        raise SetupError("Installation state lacks an exact Remote Script target; refusing rollback")
    if remote.get("rollback_complete"):
        return {"planned": False, "already_complete": True, "target": remote["target"], "moved_to": remote.get("rollback_moved_to")}
    target = Path(remote["target"])
    stored_library = state.get("settings", {}).get("user_library")
    if not stored_library:
        raise SetupError("Installation state lacks the User Library scope; refusing rollback")
    expected_target = Path(stored_library) / "Remote Scripts" / "Ableton_Live_MCP"
    if os.path.abspath(target) != os.path.abspath(expected_target):
        raise SetupError(f"Stored Remote Script target {target} is outside its recorded User Library scope {expected_target}")
    moved_to = state_path.parent / "backups" / f"{target.name}.rollback-{timestamp_slug()}"
    original = assert_original_snapshot_current(remote) if remote.get("preexisting") else None
    assert_safe_managed_tree(target)
    if runner.dry_run:
        runner.logger.log(f"DRY-RUN move {target} to {moved_to}")
        if original:
            runner.logger.log(f"DRY-RUN restore {original} to {target}")
        return {"planned": True, "target": str(target), "moved_to": str(moved_to)}
    moved_to.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.move(str(target), str(moved_to))
    if remote.get("preexisting"):
        assert original is not None
        # Keep the original snapshot immutable so interruption before state save remains retry-safe.
        shutil.copytree(str(original), str(target))
    remote["rollback_moved_to"] = str(moved_to) if moved_to.exists() else None
    remote["rollback_complete"] = True
    save_state(state_path, state)
    return {"planned": False, "target": str(target), "moved_to": remote["rollback_moved_to"], "restored_original": bool(remote.get("preexisting"))}
