#!/usr/bin/env python3
"""Verify the generated public report PDF before publication.

Global context: text extraction catches empty, corrupt, clipped-to-nothing, and
metadata-leaking builds.  Optional Poppler rendering gives maintainers a stable
set of PNGs for the visual inspection required before a release.

Primary references:
- pypdf text extraction: https://pypdf.readthedocs.io/en/stable/user/extract-text.html
- Poppler pdftoppm: https://manpages.debian.org/pdftoppm
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from pypdf import PdfReader


@dataclass(frozen=True)
class VerificationResult:
    """Describe the release-relevant facts confirmed for one PDF."""

    path: str
    pages: int
    extracted_characters: int
    title: str
    author: str
    rendered_pages: int
    renderer: str | None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse structural, source-correspondence, and optional rendering checks."""

    parser = argparse.ArgumentParser(description="Verify a generated public report PDF.")
    parser.add_argument("pdf", type=Path, help="PDF artifact to verify.")
    parser.add_argument("--source", type=Path, help="Canonical Markdown used to build the PDF.")
    parser.add_argument("--min-pages", type=int, default=1, help="Minimum accepted page count.")
    parser.add_argument(
        "--require-text",
        action="append",
        default=[],
        help="Text fragment that must appear after extraction; may be repeated.",
    )
    parser.add_argument("--render-dir", type=Path, help="Optional Poppler PNG output directory.")
    parser.add_argument(
        "--require-renderer",
        action="store_true",
        help="Fail rather than skip rendering when pdftoppm is unavailable.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    return parser.parse_args(argv)


def normalize_for_comparison(value: str) -> str:
    """Collapse extracted PDF whitespace and normalize common Markdown typography."""

    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
    normalized = "".join(replacements.get(character, character) for character in value)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def source_headings(path: Path) -> list[str]:
    """Extract public H1/H2 headings that should survive PDF rendering."""

    if not path.is_file():
        raise FileNotFoundError(f"Markdown source does not exist: {path}")
    markdown = path.read_text(encoding="utf-8")
    return [
        match.group(2).rstrip("#").strip()
        for match in re.finditer(r"^(#{1,2})\s+(.+?)\s*$", markdown, flags=re.MULTILINE)
    ]


def resolve_windows_shim(path: str, depth: int = 0) -> str:
    """Resolve the simple relative .cmd shims used by bundled Poppler runtimes."""

    shim = Path(path)
    if os.name != "nt" or shim.suffix.casefold() not in {".cmd", ".bat"} or depth >= 4:
        return str(shim)
    try:
        source = shim.read_text(encoding="utf-8")
    except OSError:
        return str(shim)
    match = re.search(r'"%(?:~dp0|SCRIPT_DIR)%?([^"\r\n]+\.(?:exe|cmd|bat))"', source, re.IGNORECASE)
    if not match:
        return str(shim)
    target = (shim.parent / match.group(1)).resolve()
    return resolve_windows_shim(str(target), depth + 1) if target.is_file() else str(shim)


def render_with_poppler(pdf: Path, render_dir: Path, required: bool) -> tuple[int, str | None]:
    """Render every page with pdftoppm when available and validate PNG outputs."""

    renderer = shutil.which("pdftoppm")
    if not renderer:
        if required:
            raise RuntimeError("pdftoppm is required but was not found on PATH")
        print("Poppler not found; structural PDF checks passed and rendering was skipped.")
        return 0, None
    render_dir.mkdir(parents=True, exist_ok=True)
    prefix = render_dir / "page"
    renderer = resolve_windows_shim(renderer)
    command = [renderer, "-png", "-r", "144", str(pdf), str(prefix)]
    # Fall back to cmd.exe only when an unfamiliar Windows shim cannot be resolved.
    use_command_shell = os.name == "nt" and renderer.casefold().endswith((".cmd", ".bat"))
    invocation: str | list[str] = subprocess.list2cmdline(command) if use_command_shell else command
    completed = subprocess.run(
        invocation,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=use_command_shell,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "pdftoppm failed with exit code "
            f"{completed.returncode}:\n{completed.stdout}\n{completed.stderr}",
        )
    images = sorted(render_dir.glob("page-*.png"))
    if not images:
        raise RuntimeError("pdftoppm succeeded but produced no page images")
    undersized = [image for image in images if image.stat().st_size < 1_024]
    if undersized:
        raise RuntimeError(f"Rendered page images are unexpectedly small: {undersized}")
    return len(images), renderer


def verify_pdf(
    pdf: Path,
    source: Path | None = None,
    min_pages: int = 1,
    required_text: Sequence[str] = (),
    render_dir: Path | None = None,
    require_renderer: bool = False,
) -> VerificationResult:
    """Require a readable, nonblank, sanitized PDF that corresponds to its source."""

    if not pdf.is_file():
        raise FileNotFoundError(f"PDF does not exist: {pdf}")
    if pdf.stat().st_size < 1_024:
        raise ValueError(f"PDF is unexpectedly small ({pdf.stat().st_size} bytes): {pdf}")
    reader = PdfReader(str(pdf), strict=True)
    if reader.is_encrypted:
        raise ValueError("Public report PDF must not be encrypted")
    if len(reader.pages) < min_pages:
        raise ValueError(f"Expected at least {min_pages} pages, found {len(reader.pages)}")

    page_texts: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if width <= 0 or height <= 0:
            raise ValueError(f"Page {page_number} has invalid dimensions: {width} x {height}")
        extracted = page.extract_text() or ""
        if len(normalize_for_comparison(extracted)) < 20:
            raise ValueError(f"Page {page_number} contains too little extractable text")
        page_texts.append(extracted)

    combined_text = "\n".join(page_texts)
    normalized_text = normalize_for_comparison(combined_text)
    metadata = reader.metadata or {}
    title = str(metadata.get("/Title") or "").strip()
    author = str(metadata.get("/Author") or "").strip()
    if not title:
        raise ValueError("PDF /Title metadata is missing")
    if not author:
        raise ValueError("PDF /Author metadata is missing")

    expected_fragments = list(required_text)
    if source is not None:
        headings = source_headings(source)
        if not headings:
            raise ValueError(f"Markdown source has no H1/H2 headings: {source}")
        expected_fragments.extend(headings)
    missing = [
        fragment
        for fragment in expected_fragments
        if normalize_for_comparison(fragment) not in normalized_text
    ]
    if missing:
        raise ValueError(f"Expected source text was not found in PDF: {missing}")

    forbidden_glyphs = {"\ufffd": "replacement character", "\u25a0": "black square"}
    present_glyphs = [label for glyph, label in forbidden_glyphs.items() if glyph in combined_text]
    if present_glyphs:
        raise ValueError(f"PDF extraction contains unsupported glyph artifacts: {present_glyphs}")
    private_home_pattern = r"(?i)(?:[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+|/User" + r"s/[^/\s]+)"
    if re.search(private_home_pattern, combined_text):
        raise ValueError("PDF contains a machine-specific home-directory path")

    rendered_pages = 0
    renderer = None
    if render_dir is not None:
        rendered_pages, renderer = render_with_poppler(pdf, render_dir, require_renderer)
        if rendered_pages and rendered_pages != len(reader.pages):
            raise ValueError(
                f"Renderer produced {rendered_pages} images for {len(reader.pages)} PDF pages",
            )
    return VerificationResult(
        path=str(pdf.resolve()),
        pages=len(reader.pages),
        extracted_characters=len(combined_text),
        title=title,
        author=author,
        rendered_pages=rendered_pages,
        renderer=renderer,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run verification and emit a concise human or machine-readable result."""

    args = parse_args(argv)
    result = verify_pdf(
        args.pdf.resolve(),
        source=args.source.resolve() if args.source else None,
        min_pages=args.min_pages,
        required_text=args.require_text,
        render_dir=args.render_dir.resolve() if args.render_dir else None,
        require_renderer=args.require_renderer,
    )
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"PDF verified: {result.pages} page(s), "
            f"{result.extracted_characters} extracted characters, title={result.title!r}",
        )
        if result.rendered_pages:
            print(f"Poppler rendered {result.rendered_pages} page(s) with {result.renderer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
