"""Global context: lock the Windows forward-slash requirement for uv's env-file invocation."""

import json
from pathlib import Path

from codex_ableton_live_mcp_setup.configuration import Settings
from codex_ableton_live_mcp_setup.logging_utils import SetupLogger
from codex_ableton_live_mcp_setup.manifest import load_manifest
from codex_ableton_live_mcp_setup.validation import stdio_smoke


class Completed:
    returncode = 0
    stderr = b""

    def __init__(self) -> None:
        responses = [
            {"jsonrpc": "2.0", "id": "init-å", "result": {}},
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700}},
            {"jsonrpc": "2.0", "id": "tools-ß", "result": {"tools": [
                {"name": f"tool-{index}", "inputSchema": {"type": "object"}} for index in range(37)
            ]}},
        ]
        self.stdout = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in responses).encode("utf-8")


def test_stdio_smoke_passes_forward_slash_paths_to_uv(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library")
    captured = {}
    monkeypatch.setattr("codex_ableton_live_mcp_setup.validation.shutil.which", lambda name: "C:/Tools/uv.exe")

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Completed()

    monkeypatch.setattr("codex_ableton_live_mcp_setup.validation.subprocess.run", fake_run)
    result = stdio_smoke(settings, load_manifest(), SetupLogger(tmp_path / "log.txt"))
    assert result["ok"] is True
    assert "\\" not in captured["command"][4]
    assert "\\" not in captured["command"][6]
