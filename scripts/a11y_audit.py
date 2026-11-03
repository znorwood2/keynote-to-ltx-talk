#!/usr/bin/env python3
"""Accessibility audit for compiled (tagged) ltx-talk PDFs.

    python3 a11y_audit.py deck-student.pdf [more.pdf ...]
    python3 a11y_audit.py --json - deck.pdf

Checks what LMS checkers such as Anthology Ally flag, from the PDF itself:
  - text painted in a color below WCAG AA against white (4.5:1; 3:1 at >= 18pt),
    including text painted fully or partly transparent (ltx-talk hides
    not-yet-revealed overlay content that way; in handouts it means hidden
    answers are still in the file)
  - white / very light text (flagged even when it sits on a dark box)
  - Figure structure elements without /Alt or /ActualText
  - Table structure elements without any TH cell
  - document language and title
It assumes a white page: text on colored fills is reported conservatively.

Requires pypdf (pip install pypdf). Exit status 1 if any problem is found.
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    from pypdf import PdfReader
    from pypdf.generic import ContentStream, IndirectObject
except ImportError:
    sys.exit("a11y_audit.py needs pypdf: pip install pypdf")

TEXT_OPS = {b"Tj", b"TJ", b"'", b'"'}


def lum(rgb):
    def ch(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(rgb, alpha=1.0):
    # blend toward the white page by the fill alpha
    rgb = tuple(alpha * c + (1 - alpha) for c in rgb)
    return 1.05 / (lum(rgb) + 0.05)


def to_rgb(vals):
    vals = [float(v) for v in vals]
    if len(vals) == 1:
        return (vals[0],) * 3
    if len(vals) == 3:
        return tuple(vals)
    if len(vals) == 4:
        c, m, y, k = vals
        return tuple((1 - x) * (1 - k) for x in (c, m, y))
    return None


def scan(stream_owner, resources, reader, findings, page_no, depth=0):
    try:
        cs = ContentStream(stream_owner, reader)
    except Exception:
        return
    st = {"rgb": (0.0, 0.0, 0.0), "alpha": 1.0, "size": 10.0, "mode": 0}
    stack = []
    egs = resources.get("/ExtGState") if resources else None
    egs = egs.get_object() if egs is not None else {}
    xobjs = resources.get("/XObject") if resources else None
    xobjs = xobjs.get_object() if xobjs is not None else {}
    for operands, op in cs.operations:
        try:
            if op == b"q":
                stack.append(dict(st))
            elif op == b"Q" and stack:
                st = stack.pop()
            elif op in (b"g", b"rg", b"k"):
                st["rgb"] = to_rgb(operands)
            elif op in (b"sc", b"scn"):
                nums = [x for x in operands if not str(x).startswith("/")]
                st["rgb"] = to_rgb(nums) if nums else None
            elif op == b"cs":
                st["rgb"] = (0.0, 0.0, 0.0)
            elif op == b"gs":
                g = egs.get(operands[0]).get_object()
                if "/ca" in g:
                    st["alpha"] = float(g["/ca"])
            elif op == b"Tf":
                st["size"] = abs(float(operands[1]))
            elif op == b"Tr":
                st["mode"] = int(operands[0])
            elif op in TEXT_OPS:
                if st["mode"] in (3, 7) or st["rgb"] is None:
                    continue
                r = contrast(st["rgb"], st["alpha"])
                need = 3.0 if st["size"] >= 18 else 4.5
                key = None
                if st["alpha"] < 0.5:
                    key = "transparent text (hidden overlay or handout answer)"
                elif min(st["rgb"]) > 0.8:
                    key = "white or very light text"
                elif r < need:
                    key = "low-contrast text #%02X%02X%02X (%.2f:1)" % (tuple(round(255 * c) for c in st["rgb"]) + (r,))
                if key:
                    findings.setdefault(key, set()).add(page_no)
            elif op == b"Do" and depth < 6:
                xo = xobjs.get(operands[0])
                xo = xo.get_object() if xo is not None else None
                if xo is not None and xo.get("/Subtype") == "/Form":
                    res = xo.get("/Resources")
                    scan(xo, res.get_object() if res is not None else resources, reader, findings, page_no, depth + 1)
        except Exception:
            continue


def walk_struct(node, out, depth=0):
    if depth > 200:
        return
    node = node.get_object() if isinstance(node, IndirectObject) else node
    if isinstance(node, list):
        for k in node:
            walk_struct(k, out, depth + 1)
        return
    if not hasattr(node, "get"):
        return
    role = node.get("/S")
    if role == "/Figure":
        out["figures"] += 1
        if "/Alt" not in node and "/ActualText" not in node:
            out["figures_no_alt"] += 1
    if role == "/Table":
        th = []
        def find_th(n, d=0):
            n = n.get_object() if isinstance(n, IndirectObject) else n
            if isinstance(n, list):
                for k in n:
                    find_th(k, d + 1)
            elif hasattr(n, "get") and d < 60:
                if n.get("/S") == "/TH":
                    th.append(1)
                if "/K" in n:
                    find_th(n["/K"], d + 1)
        find_th(node.get("/K"))
        out["tables"] += 1
        if not th:
            out["tables_no_th"] += 1
    if "/K" in node:
        walk_struct(node["/K"], out, depth + 1)


def audit(path):
    reader = PdfReader(path)
    findings: dict[str, set[int]] = {}
    for i, page in enumerate(reader.pages, 1):
        res = page.get("/Resources")
        res = res.get_object() if res is not None else {}
        contents = page.get_contents()
        if contents is not None:
            scan(contents, res, reader, findings, i)
    root = reader.trailer["/Root"].get_object()
    s = {"figures": 0, "figures_no_alt": 0, "tables": 0, "tables_no_th": 0}
    if "/StructTreeRoot" in root:
        walk_struct(root["/StructTreeRoot"].get_object().get("/K"), s)
    info = reader.metadata or {}
    problems = []
    for k, pages in sorted(findings.items()):
        problems.append(f"{k}: pages {sorted(pages)[:10]}{' ...' if len(pages) > 10 else ''}")
    if s["figures_no_alt"]:
        problems.append(f"{s['figures_no_alt']} of {s['figures']} figures have no alt text")
    if s["tables_no_th"]:
        problems.append(f"{s['tables_no_th']} of {s['tables']} tables have no header (TH) cells")
    if "/StructTreeRoot" not in root:
        problems.append("PDF is not tagged")
    if "/Lang" not in root:
        problems.append("no document language")
    if not info.get("/Title"):
        problems.append("no document title")
    return {"pdf": path, "pages": len(reader.pages), "problems": problems, **s}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--json", help="write results as JSON ('-' for stdout)")
    a = ap.parse_args()
    results = [audit(p) for p in a.pdfs]
    if a.json:
        js = json.dumps(results, indent=1)
        sys.stdout.write(js + "\n") if a.json == "-" else open(a.json, "w").write(js)
    else:
        for r in results:
            status = "OK" if not r["problems"] else f"{len(r['problems'])} problem(s)"
            print(f"{r['pdf']}: {r['pages']} pages, {r['figures']} figures, {r['tables']} tables - {status}")
            for p in r["problems"]:
                print(f"   - {p}")
    sys.exit(1 if any(r["problems"] for r in results) else 0)


if __name__ == "__main__":
    main()
