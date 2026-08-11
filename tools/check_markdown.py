#!/usr/bin/env python3
"""Check public Markdown structure and repository-local links.

Global context: this is a deliberately dependency-free release check.  It
focuses on errors that break GitHub rendering or make the setup guide hard to
navigate while leaving prose style decisions to reviewers.

Reference: https://github.github.com/gfm/
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import unquote


IGNORED_DIRECTORIES = {".git", ".local", ".venv", "__pycache__", ".pytest_cache"}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the tree to scan and optional README release contract."""

    parser = argparse.ArgumentParser(description="Check Markdown files for release-blocking issues.")
    parser.add_argument("root", nargs="?", default=Path("."), type=Path)
    parser.add_argument("--require-readme-contract", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def markdown_files(root: Path) -> Iterable[Path]:
    """Yield public Markdown files while excluding local environments and caches."""

    for path in sorted(root.rglob("*.md")):
        if not any(part in IGNORED_DIRECTORIES for part in path.parts):
            yield path


def check_local_link(path: Path, target: str) -> str | None:
    """Return an error when a relative Markdown link points to no public file."""

    target = target.strip().strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    # GitHub permits an optional title after the URL; only the URL is a path.
    target = re.split(r'\s+["\']', target, maxsplit=1)[0]
    target = unquote(target.split("#", 1)[0])
    if not target:
        return None
    destination = (path.parent / target).resolve()
    return None if destination.exists() else f"broken local link: {target}"


def check_markdown(path: Path) -> list[str]:
    """Check one document for balanced fences, heading order, and valid links."""

    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if not text.strip():
        errors.append("document is empty")
        return errors
    if "\r" in text:
        errors.append("use LF rather than CRLF line endings")
    in_fence = False
    fence_character = ""
    previous_heading = 0
    h1_count = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        trailing_spaces = len(line) - len(line.rstrip(" "))
        if line.endswith("\t") or trailing_spaces not in (0, 2):
            errors.append(f"line {line_number}: unsupported trailing whitespace")
        fence = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence:
            character = fence.group(1)[0]
            if not in_fence:
                in_fence = True
                fence_character = character
            elif character == fence_character:
                in_fence = False
                fence_character = ""
            continue
        if in_fence:
            continue
        heading = re.match(r"^(#{1,6})\s+\S", line)
        if heading:
            level = len(heading.group(1))
            h1_count += int(level == 1)
            if previous_heading and level > previous_heading + 1:
                errors.append(
                    f"line {line_number}: heading jumps from H{previous_heading} to H{level}",
                )
            previous_heading = level
    if in_fence:
        errors.append("unclosed fenced code block")
    if h1_count != 1:
        errors.append(f"expected exactly one H1 heading, found {h1_count}")

    for match in re.finditer(r"!?\[([^\]]*)\]\(([^)]+)\)", text):
        if match.group(0).startswith("![") and not match.group(1).strip():
            errors.append("image has empty alternative text")
        if link_error := check_local_link(path, match.group(2)):
            line_number = text.count("\n", 0, match.start()) + 1
            errors.append(f"line {line_number}: {link_error}")
    return errors


def check_readme_contract(root: Path) -> list[str]:
    """Require the complete setup path promised by the public README."""

    readme = root / "README.md"
    if not readme.is_file():
        return ["README.md is missing"]
    text = readme.read_text(encoding="utf-8").casefold()
    requirements = {
        "requirements": "## requirements",
        "safety warning": "[!caution]",
        "installation": "## 7. install ableton live mcp",
        "Ableton activation": "## 9. activate the remote script in ableton live",
        "Computer Use setup": "## 10. enable computer use in codex desktop",
        "post-Live validation": "## 12. validate the live connection",
        "update instructions": ".\\manage.ps1 update",
        "rollback instructions": ".\\manage.ps1 rollback",
        "Mermaid connection graph": "```mermaid",
    }
    return [f"README.md is missing {label}" for label, token in requirements.items() if token not in text]


def main(argv: Sequence[str] | None = None) -> int:
    """Scan every public Markdown file and return nonzero on any defect."""

    args = parse_args(argv)
    root = args.root.resolve()
    findings: dict[str, list[str]] = {}
    for path in markdown_files(root):
        errors = check_markdown(path)
        if errors:
            findings[str(path.relative_to(root))] = errors
    if args.require_readme_contract:
        readme_errors = check_readme_contract(root)
        if readme_errors:
            findings.setdefault("README.md", []).extend(readme_errors)
    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, indent=2, sort_keys=True))
    elif findings:
        for path, errors in findings.items():
            for error in errors:
                print(f"{path}: {error}")
    else:
        print(f"Markdown checks passed for {sum(1 for _ in markdown_files(root))} file(s).")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
