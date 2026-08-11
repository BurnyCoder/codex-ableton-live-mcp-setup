#!/usr/bin/env python3
"""Build the public experiment report PDF from sanitized Markdown.

Global context: the companion repository publishes Markdown as the canonical
experiment record and derives a deterministic, portable PDF release artifact
from it.  This intentionally small renderer supports the report constructs used
by the repository without executing Markdown, HTML, or Mermaid content.

Primary references:
- ReportLab Platypus user guide: https://docs.reportlab.com/reportlab/userguide/ch5_platypus/
- Python argparse: https://docs.python.org/3/library/argparse.html
"""

from __future__ import annotations

import argparse
import html
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)


# A restrained palette keeps technical content legible in print and on screen.
INK = colors.HexColor("#16202A")
MUTED = colors.HexColor("#52606D")
ACCENT = colors.HexColor("#276EF1")
PANEL = colors.HexColor("#F4F7FA")
RULE = colors.HexColor("#D7DEE7")


@dataclass(frozen=True)
class ReportMetadata:
    """Carry PDF metadata derived from the public Markdown source."""

    title: str
    author: str = "BurnyCoder"
    subject: str = "Reproducible Windows setup for Ableton Live MCP and Codex"


class ReportDocTemplate(SimpleDocTemplate):
    """Draw margin furniture after flowables so split content cannot cover it."""

    def __init__(self, *args, page_callback, **kwargs) -> None:
        """Store the trusted page callback before initializing Platypus state."""

        self._page_callback = page_callback
        super().__init__(*args, **kwargs)

    def afterPage(self) -> None:
        """Paint headers and footers last, outside any flowable drawing state."""

        self._page_callback(self.canv, self)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse an explicit input/output contract suitable for local use and CI."""

    parser = argparse.ArgumentParser(
        description="Render a sanitized Markdown experiment report as PDF.",
    )
    parser.add_argument("--input", required=True, type=Path, help="Canonical Markdown report.")
    parser.add_argument("--output", required=True, type=Path, help="Destination PDF path.")
    parser.add_argument("--author", default="BurnyCoder", help="Public PDF author metadata.")
    return parser.parse_args(argv)


def normalize_text(value: str) -> str:
    """Normalize typography to glyphs supported by the built-in PDF fonts."""

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
        "\u2022": "-",
        "\u2026": "...",
        "\u2192": "->",
        "\u2190": "<-",
        "\u2264": "<=",
        "\u2265": ">=",
        "\u2713": "PASS",
        "\u2714": "PASS",
        "\u2717": "FAIL",
        "\u2718": "FAIL",
        "\u00a0": " ",
    }
    normalized = "".join(replacements.get(character, character) for character in value)
    # Helvetica supports Windows-1252; replace only unsupported technical glyphs.
    return normalized.encode("cp1252", errors="replace").decode("cp1252")


def inline_markup(value: str) -> str:
    """Convert safe, small inline Markdown tokens to ReportLab paragraph XML."""

    normalized = normalize_text(value)
    token_pattern = re.compile(r"(\[[^\]]+\]\([^)]+\)|`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)")
    rendered: list[str] = []
    position = 0
    for match in token_pattern.finditer(normalized):
        rendered.append(html.escape(normalized[position : match.start()]))
        token = match.group(0)
        if token.startswith("["):
            label, url = token[1:].split("](", 1)
            url = url[:-1]
            if url.startswith(("http://", "https://")):
                rendered.append(
                    f'<a href="{html.escape(url, quote=True)}" color="{ACCENT.hexval()}">'
                    f"{html.escape(label)}</a>",
                )
            else:
                rendered.append(html.escape(label))
        elif token.startswith("`"):
            rendered.append(f'<font name="Courier">{html.escape(token[1:-1])}</font>')
        elif token.startswith("**"):
            rendered.append(f"<b>{html.escape(token[2:-2])}</b>")
        else:
            rendered.append(f"<i>{html.escape(token[1:-1])}</i>")
        position = match.end()
    rendered.append(html.escape(normalized[position:]))
    return "".join(rendered)


def report_styles() -> dict[str, ParagraphStyle]:
    """Return the complete visual system used by the generated report."""

    sample = getSampleStyleSheet()
    body = ParagraphStyle(
        "ReportBody",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=INK,
        spaceAfter=7,
        allowWidows=0,
        allowOrphans=0,
    )
    return {
        "body": body,
        "title": ParagraphStyle(
            "ReportTitle",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=16,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "ReportHeading2",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=INK,
            spaceBefore=12,
            spaceAfter=7,
            keepWithNext=False,
        ),
        "h3": ParagraphStyle(
            "ReportHeading3",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=ACCENT,
            spaceBefore=9,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h4": ParagraphStyle(
            "ReportHeading4",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=MUTED,
            spaceBefore=7,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "bullet": ParagraphStyle(
            "ReportBullet",
            parent=body,
            leftIndent=16,
            firstLineIndent=-9,
            bulletIndent=5,
            spaceAfter=4,
        ),
        "quote": ParagraphStyle(
            "ReportQuote",
            parent=body,
            leftIndent=14,
            rightIndent=8,
            borderColor=ACCENT,
            borderWidth=0,
            borderPadding=(2, 8, 2, 8),
            backColor=PANEL,
            textColor=MUTED,
        ),
        "code": ParagraphStyle(
            "ReportCode",
            parent=body,
            fontName="Courier",
            fontSize=7.4,
            leading=10,
            leftIndent=7,
            rightIndent=7,
            borderColor=RULE,
            borderWidth=0.5,
            borderPadding=7,
            backColor=PANEL,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "ReportCaption",
            parent=body,
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=9,
        ),
        "table_header": ParagraphStyle(
            "ReportTableHeader",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=10.5,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "table_cell": ParagraphStyle(
            "ReportTableCell",
            parent=body,
            fontSize=8.2,
            leading=10.5,
            spaceAfter=0,
        ),
    }


def markdown_table_cells(line: str) -> list[str]:
    """Split a pipe table row while tolerating optional outer pipes."""

    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    """Recognize the required Markdown separator row beneath table headers."""

    cells = markdown_table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def wrap_code(code: str, width: int = 92) -> str:
    """Wrap exceptionally long code lines so paths cannot leave the page frame."""

    output: list[str] = []
    for original in normalize_text(code).splitlines() or [""]:
        if len(original) <= width:
            output.append(original)
            continue
        indent = re.match(r"\s*", original).group(0)
        output.extend(
            textwrap.wrap(
                original,
                width=width,
                subsequent_indent=indent + "  ",
                break_long_words=True,
                break_on_hyphens=False,
            ),
        )
    return "\n".join(output)


def make_table(
    rows: Sequence[Sequence[str]],
    styles: dict[str, ParagraphStyle],
    available_width: float,
) -> Table:
    """Convert Markdown table cells into a repeatable, page-splittable table."""

    column_count = max(len(row) for row in rows)
    normalized_rows = [list(row) + [""] * (column_count - len(row)) for row in rows]
    rendered_rows = []
    for row_index, row in enumerate(normalized_rows):
        style = styles["table_header"] if row_index == 0 else styles["table_cell"]
        rendered_rows.append([Paragraph(inline_markup(cell), style) for cell in row])
    # Equal widths are predictable and avoid data-dependent overflow in CI output.
    table = Table(
        rendered_rows,
        colWidths=[available_width / column_count] * column_count,
        repeatRows=1,
        hAlign="LEFT",
        splitByRow=True,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PANEL]),
                ("GRID", (0, 0), (-1, -1), 0.45, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ],
        ),
    )
    return table


def repository_root(source: Path) -> Path:
    """Find the public repository boundary used to constrain local image assets."""

    for candidate in (source.parent, *source.parents):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").is_file():
            return candidate.resolve()
    return source.parent.resolve()


def append_image(
    story: list[object],
    target: str,
    alt_text: str,
    source_dir: Path,
    asset_root: Path,
    available_width: float,
    styles: dict[str, ParagraphStyle],
) -> None:
    """Embed one repository-local image without fetching or leaking external files."""

    if target.startswith(("http://", "https://")):
        story.append(Paragraph(f"Image: {inline_markup(alt_text)} (external image not embedded)", styles["quote"]))
        return
    image_path = (source_dir / target.split("#", 1)[0]).resolve()
    try:
        image_path.relative_to(asset_root)
    except ValueError as exc:
        raise ValueError(f"Image path leaves the public repository: {target}") from exc
    if not image_path.is_file():
        raise FileNotFoundError(f"Markdown image does not exist: {image_path}")
    width, height = ImageReader(str(image_path)).getSize()
    max_height = 4.6 * inch
    scale = min(available_width / float(width), max_height / float(height), 1.0)
    illustration = Image(str(image_path), width=width * scale, height=height * scale)
    illustration.hAlign = "CENTER"
    story.append(Spacer(1, 5))
    story.append(illustration)
    story.append(Paragraph(f"Figure: {inline_markup(alt_text)}", styles["caption"]))


def markdown_story(
    markdown: str,
    styles: dict[str, ParagraphStyle],
    available_width: float,
    source_dir: Path,
    asset_root: Path,
) -> list[object]:
    """Parse the repository's safe Markdown subset into Platypus flowables."""

    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    story: list[object] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        """Emit the currently buffered prose as one naturally wrapped paragraph."""

        if paragraph_lines:
            text = " ".join(part.strip() for part in paragraph_lines).strip()
            if text:
                story.append(Paragraph(inline_markup(text), styles["body"]))
            paragraph_lines.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        image_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image_match:
            flush_paragraph()
            append_image(
                story,
                image_match.group(2).strip().strip("<>"),
                image_match.group(1).strip() or "Untitled image",
                source_dir,
                asset_root,
                available_width,
                styles,
            )
        elif stripped.startswith("<!--"):
            flush_paragraph()
            while index < len(lines) and "-->" not in lines[index]:
                index += 1
        elif stripped.startswith("```"):
            flush_paragraph()
            language = stripped[3:].strip()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            label = f"[{language}]\n" if language else ""
            story.append(XPreformatted(wrap_code(label + "\n".join(code_lines)), styles["code"]))
        elif stripped.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            flush_paragraph()
            rows = [markdown_table_cells(line)]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(markdown_table_cells(lines[index]))
                index += 1
            story.append(make_table(rows, styles, available_width))
            story.append(Spacer(1, 8))
            continue
        elif match := re.match(r"^(#{1,6})\s+(.+?)\s*$", line):
            flush_paragraph()
            level = len(match.group(1))
            heading = match.group(2).rstrip("#").strip()
            style_name = "title" if level == 1 else "h2" if level == 2 else "h3" if level == 3 else "h4"
            if level == 2:
                story.append(CondPageBreak(0.9 * inch))
            next_content = index + 1
            while next_content < len(lines) and not lines[next_content].strip():
                next_content += 1
            if level >= 3 and next_content < len(lines) and lines[next_content].strip().startswith("!["):
                # Reserve the heading, image, and caption as one visual section.
                story.append(CondPageBreak(5.2 * inch))
            story.append(Paragraph(inline_markup(heading), styles[style_name]))
        elif re.fullmatch(r"-{3,}", stripped):
            flush_paragraph()
            story.append(HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=5, spaceAfter=8))
        elif stripped == "<!-- pagebreak -->":
            flush_paragraph()
            story.append(PageBreak())
        elif match := re.match(r"^\s*[-*+]\s+(.+)$", line):
            flush_paragraph()
            story.append(Paragraph(inline_markup(match.group(1)), styles["bullet"], bulletText="-"))
        elif match := re.match(r"^\s*(\d+)[.)]\s+(.+)$", line):
            flush_paragraph()
            story.append(Paragraph(inline_markup(match.group(2)), styles["bullet"], bulletText=f"{match.group(1)}."))
        elif stripped.startswith(">"):
            flush_paragraph()
            story.append(Paragraph(inline_markup(stripped.lstrip("> ")), styles["quote"]))
        elif not stripped:
            flush_paragraph()
        else:
            paragraph_lines.append(stripped)
        index += 1
    flush_paragraph()
    return story


