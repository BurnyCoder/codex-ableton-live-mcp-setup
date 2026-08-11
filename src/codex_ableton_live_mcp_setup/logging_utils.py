"""Global context: timestamp every setup action and preserve complete subprocess I/O locally."""

from __future__ import annotations

import json
import os
import re
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO


SECRET_KEY_PATTERN = re.compile(r"(?i)(token|secret|password|api[_-]?key|credential)")


@dataclass
class SetupLogger:
    """Write the same timestamped, untruncated messages to terminal and a local log file."""

    path: Path
    stream: TextIO = sys.stderr

    def __post_init__(self) -> None:
        """Create only the ignored log directory selected by the caller."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        """Emit every line with a UTC timestamp while retaining complete multiline content."""
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        rendered = f"[{timestamp}] {message}"
        print(rendered, file=self.stream, flush=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered + "\n")


def new_logger(log_root: Path | None = None) -> SetupLogger:
    """Create a collision-resistant timestamped logger in the repository's ignored logs folder."""
    root = log_root or Path(__file__).resolve().parents[2] / "logs"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return SetupLogger(root / f"setup-{stamp}.log")


def redact_for_public(value: Any, home: Path | None = None) -> Any:
    """Recursively remove secrets and replace machine identity in publishable structured output."""
    resolved_home = str((home or Path.home()).resolve())
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    machine = socket.gethostname()
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SECRET_KEY_PATTERN.search(str(key)) else redact_for_public(item, home)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_for_public(item, home) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_for_public(item, home) for item in value)
    if isinstance(value, str):
        redacted = value.replace(resolved_home, "%USERPROFILE%").replace(resolved_home.replace("\\", "/"), "%USERPROFILE%")
        if username:
            redacted = redacted.replace(username, "%USERNAME%")
        return redacted.replace(machine, "%COMPUTERNAME%")
    return value


def print_result(result: dict[str, Any], as_json: bool, home: Path | None = None) -> None:
    """Print a stable sanitized result; JSON mode remains machine-readable."""
    sanitized = redact_for_public(result, home)
    if as_json:
        print(json.dumps(sanitized, indent=2, sort_keys=True, ensure_ascii=False))
        return
    for key, value in sanitized.items():
        if isinstance(value, (dict, list)):
            print(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        else:
            print(f"{key}: {value}")
