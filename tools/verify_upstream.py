#!/usr/bin/env python3
"""Verify the exact reviewed Ableton Live MCP upstream on Windows.

Global context: this CI-only integration check fetches GitHub's pull-request ref,
fails closed on any commit/parent/tree mismatch, installs that checkout into an
isolated uv environment, classifies the two documented Windows-only test
assertions, validates a temporary Remote Script install, and exercises MCP STDIO
without calling Ableton Live.

Primary references:
- GitHub PR refs: https://docs.github.com/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/checking-out-pull-requests-locally
- uv environments: https://docs.astral.sh/uv/pip/environments/
- JSON-RPC errors: https://www.jsonrpc.org/specification#error_object
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Pins:
    """Represent the complete reviewed upstream identity and expected behavior."""

    url: str
    base_sha: str
    pr_number: int
    pr_sha: str
    tree_sha: str
    package_version: str
    tool_count: int
    accepted_failures: tuple[str, ...]


@dataclass(frozen=True)
class CommandResult:
    """Preserve complete subprocess output for classification and diagnostics."""

    args: tuple[str, ...]
    returncode: int
    output: str


def timestamp() -> str:
    """Return an unambiguous UTC timestamp for terminal phase logging."""

    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the reviewed manifest and optional retained-workspace controls."""

    parser = argparse.ArgumentParser(description="Verify the exact reviewed upstream checkout.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--workdir", type=Path, help="Use and retain this empty directory.")
    parser.add_argument("--json", action="store_true", help="Print a final JSON summary.")
    return parser.parse_args(argv)


def nested_value(data: Mapping[str, Any], *names: str) -> Any:
    """Read a manifest field from supported root/upstream/expected groupings."""

    containers: list[Mapping[str, Any]] = [data]
    for key in ("upstream", "expected", "verification", "pull_request"):
        value = data.get(key)
        if isinstance(value, Mapping):
            containers.append(value)
            nested_expected = value.get("expected")
            if isinstance(nested_expected, Mapping):
                containers.append(nested_expected)
    for container in containers:
        for name in names:
            if name in container:
                return container[name]
    raise KeyError(f"Manifest is missing required field; accepted names: {', '.join(names)}")


def require_sha(value: Any, label: str) -> str:
    """Reject abbreviated or malformed Git object identities."""

    text = str(value).lower()
    if not re.fullmatch(r"[0-9a-f]{40}", text):
        raise ValueError(f"{label} must be a full 40-character SHA-1, got {value!r}")
    return text


