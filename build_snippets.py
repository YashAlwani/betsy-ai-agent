"""build_snippets.py — render every code @token in CODE-EVIDENCE-SNIPPETS.md
to a syntax-highlighted PNG in snippets/, named after the token.

Source of truth: the quick-index table at the bottom of
decision_logs/CODE-EVIDENCE-SNIPPETS.md  (columns: @token | DL | file | lines).

Pipeline per entry: Pygments -> one HTML page (one card per line-range) ->
headless Edge screenshot -> Pillow auto-crop. Reuses the repo's existing
msedge + Pillow toolchain — no new dependencies.

Naming: filename stem = the token (without @). When a token has several
snippets, the manifest's context label is appended:  state--reset-bug.png.

Usage:  python build_snippets.py
"""
import re
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

from pygments import highlight
from pygments.lexers import guess_lexer_for_filename
from pygments.lexers.special import TextLexer
from pygments.util import ClassNotFound
from pygments.formatters import HtmlFormatter
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "decision_logs" / "CODE-EVIDENCE-SNIPPETS.md"
OUT_DIR = ROOT / "snippets"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

BG = (30, 30, 30)          # body background == crop reference
LINE_PX = 22               # logical px per code line (font 14 / line-height 1.5)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_quick_index(md: str) -> list[dict]:
    """Read the trailing '| @token | ... | file | lines |' table."""
    entries = []
    for line in md.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        token_cell, _dl, file_cell, lines_cell = cells[0], cells[1], cells[-2], cells[-1]
        m = re.search(r"`?@([A-Za-z0-9_\-]+)`?", token_cell)
        if not m:                       # header / separator rows
            continue
        token = m.group(1)
        ctx = ""
        cm = re.search(r"\(([^)]+)\)", token_cell)
        if cm:
            ctx = cm.group(1)
        # file path: strip backticks and any trailing note in parens
        file_path = re.sub(r"\([^)]*\)", "", file_cell).replace("`", "").strip()
        # ranges: collect "a-b" pairs, then any leftover bare ints
        ranges = [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*-\s*(\d+)", lines_cell)]
        masked = re.sub(r"\d+\s*-\s*\d+", "", lines_cell)
        ranges += [(int(n), int(n)) for n in re.findall(r"\d+", masked)]
        ranges = sorted(set(ranges))
        entries.append({"token": token, "ctx": ctx, "file": file_path, "ranges": ranges})
    return entries


def lexer_for(path: str, code: str):
    try:
        return guess_lexer_for_filename(path, code)
    except ClassNotFound:
        return TextLexer()


def build_html(entry: dict) -> tuple[str, int]:
    """Return (html, estimated_height_px) for all ranges of one entry."""
    src = (ROOT / entry["file"])
    all_lines = src.read_text(encoding="utf-8").splitlines()
    cards, est = [], 60
    for i, (start, end) in enumerate(entry["ranges"]):
        snippet = "\n".join(all_lines[start - 1:end])
        fmt = HtmlFormatter(style="monokai", linenos="table", linenostart=start)
        body = highlight(snippet, lexer_for(entry["file"], snippet), fmt)
        css = fmt.get_style_defs(".highlight")
        bar = f"{escape(entry['file'])}:{start}-{end}"
        if i > 0:
            cards.append('<div class="gap">&#8943;</div>')
            est += 26
        cards.append(f'<style>{css}</style>'
                     f'<div class="card"><div class="bar">{bar}</div>{body}</div>')
        est += (end - start + 1) * LINE_PX + 60
    label = entry["token"] + (f" — {entry['ctx']}" if entry["ctx"] else "")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      body {{ background:#1e1e1e; padding:22px; font-family:'Cascadia Code',Consolas,monospace;
              display:flex; flex-direction:column; align-items:flex-start; gap:0; }}
      .title {{ color:#9cdcfe; font:700 15px 'Segoe UI',sans-serif; margin-bottom:12px; }}
      .title span {{ color:#7c3aed; }}
      .card {{ display:inline-block; background:#272822; border-radius:10px;
               border:1px solid #3a3a3a; overflow:hidden; margin-bottom:0; }}
      .gap {{ color:#6a6a6a; font-size:18px; padding:6px 0 6px 26px; }}
      .bar {{ background:#1b1c18; color:#9cdcfe; font:600 12px 'Segoe UI',sans-serif;
              padding:8px 16px; border-bottom:1px solid #3a3a3a; }}
      .highlight {{ padding:12px 18px; font-size:14px; line-height:1.5; }}
      .highlight pre {{ margin:0; white-space:pre; }}
      .linenodiv pre {{ color:#5a5a5a; padding-right:14px; }}
      td.linenos {{ user-select:none; }}
    </style></head><body>
      <div class="title">@<span>{escape(label)}</span></div>
      {''.join(cards)}
    </body></html>"""
    return html, int(est * 1.15) + 80


def shoot(html: str, height: int, out_png: Path) -> tuple[int, int]:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as tf:
        tf.write(html)
        tmp = tf.name
    subprocess.run([
        EDGE, "--headless=new", f"--screenshot={out_png}",
        f"--window-size=1700,{max(height, 400)}", "--force-device-scale-factor=2",
        "--hide-scrollbars", Path(tmp).as_uri(),
    ], check=True, capture_output=True)
    img = Image.open(out_png).convert("RGB")
    bbox = ImageChops.difference(img, Image.new("RGB", img.size, BG)).getbbox()
    if bbox:
        l, t, r, b = bbox
        p = 18
        img = img.crop((max(0, l - p), max(0, t - p),
                        min(img.width, r + p), min(img.height, b + p)))
        img.save(out_png)
    Path(tmp).unlink(missing_ok=True)
    return img.width, img.height


def main():
    OUT_DIR.mkdir(exist_ok=True)
    entries = parse_quick_index(MANIFEST.read_text(encoding="utf-8"))
    seen, rows = {}, []
    for e in entries:
        stem = e["token"] + (f"--{slug(e['ctx'])}" if e["ctx"] else "")
        if not e["ranges"]:
            rows.append((stem, e["file"], "— no line range (served route / runtime artifact)"))
            continue
        if not (ROOT / e["file"]).exists():
            rows.append((stem, e["file"], "— file not found, skipped"))
            continue
        out_png = OUT_DIR / f"{stem}.png"
        html, height = build_html(e)
        try:
            w, h = shoot(html, height, out_png)
            rows.append((stem, e["file"], f"{w}x{h}  ({', '.join(f'{a}-{b}' for a, b in e['ranges'])})"))
        except Exception as exc:
            rows.append((stem, e["file"], f"ERROR: {exc}"))

    # Write a small linkable index.
    idx = ["# Snippets index\n",
           "Rendered from `decision_logs/CODE-EVIDENCE-SNIPPETS.md`. "
           "Filename stem = the `@token`.\n"]
    for stem, fpath, note in rows:
        if note.startswith("—") or note.startswith("ERROR"):
            idx.append(f"- `{stem}` — {fpath} {note}")
        else:
            idx.append(f"- ![{stem}](./{stem}.png) &nbsp; `@{stem}` → {fpath}")
    (OUT_DIR / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")

    ok = sum(1 for _, _, n in rows if "x" in n and "ERROR" not in n)
    print(f"\n{ok} images written to {OUT_DIR}")
    for stem, fpath, note in rows:
        print(f"  {stem:34} {note}")


if __name__ == "__main__":
    main()
