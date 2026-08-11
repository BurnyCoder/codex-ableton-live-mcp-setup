"""Global context: create the upstream server's local, excluded, UTF-8 runtime configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .configuration import Settings
from .errors import SetupError
from .process import Runner


def runtime_env_text(settings: Settings) -> str:
    """Render non-secret values with quoted JSON strings and forward-slash Windows paths."""
    values = {
        "ABLETON_MCP_HOST": settings.host,
        "ABLETON_MCP_PORT": str(settings.port),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "ABLETON_USER_LIBRARY": settings.user_library.as_posix(),
    }
    return "".join(f"{key}={json.dumps(value, ensure_ascii=False)}\n" for key, value in values.items())


def configure_runtime(settings: Settings, runner: Runner) -> dict[str, Any]:
    """Write .env and exclude it only in the nested upstream checkout's local Git metadata."""
    expected = runtime_env_text(settings)
    exclude_path = settings.checkout / ".git" / "info" / "exclude"
    if runner.dry_run:
        runner.logger.log(f"DRY-RUN write UTF-8 runtime config {settings.runtime_env_path}")
        runner.logger.log(f"DRY-RUN ensure .env in {exclude_path}")
        return {"planned": True, "path": str(settings.runtime_env_path)}
    if not exclude_path.parent.is_dir():
        raise SetupError(f"Upstream checkout has no local Git exclude directory: {exclude_path.parent}")
    # Exclude the machine-specific file before creating it, eliminating an accidental-commit window.
    exclude = exclude_path.read_text(encoding="utf-8") if exclude_path.is_file() else ""
    entries = {line.strip() for line in exclude.splitlines()}
    if ".env" not in entries:
        prefix = "" if not exclude or exclude.endswith("\n") else "\n"
        with exclude_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(prefix + ".env\n")
    current = settings.runtime_env_path.read_text(encoding="utf-8") if settings.runtime_env_path.is_file() else None
    if current != expected:
        settings.runtime_env_path.write_text(expected, encoding="utf-8", newline="\n")
    return {"planned": False, "path": str(settings.runtime_env_path), "excluded_locally": True}
