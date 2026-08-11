"""Global context: prove deterministic dotenv precedence, discovery, and validation."""

from pathlib import Path

import pytest

from codex_ableton_live_mcp_setup.configuration import Settings, discover_user_library, load_settings, read_dotenv, repository_root
from codex_ableton_live_mcp_setup.errors import SetupError
from codex_ableton_live_mcp_setup.runtime import runtime_env_text


def test_dotenv_supports_utf8_quoted_spaces_and_forward_slashes(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('ABLETON_SETUP_CHECKOUT="C:/Música Setup/ableton-live-mcp"\nABLETON_MCP_PORT="8766"\n', encoding="utf-8")
    assert read_dotenv(env_file) == {"ABLETON_SETUP_CHECKOUT": "C:/Música Setup/ableton-live-mcp", "ABLETON_MCP_PORT": "8766"}


def test_cli_overrides_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    library = home / "Documents" / "Ableton" / "User Library"
    library.mkdir(parents=True)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    env_file = tmp_path / ".env"
    env_file.write_text(f'ABLETON_USER_LIBRARY="{library.as_posix()}"\nABLETON_MCP_PORT="9000"\n', encoding="utf-8")
    settings = load_settings({"port": 8765, "checkout": tmp_path / "checkout"}, env_file)
    assert settings.port == 8765
    assert settings.checkout == (tmp_path / "checkout").resolve()
    assert settings.user_library == library.resolve()


def test_discovery_fails_when_multiple_libraries_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = tmp_path / "Documents" / "Ableton" / "User Library"
    second = tmp_path / "OneDrive" / "Documents" / "Ableton" / "User Library"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    monkeypatch.delenv("OneDrive", raising=False)
    with pytest.raises(SetupError, match="Multiple"):
        discover_user_library(tmp_path)


@pytest.mark.parametrize("port", [0, 65536])
def test_invalid_ports_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, port: int) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    with pytest.raises(SetupError, match="between"):
        load_settings({"port": port, "user_library": tmp_path / "library"}, tmp_path / "missing")


def test_runtime_env_is_utf8_quoted_and_loopback(tmp_path: Path) -> None:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "Música Library")
    text = runtime_env_text(settings)
    assert 'ABLETON_MCP_HOST="127.0.0.1"' in text
    assert 'ABLETON_MCP_PORT="8765"' in text
    assert "Música Library" in text
    assert "\\" not in next(line for line in text.splitlines() if line.startswith("ABLETON_USER_LIBRARY="))


def test_default_env_is_repository_root_not_calling_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    library = tmp_path / "library"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settings = load_settings({"user_library": library}, None)
    assert settings.port == 8765
    assert settings.checkout == (tmp_path / "Documents" / "Codex" / "MCP" / "ableton-live-mcp").resolve()


def test_checkout_inside_public_repository_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SetupError, match="outside"):
        load_settings({"checkout": repository_root() / "ableton-live-mcp", "user_library": tmp_path}, tmp_path / "missing")


def test_unsafe_server_name_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SetupError, match="only letters"):
        load_settings({"checkout": tmp_path / "checkout", "user_library": tmp_path, "server_name": "bad.name"}, tmp_path / "missing")
