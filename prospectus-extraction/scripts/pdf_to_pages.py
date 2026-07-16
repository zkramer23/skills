# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf>=5"]
# ///
"""Emit page-tagged, token-efficient text from a prospectus PDF.

Usage: uv run pdf_to_pages.py <document.pdf> [out.txt] [--raw]

Output format matches the payout-grapher extraction context: each page is
preceded by a `[[page N]]` marker (1-indexed), so evidence quotes can cite
page numbers. Layout mode is used so terms tables and observation schedules
keep their columnar structure.

By default the text is whitespace-normalized: huge left margins (an EDGAR
HTM-to-PDF artifact) are stripped, runs of 3+ spaces collapse to 2, and blank
runs squeeze — measured ~53% smaller than raw layout text on a real 424B2,
beating markitdown (~20%) while keeping page markers and column alignment.
Two spaces still signal a column break, so tables stay readable. Pass --raw
to skip normalization if exact spacing ever matters.

NOTE: evidence quotes should be matched against THIS normalized text (or with
whitespace-insensitive matching) — the PDF's original spacing differs.

Pages with almost no text are flagged inline with [[page N — EMPTY/SCANNED?]]
and a summary warning goes to stderr: that signals a scanned document that
needs the OCR path instead.
"""

import re
import sys
from pathlib import Path

from pypdf import PdfReader

MIN_CHARS_REAL_PAGE = 40  # below this, the page is likely an image/scan


def normalize(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        line = line.rstrip()
        line = re.sub(r"^ {20,}", "", line)  # uniform giant margins carry no meaning
        line = re.sub(r" {3,}", "  ", line)  # 2 spaces still mark a column break
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def main() -> int:
    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        print(__doc__)
        return 0
    args = [a for a in sys.argv[1:] if a != "--raw"]
    raw = "--raw" in sys.argv
    if not 1 <= len(args) <= 2:
        print(__doc__, file=sys.stderr)
        return 2
    src = Path(args[0])
    out_path = Path(args[1]) if len(args) > 1 else None
    if not src.is_file():
        print(f"ERROR: PDF not found: {src}", file=sys.stderr)
        return 2

    reader = PdfReader(src)
    chunks: list[str] = []
    empty_pages: list[int] = []
    raw_chars = 0
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text(extraction_mode="layout") or ""
        except Exception:
            text = page.extract_text() or ""
        raw_chars += len(text)
        if not raw:
            text = normalize(text)
        if len(text.strip()) < MIN_CHARS_REAL_PAGE:
            empty_pages.append(i)
            chunks.append(f"[[page {i} — EMPTY/SCANNED?]]\n{text}")
        else:
            chunks.append(f"[[page {i}]]\n{text}")

    result = "\n".join(chunks)
    if out_path:
        out_path.write_text(result)
        note = "" if raw else f" (normalized from {raw_chars})"
        print(f"{len(reader.pages)} pages -> {out_path} ({len(result)} chars{note})")
    else:
        print(result)

    if empty_pages:
        frac = len(empty_pages) / max(1, len(reader.pages))
        print(
            f"WARNING: {len(empty_pages)}/{len(reader.pages)} pages near-empty "
            f"(pages {empty_pages[:10]}{'…' if len(empty_pages) > 10 else ''}). "
            + ("Document looks SCANNED — use the OCR path." if frac > 0.5 else "Check those pages for images/charts."),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
