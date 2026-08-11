"""Global context: prove dry-run suppression, port detection, Computer Use parsing, and redaction."""

import json
import socket
import sys
from pathlib import Path

import pytest

from codex_ableton_live_mcp_setup.configuration import Settings
from codex_ableton_live_mcp_setup.doctor import checkout_destination_status, computer_use_status, doctor, port_status
from codex_ableton_live_mcp_setup.logging_utils import SetupLogger, redact_for_public
from codex_ableton_live_mcp_setup.manifest import load_manifest
from codex_ableton_live_mcp_setup.process import CommandResult, Runner
from codex_ableton_live_mcp_setup.errors import SetupError


class FakePluginRunner:
    def run(self, args, **kwargs):
        payload = {"installed": [{"pluginId": "computer-use@openai-bundled", "installed": True, "enabled": True, "version": "1"}]}
        return CommandResult(tuple(map(str, args)), 0, json.dumps(payload), "")


def test_dry_run_never_executes_mutating_command(tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    runner = Runner(SetupLogger(tmp_path / "log.txt"), dry_run=True)
    result = runner.run([sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('x')"], mutating=True)
    assert result.planned is True
    assert not marker.exists()
    assert "DRY-RUN" in (tmp_path / "log.txt").read_text(encoding="utf-8")


def test_runner_retains_streamed_output_and_timeout_partial(tmp_path: Path) -> None:
    runner = Runner(SetupLogger(tmp_path / "log.txt"))
    result = runner.run([sys.executable, "-c", "print('first', flush=True); print('second', flush=True)"])
    assert result.stdout == "first\nsecond\n"
    assert "stdout | first" in (tmp_path / "log.txt").read_text(encoding="utf-8")
    with pytest.raises(SetupError, match="Partial output"):
        runner.run([sys.executable, "-c", "import time; print('before-timeout', flush=True); time.sleep(2)"], timeout=0.1)
    assert "before-timeout" in (tmp_path / "log.txt").read_text(encoding="utf-8")


def test_port_status_detects_conflict() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        assert port_status("127.0.0.1", port)["listening"] is True


def test_checkout_destination_rejects_existing_nonrepository(tmp_path: Path) -> None:
    checkout = tmp_path / "occupied"
    checkout.mkdir()
    settings = Settings(checkout=checkout, user_library=tmp_path / "library")
    result = checkout_destination_status(settings, {"present": False, "path": str(checkout)})
    assert result["ok"] is False and result["existing_path_reusable"] is False


def test_computer_use_plugin_status_is_read_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("codex_ableton_live_mcp_setup.doctor.shutil.which", lambda name: "codex.exe")
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library", codex_home=tmp_path / "codex")
    settings.codex_home.mkdir()
    settings.codex_config_path.write_text('[plugins."computer-use@openai-bundled"]\nenabled=true\n', encoding="utf-8")
    result = computer_use_status(settings, FakePluginRunner())
    assert result["installed"] is True and result["enabled"] is True
    assert result["desktop_server_skill_toggles"] == "verify_manually"


def test_public_redaction_removes_home_machine_and_secrets(tmp_path: Path) -> None:
    value = {"path": str(tmp_path / "private"), "api_key": "secret", "nested": [str(tmp_path)]}
    redacted = redact_for_public(value, tmp_path)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["path"].startswith("%USERPROFILE%")


def test_doctor_fails_closed_on_unmanaged_requested_port_listener(monkeypatch, tmp_path: Path) -> None:
    library = tmp_path / "library"
    library.mkdir()
    monkeypatch.setattr("codex_ableton_live_mcp_setup.doctor.platform.system", lambda: "Windows")
    monkeypatch.setattr("codex_ableton_live_mcp_setup.doctor.platform.release", lambda: "11")
    monkeypatch.setattr("codex_ableton_live_mcp_setup.doctor.shutil.which", lambda name: f"C:/{name}.exe")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        settings = Settings(
            checkout=tmp_path / "missing-checkout",
            user_library=library,
            port=listener.getsockname()[1],
            codex_home=tmp_path / "codex",
            state_dir=tmp_path / "state",
        )
        result = doctor(settings, load_manifest(), FakePluginRunner())
    assert result["port_conflict"] is True
    assert result["ok"] is False
