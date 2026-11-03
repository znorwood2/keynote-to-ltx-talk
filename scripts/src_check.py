#!/usr/bin/env python3
"""Source-level checks for converted ltx-talk decks.

    python3 src_check.py deck.tex [more.tex ...] [--palette black,blue,violet,accentred,...]

Reports:
  - tikzpicture / \\tikz without an explicit tagging class in its options
    (alt={...}, artifact, actualtext=..., or tagging-setup=text)
  - \\includegraphics without alt={...}
  - tabular without a table/... \\tagpdfsetup in the preceding lines
    (header-rows / header-columns for data tables, tagging=div for layout)
  - text colors outside the palette in \\textcolor, \\color, text=, color=
  - \\uncover<... | handout:N> (handout builds keep the content as transparent
    text; use \\only<handout:N>{\\uncover<...>{...}} so it is omitted)
  - absolute overlay numbers such as <2-> (prefer relative <+-> / <.->)
Comments and anything after \\end{document} are ignored. Exit status 1 if any
problem is found. A flag can be a false positive (e.g. a table whose
\\tagpdfsetup sits further up); check the compiled PDF with a11y_audit.py.
"""
from __future__ import annotations

import argparse
import re
import sys

DEFAULT_PALETTE = "black,white,blue,violet,accentred,accentgreen,accentorange"
CLASSIFIED = re.compile(r"\balt\s*=|\bartifact\b|actualtext|tagging-setup\s*=\s*\{?\s*text")


def strip_comments(src: str) -> str:
    out = []
    for line in src.split("\n"):
        m = re.search(r"(?<!\\)%", line)
        out.append(line[: m.start()] if m else line)
    return "\n".join(out)


def bracket_arg(s: str, i: int) -> tuple[str, int]:
    """If s[i:] starts (after spaces) with [...], return its contents and end."""
    j = i
    while j < len(s) and s[j] in " \t\n":
        j += 1
    if j >= len(s) or s[j] != "[":
        return "", i
    depth, k = 0, j
    while k < len(s):
        c = s[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "]" and depth == 0:
            return s[j + 1:k], k + 1
        k += 1
    return s[j + 1:], len(s)


def check(path: str, palette: set[str]) -> list[str]:
    raw = open(path).read()
    src = strip_comments(raw)
    m = re.search(r"^\\end\s*\{document\}", src, re.M)
    src = src[: m.start()] if m else src
    line_of = lambda pos: src.count("\n", 0, pos) + 1  # noqa: E731
    probs = []
    for m in re.finditer(r"\\begin\s*\{tikzpicture\}|\\tikz(?![a-zA-Z])", src):
        opts, _ = bracket_arg(src, m.end())
        if not CLASSIFIED.search(opts):
            probs.append(f"{line_of(m.start())}: picture without alt/artifact/tagging-setup=text")
    for m in re.finditer(r"\\includegraphics\s*(\[)?", src):
        opts, _ = bracket_arg(src, m.end() - (1 if m.group(1) else 0))
        if "alt" not in opts:
            probs.append(f"{line_of(m.start())}: \\includegraphics without alt")
    for m in re.finditer(r"\\begin\s*\{tabular", src):
        before = src[max(0, m.start() - 600):m.start()]
        if "table/" not in before and "table-tagging" not in before:
            probs.append(f"{line_of(m.start())}: tabular without a nearby table/ \\tagpdfsetup")
    for m in re.finditer(r"\\(?:textcolor|color)\s*(?:<[^>]*>)?\s*\{([^}]*)\}|[\[,{]\s*(?:text|color)\s*=\s*([A-Za-z][\w!.]*)", src):
        name = (m.group(1) or m.group(2) or "").strip()
        base = name.split("!")[0]
        if base and base not in palette:
            probs.append(f"{line_of(m.start())}: text color '{name}' not in palette")
        elif "!" in name and base not in ("white",):
            probs.append(f"{line_of(m.start())}: tinted text color '{name}' (check contrast)")
    for m in re.finditer(r"\\uncover\s*<[^>]*\|\s*handout:\d+\s*>", src):
        probs.append(f"{line_of(m.start())}: \\uncover with handout spec leaves transparent text; use \\only<handout:N>{{\\uncover<..>{{..}}}}")
    for m in re.finditer(r"<\s*\d+\s*-?\s*\d*\s*(?:\|[^>]*)?>", src):
        ctx = src[max(0, m.start() - 12):m.start()]
        if re.search(r"\\(?:only|uncover|visible|invisible|alt|item|alert|textcolor|onslide|temporal|pause)\s*$|\]\s*$|item\s*$", ctx):
            probs.append(f"{line_of(m.start())}: absolute overlay spec {m.group(0)} (prefer relative)")
    return probs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--palette", default=DEFAULT_PALETTE, help="comma-separated allowed text colors")
    a = ap.parse_args()
    palette = {c.strip() for c in a.palette.split(",") if c.strip()}
    bad = 0
    for f in a.files:
        probs = check(f, palette)
        bad += bool(probs)
        print(f"== {f}: {len(probs)} problem(s)")
        for p in probs:
            print("   ", p)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
