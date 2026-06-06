"""
Converts all project MD files to PDF, preserving folder structure under pdf_exports/.
Uses reportlab for rendering and markdown for parsing.
"""

import os
import re
import markdown
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Preformatted, HRFlowable, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from html.parser import HTMLParser
import reportlab

# Register Vera TTF fonts (bundled with reportlab) for Unicode support
_FONTS_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
pdfmetrics.registerFont(TTFont("Vera", os.path.join(_FONTS_DIR, "Vera.ttf")))
pdfmetrics.registerFont(TTFont("VeraBd", os.path.join(_FONTS_DIR, "VeraBd.ttf")))
pdfmetrics.registerFont(TTFont("VeraIt", os.path.join(_FONTS_DIR, "VeraIt.ttf")))
pdfmetrics.registerFont(TTFont("VeraBI", os.path.join(_FONTS_DIR, "VeraBI.ttf")))

# Unicode → readable ASCII substitutions for characters outside Vera's range
UNICODE_SUBS = {
    "→": "->",   # →
    "←": "<-",   # ←
    "↔": "<->",  # ↔
    "↑": "^",    # ↑
    "↓": "v",    # ↓
    "⇒": "=>",   # ⇒
    "⇐": "<=",   # ⇐
    "✓": "v",    # ✓
    "✔": "v",    # ✔
    "✕": "x",    # ✕
    "✖": "x",    # ✖
    "✘": "x",    # ✘
    "•": "-",    # •
    "’": "'",    # '
    "‘": "'",    # '
    "“": '"',    # "
    "”": '"',    # "
    "–": "-",    # –
    "—": "--",   # —
    "…": "...",  # …
    " ": " ",    # non-breaking space
    "☐": "[ ]",  # ☐
    "☑": "[x]",  # ☑
    "☒": "[x]",  # ☒
    "▶": ">",    # ▶
    "◀": "<",    # ◀
    "★": "*",    # ★
    "☆": "*",    # ☆
}


def sanitize(text: str) -> str:
    for char, repl in UNICODE_SUBS.items():
        text = text.replace(char, repl)
    # Drop any remaining non-latin1 chars that Vera can't handle
    return text.encode("latin-1", errors="replace").decode("latin-1")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm

MD_FILES = [
    "PROJECT_PLAN.md",
    "README.md",
    "analysis/build_strategy.md",
    "analysis/case_summary.md",
    "analysis/constraints.md",
    "analysis/phases.md",
    "analysis/research_questions.md",
    "analysis/risk_assessment.md",
    "analysis/stakeholder_analysis.md",
    "decision_logs/evidence/ORCHESTRA_ARCHITECTURE.md",
    "decision_logs/evidence/PIPELINE_ARCHITECTURE.md",
    "docs/ORCHESTRA_ARCHITECTURE.md",
    "docs/PIPELINE_ARCHITECTURE.md",
    "docs/api-control-layer.md",
    "docs/dl06-plan.md",
    "docs/test-report-dl05.md",
    "docs/test-report-dl06.md",
    "docs/user_requirements.md",
    "docs/wireframes.md",
    "decision_logs/DL-SUMMARY.md",
    "decision_logs/DOT_METHODS.md",
    "decision_logs/COMMIT_TIMELINE.md",
]

OUTPUT_ROOT = "pdf_exports"