def load_pins(path: Path) -> Pins:
    """Load and strictly validate the single source of upstream version truth."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("Version manifest root must be a JSON object")
    failures = nested_value(
        data,
        "accepted_test_failures",
        "accepted_windows_failures",
        "allowed_test_failures",
    )
    if not isinstance(failures, list) or not all(isinstance(item, str) for item in failures):
        raise ValueError("accepted_test_failures must be an array of pytest node IDs")
    normalized_failures = tuple(normalize_nodeid(item) for item in failures)
    if len(normalized_failures) != 2 or len(set(normalized_failures)) != 2:
        raise ValueError("Exactly two distinct documented Windows failures must be accepted")
    url = str(nested_value(data, "url", "upstream_url", "upstream_repository"))
    if url.rstrip("/") != "https://github.com/bschoepke/ableton-live-mcp.git".rstrip("/"):
        raise ValueError(f"Unexpected upstream URL: {url}")
    return Pins(
        url=url,
        base_sha=require_sha(nested_value(data, "base_sha", "base_commit"), "base_sha"),
        pr_number=int(nested_value(data, "windows_pr_number", "pr_number", "number")),
        pr_sha=require_sha(nested_value(data, "windows_pr_sha", "pr_sha", "commit"), "windows_pr_sha"),
        tree_sha=require_sha(nested_value(data, "expected_tree", "tree_sha", "tree"), "expected_tree"),
        package_version=str(nested_value(data, "package_version")),
        tool_count=int(nested_value(data, "tool_count")),
        accepted_failures=normalized_failures,
    )


def run_logged(
    args: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> CommandResult:
    """Stream and retain complete merged subprocess output without truncation."""

    command = tuple(str(item) for item in args)
    print(f"[{timestamp()}] $ {subprocess.list2cmdline(command)}", flush=True)
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        lines.append(line)
        print(line, end="", flush=True)
    returncode = process.wait()
    result = CommandResult(command, returncode, "".join(lines))
    print(f"[{timestamp()}] exit={returncode}", flush=True)
    if check and returncode != 0:
        raise RuntimeError(f"Command failed with exit code {returncode}: {subprocess.list2cmdline(command)}")
    return result


def git_output(checkout: Path, *args: str) -> str:
    """Run a quiet Git query and return its strict UTF-8 output."""

    completed = subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def acquire_checkout(pins: Pins, checkout: Path) -> None:
    """Fetch the exact base and GitHub PR ref, then verify commit, parent, and tree."""

    run_logged(["git", "init", str(checkout)])
    run_logged(["git", "-C", checkout, "remote", "add", "origin", pins.url])
    run_logged(["git", "-C", checkout, "fetch", "--no-tags", "--depth=1", "origin", pins.base_sha])
    pr_ref = f"pull/{pins.pr_number}/head"
    run_logged(["git", "-C", checkout, "fetch", "--no-tags", "--depth=2", "origin", pr_ref])
    fetched = git_output(checkout, "rev-parse", "FETCH_HEAD").lower()
    if fetched != pins.pr_sha:
        raise ValueError(f"GitHub PR ref moved: expected {pins.pr_sha}, fetched {fetched}")
    run_logged(["git", "-C", checkout, "checkout", "--detach", pins.pr_sha])
    actual_commit = git_output(checkout, "rev-parse", "HEAD").lower()
    actual_parents = git_output(checkout, "show", "-s", "--format=%P", "HEAD").lower().split()
    actual_tree = git_output(checkout, "show", "-s", "--format=%T", "HEAD").lower()
    if actual_commit != pins.pr_sha:
        raise ValueError(f"Commit mismatch: expected {pins.pr_sha}, found {actual_commit}")
    if actual_parents != [pins.base_sha]:
        raise ValueError(f"Parent mismatch: expected {[pins.base_sha]}, found {actual_parents}")
    if actual_tree != pins.tree_sha:
        raise ValueError(f"Tree mismatch: expected {pins.tree_sha}, found {actual_tree}")
    if git_output(checkout, "status", "--short"):
        raise ValueError("Exact upstream checkout is unexpectedly dirty")


def verify_package_version(checkout: Path, expected: str) -> None:
    """Require the pinned checkout to advertise the reviewed package version."""

    with (checkout / "pyproject.toml").open("rb") as stream:
        actual = str(tomllib.load(stream)["project"]["version"])
    if actual != expected:
        raise ValueError(f"Package version mismatch: expected {expected}, found {actual}")


def clear_exact_directory_readonly(path: Path) -> bool:
    """Clear only one Windows directory's ReadOnly bit and report whether it changed."""

    if os.name != "nt" or not path.is_dir():
        return False
    # GetFileAttributesW/SetFileAttributesW preserve every unrelated attribute.
    # Source: https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-setfileattributesw
    import ctypes

    file_api = ctypes.windll.kernel32
    file_api.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
    file_api.GetFileAttributesW.restype = ctypes.c_uint32
    file_api.SetFileAttributesW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    file_api.SetFileAttributesW.restype = ctypes.c_int
    invalid_attributes = 0xFFFFFFFF
    readonly_attribute = 0x00000001
    attributes = file_api.GetFileAttributesW(str(path))
    if attributes == invalid_attributes:
        raise OSError(f"Could not read Windows attributes for exact directory: {path}")
    if not attributes & readonly_attribute:
        return False
    if not file_api.SetFileAttributesW(str(path), attributes & ~readonly_attribute):
        raise ctypes.WinError()
    updated = file_api.GetFileAttributesW(str(path))
    if updated == invalid_attributes or updated & readonly_attribute:
        raise OSError(f"ReadOnly attribute remained on exact directory: {path}")
    print(f"[{timestamp()}] Cleared ReadOnly on exact directory: {path}", flush=True)
    return True


def deterministic_tree_hash(root: Path) -> str:
    """Hash normalized relative names and file bytes, excluding timestamps and attributes."""

    if not root.is_dir():
        raise FileNotFoundError(f"Tree hash root is missing: {root}")
    digest = hashlib.sha256()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"Tree hash root contains no files: {root}")
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def venv_python(venv: Path) -> Path:
    """Return the platform-specific isolated Python executable."""

    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def venv_command(venv: Path, name: str) -> Path:
    """Return a console script path inside the isolated environment."""

    suffix = ".exe" if os.name == "nt" else ""
    directory = "Scripts" if os.name == "nt" else "bin"
    return venv / directory / f"{name}{suffix}"


def install_upstream(checkout: Path, venv: Path) -> Path:
    """Create a Python 3.14 uv environment and install only the exact checkout."""

    run_logged(["uv", "venv", "--python", "3.14", venv])
    python = venv_python(venv)
    run_logged(["uv", "pip", "install", "--python", python, "-e", f"{checkout}[dev]"])
    return python


def normalize_nodeid(nodeid: str) -> str:
    """Normalize pytest path separators without weakening the exact test identity."""

    return nodeid.strip().replace("\\", "/")


