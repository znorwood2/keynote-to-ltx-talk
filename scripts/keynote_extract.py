#!/usr/bin/env python3
"""Read a Keynote (.key) file without Keynote and print what a conversion needs.

    python3 keynote_extract.py deck.key                 # human-readable report
    python3 keynote_extract.py deck.key --json out.json # machine-readable
    python3 keynote_extract.py deck.key --pdf deck.pdf  # also reconcile with an export

For each slide, in show order: skip flag, thumbnail file, title and text (with
U+FFFC marking inline objects such as equations), the LaTeX source of every
equation object, hyperlinks, presenter notes, and its builds: each build's
effect and delivery plus the number of click steps. The predicted number of
exported PDF pages for a visible slide is clicks + 1 (Keynote's PDF export with
"each stage of builds" prints the state before the first click too).

Never writes inside the .key; everything is read from the zip in memory.

Field meanings below were reverse-engineered from Keynote 13/14 files
(2023-2026) and checked against build-expanded PDF exports:
  Document.iwa  type 2  ShowArchive        field 3 (inline) -> slide list (field 2 refs)
                type 4  SlideNodeArchive   field 2 slide ref, field 4 skipped (1),
                                           field 16 thumbnail data id (Data/st-*-<id>.jpg)
  Slide-*.iwa   type 5  SlideArchive       field 5 title placeholder, field 43 build-chunk
                                           refs (in order)
                type 8  BuildArchive       field 1 drawable ref, field 2 delivery,
                                           field 4.18.2 effect id
                type 153 BuildChunkArchive field 1 build ref, field 5 automatic (1)
                                           vs. on click (0)
                type 2001 TSWP storage     field 3 text
                type 2032 hyperlink field  field 2 URL
                type 3005 equation         field 100 LaTeX source
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iwa import decode, iwa_stream, _varint  # noqa: E402


def read_iwa_bytes(raw: bytes) -> dict[int, list[tuple[int, bytes]]]:
    data = iwa_stream(raw)
    objs: dict[int, list[tuple[int, bytes]]] = {}
    i = 0
    while i < len(data):
        n, i = _varint(data, i)
        info = decode(data[i:i + n])
        i += n
        ident = next(v for f, _, v in info if f == 1)
        entry = []
        for f, _, mi in info:
            if f != 2:
                continue
            m = decode(mi)
            mtype = next(v for g, _, v in m if g == 1)
            mlen = next(v for g, _, v in m if g == 3)
            entry.append((mtype, data[i:i + mlen]))
            i += mlen
        objs[ident] = entry
    return objs


def ref(b: bytes) -> int | None:
    for f, _, v in decode(b):
        if f == 1:
            return v
    return None


def fields(b: bytes) -> dict[int, list]:
    out: dict[int, list] = {}
    for f, _, v in decode(b):
        out.setdefault(f, []).append(v)
    return out


def text_of(v: bytes) -> str | None:
    try:
        s = v.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return s if all(c.isprintable() or c in "\n\t  ￼" for c in s) else None


def find_in(b: bytes, path: tuple[int, ...]):
    """Values at a nested field path inside a message."""
    cur = [b]
    for k in path:
        nxt = []
        for m in cur:
            try:
                nxt += [v for f, wt, v in decode(m) if f == k]
            except Exception:
                pass
        cur = nxt
    return cur


def _varints(b: bytes, depth: int = 0):
    """All varint values in a message and its nested messages (candidate refs)."""
    try:
        d = decode(b)
    except Exception:
        return
    for _, wt, v in d:
        if wt == 0:
            yield v
        elif wt == 2 and depth < 12:
            yield from _varints(v, depth + 1)


def slide_record(objs, slide_id):
    for t, b in objs.get(slide_id, []):
        if t == 5:
            return b
    for v in objs.values():
        for t, b in v:
            if t == 5:
                return b
    return None


def parse_slide(z: zipfile.ZipFile, names: dict[int, str], slide_id: int) -> dict:
    name = names.get(slide_id)
    info = {"slide_id": slide_id, "iwa": name, "texts": [], "equations": [], "links": [],
            "builds": [], "clicks": 0, "automatic_steps": 0}
    if not name:
        return info
    objs = read_iwa_bytes(z.read(name))
    by_id = {k: v for k, v in objs.items()}
    # A shared file (e.g. Index/Slide.iwa) can hold several slides' objects:
    # keep only those reachable from this slide's record.
    if slide_id in objs:
        keep, todo = set(), [slide_id]
        while todo:
            oid = todo.pop()
            if oid in keep or oid not in objs:
                continue
            keep.add(oid)
            for _, payload in objs[oid]:
                todo.extend(i for i in _varints(payload) if i in objs and i not in keep)
        objs = {k: v for k, v in objs.items() if k in keep}
    builds = {}
    for k, v in objs.items():
        for t, b in v:
            if t == 2001:
                for s in fields(b).get(3, []):
                    s = text_of(s)
                    if s and s.strip():
                        info["texts"].append(s)
            elif t == 3005:
                for s in fields(b).get(100, []):
                    s = text_of(s)
                    if s:
                        info["equations"].append(s)
            elif t == 2032:
                for s in fields(b).get(2, []):
                    s = text_of(s)
                    if s:
                        info["links"].append(s)
            elif t == 8:
                f = fields(b)
                eff = [text_of(x) for x in find_in(b, (4, 18, 2))]
                builds[k] = {"delivery": text_of(f.get(2, [b""])[0]) or "",
                             "effect": next((e for e in eff if e), ""), "steps": 0, "clicks": 0}
    srec = slide_record(objs, slide_id)
    if srec is not None:
        for chunk_ref in fields(srec).get(43, []):
            cid = ref(chunk_ref)
            for t, b in by_id.get(cid, []):
                if t != 153:
                    continue
                f = {g: x for g, w, x in decode(b) if w == 0}
                bref = ref(fields(b).get(1, [b""])[0])
                automatic = f.get(5, 0) == 1
                if automatic:
                    info["automatic_steps"] += 1
                else:
                    info["clicks"] += 1
                if bref in builds:
                    builds[bref]["steps"] += 1
                    builds[bref]["clicks"] += 0 if automatic else 1
        # Title: the text of the title placeholder (slide field 5) when present.
        tref = fields(srec).get(5)
        if tref:
            seen, todo = set(), [ref(tref[0])]
            while todo and "title" not in info:
                oid = todo.pop(0)
                if oid in seen or oid not in by_id:
                    continue
                seen.add(oid)
                for t, b in by_id[oid]:
                    if t == 2001:
                        txt = [text_of(x) for x in fields(b).get(3, [])]
                        txt = [x for x in txt if x and x.strip()]
                        if txt:
                            info["title"] = txt[0]
                    todo.extend(i for i in _varints(b) if i in by_id and i not in seen)
    info["builds"] = list(builds.values())
    info["links"] = sorted(set(info["links"]))
    return info


def extract(key_path: str) -> dict:
    z = zipfile.ZipFile(key_path)
    names = {}
    for n in z.namelist():
        m = re.match(r"Index/(?:Slide|TemplateSlide)-(\d+)\.iwa$", n)
        if m:
            names[int(m.group(1))] = n
    # Most slides live in Index/Slide-<id>.iwa; some (often the first) live in
    # files without the id in the name, e.g. Index/Slide.iwa. Index those by
    # the object ids they contain.
    for n in z.namelist():
        if re.match(r"Index/(?:Slide|TemplateSlide)[^/]*\.iwa$", n) and not re.search(r"-\d+\.iwa$", n):
            try:
                for oid in read_iwa_bytes(z.read(n)):
                    names.setdefault(oid, n)
            except Exception:
                pass
    doc = read_iwa_bytes(z.read("Index/Document.iwa"))
    show = next(b for v in doc.values() for t, b in v if t == 2)
    tree = fields(show).get(3, [b""])[0]
    node_ids = [ref(v) for v in fields(tree).get(2, [])]
    thumbs = {}
    for n in z.namelist():
        m = re.match(r"Data/st-.*-(\d+)\.\w+$", n)
        if m:
            thumbs[int(m.group(1))] = n
    slides = []

    def walk(nid, depth):
        node = next(b for t, b in doc[nid] if t == 4)
        f = fields(node)
        sid = ref(f[2][0])
        thumb_id = ref(f[16][0]) if 16 in f else None
        s = parse_slide(z, names, sid)
        s.update({"number": len(slides) + 1, "skipped": bool(f.get(4, [0])[0]),
                  "depth": depth, "thumbnail": thumbs.get(thumb_id)})
        if not s.get("title"):
            s["title"] = s["texts"][0] if s["texts"] else ""
        s["predicted_pages"] = 0 if s["skipped"] else s["clicks"] + 1
        slides.append(s)
        for child in f.get(1, []):
            walk(ref(child), depth + 1)

    for nid in node_ids:
        walk(nid, 0)
    times = [zi.date_time for zi in z.infolist() if zi.filename.startswith("Index/Document")]
    return {"key": key_path, "saved": "%04d-%02d-%02d %02d:%02d:%02d" % times[0] if times else None,
            "slides": slides,
            "predicted_pdf_pages": sum(s["predicted_pages"] for s in slides)}


def pdf_info(pdf: str) -> tuple[int | None, str | None]:
    try:
        out = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return None, None
    pages = re.search(r"^Pages:\s+(\d+)", out, re.M)
    created = re.search(r"^CreationDate:\s+(.*)$", out, re.M)
    return (int(pages.group(1)) if pages else None), (created.group(1).strip() if created else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("key")
    ap.add_argument("--pdf", help="build-expanded PDF export to reconcile against")
    ap.add_argument("--json", help="write full extraction as JSON ('-' for stdout)")
    a = ap.parse_args()
    d = extract(a.key)
    if a.pdf and not Path(a.pdf).exists():
        sys.exit(f"error: {a.pdf} not found")
    if a.pdf:
        d["pdf_pages"], d["pdf_created"] = pdf_info(a.pdf)
    if a.json:
        js = json.dumps(d, indent=1, ensure_ascii=False)
        (sys.stdout.write(js + "\n") if a.json == "-" else Path(a.json).write_text(js))
        if a.json == "-":
            return
    print(f"{a.key}: {len(d['slides'])} slides; .key saved {d['saved']} (zip time)")
    for s in d["slides"]:
        b = "; ".join(f"{x['delivery'] or '?'} {x['effect']} x{x['clicks']}" for x in s["builds"] if x["steps"])
        title = s["title"].replace("\n", " ")[:60]
        print(f"{s['number']:3} {'SKIP' if s['skipped'] else '    '} clicks={s['clicks']:2}"
              f"{'+' + str(s['automatic_steps']) + 'auto' if s['automatic_steps'] else ''}"
              f"  {title!r}" + (f"  builds: {b}" if b else ""))
        for e in s["equations"]:
            print(f"        eq: {e[:100]!r}")
        for l in s["links"]:
            print(f"        link: {l}")
    print(f"predicted build-expanded PDF pages (non-skipped slides): {d['predicted_pdf_pages']}")
    if a.pdf:
        print(f"{a.pdf}: {d['pdf_pages']} pages, created {d['pdf_created']}")
        if d["pdf_pages"] != d["predicted_pdf_pages"]:
            print("  MISMATCH: the .key's skip flags or builds changed after the export, or"
                  " a build model edge case; compare slide by slide.")


if __name__ == "__main__":
    main()