def build_styles():
    base = getSampleStyleSheet()
    s = {}

    s["h1"] = ParagraphStyle(
        "h1", parent=base["Normal"],
        fontSize=20, leading=26, spaceBefore=14, spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"), fontName="VeraBd",
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=base["Normal"],
        fontSize=16, leading=22, spaceBefore=12, spaceAfter=4,
        textColor=colors.HexColor("#16213e"), fontName="VeraBd",
    )
    s["h3"] = ParagraphStyle(
        "h3", parent=base["Normal"],
        fontSize=13, leading=18, spaceBefore=10, spaceAfter=3,
        textColor=colors.HexColor("#0f3460"), fontName="VeraBd",
    )
    s["h4"] = ParagraphStyle(
        "h4", parent=base["Normal"],
        fontSize=11, leading=16, spaceBefore=8, spaceAfter=2,
        textColor=colors.HexColor("#0f3460"), fontName="VeraBI",
    )
    s["body"] = ParagraphStyle(
        "body", parent=base["Normal"],
        fontSize=10, leading=15, spaceBefore=2, spaceAfter=4,
        fontName="Vera",
    )
    s["li"] = ParagraphStyle(
        "li", parent=base["Normal"],
        fontSize=10, leading=14, spaceBefore=1, spaceAfter=1,
        fontName="Vera", leftIndent=12,
    )
    s["code"] = ParagraphStyle(
        "code", parent=base["Normal"],
        fontSize=8.5, leading=13, spaceBefore=4, spaceAfter=4,
        fontName="Courier", backColor=colors.HexColor("#f4f4f4"),
        leftIndent=10, rightIndent=10,
    )
    s["blockquote"] = ParagraphStyle(
        "blockquote", parent=base["Normal"],
        fontSize=10, leading=15, spaceBefore=4, spaceAfter=4,
        fontName="VeraIt", leftIndent=20,
        textColor=colors.HexColor("#555555"),
    )
    return s


class HTMLToFlowables(HTMLParser):
    """Minimal HTML→reportlab flowable converter for markdown output."""

    def __init__(self, styles):
        super().__init__()
        self.styles = styles
        self.flowables = []
        self._tag_stack = []
        self._text_buf = ""
        self._in_code_block = False
        self._code_buf = ""
        self._list_stack = []   # stack of ("ul"|"ol", [items])
        self._li_buf = ""
        self._in_li = False
        self._in_table = False
        self._table_buf = []
        self._row_buf = []
        self._cell_buf = ""
        self._in_cell = False

    def _flush_text(self, style_key="body"):
        text = self._text_buf.strip()
        self._text_buf = ""
        if text:
            self.flowables.append(Paragraph(text, self.styles[style_key]))

    def _escape(self, s):
        s = sanitize(s)
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag == "pre":
            self._flush_text()
            self._in_code_block = True
            self._code_buf = ""
        elif tag in ("h1", "h2", "h3", "h4"):
            self._flush_text()
            self._text_buf = ""
        elif tag == "ul":
            self._flush_text()
            self._list_stack.append(("ul", []))
        elif tag == "ol":
            self._flush_text()
            self._list_stack.append(("ol", []))
        elif tag == "li":
            self._in_li = True
            self._li_buf = ""
        elif tag == "blockquote":
            self._flush_text()
        elif tag == "hr":
            self._flush_text()
            self.flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        elif tag == "table":
            self._in_table = True
            self._table_buf = []
        elif tag in ("tr",):
            self._row_buf = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cell_buf = ""
        elif tag == "strong" or tag == "b":
            if self._in_li:
                self._li_buf += "<b>"
            else:
                self._text_buf += "<b>"
        elif tag == "em" or tag == "i":
            if self._in_li:
                self._li_buf += "<i>"
            else:
                self._text_buf += "<i>"
        elif tag == "code" and not self._in_code_block:
            if self._in_li:
                self._li_buf += "<font name='Courier'>"
            else:
                self._text_buf += "<font name='Courier'>"

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        if tag == "pre":
            self._in_code_block = False
            code = sanitize(self._code_buf.rstrip("\n"))
            if code:
                self.flowables.append(Preformatted(code, self.styles["code"]))
            self._code_buf = ""
        elif tag in ("h1", "h2", "h3", "h4"):
            text = self._text_buf.strip()
            self._text_buf = ""
            if text:
                self.flowables.append(Paragraph(text, self.styles[tag]))
        elif tag == "p":
            if self._in_li:
                self._li_buf += self._text_buf
                self._text_buf = ""
            else:
                self._flush_text()
        elif tag == "li":
            self._in_li = False
            if self._list_stack:
                self._list_stack[-1][1].append(self._li_buf.strip())
            self._li_buf = ""
        elif tag in ("ul", "ol"):
            if self._list_stack:
                kind, items = self._list_stack.pop()
                bullet = "bullet" if kind == "ul" else "1"
                list_items = [
                    ListItem(Paragraph(item or "&nbsp;", self.styles["li"]), bulletColor=colors.HexColor("#333333"))
                    for item in items
                ]
                if list_items:
                    self.flowables.append(
                        ListFlowable(list_items, bulletType=bullet, leftIndent=20, bulletFontSize=9)
                    )
        elif tag == "blockquote":
            self._flush_text("blockquote")
        elif tag == "table":
            self._in_table = False
            if self._table_buf:
                # Render table as preformatted text (simple approach)
                lines = []
                for row in self._table_buf:
                    lines.append("  |  ".join(cell.strip() for cell in row))
                    lines.append("-" * min(80, max((len(l) for l in lines), default=40)))
                self.flowables.append(Preformatted("\n".join(lines), self.styles["code"]))
        elif tag == "tr":
            if self._row_buf:
                self._table_buf.append(self._row_buf)
        elif tag in ("td", "th"):
            self._in_cell = False
            self._row_buf.append(self._cell_buf)
            self._cell_buf = ""
        elif tag == "strong" or tag == "b":
            if self._in_li:
                self._li_buf += "</b>"
            else:
                self._text_buf += "</b>"
        elif tag == "em" or tag == "i":
            if self._in_li:
                self._li_buf += "</i>"
            else:
                self._text_buf += "</i>"
        elif tag == "code" and not self._in_code_block:
            if self._in_li:
                self._li_buf += "</font>"
            else:
                self._text_buf += "</font>"

    def handle_data(self, data):
        if self._in_code_block:
            self._code_buf += data
        elif self._in_cell:
            self._cell_buf += self._escape(data)
        elif self._in_li:
            self._li_buf += self._escape(data)
        else:
            self._text_buf += self._escape(data)

    def get_flowables(self):
        self._flush_text()
        return self.flowables