def reported_failures(output: str) -> set[str]:
    """Extract exact failed pytest node IDs from the short summary."""

    return {
        normalize_nodeid(match.group(1))
        for match in re.finditer(r"^FAILED\s+(\S+?)(?:\s+-\s+.*)?$", output, flags=re.MULTILINE)
    }


def run_upstream_tests(
    python: Path,
    checkout: Path,
    accepted: Sequence[str],
    environment: Mapping[str, str],
) -> dict[str, Any]:
    """Accept zero failures or exactly the two documented defects, then rerun the remainder."""

    full = run_logged([python, "-m", "pytest", "-q", "--tb=short"], cwd=checkout, env=environment, check=False)
    failures = reported_failures(full.output)
    accepted_set = set(accepted)
    if full.returncode != 0 and failures != accepted_set:
        raise RuntimeError(
            "Upstream failures differ from the documented allowance: "
            f"expected {sorted(accepted_set)}, found {sorted(failures)}",
        )
    if full.returncode == 0 and failures:
        raise RuntimeError(f"pytest returned success while reporting failures: {sorted(failures)}")
    deselect = [f"--deselect={nodeid}" for nodeid in accepted]
    run_logged([python, "-m", "pytest", "-q", *deselect], cwd=checkout, env=environment)
    return {
        "full_suite_exit": full.returncode,
        "accepted_failures_observed": sorted(failures),
        "remaining_suite_passed": True,
    }


def validate_offline(
    venv: Path,
    checkout: Path,
    remote_root: Path,
    environment: Mapping[str, str],
) -> dict[str, Any]:
    """Require two byte-stable --update installs followed by --skip-live validation."""

    installer = venv_command(venv, "ableton-live-mcp-install-remote-script")
    validator = venv_command(venv, "ableton-live-mcp-validate")
    installed = remote_root / "Ableton_Live_MCP"
    run_logged([installer, "--target-dir", remote_root, "--update"], cwd=checkout, env=environment)
    first_hash = deterministic_tree_hash(installed)
    target_attribute_changed = clear_exact_directory_readonly(installed)
    run_logged([installer, "--target-dir", remote_root, "--update"], cwd=checkout, env=environment)
    second_hash = deterministic_tree_hash(installed)
    if first_hash != second_hash:
        raise ValueError(
            "Remote Script --update is not byte-idempotent: "
            f"first={first_hash}, second={second_hash}",
        )
    run_logged([validator, "--skip-live", "--target-dir", remote_root], cwd=checkout, env=environment)
    return {
        "update_runs": 2,
        "tree_sha256": second_hash,
        "idempotent": True,
        "target_readonly_cleared": target_attribute_changed,
    }


