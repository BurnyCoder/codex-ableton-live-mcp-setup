"""Global context: persist transaction evidence needed for exact, section-scoped rollback."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import SetupError


STATE_SCHEMA_VERSION = 1


def timestamp_slug() -> str:
    """Return a filesystem-safe UTC timestamp for backups and transaction identifiers."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def new_state() -> dict[str, Any]:
    """Create the minimal initial transaction record before system mutations begin."""
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "installation_id": timestamp_slug(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rolled_back": False,
    }


def load_state(path: Path, required: bool = False) -> dict[str, Any] | None:
    """Load validated state or fail closed when rollback requires missing/corrupt evidence."""
    if not path.is_file():
        if required:
            raise SetupError(f"No installation state exists at {path}; refusing an unscoped rollback")
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SetupError(f"Installation state is unreadable at {path}: {exc}") from exc
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise SetupError(f"Unsupported installation state schema at {path}")
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Atomically replace state so interruption cannot leave partially written rollback data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix="state-", suffix=".json", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(state, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
