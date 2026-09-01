#!/usr/bin/env python3
"""Render Jumoo licence agreements from markdown to house-style PDFs.

Usage
-----
    python render-licences.py                     # every *.md in the current folder
    python render-licences.py usync-complete-project-licence.md   # named files
    python render-licences.py --out dist *.md

Output goes to <version> next to the sources (e.g. v1.4/) unless --out says
otherwise. The version comes from the bold version line under the title.

Requirements
------------
    pip install weasyprint markdown

WeasyPrint pulls in native libraries (pango, cairo, gdk-pixbuf). On Debian and
Ubuntu these come from libpango-1.0-0, libpangoft2-1.0-0 and libgdk-pixbuf-2.0-0.
The body font is DejaVu Serif (fonts-dejavu); if it is missing, WeasyPrint falls
back to Georgia or the generic serif and the layout shifts slightly.

Source document conventions
---------------------------
Each markdown file is expected to have:

    # Jumoo <Product>                                   <- H1, document title
    ## "<Variant>" licence agreement                    <- H2 immediately after, subtitle
    **v1.4, 09-2026**                                   <- bold version line
    ...
    _Jumoo - <Product> "<Variant>" - Licence Agreement, v1.4, 09-2026_

The trailing italic line is split on the version to build the running footer, so
keep its shape if you add new documents. Horizontal rules (---) in the source are
section separators for reading the markdown and are not rendered.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import markdown
from weasyprint import CSS, HTML

CSS_TEMPLATE = """
@page {
    size: A4;
    margin: 22mm 20mm 24mm 20mm;

    @bottom-left {
        content: "%(footer_name)s";
        font-family: "DejaVu Serif", Georgia, serif;
        font-size: 7.5pt;
        color: #5b5b5b;
        vertical-align: top;
        padding-top: 6mm;
    }
    @bottom-right {
        content: counter(page) "/" counter(pages) "  \\2022  %(version)s";
        font-family: "DejaVu Serif", Georgia, serif;
        font-size: 7.5pt;
        color: #5b5b5b;
        vertical-align: top;
        padding-top: 6mm;
    }
}

html { font-size: 10.5pt; }

body {
    font-family: "DejaVu Serif", Georgia, serif;
    line-height: 1.5;
    color: #1a1a1a;
    text-align: left;
    hyphens: none;
}

h1 {
    font-size: 21pt;
    font-weight: normal;
    letter-spacing: 0.2pt;
    margin: 0 0 2mm 0;
    color: #111;
}

/* the subtitle: the H2 directly after the title */
h1 + h2 {
    font-size: 13pt;
    font-weight: normal;
    font-style: italic;
    color: #444;
    margin: 0 0 3mm 0;
    padding: 0;
    border: none;
}

h2 {
    font-size: 12pt;
    font-weight: bold;
    color: #111;
    margin: 8mm 0 2.5mm 0;
    padding-bottom: 1.2mm;
    border-bottom: 0.4pt solid #c9c9c9;
    break-after: avoid;
    page-break-after: avoid;
}

p.docversion {
    font-size: 9.5pt;
    color: #555;
    margin: 0 0 9mm 0;
    padding-bottom: 4mm;
    border-bottom: 0.8pt solid #333;
}

p {
    margin: 0 0 3.2mm 0;
    orphans: 2;
    widows: 2;
}

/* lettered sub-clauses: (a) ... (b) ... with a hanging indent */
p.clause {
    margin-left: 8mm;
    text-indent: -8mm;
    margin-bottom: 2.6mm;
}

p.closing {
    margin-top: 10mm;
    padding-top: 3mm;
    border-top: 0.4pt solid #c9c9c9;
    font-size: 9pt;
    font-style: italic;
    color: #555;
}

a { color: #1a1a1a; text-decoration: none; }

hr { display: none; }
"""


def parse_closing_line(lines: list[str]) -> tuple[str, str, str]:
    """Return (closing line, footer name, version) from the trailing italic line."""
    closing = ""
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("_") and stripped.endswith("_") and len(stripped) > 2:
            closing = stripped.strip("_")
            break
    match = re.match(r"^(.*?),\s*(v[\d.]+,\s*[\d-]+)$", closing)
    footer_name, version = (match.group(1), match.group(2)) if match else (closing, "")
    return closing, footer_name, version


def build(md_path: Path, out_dir: Path | None) -> Path:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    closing, footer_name, version = parse_closing_line(lines)
    version_short = version.split(",")[0].strip() if version else ""

    if out_dir is None:
        out_dir = md_path.parent / version_short

    # The document name contains quotes (... uSync.Complete "Agency" ...). Straight
    # quotes inside a CSS content: "..." string silently invalidate the rule and the
    # footer disappears, so use curly quotes in the footer.
    footer_name = re.sub(r'"([^"]*)"', "“\\1”", footer_name)

    body_md = "\n".join(
        line for line in lines
        if line.strip() != closing and not line.strip().startswith("_Jumoo")
    )
    html_body = markdown.markdown(
        body_md, extensions=["extra", "sane_lists", "smarty"]
    )

    # the bold version line under the title gets its own rule
    html_body = re.sub(
        r"<p><strong>(v[\d.]+,\s*[\d-]+)</strong></p>",
        r'<p class="docversion">\1</p>',
        html_body,
        count=1,
    )

    # hanging indent for lettered clauses
    html_body = re.sub(r"<p>\((\w)\)\s", r'<p class="clause">(\1)&nbsp;', html_body)

    html_body += f'<p class="closing">{closing}</p>'

    # Non-breaking hyphens inside words. Without this, "sub-licence" split across a
    # line loses its hyphen when the PDF text is copied out ("sublicence").
    html_body = re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "‑", html_body)

    css = CSS_TEMPLATE % {"footer_name": footer_name, "version": version}
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{version_short}" if version_short else ""
    out_pdf = out_dir / f"{md_path.stem}{suffix}.pdf"
    HTML(string=f"<html><body>{html_body}</body></html>").write_pdf(
        out_pdf, stylesheets=[CSS(string=css)]
    )
    return out_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render Jumoo licence markdown files to house-style PDFs."
    )
    parser.add_argument(
        "sources", nargs="*", type=Path,
        help="markdown files to render (default: every *.md in the current folder)",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="output folder (default: a '<version>' folder beside each source)",
    )
    args = parser.parse_args(argv)

    sources = args.sources or sorted(Path(".").glob("*.md"))
    sources = [p for p in sources if p.is_file()]
    if not sources:
        parser.error("no markdown sources found")

    for md_path in sources:
        pdf = build(md_path, args.out)
        print(f"{md_path}  ->  {pdf}  ({pdf.stat().st_size:,} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
