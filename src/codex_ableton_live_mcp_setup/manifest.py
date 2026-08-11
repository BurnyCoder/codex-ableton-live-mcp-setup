"""Global context: load the single reviewed manifest that pins every upstream artifact."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import SetupError


@dataclass(frozen=True)
class VersionManifest:
    """Hold immutable upstream identity and expected validation results."""

    repository: str
    base_commit: str
    pr_number: int
    pr_ref: str
    pr_commit: str
    pr_parent: str
    pr_tree: str
    package_version: str
    tool_count: int
    accepted_windows_failures: tuple[str, ...]


def default_manifest_path() -> Path:
    """Resolve the manifest from the source checkout used by the thin wrapper."""
    repository_root = Path(__file__).resolve().parents[2]
    return repository_root / "config" / "versions.json"


def load_manifest(path: Path | None = None) -> VersionManifest:
    """Parse and validate the reviewed version manifest, failing closed on missing fields."""
    manifest_path = path or default_manifest_path()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        pull_request = payload["pull_request"]
        manifest = VersionManifest(
            repository=str(payload["upstream_repository"]),
            base_commit=_sha(payload["base_commit"], "base_commit"),
            pr_number=int(pull_request["number"]),
            pr_ref=str(pull_request["ref"]),
            pr_commit=_sha(pull_request["commit"], "pull_request.commit"),
            pr_parent=_sha(pull_request["parent"], "pull_request.parent"),
            pr_tree=_sha(pull_request["tree"], "pull_request.tree"),
            package_version=str(payload["package_version"]),
            tool_count=int(payload["tool_count"]),
            accepted_windows_failures=tuple(str(item) for item in payload["accepted_windows_failures"]),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SetupError(f"Invalid version manifest at {manifest_path}: {exc}") from exc
    if manifest.pr_parent != manifest.base_commit:
        raise SetupError("Version manifest is inconsistent: PR parent must equal the pinned base commit")
    if manifest.tool_count <= 0 or not manifest.package_version:
        raise SetupError("Version manifest must specify a positive tool count and package version")
    return manifest


def _sha(value: object, field: str) -> str:
    """Require a full lowercase hexadecimal Git object identifier."""
    text = str(value)
    if len(text) != 40 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{field} must be a full lowercase 40-character SHA")
    return text
