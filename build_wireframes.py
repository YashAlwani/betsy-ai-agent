"""
Builds Betsy's wireframes from wiremd sources into trimmed PNGs for diagrams/.

Pipeline per source (diagrams/wireframes/*.wmd.md):
  1. Render the wiremd markdown to styled HTML via the wiremd CLI
     (npm install -g wiremd), using the grayscale "wireframe" style.
  2. Screenshot that HTML to PNG with headless Microsoft Edge (present on
     Windows 11 — no extra dependency).
  3. Auto-crop the PNG to its content box with Pillow, so there is no large
     empty margin left by the fixed browser window.

Output:  diagrams/wireframe-<name>.png   (<name> = source minus the .wmd.md)

Run:  python build_wireframes.py
Requires: Pillow, the global `wiremd` CLI, and Microsoft Edge.
"""

import glob
import os
import subprocess
import sys

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE, "diagrams", "wireframes")
OUT_DIR = os.path.join(BASE, "diagrams")

STYLE = "wireframe"          # wiremd visual style (grayscale, traditional)
SCALE = "2"                  # device scale factor — sharp on zoom
WINDOW = "1100,1600"         # generous canvas; auto-crop trims the excess
MARGIN = 32                  # px margin kept around the cropped content

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_edge() -> str:
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("Microsoft Edge not found — adjust EDGE_CANDIDATES.")


def render_html(src: str, html: str) -> None:
    # wiremd is a global npm bin; shell=True so Windows resolves the .cmd shim.
    subprocess.run(
        ["wiremd", src, "-s", STYLE, "-o", html],
        check=True, shell=(os.name == "nt"),
    )


def screenshot(edge: str, html: str, png: str) -> None:
    subprocess.run([
        edge, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        f"--force-device-scale-factor={SCALE}",
        f"--window-size={WINDOW}",
        f"--screenshot={png}", html,
    ], check=True)


def autocrop(png: str) -> None:
    """Trim the fixed-window screenshot down to its actual content."""
    im = Image.open(png).convert("RGB")
    bg = im.getpixel((0, 0))                      # page background colour
    # Build a mask of pixels that differ from the background, find its box.
    from PIL import ImageChops
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg))
    bbox = diff.getbbox()
    if not bbox:
        return
    left, top, right, bottom = bbox
    left = max(0, left - MARGIN)
    top = max(0, top - MARGIN)
    right = min(im.width, right + MARGIN)
    bottom = min(im.height, bottom + MARGIN)
    im.crop((left, top, right, bottom)).save(png)


def main() -> None:
    edge = find_edge()
    sources = sorted(glob.glob(os.path.join(SRC_DIR, "*.wmd.md")))
    if not sources:
        sys.exit(f"No *.wmd.md sources in {SRC_DIR}")
    for src in sources:
        name = os.path.basename(src)[: -len(".wmd.md")]
        html = os.path.join(SRC_DIR, name + ".html")
        png = os.path.join(OUT_DIR, "wireframe-" + name + ".png")
        print(f"  {os.path.basename(src)} -> {os.path.relpath(png, BASE)}")
        render_html(src, html)
        screenshot(edge, html, png)
        autocrop(png)
    print("\nDone.")


if __name__ == "__main__":
    main()