def infer_title(markdown: str, fallback: str) -> str:
    """Use the first H1 as public metadata, falling back to the file stem."""

    match = re.search(r"^#\s+(.+?)\s*$", markdown, flags=re.MULTILINE)
    return normalize_text(match.group(1).rstrip("#").strip()) if match else fallback


def page_decorator(metadata: ReportMetadata):
    """Create the callback that paints stable headers, rules, and page numbers."""

    def decorate(canvas, document) -> None:
        """Paint one page without altering the Platypus flowable frame."""

        canvas.saveState()
        # afterPage may inherit a flowable translation; return to page coordinates.
        canvas.resetTransforms()
        canvas.setTitle(metadata.title)
        canvas.setAuthor(metadata.author)
        canvas.setSubject(metadata.subject)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        header = metadata.title
        max_width = document.pagesize[0] - document.leftMargin - document.rightMargin
        while stringWidth(header, "Helvetica", 7.5) > max_width and len(header) > 4:
            header = header[:-4].rstrip() + "..."
        canvas.drawString(document.leftMargin, document.pagesize[1] - 0.42 * inch, header)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(
            document.leftMargin,
            document.pagesize[1] - 0.49 * inch,
            document.pagesize[0] - document.rightMargin,
            document.pagesize[1] - 0.49 * inch,
        )
        canvas.drawCentredString(document.pagesize[0] / 2, 0.34 * inch, f"Page {document.page}")
        canvas.restoreState()

    return decorate


