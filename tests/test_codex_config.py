"""Global context: prove comment-preserving allow-all TOML upsert and section-scoped rollback."""

import tomllib
import hashlib
from pathlib import Path

from codex_ableton_live_mcp_setup.codex_config import (
    configure_codex,
    extract_server_blocks,
    format_server_block,
    remove_server_blocks,
    rollback_codex,
    semantic_server_config,
    upsert_server_block,
)
from codex_ableton_live_mcp_setup.configuration import Settings
from codex_ableton_live_mcp_setup.logging_utils import SetupLogger
from codex_ableton_live_mcp_setup.process import Runner
from codex_ableton_live_mcp_setup.state import new_state, save_state


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        checkout=tmp_path / "checkout with spaces",
        user_library=tmp_path / "library",
        codex_home=tmp_path / "codex",
        state_dir=tmp_path / "state",
    )


def test_upsert_preserves_unrelated_comments_and_removes_tool_filters(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    original = '# keep this\nmodel = "gpt-test"\n\n[mcp_servers.other]\ncommand = "other"\n\n[mcp_servers.ableton-live-mcp]\ndisabled_tools = ["x"]\n'
    block = format_server_block(settings, Path("C:/Tools/uv.exe"))
    updated = upsert_server_block(original, settings.server_name, block)
    parsed = tomllib.loads(updated)
    ableton = parsed["mcp_servers"][settings.server_name]
    assert "# keep this" in updated
    assert parsed["mcp_servers"]["other"]["command"] == "other"
    assert "enabled_tools" not in ableton and "disabled_tools" not in ableton
    assert ableton["default_tools_approval_mode"] == "approve"
    assert ableton["required"] is False


def test_extract_and_remove_include_managed_tool_subtables() -> None:
    text = '[mcp_servers."ableton-live-mcp"]\ncommand="x"\n[mcp_servers."ableton-live-mcp".tools.live_ping]\napproval_mode="auto"\n[mcp_servers.other]\ncommand="y"\n'
    blocks = extract_server_blocks(text, "ableton-live-mcp")
    assert len(blocks) == 2
    remaining = remove_server_blocks(text, "ableton-live-mcp")
    assert "live_ping" not in remaining
    assert "mcp_servers.other" in remaining


def test_rollback_restores_only_prior_server_section(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.codex_home.mkdir(parents=True)
    prior = '[mcp_servers."ableton-live-mcp"]\ncommand = "prior"\n'
    current = '# later user edit\nmodel="new"\n\n[mcp_servers."ableton-live-mcp"]\ncommand="managed"\n'
    settings.codex_config_path.write_text(current, encoding="utf-8")
    state = new_state()
    state["codex"] = {"config_path": str(settings.codex_config_path), "server_name": settings.server_name, "prior_server_blocks": [prior]}
    save_state(settings.state_path, state)
    runner = Runner(SetupLogger(tmp_path / "log.txt"))
    result = rollback_codex(state, settings.state_path, runner)
    restored = settings.codex_config_path.read_text(encoding="utf-8")
    assert result["restored_prior"] is True
    assert '# later user edit' in restored and 'model="new"' in restored
    assert 'command = "prior"' in restored
    assert 'command="managed"' not in restored


def test_semantic_config_rejects_filters_by_visibility(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.codex_home.mkdir(parents=True)
    settings.codex_config_path.write_text(format_server_block(settings, Path("C:/uv.exe")), encoding="utf-8")
    table = semantic_server_config(settings.codex_config_path, settings.server_name)
    assert table["enabled"] is True
    assert "enabled_tools" not in table and "disabled_tools" not in table


def test_array_of_tables_is_unrelated_boundary() -> None:
    text = '[mcp_servers.ableton-live-mcp]\ncommand="x"\n[[other.items]]\nname="keep"\n'
    remaining = remove_server_blocks(text, "ableton-live-mcp")
    assert '[[other.items]]' in remaining and 'name="keep"' in remaining


def test_config_backup_hash_matches_crlf_backup_bytes(monkeypatch, tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings.codex_home.mkdir(parents=True)
    original = b'# CRLF\r\n[mcp_servers."ableton-live-mcp"]\r\ncommand="old"\r\n'
    settings.codex_config_path.write_bytes(original)
    state = new_state()
    monkeypatch.setattr("codex_ableton_live_mcp_setup.codex_config.shutil.which", lambda name: f"C:/{name}.exe")

    class FakeRunner:
        dry_run = False
        def run(self, args, **kwargs):
            from codex_ableton_live_mcp_setup.process import CommandResult
            return CommandResult(tuple(map(str, args)), 0, "{}", "")

    configure_codex(settings, FakeRunner(), state)
    backup = Path(state["codex"]["backup_path"])
    assert state["codex"]["backup_sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()