def md_to_pdf(md_path: str, pdf_path: str):
    with open(md_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Apply substitutions before markdown parsing so no unicode escapes leak through
    for char, repl in UNICODE_SUBS.items():
        raw = raw.replace(char, repl)
    # Drop any remaining non-latin1 characters
    md_text = raw.encode("latin-1", errors="replace").decode("latin-1")

    html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    styles = build_styles()
    parser = HTMLToFlowables(styles)
    parser.feed(html)
    flowables = parser.get_flowables()

    if not flowables:
        flowables = [Paragraph("(empty document)", styles["body"])]

    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=os.path.basename(md_path),
    )
    doc.build(flowables)
    print(f"  OK  {md_path}  ->  {pdf_path}")


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    converted, skipped = 0, 0

    for rel in MD_FILES:
        md_path = os.path.join(base, rel.replace("/", os.sep))
        if not os.path.exists(md_path):
            print(f"  --  SKIP (not found): {rel}")
            skipped += 1
            continue

        # Mirror folder structure: pdf_exports/<original_subdir>/<name>.pdf
        pdf_rel = rel.replace(".md", ".pdf")
        pdf_path = os.path.join(base, OUTPUT_ROOT, pdf_rel.replace("/", os.sep))

        try:
            md_to_pdf(md_path, pdf_path)
            converted += 1
        except Exception as e:
            print(f"  ERR {rel}: {e}")
            skipped += 1

    print(f"\nDone: {converted} converted, {skipped} skipped.")
    print(f"PDFs are in: {os.path.join(base, OUTPUT_ROOT)}")


if __name__ == "__main__":
    main()
