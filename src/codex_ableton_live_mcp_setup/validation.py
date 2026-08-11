"""Global context: verify offline STDIO behavior and upstream pre/post-Live acceptance contracts."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from .state import timestamp_slug
from typing import Any

from .configuration import Settings
from .errors import SetupError
from .logging_utils import SetupLogger
from .manifest import VersionManifest
from .process import Runner, merged_environment


def stdio_smoke(settings: Settings, manifest: VersionManifest, logger: SetupLogger) -> dict[str, Any]:
    """Initialize, recover from malformed JSON, list schemas, and prove Unicode/LF framing."""
    uv = shutil.which("uv")
    if not uv:
        raise SetupError("uv is required for the configured STDIO smoke check")
    requests = [
        {"jsonrpc": "2.0", "id": "init-å", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "setup-検証", "version": "1"}, "capabilities": {}}},
        "{malformed",
        {"jsonrpc": "2.0", "id": "tools-ß", "method": "tools/list", "params": {}},
    ]
    payload = b"".join(
        (item.encode("utf-8") if isinstance(item, str) else json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + b"\n"
        for item in requests
    )
    # uv's Windows env-file parser treats backslashes as escapes, so pass normalized forward slashes.
    command = [uv, "run", "--no-project", "--env-file", settings.runtime_env_path.as_posix(), "--", settings.server_executable.as_posix()]
    logger.log("$ " + subprocess.list2cmdline(command) + " [binary UTF-8 STDIO smoke]")
    try:
        completed = subprocess.run(command, cwd=settings.checkout, input=payload, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SetupError(f"STDIO smoke process failed: {exc}") from exc
    stdout_text = completed.stdout.decode("utf-8", errors="strict")
    stderr_text = completed.stderr.decode("utf-8", errors="replace")
    logger.log(f"exit={completed.returncode}\nstdout:\n{stdout_text}\nstderr:\n{stderr_text}")
    if completed.returncode != 0 or b"\r\n" in completed.stdout:
        raise SetupError("STDIO server failed or emitted CRLF instead of LF-only framing")
    try:
        responses = [json.loads(line) for line in stdout_text.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise SetupError(f"STDIO server emitted invalid JSON: {exc}") from exc
    by_id = {item.get("id"): item for item in responses}
    if "init-å" not in by_id or "tools-ß" not in by_id:
        raise SetupError("STDIO Unicode JSON-RPC identifiers did not round trip")
    parse_errors = [item for item in responses if item.get("error", {}).get("code") == -32700]
    if len(parse_errors) != 1:
        raise SetupError("STDIO malformed JSON did not produce one recoverable -32700 error")
    tools = by_id["tools-ß"].get("result", {}).get("tools", [])
    names = [tool.get("name") for tool in tools]
    if len(tools) != manifest.tool_count or len(set(names)) != manifest.tool_count:
        raise SetupError(f"Expected {manifest.tool_count} unique tools, received {len(tools)}")
    invalid = [tool.get("name") for tool in tools if not isinstance(tool.get("inputSchema"), dict) or tool["inputSchema"].get("type") != "object"]
    if invalid:
        raise SetupError(f"Invalid MCP tool schemas: {invalid}")
    return {"ok": True, "tool_count": len(tools), "unicode_roundtrip": True, "lf_only": True, "parse_recovery": True}


def validate_install(settings: Settings, runner: Runner, stage: str) -> dict[str, Any]:
    """Run the pinned upstream validator and enforce stronger post-Live mutation-safety fields."""
    if stage not in {"pre-live", "post-live"}:
        raise SetupError(f"Unknown validation stage: {stage}")
    args = [settings.validator_executable, "--target-dir", settings.remote_scripts_dir]
    if stage == "pre-live":
        args.append("--skip-live")
    environment = merged_environment({
        "ABLETON_MCP_HOST": settings.host,
        "ABLETON_MCP_PORT": str(settings.port),
        "ABLETON_USER_LIBRARY": str(settings.user_library),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    result = runner.run(args, cwd=settings.checkout, env=environment, check=False, timeout=180)
    if result.returncode != 0:
        raise SetupError(f"Upstream {stage} validation failed: {result.stderr.strip() or result.stdout.strip()}")
    payload = parse_json_output(result.stdout)
    remote = payload.get("remote_script", {})
    if not remote.get("installed_files_current"):
        raise SetupError("Validation did not confirm current installed Remote Script files")
    if not payload.get("visual_capture", {}).get("ok"):
        raise SetupError("Validation did not confirm working visual capture dependencies")
    if stage == "post-live" and (not remote.get("runtime_current") or not remote.get("live_mutations_safe")):
        raise SetupError("Post-Live validation did not confirm runtime_current and live_mutations_safe")
    return {"ok": True, "stage": stage, "results": payload}


def parse_json_output(output: str) -> dict[str, Any]:
    """Parse the validator's single JSON document and require an object result."""
    try:
        value = json.loads(output)
    except json.JSONDecodeError as exc:
        raise SetupError(f"Validator did not emit valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SetupError("Validator JSON must be an object")
    return value


def capture_ableton_evidence(settings: Settings, runner: Runner) -> dict[str, Any]:
    """Capture one Ableton-only PNG and require upstream's pixel statistics to prove it nonblank."""
    if not settings.capture_executable.is_file():
        raise SetupError(f"Ableton-only capture executable is missing: {settings.capture_executable}")
    output = settings.state_dir / "evidence" / f"ableton-post-live-{timestamp_slug()}.png"
    result = runner.run(
        [settings.capture_executable, "--output", output, "--max-width", "1920"],
        cwd=settings.checkout,
        check=False,
        timeout=90,
    )
    if result.returncode != 0:
        raise SetupError(f"Ableton-only visual capture failed: {result.stderr.strip() or result.stdout.strip()}")
    payload = parse_json_output(result.stdout)
    content = payload.get("postprocess", {}).get("content", {})
    if not payload.get("ok"):
        raise SetupError(f"Ableton-only visual capture failed: {payload.get('error') or 'unknown capture error'}")
    if content.get("blank") is not False:
        raise SetupError("Ableton-only capture is blank or could not be pixel-validated; keep Live visible and the display unlocked")
    if not output.is_file() or output.stat().st_size <= 0:
        raise SetupError(f"Ableton-only capture did not create a nonempty PNG: {output}")
    return {
        "ok": True,
        "path": str(output),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "size": payload.get("postprocess", {}).get("size"),
        "content": content,
        "backend": payload.get("backend"),
    }


def scan_recent_live_log(log_root: Path | None = None, tail_lines: int = 4000, evidence_dir: Path | None = None) -> dict[str, Any]:
    """Scan the newest Live Log.txt tail for Python/Remote Script errors near this integration."""
    app_data = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    root = log_root or app_data / "Ableton"
    candidates = sorted(root.glob("Live */Preferences/Log.txt"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise SetupError(f"No Ableton Live Log.txt was found under {root}; start Live once and retry post-live validation")
    log_path = candidates[0]
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-tail_lines:]
    marker_words = ("ableton_live_mcp", "ableton live mcp", "ableton-live-mcp")
    error_words = ("traceback", "syntaxerror", "importerror", "exception", "remote script error", "failed to load")
    marker_indexes = [index for index, line in enumerate(lines) if any(word in line.lower() for word in marker_words)]
    suspicious: list[str] = []
    for index, line in enumerate(lines):
        lower = line.lower()
        near_marker = any(abs(index - marker) <= 5 for marker in marker_indexes)
        if any(word in lower for word in error_words) and (near_marker or any(word in lower for word in marker_words)):
            suspicious.append(line.strip())
    report: dict[str, Any] = {
        "ok": not suspicious,
        "path": str(log_path),
        "tail_lines_scanned": len(lines),
        "script_mentions": len(marker_indexes),
        "errors": suspicious[:10],
    }
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = evidence_dir / f"live-log-scan-{timestamp_slug()}.json"
        evidence_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        report["evidence_path"] = str(evidence_path)
    if suspicious:
        raise SetupError("Recent Ableton Log.txt contains Ableton_Live_MCP/Python errors: " + " | ".join(suspicious[:10]))
    if not marker_indexes:
        raise SetupError("Recent Ableton Log.txt has no Ableton_Live_MCP startup marker; reload/select the Control Surface and retry")
    return report
