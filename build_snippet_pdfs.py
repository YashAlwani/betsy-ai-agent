"""build_snippet_pdfs.py — wrap each rendered snippet PNG in snippets/ into its
own embedded PDF, styled like the demo: title, which DL(s), the decision-log
sentence, the embedded code image, and the description.

Reuses the PNGs already produced by build_snippets.py (no re-screenshotting).
Metadata comes from decision_logs/CODE-EVIDENCE-SNIPPETS.md:
  - DL(s), file, line-ranges  -> the quick-index table (clean)
  - sentence + description     -> the prose entry (matched by token+file+range)

Output: snippets/<token>.pdf  (one per snippet image).

Usage:  python build_snippet_pdfs.py
"""
import re
from html import escape
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, HRFlowable

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "decision_logs" / "CODE-EVIDENCE-SNIPPETS.md"
SNIP = ROOT / "snippets"

PW = A4[0]                      # A4 width; height is computed per snippet
LM = RM = 44
TM, BM = 40, 36
CW = PW - LM - RM              # content width


def md_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def rl(text: str) -> str:
    """Minimal markdown-inline -> reportlab markup."""
    text = escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    return text


def range_strs(ranges):
    return [f"{a}-{b}" if a != b else str(a) for a, b in ranges]


# ── Parse the quick-index table (clean: token, dl, file, ranges) ───────────────

