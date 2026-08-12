#!/usr/bin/env python3
"""Fail when the public tree contains credentials or private setup evidence.

Global context: the companion repository must publish setup documentation, not
machine-specific transcripts, runtime configuration, Live object IDs, or
credentials. This scanner checks text and PNG metadata conservatively.

Reference: https://docs.github.com/code-security/secret-scanning/introduction/about-secret-scanning
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import zlib
from pathlib import Path
from typing import Iterable, Sequence


TEXT_SUFFIXES = {
    ".css",
    ".env.example",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
IGNORED_DIRECTORIES = {".git", ".venv", "__pycache__", ".pytest_cache"}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the public root and optional machine-readable output mode."""

    parser = argparse.ArgumentParser(description="Scan a public repository for private evidence.")
    parser.add_argument("root", nargs="?", default=Path("."), type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def candidate_files(root: Path) -> Iterable[Path]:
    """Yield tracked and untracked public files while honoring .gitignore."""

    command = ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    completed = subprocess.run(command, check=False, capture_output=True)
    if completed.returncode == 0:
        for raw_name in completed.stdout.split(b"\0"):
            if raw_name:
                path = root / raw_name.decode("utf-8", errors="strict")
                if path.is_file():
                    yield path
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part in IGNORED_DIRECTORIES for part in path.parts):
            yield path


def secret_patterns() -> list[tuple[str, re.Pattern[str]]]:
    """Compile high-confidence credential and private-path signatures."""

    # Split literal credential prefixes so this scanner does not flag its own source.
    pem_header = "-----" + "BEGIN " + "(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    placeholders = r"(?:USERNAME|USER|YOUR_NAME|YOUR_USERNAME)\b|<[^>]+>"
    mac_home = r"(?i)(?<![A-Za-z0-9_])/User" + rf"s/(?!{placeholders})[^/\s]+"
    transcript = r"(?i)PowerShell " + r"transcript (?:start|end)"
    return [
        ("private key", re.compile(pem_header)),
        ("OpenAI-style API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
        ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
        ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
        ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
        (
            "machine-specific Windows home path",
            re.compile(rf"(?i)\b[A-Z]:[\\/]+Users[\\/]+(?!{placeholders})[^\\/\s]+"),
        ),
        (
            "machine-specific macOS home path",
            re.compile(mac_home),
        ),
        ("raw PowerShell transcript", re.compile(transcript)),
        ("raw Live object ID", re.compile(r'(?i)"(?:id|object_id)"\s*:\s*[1-9][0-9]{6,}')),
    ]


def png_text(path: Path) -> str:
    """Extract textual PNG chunks so screenshots cannot hide local paths in metadata."""

    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("file has .png suffix but no PNG signature")
    position = 8
    chunks: list[str] = []
    while position + 12 <= len(data):
        length = int.from_bytes(data[position : position + 4], "big")
        chunk_type = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        position += 12 + length
        if chunk_type == b"tEXt":
            chunks.append(payload.decode("latin-1", errors="replace"))
        elif chunk_type == b"zTXt" and b"\0" in payload:
            keyword, compressed = payload.split(b"\0", 1)
            if compressed[:1] == b"\0":
                chunks.append(keyword.decode("latin-1") + " " + zlib.decompress(compressed[1:]).decode("latin-1"))
        elif chunk_type == b"iTXt":
            chunks.append(payload.decode("utf-8", errors="replace"))
        elif chunk_type == b"IEND":
            break
    return "\n".join(chunks)


def public_text(path: Path) -> str | None:
    """Return searchable public text for supported source and PNG formats."""

    if path.suffix.casefold() == ".png":
        return png_text(path)
    if path.name == ".env.example" or path.suffix.casefold() in TEXT_SUFFIXES or path.name == "uv.lock":
        return path.read_text(encoding="utf-8", errors="strict")
    return None


def scan_file(path: Path) -> list[str]:
    """Return all high-confidence publication defects found in one file."""

    findings: list[str] = []
    name = path.name.casefold()
    if name == ".env":
        findings.append("runtime .env file must not be public")
    if path.suffix.casefold() == ".log" or "transcript" in name:
        findings.append("raw log/transcript must not be public")
    if any(token in name for token in ("config.toml.before", ".bak", ".backup")):
        findings.append("configuration backup must not be public")
    try:
        text = public_text(path)
    except Exception as exc:
        findings.append(f"could not inspect artifact safely: {exc}")
        return findings
    if text is None:
        return findings
    for label, pattern in secret_patterns():
        if pattern.search(text):
            findings.append(label)
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    """Scan the public tree and fail with paths but never print matched secrets."""

    args = parse_args(argv)
    root = args.root.resolve()
    findings: dict[str, list[str]] = {}
    scanned = 0
    for path in candidate_files(root):
        scanned += 1
        defects = scan_file(path)
        if defects:
            findings[str(path.relative_to(root))] = defects
    result = {"ok": not findings, "scanned_files": scanned, "findings": findings}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif findings:
        for path, defects in findings.items():
            print(f"{path}: {', '.join(defects)}")
    else:
        print(f"Public safety scan passed for {scanned} file(s).")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
