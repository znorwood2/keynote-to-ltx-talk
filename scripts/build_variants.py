#!/usr/bin/env python3
"""Build the standard PDF variants of an ltx-talk deck without editing it.

    python3 build_variants.py deck.tex                    # instr-anim, instr-handout, student
    python3 build_variants.py deck.tex --solutions        # also solutions-anim, solutions-handout
    python3 build_variants.py deck.tex --only student     # just one
    python3 build_variants.py deck.tex --outdir build/ --passes 3

Variants (suffix: handout class option, instructor, instructorsolutions):
    instr-anim           no   on   (as in source)
    instr-handout        yes  on   (as in source)
    student              yes  off  (as in source)
    solutions-anim       no   on   on
    solutions-handout    yes  on   on

Each variant is compiled from a temporary copy next to the source (so relative
\\graphicspath entries resolve) and the copy is removed afterwards unless the build fails. Output (PDF, and
logs only on failure) goes to --outdir, default next to the source. The source needs:
  - a one-line \\documentclass[...]{ltx-talk}
  - \\newtoggle{instructor} (and \\newtoggle{instructorsolutions} for --solutions)
  - lines beginning \\toggletrue{...} / \\togglefalse{...} for those toggles
    in the document body.

Compatible with the instructor-made `slidemake` tool this is modeled on: the
first three variants have the same file names.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DOCCLASS = re.compile(r"\\documentclass\s*(?:\[(?P<opts>[^\]]*)\])?(?:\s*%[^\n]*\n)*\s*\{\s*ltx-talk\s*\}")
VARIANTS = {
    "instr-anim": (False, True, None),
    "instr-handout": (True, True, None),
    "student": (True, False, None),
    "solutions-anim": (False, True, True),
    "solutions-handout": (True, True, True),
}
AUX = [".aux", ".log", ".out", ".toc", ".nav", ".snm", ".vrb", ".synctex.gz", "-luamml-mathml.html"]


def set_handout(src: str, on: bool) -> str:
    m = DOCCLASS.search(src)
    if not m:
        raise SystemExit("error: no \\documentclass[...]{ltx-talk} found")
    opts = [o.strip() for o in (m.group("opts") or "").split(",") if o.strip() and o.strip() != "handout"]
    if on:
        opts.append("handout")
    new = "\\documentclass" + (f"[{', '.join(opts)}]" if opts else "") + "{ltx-talk}"
    return src[: m.start()] + new + src[m.end():]


def set_toggle(src: str, name: str, value: bool) -> str:
    pat = re.compile(r"(?m)^(?P<i>[ \t]*)\\toggle(?:true|false)\s*\{\s*" + re.escape(name) + r"\s*\}")
    cmd = ("\\toggletrue{%s}" if value else "\\togglefalse{%s}") % name
    if pat.search(src):
        return pat.sub(lambda m: m.group("i") + cmd, src)
    m = re.search(r"\\begin\s*\{\s*document\s*\}", src)
    return src[: m.end()] + "\n" + cmd + src[m.end():]


def build(source: Path, variant: str, passes: int, engine: str, outdir: Path) -> Path:
    handout, instructor, solutions = VARIANTS[variant]
    text = source.read_text()
    if not re.search(r"\\(?:newtoggle|providetoggle)\s*\{\s*instructor\s*\}", text):
        raise SystemExit("error: the deck has no \\newtoggle{instructor}")
    text = set_handout(text, handout)
    text = set_toggle(text, "instructor", instructor)
    if solutions is not None:
        if not re.search(r"\\(?:newtoggle|providetoggle)\s*\{\s*instructorsolutions\s*\}", text):
            raise SystemExit("error: --solutions needs \\newtoggle{instructorsolutions}")
        text = set_toggle(text, "instructorsolutions", solutions)
    base = f"{source.stem}-{variant}"
    tmp = source.with_name(base + ".tex")
    tmp.write_text(text)
    # Compile straight into outdir so nothing next to the source (for example
    # PDFs from an earlier build) is touched when outdir is elsewhere.
    outdir.mkdir(parents=True, exist_ok=True)
    result = None
    for _ in range(passes):
        result = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error",
                                 f"-output-directory={outdir}", tmp.name],
                                cwd=source.parent, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            break
    pdf = outdir / (base + ".pdf")
    if result is None or result.returncode != 0 or not pdf.exists():
        tail = "\n".join(result.stdout.decode("utf-8", "replace").splitlines()[-40:]) if result else ""
        raise SystemExit(f"error: {engine} failed for {tmp.name} (kept; log in {outdir})\n{tail}")
    for ext in AUX:
        p = outdir / (base + ext)
        if p.exists():
            p.unlink()
    tmp.unlink()
    return pdf


def pages(pdf: Path) -> str:
    try:
        out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
        return re.search(r"Pages:\s+(\d+)", out).group(1)
    except Exception:
        return "?"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("--solutions", action="store_true", help="also build the two solutions variants")
    ap.add_argument("--only", choices=sorted(VARIANTS), action="append", help="build just these variants")
    ap.add_argument("--passes", type=int, default=3, help="LaTeX runs per variant (default 3; tikzmark needs >= 2)")
    ap.add_argument("--engine", default="lualatex")
    ap.add_argument("--outdir", help="move the PDFs here (default: next to the source)")
    a = ap.parse_args()
    source = Path(a.source).expanduser().resolve()
    if not source.exists():
        sys.exit(f"error: {a.source} not found")
    names = a.only or (list(VARIANTS) if a.solutions else ["instr-anim", "instr-handout", "student"])
    outdir = Path(a.outdir).resolve() if a.outdir else source.parent
    for v in names:
        print(f"building {source.stem}-{v} ...", flush=True)
        pdf = build(source, v, a.passes, a.engine, outdir)
        print(f"  wrote {pdf} ({pages(pdf)} pages)")


if __name__ == "__main__":
    main()
