"""Global context: add one global Codex MCP table while preserving unrelated TOML and rollback state."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

from .configuration import Settings
from .errors import SetupError
from .process import Runner
from .state import save_state, timestamp_slug


TABLE_HEADER = re.compile(r"^\s*\[{1,2}([^\]]+)\]{1,2}\s*(?:#.*)?$")


def _target_prefixes(server_name: str) -> tuple[str, str]:
    """Return valid bare and quoted TOML table prefixes for one server name."""
    escaped = server_name.replace("\\", "\\\\").replace('"', '\\"')
    return f"mcp_servers.{server_name}", f'mcp_servers."{escaped}"'


def is_managed_header(header: str, server_name: str) -> bool:
    """Match the server table and any of its per-tool subtables, but no sibling server."""
    normalized = header.strip()
    return any(normalized == prefix or normalized.startswith(prefix + ".") for prefix in _target_prefixes(server_name))


def extract_server_blocks(text: str, server_name: str) -> list[str]:
    """Extract all matching table blocks so rollback can restore only this server subtree."""
    lines = text.splitlines(keepends=True)
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        match = TABLE_HEADER.match(lines[index].rstrip("\r\n"))
        if not match or not is_managed_header(match.group(1), server_name):
            index += 1
            continue
        end = index + 1
        while end < len(lines) and not TABLE_HEADER.match(lines[end].rstrip("\r\n")):
            end += 1
        blocks.append("".join(lines[index:end]))
        index = end
    return blocks


def remove_server_blocks(text: str, server_name: str) -> str:
    """Remove only matching server tables while leaving unrelated bytes and comments untouched."""
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
    index = 0
    while index < len(lines):
        match = TABLE_HEADER.match(lines[index].rstrip("\r\n"))
        if match and is_managed_header(match.group(1), server_name):
            index += 1
            while index < len(lines) and not TABLE_HEADER.match(lines[index].rstrip("\r\n")):
                index += 1
            continue
        kept.append(lines[index])
        index += 1
    return "".join(kept)


def format_server_block(settings: Settings, uv_executable: Path) -> str:
    """Render the reviewed allow-all STDIO table without tool filters or approval overrides."""
    args = [
        "run", "--no-project", "--env-file", settings.runtime_env_path.as_posix(), "--",
        settings.server_executable.as_posix(),
    ]
    encoded_args = ", ".join(json.dumps(item, ensure_ascii=False) for item in args)
    escaped_name = settings.server_name.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'[mcp_servers."{escaped_name}"]\n'
        f"command = {json.dumps(uv_executable.as_posix(), ensure_ascii=False)}\n"
        f"args = [{encoded_args}]\n"
        f"cwd = {json.dumps(settings.checkout.as_posix(), ensure_ascii=False)}\n"
        "enabled = true\n"
        "required = false\n"
        f"startup_timeout_sec = {settings.startup_timeout}\n"
        f"tool_timeout_sec = {settings.tool_timeout}\n"
        f"default_tools_approval_mode = {json.dumps(settings.approval_mode)}\n"
    )


def upsert_server_block(text: str, server_name: str, block: str) -> str:
    """Replace the managed subtree and append one canonical table after unrelated configuration."""
    remaining = remove_server_blocks(text, server_name).rstrip()
    return (remaining + "\n\n" if remaining else "") + block.rstrip() + "\n"


def configure_codex(settings: Settings, runner: Runner, state: dict[str, Any]) -> dict[str, Any]:
    """Back up config, establish CLI registration when new, then apply verified fine-grained options."""
    uv_path_text = shutil.which("uv")
    codex_path = shutil.which("codex")
    if not uv_path_text or not codex_path:
        raise SetupError("Both uv and codex must be available on PATH")
    uv_path = Path(uv_path_text).resolve()
    config_path = settings.codex_config_path
    original_bytes = config_path.read_bytes() if config_path.is_file() else b""
    original_text = original_bytes.decode("utf-8")
    prior_blocks = extract_server_blocks(original_text, settings.server_name)
    codex_state = state.get("codex")
    if codex_state is None:
        backup_path = config_path.with_name(f"config.toml.before-ableton-setup-{timestamp_slug()}")
        backup_sha = hashlib.sha256(original_bytes).hexdigest()
        codex_state = {
            "config_path": str(config_path),
            "server_name": settings.server_name,
            "prior_server_blocks": prior_blocks,
            "backup_path": str(backup_path),
            "backup_sha256": backup_sha,
            "config_preexisted": config_path.is_file(),
        }
        state["codex"] = codex_state
        if not runner.dry_run:
            settings.state_dir.mkdir(parents=True, exist_ok=True)
            if config_path.is_file():
                shutil.copy2(config_path, backup_path)
            save_state(settings.state_path, state)
    block = format_server_block(settings, uv_path)
    if runner.dry_run:
        runner.logger.log(f"DRY-RUN upsert [{settings.server_name}] in {config_path}")
        return {"planned": True, "config": str(config_path), "approval_mode": settings.approval_mode}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not prior_blocks:
        runner.run(
            [codex_path, "mcp", "add", settings.server_name, "--", uv_path, "run", "--no-project", "--env-file", settings.runtime_env_path, "--", settings.server_executable],
            mutating=True,
        )
        current_text = config_path.read_text(encoding="utf-8")
    else:
        current_text = original_text
    updated = upsert_server_block(current_text, settings.server_name, block)
    config_path.write_text(updated, encoding="utf-8", newline="\n")
    resolved = semantic_server_config(config_path, settings.server_name)
    expected = {
        "enabled": True,
        "required": False,
        "startup_timeout_sec": settings.startup_timeout,
        "tool_timeout_sec": settings.tool_timeout,
        "default_tools_approval_mode": settings.approval_mode,
    }
    for key, value in expected.items():
        if resolved.get(key) != value:
            raise SetupError(f"Codex semantic config verification failed for {key}: {resolved.get(key)!r}")
    if "enabled_tools" in resolved or "disabled_tools" in resolved:
        raise SetupError("Allow-all configuration must omit both enabled_tools and disabled_tools")
    runner.run([codex_path, "mcp", "get", settings.server_name, "--json"])
    runner.run([codex_path, "mcp", "list"])
    return {"planned": False, "config": str(config_path), "approval_mode": settings.approval_mode, "all_tools_exposed": True}


def semantic_server_config(config_path: Path, server_name: str) -> dict[str, Any]:
    """Parse the resulting TOML using Python's strict standard parser and return one server table."""
    try:
        with config_path.open("rb") as handle:
            payload = tomllib.load(handle)
        value = payload["mcp_servers"][server_name]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise SetupError(f"Codex config cannot resolve mcp_servers.{server_name}: {exc}") from exc
    if not isinstance(value, dict):
        raise SetupError(f"Codex server config is not a table: {server_name}")
    return value


