#!/usr/bin/env python3
"""Contact sheets for reviewing conversions.

  All pages of one PDF, in order:
    python3 contact_sheet.py sheet.png deck.pdf

  Source vs. output side by side, in source-page order:
    python3 contact_sheet.py review.png source.pdf output.pdf --map map.txt

  map.txt has one line per source page: "<source page> <output page or label>",
  e.g.
      1 1
      2 archival
      3 2
      4 collapsed
      5 3
  A non-numeric second column draws a gray placeholder with that label
  (collapsed title-only state, archival slide, solutions-only, ...).

Options: --width (pixels per page, default 480; source and output pages are
scaled to the same width), --per-sheet N (split into review-1.png, -2, ...),
--cols. Needs poppler (pdftoppm) and ImageMagick (magick).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",          # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       # Debian/Ubuntu
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",     # Fedora
    "C:/Windows/Fonts/arial.ttf",
]
FONT = next((["-font", f] for f in FONT_CANDIDATES if Path(f).exists()), [])


def need(tool):
    if not shutil.which(tool):
        sys.exit(f"contact_sheet.py needs {tool} on PATH")


_ids: dict[str, int] = {}


def render(pdf: str, page: int, width: int, out: Path) -> Path:
    # Name renders by an index per PDF (file names like "4.6-anim-qr" confuse
    # suffix handling, and source/output stems may coincide).
    tag = _ids.setdefault(pdf, len(_ids))
    stem = out / f"pdf{tag}-p{page}"
    subprocess.run(["pdftoppm", "-scale-to-x", str(width), "-scale-to-y", "-1", "-png", "-f", str(page), "-l", str(page),
                    "-singlefile", pdf, str(stem)], check=True)
    return Path(str(stem) + ".png")


def pages(pdf: str) -> int:
    out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    return int(next(l.split()[1] for l in out.splitlines() if l.startswith("Pages:")))


def placeholder(like: Path, label: str, out: Path) -> Path:
    p = out / f"ph-{abs(hash((label, str(like))))}.png"
    size = subprocess.run(["magick", "identify", "-format", "%wx%h", str(like)],
                          capture_output=True, text=True).stdout.strip()
    subprocess.run(["magick", "-size", size, "xc:#d8d8d8", *FONT, "-gravity", "center", "-pointsize", "14",
                    "-annotate", "0", label, str(p)], check=True)
    return p


def montage(tiles: list[tuple[Path, str]], cols: int, dest: Path):
    args = ["magick", "montage", *FONT]
    for img, label in tiles:
        args += ["-label", label, str(img)]
    args += ["-tile", f"{cols}x", "-geometry", "+4+4", "-pointsize", "11", "-background", "white", str(dest)]
    subprocess.run(args, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dest")
    ap.add_argument("source")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--map")
    ap.add_argument("--width", type=int, default=480, help="pixel width of each rendered page (default 480)")
    ap.add_argument("--per-sheet", type=int, default=18)
    ap.add_argument("--cols", type=int)
    a = ap.parse_args()
    need("pdftoppm")
    need("magick")
    tmp = Path(tempfile.mkdtemp(prefix="sheet-"))
    tiles: list[tuple[Path, str]] = []
    if not a.output:
        for p in range(1, pages(a.source) + 1):
            tiles.append((render(a.source, p, a.width, tmp), f"p{p}"))
        cols = a.cols or 6
    else:
        if a.map:
            rows = [l.split(None, 1) for l in Path(a.map).read_text().splitlines() if l.strip()]
        else:  # one-to-one
            rows = [[str(p), str(p)] for p in range(1, pages(a.source) + 1)]
        for src_page, target in rows:
            s = render(a.source, int(src_page), a.width, tmp)
            if target.strip().isdigit():
                o = render(a.output, int(target), a.width, tmp)
                label = f"src {src_page} | out {target.strip()}"
            else:
                o = placeholder(s, target.strip(), tmp)
                label = f"src {src_page} | {target.strip()}"
            pair = tmp / f"pair-{src_page}.png"
            subprocess.run(["magick", str(s), str(o), "+append", str(pair)], check=True)
            tiles.append((pair, label))
        cols = a.cols or 3
    dest = Path(a.dest)
    chunks = [tiles[i:i + a.per_sheet] for i in range(0, len(tiles), a.per_sheet)] or [[]]
    for n, chunk in enumerate(chunks, 1):
        d = dest if len(chunks) == 1 else dest.with_name(f"{dest.stem}-{n}{dest.suffix}")
        montage(chunk, cols, d)
        print(f"wrote {d}")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