def build_pdf(input_path: Path, output_path: Path, author: str = "BurnyCoder") -> ReportMetadata:
    """Render one sanitized Markdown source to a deterministic PDF artifact."""

    if not input_path.is_file():
        raise FileNotFoundError(f"Markdown input does not exist: {input_path}")
    markdown = input_path.read_text(encoding="utf-8")
    if not markdown.strip():
        raise ValueError(f"Markdown input is empty: {input_path}")
    metadata = ReportMetadata(title=infer_title(markdown, input_path.stem), author=author)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    decorate = page_decorator(metadata)
    document = ReportDocTemplate(
        str(output_path),
        page_callback=decorate,
        pagesize=LETTER,
        leftMargin=0.68 * inch,
        rightMargin=0.68 * inch,
        topMargin=0.72 * inch,
        bottomMargin=0.75 * inch,
        title=metadata.title,
        author=metadata.author,
        subject=metadata.subject,
        invariant=1,
        pageCompression=1,
    )
    styles = report_styles()
    story = markdown_story(
        markdown,
        styles,
        document.width,
        input_path.parent,
        repository_root(input_path),
    )
    if not story:
        raise ValueError("Markdown did not produce any report content")
    document.build(story)
    return metadata


def main(argv: Sequence[str] | None = None) -> int:
    """Build the requested PDF and print a concise, script-friendly result."""

    args = parse_args(argv)
    metadata = build_pdf(args.input.resolve(), args.output.resolve(), args.author)
    print(f"Built PDF: {args.output.resolve()}")
    print(f"Title: {metadata.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
