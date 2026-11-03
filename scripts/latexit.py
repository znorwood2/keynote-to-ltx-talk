#!/usr/bin/env python3
"""Read the LaTeX source that LaTeXiT embeds in the equation images it makes.

Many instructors typeset math in LaTeXiT and paste the result into Keynote,
where it is stored as an ordinary image (Data/pasted-image-<id>.pdf). LaTeXiT
hides its settings in that PDF as invisible text:

    <latexit sha1_base64="...">BASE64</latexit>

BASE64 decodes to a 4-byte big-endian length followed by zlib data, which
inflates to a binary property list with keys such as `source`, `preamble`,
`color` (RGBA floats as text), `mode`/`type` and `version`.

    python3 latexit.py pasted-image-647.pdf ...   # print each image's source

No dependencies beyond the Python standard library.
"""
from __future__ import annotations

import base64
import plistlib
import re
import sys
import zlib
from pathlib import Path

_STREAM = re.compile(rb"stream\r?\n")
_BLOB = re.compile(r"<latexit[^>]*>\s*([A-Za-z0-9+/=\s]+?)\s*</latexit>", re.S)


def _pdf_strings(pdf: bytes) -> str:
    """Concatenated literal strings of every (inflatable) content stream."""
    out = []
    for m in _STREAM.finditer(pdf):
        end = pdf.find(b"endstream", m.end())
        try:
            data = zlib.decompress(pdf[m.end():end])
        except zlib.error:
            data = pdf[m.end():end]
        if b"latexit" not in data:
            continue
        # Literal strings: (...) with \-escapes. Base64 never contains parentheses.
        for s in re.findall(rb"\(((?:\\.|[^\\)])*)\)", data, re.S):
            out.append(re.sub(rb"\\(.)", rb"\1", s).decode("latin-1"))
    return "".join(out)


def _inflate(raw: bytes) -> bytes | None:
    for start in (4, 0):
        for wbits in (15, -15):
            try:
                return zlib.decompress(raw[start:], wbits)
            except zlib.error:
                pass
    return None


def read_latexit(pdf: bytes) -> dict | None:
    """Return {'source', 'color', 'mode', 'preamble'} for a LaTeXiT PDF, else None."""
    if b"latexit" not in pdf and b"stream" not in pdf:
        return None
    m = _BLOB.search(_pdf_strings(pdf))
    if not m:
        return None
    raw = base64.b64decode(re.sub(r"\s", "", m.group(1)) + "==", validate=False)
    data = _inflate(raw)
    if data is None:
        return None
    try:
        p = plistlib.loads(data)
    except Exception:
        return None
    src = str(p.get("source", "")).strip()
    # Display-mode sources carry their own \[ ... \] wrapper; strip it.
    w = re.fullmatch(r"\\\[(.*)\\\]", src, re.S)
    if w:
        src = w.group(1).strip()
    color = None
    try:
        rgb = [float(x) for x in str(p.get("color", "")).split()[:3]]
        if len(rgb) == 3 and any(c > 0.001 for c in rgb):
            color = "#%02X%02X%02X" % tuple(round(c * 255) for c in rgb)
    except ValueError:
        pass
    return {"source": src, "color": color, "mode": p.get("mode", p.get("type")),
            "preamble": p.get("preamble")}


def main():
    for path in sys.argv[1:]:
        info = read_latexit(Path(path).read_bytes())
        if not info:
            print(f"{path}: no LaTeXiT source")
        else:
            col = f"  [color {info['color']}]" if info["color"] else ""
            print(f"{path}: {info['source']}{col}")


if __name__ == "__main__":
    main()