def stdio_smoke(
    venv: Path,
    checkout: Path,
    pins: Pins,
    base_environment: Mapping[str, str],
) -> dict[str, Any]:
    """Verify LF framing, Unicode, schemas, parse recovery, and clean process exit."""

    server = venv_command(venv, "ableton-live-mcp")
    environment = dict(base_environment)
    environment.update(
        {
            "ABLETON_MCP_HOST": "127.0.0.1",
            "ABLETON_MCP_PORT": "65530",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    )
    requests = [
        b"{malformed json}\n",
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "caf\u00e9",
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        + b"\n",
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).encode("utf-8") + b"\n",
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "\u65e5\u672c\u8a9e",
                "method": "tools/call",
                "params": {"name": "unknown-\u03a9", "arguments": {}},
            },
            ensure_ascii=False,
        ).encode("utf-8")
        + b"\n",
    ]
    print(f"[{timestamp()}] STDIO smoke: {server}", flush=True)
    process = subprocess.Popen(
        [str(server)],
        cwd=str(checkout),
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(b"".join(requests), timeout=30)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        stdout, stderr = process.communicate()
        raise RuntimeError(
            "MCP STDIO smoke timed out; partial stdout/stderr were preserved: "
            f"stdout={stdout.decode('utf-8', 'replace')!r}, "
            f"stderr={stderr.decode('utf-8', 'replace')!r}",
        ) from exc
    if process.returncode != 0:
        raise RuntimeError(f"MCP server exited {process.returncode}: {stderr.decode('utf-8', 'replace')}")
    if stderr:
        raise RuntimeError(f"MCP server wrote unexpected stderr: {stderr.decode('utf-8', 'replace')}")
    if b"\r\n" in stdout or not stdout.endswith(b"\n"):
        raise ValueError("MCP output is not bare-LF framed")
    decoded = stdout.decode("utf-8", errors="strict")
    records = [json.loads(line) for line in decoded.splitlines() if line]
    if len(records) != 4:
        raise ValueError(f"Expected 4 MCP responses, found {len(records)}")
    if records[0].get("id") is not None or records[0].get("error", {}).get("code") != -32700:
        raise ValueError("Malformed JSON did not return JSON-RPC -32700 with a null ID")
    initialization = records[1]
    if initialization.get("id") != "caf\u00e9":
        raise ValueError("Non-ASCII initialize ID did not round-trip")
    server_info = initialization.get("result", {}).get("serverInfo", {})
    if server_info.get("version") != pins.package_version:
        raise ValueError(f"STDIO server version mismatch: {server_info}")
    tools = records[2].get("result", {}).get("tools")
    if not isinstance(tools, list) or len(tools) != pins.tool_count:
        raise ValueError(f"Expected {pins.tool_count} tools, found {len(tools) if isinstance(tools, list) else tools}")
    names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
    if len(names) != len(set(names)):
        raise ValueError("MCP tools/list contains duplicate names")
    for tool in tools:
        schema = tool.get("inputSchema") if isinstance(tool, dict) else None
        if not isinstance(schema, dict) or schema.get("type") != "object":
            raise ValueError(f"Invalid tool inputSchema: {tool}")
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise ValueError(f"Invalid JSON Schema collections for tool {tool.get('name')}")
        if not set(required).issubset(properties):
            raise ValueError(f"Tool required fields are not declared as properties: {tool.get('name')}")
        json.dumps(schema, ensure_ascii=False)
    if records[3].get("id") != "\u65e5\u672c\u8a9e" or "unknown-\u03a9" not in records[3].get("error", {}).get("message", ""):
        raise ValueError("Non-ASCII error response did not round-trip after parse recovery")
    return {"responses": 4, "tool_count": len(tools), "lf_only": True, "unicode": True}


def verify_clean(checkout: Path) -> None:
    """Require validation and tests to leave the reviewed checkout unchanged."""

    status = git_output(checkout, "status", "--short")
    if status:
        raise ValueError(f"Upstream checks modified tracked or unignored files:\n{status}")


def run_verification(pins: Pins, root: Path) -> dict[str, Any]:
    """Execute the complete exact-pin Windows integration pipeline."""

    checkout = root / "upstream"
    venv = root / "runtime" / ".venv"
    remote_root = root / "remote-scripts"
    user_library = root / "user-library"
    sandbox_home = root / "home"
    sandbox_temp = root / "temp"
    user_library.mkdir(parents=True, exist_ok=True)
    (sandbox_home / "AppData" / "Roaming").mkdir(parents=True, exist_ok=True)
    (sandbox_home / "AppData" / "Local").mkdir(parents=True, exist_ok=True)
    sandbox_temp.mkdir(parents=True, exist_ok=True)
    isolated_environment = os.environ.copy()
    isolated_environment.update(
        {
            "ABLETON_MCP_HOST": "127.0.0.1",
            "ABLETON_MCP_PORT": "65530",
            "ABLETON_USER_LIBRARY": str(user_library),
            "APPDATA": str(sandbox_home / "AppData" / "Roaming"),
            "HOME": str(sandbox_home),
            "LOCALAPPDATA": str(sandbox_home / "AppData" / "Local"),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "TEMP": str(sandbox_temp),
            "TMP": str(sandbox_temp),
            "USERPROFILE": str(sandbox_home),
        },
    )
    acquire_checkout(pins, checkout)
    verify_package_version(checkout, pins.package_version)
    source_attribute_changed = clear_exact_directory_readonly(checkout / "Ableton_Live_MCP")
    python = install_upstream(checkout, venv)
    tests = run_upstream_tests(python, checkout, pins.accepted_failures, isolated_environment)
    offline_validation = validate_offline(venv, checkout, remote_root, isolated_environment)
    stdio = stdio_smoke(venv, checkout, pins, isolated_environment)
    verify_clean(checkout)
    return {
        "ok": True,
        "commit": pins.pr_sha,
        "parent": pins.base_sha,
        "tree": pins.tree_sha,
        "package_version": pins.package_version,
        "tests": tests,
        "offline_validation": offline_validation,
        "source_readonly_cleared": source_attribute_changed,
        "stdio": stdio,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Create an isolated workspace, run verification, and clean it by default."""

    args = parse_args(argv)
    pins = load_pins(args.manifest.resolve())
    if args.workdir:
        root = args.workdir.resolve()
        if root.exists() and any(root.iterdir()):
            raise ValueError(f"--workdir must be empty: {root}")
        root.mkdir(parents=True, exist_ok=True)
        result = run_verification(pins, root)
    else:
        with tempfile.TemporaryDirectory(prefix="ableton-mcp-upstream-") as temporary:
            result = run_verification(pins, Path(temporary))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Exact upstream integration passed for {pins.pr_sha} ({pins.tool_count} tools).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
