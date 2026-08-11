"""Global context: prove validation acceptance fields, CLI placement, and approve risk gating."""

import json
from pathlib import Path

import pytest

from codex_ableton_live_mcp_setup.cli import build_parser, main
from codex_ableton_live_mcp_setup.configuration import Settings
from codex_ableton_live_mcp_setup.errors import SetupError
from codex_ableton_live_mcp_setup.process import CommandResult
from codex_ableton_live_mcp_setup.validation import capture_ableton_evidence, parse_json_output, scan_recent_live_log, validate_install
from codex_ableton_live_mcp_setup.workflow import require_risk_acceptance


class FakeValidatorRunner:
    def __init__(self, payload, returncode=0):
        self.payload = payload
        self.returncode = returncode

    def run(self, args, **kwargs):
        return CommandResult(tuple(map(str, args)), self.returncode, json.dumps(self.payload), "failure" if self.returncode else "")


def settings_for(tmp_path: Path, approval_mode: str = "approve") -> Settings:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library", approval_mode=approval_mode)
    settings.validator_executable.parent.mkdir(parents=True, exist_ok=True)
    settings.validator_executable.write_text("", encoding="utf-8")
    return settings


def valid_payload(post: bool = False) -> dict:
    remote = {"installed_files_current": True}
    if post:
        remote.update(runtime_current=True, live_mutations_safe=True)
    return {"remote_script": remote, "visual_capture": {"ok": True}}


def test_validate_pre_and_post_require_acceptance_fields(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    assert validate_install(settings, FakeValidatorRunner(valid_payload()), "pre-live")["ok"]
    assert validate_install(settings, FakeValidatorRunner(valid_payload(True)), "post-live")["ok"]
    with pytest.raises(SetupError, match="runtime_current"):
        validate_install(settings, FakeValidatorRunner(valid_payload()), "post-live")


def test_validator_nonzero_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(SetupError, match="failed"):
        validate_install(settings_for(tmp_path), FakeValidatorRunner({}, 1), "pre-live")


def test_nonzero_validator_does_not_mask_stderr_with_json_error(tmp_path: Path) -> None:
    class InvalidRunner:
        def run(self, args, **kwargs):
            return CommandResult(tuple(map(str, args)), 1, "not-json", "validator crashed")
    with pytest.raises(SetupError, match="validator crashed"):
        validate_install(settings_for(tmp_path), InvalidRunner(), "pre-live")


def test_json_output_must_be_object() -> None:
    assert parse_json_output('{"ok":true}') == {"ok": True}
    with pytest.raises(SetupError):
        parse_json_output("[]")


def test_cli_options_are_after_subcommand() -> None:
    args = build_parser().parse_args(["install", "--dry-run", "--accept-risk", "--port", "9000", "--approval-mode", "approve"])
    assert args.command == "install" and args.dry_run and args.accept_risk and args.port == 9000
    validate = build_parser().parse_args(["validate", "post-live", "--json"])
    assert validate.stage == "post-live" and validate.json


def test_json_mode_keeps_validation_errors_structured(capsys, tmp_path: Path) -> None:
    returncode = main(["doctor", "--json", "--port", "0", "--user-library", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)
    assert returncode == 2 and payload["ok"] is False
    assert "between" in payload["error"]


def test_only_approve_requires_explicit_risk(tmp_path: Path) -> None:
    with pytest.raises(SetupError, match="arbitrary Python"):
        require_risk_acceptance(settings_for(tmp_path, "approve"), False)
    require_risk_acceptance(settings_for(tmp_path, "approve"), True)
    for mode in ("auto", "prompt", "writes"):
        require_risk_acceptance(settings_for(tmp_path, mode), False)


def test_capture_requires_nonblank_upstream_pixel_evidence(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    settings.capture_executable.write_text("", encoding="utf-8")

    class CaptureRunner:
        def run(self, args, **kwargs):
            output = Path(args[2])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"png-evidence")
            payload = {"ok": True, "path": str(output), "postprocess": {"size": [10, 10], "content": {"blank": False, "mean_luma": 42}}, "window": {"title": "Live"}}
            return CommandResult(tuple(map(str, args)), 0, json.dumps(payload), "")

    result = capture_ableton_evidence(settings, CaptureRunner())
    assert result["ok"] is True and Path(result["path"]).is_file()
    assert "window" not in result and "pid" not in json.dumps(result).lower()


def test_capture_blank_is_validation_blocker(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    settings.capture_executable.write_text("", encoding="utf-8")

    class BlankRunner:
        def run(self, args, **kwargs):
            output = Path(args[2])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"blank")
            return CommandResult(tuple(map(str, args)), 0, json.dumps({"ok": True, "postprocess": {"content": {"blank": True}}}), "")

    with pytest.raises(SetupError, match="blank"):
        capture_ableton_evidence(settings, BlankRunner())


def test_nonzero_capture_does_not_mask_stderr_with_json_error(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    settings.capture_executable.write_text("", encoding="utf-8")
    class FailedRunner:
        def run(self, args, **kwargs):
            return CommandResult(tuple(map(str, args)), 1, "not-json", "capture crashed")
    with pytest.raises(SetupError, match="capture crashed"):
        capture_ableton_evidence(settings, FailedRunner())


def test_live_log_scan_reports_clean_and_blocks_script_errors(tmp_path: Path) -> None:
    log = tmp_path / "Live 12.3.8" / "Preferences" / "Log.txt"
    log.parent.mkdir(parents=True)
    log.write_text("Loading Ableton_Live_MCP control surface\nStarted successfully\n", encoding="utf-8")
    assert scan_recent_live_log(tmp_path)["errors"] == []
    log.write_text("Loading Ableton_Live_MCP control surface\nImportError: failed to load Ableton_Live_MCP\n", encoding="utf-8")
    with pytest.raises(SetupError, match="ImportError"):
        scan_recent_live_log(tmp_path)


def test_live_log_scan_requires_startup_marker(tmp_path: Path) -> None:
    log = tmp_path / "Live 12.3.8" / "Preferences" / "Log.txt"
    log.parent.mkdir(parents=True)
    log.write_text("Live started with no selected custom control surface\n", encoding="utf-8")
    with pytest.raises(SetupError, match="startup marker"):
        scan_recent_live_log(tmp_path)