def parse_quick_index(md: str):
    out = []
    for line in md.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        token_cell, dl_cell, file_cell, lines_cell = cells[0], cells[1], cells[-2], cells[-1]
        m = re.search(r"`?@([A-Za-z0-9_\-]+)`?", token_cell)
        if not m:
            continue
        ctx = (re.search(r"\(([^)]+)\)", token_cell) or [None, ""])[1] if "(" in token_cell else ""
        ctx = re.search(r"\(([^)]+)\)", token_cell).group(1) if "(" in token_cell else ""
        file_path = re.sub(r"\([^)]*\)", "", file_cell).replace("`", "").strip()
        ranges = [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*-\s*(\d+)", lines_cell)]
        masked = re.sub(r"\d+\s*-\s*\d+", "", lines_cell)
        ranges += [(int(n), int(n)) for n in re.findall(r"\d+", masked)]
        ranges = sorted(set(ranges))
        dls = ", ".join(f"DL-{d.strip().zfill(2)}" for d in dl_cell.split(",") if d.strip().isdigit())
        out.append({"token": m.group(1), "ctx": ctx, "file": file_path,
                    "ranges": ranges, "dls": dls})
    return out


# ── Parse the prose entries (sentence + description) ───────────────────────────

def parse_prose(md: str):
    entries, cur, field = [], None, None
    for line in md.splitlines():
        if re.match(r"^##\s", line) and not line.startswith("###"):
            continue
        if line.startswith("### "):
            if cur:
                entries.append(cur)
            tok = re.search(r"@([A-Za-z0-9_\-]+)", line)
            cur = {"token": tok.group(1) if tok else "", "file": "",
                   "lines_raw": "", "sentence": "", "description": ""}
            field = None
            continue
        if cur is None:
            continue
        mfield = re.match(r"\s*-\s*\*\*(Sentence\(s\)|File|Lines|Description):\*\*\s*(.*)", line)
        if mfield:
            key, val = mfield.group(1), mfield.group(2)
            if key == "Sentence(s)":
                cur["sentence"] = val; field = "sentence"
            elif key == "File":
                cur["file"] = val.replace("`", "").strip(); field = None
            elif key == "Lines":
                cur["lines_raw"] = val; field = None
            elif key == "Description":
                cur["description"] = val; field = "description"
        elif field and line.strip() and not line.startswith(("-", "#", "|", ">")):
            cur[field] += " " + line.strip()
    if cur:
        entries.append(cur)
    return entries


def match_prose(qi, prose):
    """Find the prose entry sharing token + file basename + a line-range string."""
    base = Path(qi["file"]).name
    rs = range_strs(qi["ranges"])
    for p in prose:
        if p["token"] != qi["token"]:
            continue
        if Path(p["file"]).name != base:
            continue
        if any(re.search(rf"(?<!\d){re.escape(r)}(?!\d)", p["lines_raw"]) for r in rs):
            return p
    # looser fallback: token + file only
    for p in prose:
        if p["token"] == qi["token"] and Path(p["file"]).name == base:
            return p
    return None


# ── Build one PDF ──────────────────────────────────────────────────────────────

styles = getSampleStyleSheet()
S_TITLE = ParagraphStyle("t", parent=styles["Heading2"], textColor=HexColor("#0f172a"),
                         fontSize=15, spaceAfter=3)
S_META = ParagraphStyle("m", parent=styles["Normal"], textColor=HexColor("#7c3aed"),
                        fontSize=9.5, spaceAfter=2)
S_SRC = ParagraphStyle("s", parent=styles["Normal"], textColor=HexColor("#94a3b8"),
                       fontSize=8.5, spaceBefore=2)
S_QUOTE = ParagraphStyle("q", parent=styles["Normal"], leftIndent=12,
                         textColor=HexColor("#334155"), fontName="Helvetica-Oblique",
                         fontSize=10, leading=14, spaceBefore=10, spaceAfter=12)
S_BODY = ParagraphStyle("b", parent=styles["Normal"], fontSize=10, leading=15, spaceBefore=12)


def build_pdf(qi, prose_match, png: Path, out_pdf: Path):
    pil = PILImage.open(png)
    img = Image(str(png), width=CW, height=CW * pil.height / pil.width)

    label = "@" + qi["token"] + (f" — {qi['ctx']}" if qi["ctx"] else "")
    ranges = ", ".join(range_strs(qi["ranges"]))
    story = [
        Paragraph(rl(label), S_TITLE),
        Paragraph(f"Appears in: <b>{qi['dls'] or '—'}</b>", S_META),
        Paragraph(f"<font color='#94a3b8'>{escape(qi['file'])}:{ranges}</font>", S_META),
        HRFlowable(width="100%", color=HexColor("#e2e8f0"), spaceBefore=8, spaceAfter=4),
    ]
    if prose_match and prose_match["sentence"]:
        story.append(Paragraph(rl(prose_match["sentence"]), S_QUOTE))
    else:
        story.append(Spacer(1, 8))
    story.append(img)
    if prose_match and prose_match["description"]:
        story.append(Paragraph("<b>What it shows:</b> " + rl(prose_match["description"]), S_BODY))
    story.append(Paragraph(f"Source: {escape(qi['file'])}:{ranges} · image rendered by "
                           f"build_snippets.py", S_SRC))

    # Measure to size a single page that fits everything (incl. para spacing).
    total = TM + BM
    for f in story:
        _, fh = f.wrap(CW, 100000)
        sb = f.getSpaceBefore() if hasattr(f, "getSpaceBefore") else getattr(f, "spaceBefore", 0)
        sa = f.getSpaceAfter() if hasattr(f, "getSpaceAfter") else getattr(f, "spaceAfter", 0)
        total += fh + sb + sa
    total += 16  # slack
    doc = SimpleDocTemplate(str(out_pdf), pagesize=(PW, total),
                            leftMargin=LM, rightMargin=RM, topMargin=TM, bottomMargin=BM)
    doc.build(story)


def main():
    md = MANIFEST.read_text(encoding="utf-8")
    qis = parse_quick_index(md)
    prose = parse_prose(md)

    made, skipped = 0, []
    for qi in qis:
        stem = qi["token"] + (f"--{md_slug(qi['ctx'])}" if qi["ctx"] else "")
        png = SNIP / f"{stem}.png"
        if not png.exists():
            skipped.append((stem, "no image (served route / runtime artifact)"))
            continue
        build_pdf(qi, match_prose(qi, prose), png, SNIP / f"{stem}.pdf")
        made += 1
        print(f"  {stem}.pdf")

    print(f"\n{made} PDFs written to {SNIP}")
    for stem, why in skipped:
        print(f"  skipped {stem}: {why}")


if __name__ == "__main__":
    main()
