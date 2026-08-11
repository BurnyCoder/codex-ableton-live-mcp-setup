"""Global context: acquire and verify the exact reviewed upstream PR checkout; never use PyPI."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from .configuration import Settings
from .errors import SetupError
from .manifest import VersionManifest
from .process import Runner


FAILED_NODE_PATTERN = re.compile(r"^FAILED\s+(\S+?)(?:\s+-.*)?$", re.MULTILINE)


def acquire_checkout(settings: Settings, manifest: VersionManifest, runner: Runner, require_existing: bool = False) -> dict[str, Any]:
    """Clone/fetch the reviewed PR ref, verify SHA/parent/tree, and detach at the exact commit."""
    checkout = settings.checkout
    if checkout.exists() and not (checkout / ".git").is_dir():
        raise SetupError(f"Checkout path exists but is not a Git repository: {checkout}")
    if not checkout.exists():
        if require_existing:
            raise SetupError(f"Update requires an existing managed checkout at {checkout}")
        runner.run(["git", "clone", "--no-checkout", manifest.repository, checkout], mutating=True)
        if runner.dry_run:
            return {"planned": True, "checkout": str(checkout), "pin": manifest.pr_commit}

    origin = runner.run(["git", "remote", "get-url", "origin"], cwd=checkout).stdout.strip()
    if normalize_repository_url(origin) != normalize_repository_url(manifest.repository):
        raise SetupError(f"Refusing checkout with unexpected origin {origin!r}; expected {manifest.repository!r}")
    dirty = runner.run(["git", "status", "--porcelain"], cwd=checkout).stdout.strip()
    if dirty:
        raise SetupError(f"Upstream checkout has local changes; preserve or remove them before setup:\n{dirty}")

    # GitHub documents fetching pull-request refs under refs/pull/<number>/head.
    remote_ref = f"refs/remotes/origin/reviewed-pr-{manifest.pr_number}"
    runner.run(["git", "fetch", "--force", "origin", manifest.base_commit], cwd=checkout, mutating=True)
    runner.run(["git", "fetch", "--force", "origin", f"{manifest.pr_ref}:{remote_ref}"], cwd=checkout, mutating=True)
    if runner.dry_run:
        return {"planned": True, "checkout": str(checkout), "pin": manifest.pr_commit}
    fetched_commit = git_value(runner, checkout, ["rev-parse", f"{remote_ref}^{{commit}}"])
    verify_revision_metadata(
        commit=fetched_commit,
        parents=git_value(runner, checkout, ["show", "-s", "--format=%P", fetched_commit]).split(),
        tree=git_value(runner, checkout, ["show", "-s", "--format=%T", fetched_commit]),
        manifest=manifest,
    )
    runner.run(["git", "cat-file", "-e", f"{manifest.base_commit}^{{commit}}"], cwd=checkout)
    runner.run(["git", "checkout", "--detach", manifest.pr_commit], cwd=checkout, mutating=True)
    head = git_value(runner, checkout, ["rev-parse", "HEAD"])
    if head != manifest.pr_commit:
        raise SetupError(f"Checkout resolved to {head}, not reviewed commit {manifest.pr_commit}")
    package_version = read_upstream_package_version(checkout / "pyproject.toml")
    if package_version != manifest.package_version:
        raise SetupError(f"Upstream package version {package_version!r} does not match manifest {manifest.package_version!r}")
    return {
        "planned": False,
        "checkout": str(checkout),
        "origin": origin,
        "commit": head,
        "parent": manifest.pr_parent,
        "tree": manifest.pr_tree,
        "package_version": package_version,
    }


def verify_revision_metadata(*, commit: str, parents: list[str], tree: str, manifest: VersionManifest) -> None:
    """Fail closed unless the fetched PR has the reviewed SHA, single parent, and tree."""
    mismatches: list[str] = []
    if commit != manifest.pr_commit:
        mismatches.append(f"commit {commit} != {manifest.pr_commit}")
    if parents != [manifest.pr_parent]:
        mismatches.append(f"parents {parents!r} != {[manifest.pr_parent]!r}")
    if tree != manifest.pr_tree:
        mismatches.append(f"tree {tree} != {manifest.pr_tree}")
    if mismatches:
        raise SetupError("Fetched PR ref failed reviewed identity checks: " + "; ".join(mismatches))


def normalize_repository_url(value: str) -> str:
    """Normalize common GitHub HTTPS/SSH spelling without weakening owner/repository identity."""
    normalized = value.strip().replace("\\", "/")
    if normalized.startswith("git@github.com:"):
        normalized = "https://github.com/" + normalized.removeprefix("git@github.com:")
    if normalized.startswith("ssh://git@github.com/"):
        normalized = "https://github.com/" + normalized.removeprefix("ssh://git@github.com/")
    return normalized.removesuffix("/").removesuffix(".git").lower()


def git_value(runner: Runner, checkout: Path, args: list[str]) -> str:
    """Run a read-only Git query and require a non-empty answer."""
    value = runner.run(["git", *args], cwd=checkout).stdout.strip()
    if not value:
        raise SetupError(f"Git query returned no value: {' '.join(args)}")
    return value


def read_upstream_package_version(path: Path) -> str:
    """Read the checked-out project metadata with Python's standard TOML parser."""
    try:
        with path.open("rb") as handle:
            return str(tomllib.load(handle)["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise SetupError(f"Cannot read upstream package version from {path}: {exc}") from exc


def create_environment(settings: Settings, runner: Runner) -> dict[str, Any]:
    """Create a local Python 3.14 environment and install only the checkout's editable dev extra."""
    runner.run(
        ["uv", "venv", "--allow-existing", "--python", settings.python_version, settings.checkout / ".venv"],
        cwd=settings.checkout,
        mutating=True,
    )
    editable_spec = f"{settings.checkout}[dev]"
    runner.run(
        ["uv", "pip", "install", "--python", settings.venv_python, "--editable", editable_spec],
        cwd=settings.checkout,
        mutating=True,
    )
    if not runner.dry_run:
        for required in (settings.venv_python, settings.server_executable, settings.validator_executable, settings.installer_executable):
            if not required.is_file():
                raise SetupError(f"Editable installation did not create required executable: {required}")
    return {"python": str(settings.venv_python), "editable_source": str(settings.checkout), "planned": runner.dry_run}


def run_upstream_tests(settings: Settings, manifest: VersionManifest, runner: Runner) -> dict[str, Any]:
    """Accept a full pass or exactly PR #14's two Windows-only assertion failures, then rerun the rest."""
    command = [settings.venv_python, "-m", "pytest", "-q"]
    full = runner.run(command, cwd=settings.checkout, check=False, timeout=900)
    failures = [] if full.returncode == 0 else extract_failed_nodeids(full.stdout + "\n" + full.stderr)
    accepted = set(manifest.accepted_windows_failures)
    if full.returncode != 0 and set(failures) != accepted:
        raise SetupError(
            "Upstream suite failed outside the two reviewed PR #14 path assertions: "
            + repr(failures)
        )
    deselections = [argument for node_id in manifest.accepted_windows_failures for argument in ("--deselect", node_id)]
    remaining = runner.run([*command, *deselections], cwd=settings.checkout, check=False, timeout=900)
    if remaining.returncode != 0:
        raise SetupError("Upstream suite still fails after deselecting only the two reviewed Windows assertions")
    return {
        "ok": True,
        "full_suite_returncode": full.returncode,
        "accepted_failures": failures,
        "remaining_suite_returncode": remaining.returncode,
    }


def extract_failed_nodeids(output: str) -> list[str]:
    """Extract stable pytest node IDs from the failure summary without matching progress output."""
    without_ansi = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output)
    return sorted(set(FAILED_NODE_PATTERN.findall(without_ansi)))


def checkout_status(settings: Settings, manifest: VersionManifest, runner: Runner) -> dict[str, Any]:
    """Inspect an existing checkout without fetching or mutating it."""
    if not (settings.checkout / ".git").is_dir():
        return {"present": False, "path": str(settings.checkout)}
    try:
        origin = runner.run(["git", "remote", "get-url", "origin"], cwd=settings.checkout).stdout.strip()
        head = runner.run(["git", "rev-parse", "HEAD"], cwd=settings.checkout).stdout.strip()
        tree = runner.run(["git", "show", "-s", "--format=%T", "HEAD"], cwd=settings.checkout).stdout.strip()
        dirty = bool(runner.run(["git", "status", "--porcelain"], cwd=settings.checkout).stdout.strip())
    except SetupError as exc:
        return {"present": True, "path": str(settings.checkout), "ok": False, "error": str(exc)}
    return {
        "present": True,
        "path": str(settings.checkout),
        "origin": origin,
        "origin_current": normalize_repository_url(origin) == normalize_repository_url(manifest.repository),
        "head": head,
        "commit_current": head == manifest.pr_commit,
        "tree": tree,
        "tree_current": tree == manifest.pr_tree,
        "dirty": dirty,
    }
