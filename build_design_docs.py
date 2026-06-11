"""
Builds Betsy's plain-English design documents into PDFs with embedded diagrams.

Pipeline:
  1. Render every diagrams/*.mmd to diagrams/*.png (via mermaid-cli, npx).
  2. For each design .txt in DESIGN_DOCS, build a PDF that lays out the plain
     text and embeds the matching diagram image wherever the text contains a
     line like:  "See the picture: diagrams/<name>.mmd"

Outputs to pdf_exports/design/<name>.pdf

Run:  python build_design_docs.py
Requires: reportlab, Pillow, and Node/npx (for mermaid-cli, fetched on demand).
"""

import os
import re
import subprocess
import sys

from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab

# ── Fonts (Vera ships with reportlab; good Unicode coverage for our text) ─────
_FONTS_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
pdfmetrics.registerFont(TTFont("Vera", os.path.join(_FONTS_DIR, "Vera.ttf")))
pdfmetrics.registerFont(TTFont("VeraBd", os.path.join(_FONTS_DIR, "VeraBd.ttf")))
pdfmetrics.registerFont(TTFont("VeraIt", os.path.join(_FONTS_DIR, "VeraIt.ttf")))

BASE = os.path.dirname(os.path.abspath(__file__))
DIAGRAMS_DIR = os.path.join(BASE, "diagrams")
OUTPUT_DIR = os.path.join(BASE, "pdf_exports", "design")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
CONTENT_W = PAGE_W - 2 * MARGIN
CONTENT_H = PAGE_H - 2 * MARGIN

# Design docs to build (plain-English .txt sources)
DESIGN_DOCS = [
    "docs/pipeline-architecture.txt",
    "docs/orchestra-architecture.txt",
    "docs/api-control-layer.txt",
    "docs/gap-analysis.txt",
]

PICTURE_RE = re.compile(r"See the picture:\s*(diagrams/[\w\-]+)\.mmd", re.IGNORECASE)
_UNICODE_SUBS = {"→": "->", "←": "<-", "✦": "*", "●": "*", "◐": "o", "○": "o"}


def sanitize(text: str) -> str:
    for a, b in _UNICODE_SUBS.items():
        text = text.replace(a, b)
    return text


def render_diagrams() -> None:
    """Render every .mmd to a .png if the PNG is missing or out of date."""
    if not os.path.isdir(DIAGRAMS_DIR):
        return
    for name in sorted(os.listdir(DIAGRAMS_DIR)):
        if not name.endswith(".mmd"):
            continue
        mmd = os.path.join(DIAGRAMS_DIR, name)
        png = mmd[:-4] + ".png"
        if os.path.exists(png) and os.path.getmtime(png) >= os.path.getmtime(mmd):
            continue
        print(f"  rendering {name} -> {os.path.basename(png)}")
        # -s 3 renders at 3x scale so diagrams stay sharp when zoomed in a PDF
        # or viewer; -w 1600 sets a generous base width before that scaling.
        subprocess.run(
            ["npx", "-y", "@mermaid-js/mermaid-cli", "-i", mmd, "-o", png,
             "-b", "white", "-s", "3", "-w", "1600"],
            check=True, shell=(os.name == "nt"),
        )


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Normal"], fontName="VeraBd",
                                 fontSize=20, leading=26, spaceAfter=2,
                                 textColor=colors.HexColor("#0d1b2a")),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontName="VeraIt",
                                   fontSize=12, leading=16, spaceAfter=10,
                                   textColor=colors.HexColor("#3a6ea5")),
        "h": ParagraphStyle("h", parent=base["Normal"], fontName="VeraBd",
                            fontSize=13, leading=18, spaceBefore=14, spaceAfter=4,
                            textColor=colors.HexColor("#0f3460")),
        "body": ParagraphStyle("body", parent=base["Normal"], fontName="Vera",
                               fontSize=10.5, leading=15.5, spaceAfter=6),
        "li": ParagraphStyle("li", parent=base["Normal"], fontName="Vera",
                             fontSize=10.5, leading=15, leftIndent=14, spaceAfter=2),
        "caption": ParagraphStyle("caption", parent=base["Normal"], fontName="VeraIt",
                                  fontSize=9, leading=12, spaceBefore=3, spaceAfter=12,
                                  textColor=colors.HexColor("#666666")),
    }


def scaled_image(png_path: str) -> Image:
    """Fit a PNG within the content box, preserving aspect ratio."""
    with PILImage.open(png_path) as im:
        px_w, px_h = im.size
    w = px_w * 72.0 / 96.0
    h = px_h * 72.0 / 96.0
    scale = min(CONTENT_W / w, (CONTENT_H * 0.85) / h, 1.0)
    return Image(png_path, width=w * scale, height=h * scale)


def esc(s: str) -> str:
    return sanitize(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def txt_to_flowables(txt_path: str, styles) -> list:
    with open(txt_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    flow, para, bullet, i = [], [], [], 0

    def flush_para():
        if para:
            flow.append(Paragraph(esc(" ".join(para)), styles["body"]))
            para.clear()

    def flush_bullet():
        if bullet:
            flow.append(Paragraph("• " + esc(" ".join(bullet)), styles["li"]))
            bullet.clear()

    # Title block: lines between the first pair of ==== rules
    if lines and set(lines[0].strip()) == {"="}:
        i = 1
        title_lines = []
        while i < len(lines) and set(lines[i].strip()) != {"="}:
            title_lines.append(lines[i].strip())
            i += 1
        i += 1  # skip closing ====
        if title_lines:
            flow.append(Paragraph(esc(title_lines[0]), styles["title"]))
            if len(title_lines) > 1:
                flow.append(Paragraph(esc(" — ".join(title_lines[1:])), styles["subtitle"]))
        flow.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#3a6ea5")))

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Section heading = text line followed by a line of dashes
        if stripped and i + 1 < len(lines) and set(lines[i + 1].strip()) == {"-"} and len(lines[i + 1].strip()) >= 3:
            flush_para()
            flush_bullet()
            flow.append(Paragraph(esc(stripped), styles["h"]))
            i += 2
            continue

        # Embedded diagram
        m = PICTURE_RE.search(stripped)
        if m:
            flush_para()
            flush_bullet()
            png = os.path.join(BASE, m.group(1) + ".png")
            if os.path.exists(png):
                flow.append(scaled_image(png))
                flow.append(Paragraph(esc(stripped), styles["caption"]))
            else:
                para.append(stripped)
            i += 1
            continue

        if not stripped:
            flush_para()
            flush_bullet()
            i += 1
            continue

        if stripped.startswith("- "):
            flush_para()
            flush_bullet()
            bullet.append(stripped[2:])
            i += 1
            continue

        # Indented line while a bullet is open = wrapped continuation of it
        if bullet and line[:1] in (" ", "\t"):
            bullet.append(stripped)
            i += 1
            continue

        flush_bullet()
        para.append(stripped)
        i += 1

    flush_para()
    flush_bullet()
    return flow


def main():
    print("Rendering diagrams...")
    render_diagrams()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    styles = build_styles()

    for rel in DESIGN_DOCS:
        src = os.path.join(BASE, rel.replace("/", os.sep))
        if not os.path.exists(src):
            print(f"  SKIP (missing): {rel}")
            continue
        name = os.path.splitext(os.path.basename(src))[0]
        out = os.path.join(OUTPUT_DIR, name + ".pdf")
        doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                                topMargin=MARGIN, bottomMargin=MARGIN, title=name)
        doc.build(txt_to_flowables(src, styles))
        print(f"  OK  {rel}  ->  {os.path.relpath(out, BASE)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