def rollback_codex(state: dict[str, Any], state_path: Path, runner: Runner) -> dict[str, Any]:
    """Restore only the prior server subtree in the current config, preserving later unrelated edits."""
    codex = state.get("codex")
    if not isinstance(codex, dict):
        raise SetupError("Installation state lacks Codex section evidence; refusing rollback")
    if codex.get("rollback_complete"):
        return {"planned": False, "already_complete": True, "config": codex["config_path"], "restored_prior": bool(codex.get("prior_server_blocks"))}
    config_path = Path(codex["config_path"])
    server_name = str(codex["server_name"])
    current = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    restored = remove_server_blocks(current, server_name).rstrip()
    prior_blocks = [str(block).rstrip() for block in codex.get("prior_server_blocks", [])]
    if prior_blocks:
        restored = (restored + "\n\n" if restored else "") + "\n\n".join(prior_blocks)
    restored = restored.rstrip() + ("\n" if restored.strip() else "")
    if runner.dry_run:
        runner.logger.log(f"DRY-RUN restore only [{server_name}] in {config_path}")
        return {"planned": True, "config": str(config_path), "restored_prior": bool(prior_blocks)}
    backup_path = config_path.with_name(f"config.toml.before-ableton-rollback-{timestamp_slug()}")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.is_file():
        shutil.copy2(config_path, backup_path)
    config_path.write_text(restored, encoding="utf-8", newline="\n")
    codex["rollback_backup_path"] = str(backup_path) if backup_path.exists() else None
    codex["rollback_complete"] = True
    save_state(state_path, state)
    return {"planned": False, "config": str(config_path), "restored_prior": bool(prior_blocks)}
