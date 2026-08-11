"""Global context: prove exact Git identity checks and the narrow PR #14 test exception."""

from pathlib import Path

import pytest

from codex_ableton_live_mcp_setup.errors import SetupError
from codex_ableton_live_mcp_setup.configuration import Settings
from codex_ableton_live_mcp_setup.manifest import load_manifest
from codex_ableton_live_mcp_setup.process import CommandResult
from codex_ableton_live_mcp_setup.upstream import create_environment, extract_failed_nodeids, normalize_repository_url, read_upstream_package_version, run_upstream_tests, verify_revision_metadata


def test_manifest_contains_reviewed_exact_identity_and_failures() -> None:
    manifest = load_manifest()
    assert manifest.pr_commit == "a93d223440b275feda2fb08cdf814238c1270e00"
    assert manifest.pr_parent == manifest.base_commit
    assert manifest.pr_tree == "2d97d0b270f4d9058e2fd624af7e3b769e3493bd"
    assert manifest.accepted_windows_failures == (
        "tests/test_agent_audio_tap_build.py::test_agent_audio_tap_builds_amxd_container",
        "tests/test_agent_m4l_build.py::test_agent_m4l_host_patch_contains_runtime_and_role_io",
    )


def test_revision_metadata_accepts_only_exact_values() -> None:
    manifest = load_manifest()
    verify_revision_metadata(commit=manifest.pr_commit, parents=[manifest.pr_parent], tree=manifest.pr_tree, manifest=manifest)
    with pytest.raises(SetupError, match="commit"):
        verify_revision_metadata(commit="0" * 40, parents=[manifest.pr_parent], tree=manifest.pr_tree, manifest=manifest)
    with pytest.raises(SetupError, match="parents"):
        verify_revision_metadata(commit=manifest.pr_commit, parents=[], tree=manifest.pr_tree, manifest=manifest)
    with pytest.raises(SetupError, match="tree"):
        verify_revision_metadata(commit=manifest.pr_commit, parents=[manifest.pr_parent], tree="0" * 40, manifest=manifest)


def test_repository_normalization_does_not_change_identity() -> None:
    expected = "https://github.com/bschoepke/ableton-live-mcp"
    assert normalize_repository_url("git@github.com:bschoepke/ableton-live-mcp.git") == expected
    assert normalize_repository_url("https://github.com/bschoepke/ableton-live-mcp.git") == expected
    assert normalize_repository_url("https://github.com/other/ableton-live-mcp.git") != expected


def test_extract_failed_nodeids_ignores_non_summary_text() -> None:
    output = "FAILED tests/a.py::test_one - AssertionError\n\x1b[31mFAILED tests/b.py::test_two\x1b[0m\n2 failed"
    assert extract_failed_nodeids(output) == ["tests/a.py::test_one", "tests/b.py::test_two"]


def test_read_upstream_package_version(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname="x"\nversion="0.1.1"\n', encoding="utf-8")
    assert read_upstream_package_version(pyproject) == "0.1.1"


def test_full_pass_still_runs_exact_deselected_suite(tmp_path: Path) -> None:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library")

    class FakeRunner:
        def __init__(self):
            self.calls = []
        def run(self, args, **kwargs):
            self.calls.append(list(map(str, args)))
            return CommandResult(tuple(map(str, args)), 0, "all passed\n", "")

    runner = FakeRunner()
    result = run_upstream_tests(settings, load_manifest(), runner)
    assert result["full_suite_returncode"] == 0 and result["remaining_suite_returncode"] == 0
    assert len(runner.calls) == 2
    for node in load_manifest().accepted_windows_failures:
        assert node in runner.calls[1]


def test_environment_creation_is_repeatable_with_allow_existing(tmp_path: Path) -> None:
    settings = Settings(checkout=tmp_path / "checkout", user_library=tmp_path / "library")

    class FakeRunner:
        dry_run = True
        def __init__(self):
            self.calls = []
        def run(self, args, **kwargs):
            self.calls.append(list(map(str, args)))
            return CommandResult(tuple(map(str, args)), 0, "", "", planned=True)

    runner = FakeRunner()
    create_environment(settings, runner)
    create_environment(settings, runner)
    venv_calls = [call for call in runner.calls if call[:2] == ["uv", "venv"]]
    assert len(venv_calls) == 2 and all("--allow-existing" in call for call in venv_calls)
