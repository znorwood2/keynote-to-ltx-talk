#!/usr/bin/env python3
"""Read a Keynote (.key) file without Keynote and print what a conversion needs.

    python3 keynote_extract.py deck.key                 # human-readable report
    python3 keynote_extract.py deck.key --json out.json # machine-readable
    python3 keynote_extract.py deck.key --pdf deck.pdf  # also reconcile with an export
    python3 keynote_extract.py deck.key --media DIR     # also copy embedded media to DIR

For each slide, in show order: skip flag, thumbnail file, title and text (with
U+FFFC marking inline objects such as equations), the LaTeX source of every
equation (Keynote's own equation objects and LaTeXiT images, see latexit.py),
in reading order, the images it shows, hyperlinks, presenter notes, and its
builds: each build's effect and delivery plus the number of click steps. The predicted number of
exported PDF pages for a visible slide is clicks + 1 (Keynote's PDF export with
"each stage of builds" prints the state before the first click too).

Many instructors build by duplicating slides instead of using Keynote builds.
Consecutive slides with the same title are reported as a "run", marked
cumulative (each slide only adds to the previous one) or rearranged.

Never writes inside the .key; everything is read from the zip in memory.
--media writes copies of Data/ files under safe names (Keynote stores some
names, e.g. screenshots with U+202F, without the zip UTF-8 flag, which breaks
`unzip`); the JSON's image file names refer to those copies.

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
                type 3005 image            field 1.1.1 position (x, y float32),
                                           field 1.1.2 size, field 11 data id
                                           (Data/*-<id>.*), field 100 LaTeX source
                                           for Keynote equation objects
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from iwa import decode, iwa_stream, _varint  # noqa: E402
from latexit import read_latexit  # noqa: E402


def member_name(zi: zipfile.ZipInfo) -> str:
    """The member's real name: Keynote writes UTF-8 names without the UTF-8 flag."""
    if zi.flag_bits & 0x800:
        return zi.filename
    try:
        return zi.filename.encode("cp437").decode("utf-8")
    except UnicodeError:
        return zi.filename


def safe_name(name: str) -> str:
    """A file-system-safe version of a Data/ file name (used by --media)."""
    base = name.rsplit("/", 1)[-1]
    return re.sub(r"[^\w.\-]+", "_", base, flags=re.ASCII).strip("_") or "file"


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


def _floats(b: bytes) -> tuple[float, ...]:
    return tuple(struct.unpack("<f", v)[0] for _, wt, v in decode(b) if wt == 5)


def image_record(b: bytes, data: dict[int, tuple[zipfile.ZipFile, zipfile.ZipInfo]],
                 cache: dict) -> dict:
    """Position, size, file and any LaTeX source of a type-3005 image object."""
    img = {"file": None, "x": None, "y": None, "w": None, "h": None, "latex": None,
           "latex_from": None, "color": None}
    geom = find_in(b, (1, 1))
    if geom:
        pos, size = find_in(geom[0], (1,)), find_in(geom[0], (2,))
        if pos and len(_floats(pos[0])) == 2:
            img["x"], img["y"] = (round(v, 1) for v in _floats(pos[0]))
        if size and len(_floats(size[0])) == 2:
            img["w"], img["h"] = (round(v, 1) for v in _floats(size[0]))
    for s in fields(b).get(100, []):
        s = text_of(s)
        if s:
            img["latex"], img["latex_from"] = s, "equation"
    for v in find_in(b, (11, 1)):
        if not isinstance(v, int) or v not in data:
            continue
        zf, zi = data[v]
        img["file"] = safe_name(member_name(zi))
        if img["latex"] is None and zi.filename.lower().endswith(".pdf"):
            if zi.filename not in cache:
                cache[zi.filename] = read_latexit(zf.read(zi))
            lx = cache[zi.filename]
            if lx:
                img["latex"], img["latex_from"], img["color"] = lx["source"], "latexit", lx["color"]
    return img


def parse_slide(z: zipfile.ZipFile, names: dict[int, str], slide_id: int,
                data: dict | None = None, cache: dict | None = None) -> dict:
    data = data or {}
    cache = {} if cache is None else cache
    name = names.get(slide_id)
    info = {"slide_id": slide_id, "iwa": name, "texts": [], "equations": [], "images": [],
            "links": [], "builds": [], "clicks": 0, "automatic_steps": 0}
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
                info["images"].append(image_record(b, data, cache))
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
    # Reading order: top to bottom, then left to right (rows within ~20 pt).
    info["images"].sort(key=lambda im: (round((im["y"] or 0) / 20), im["x"] or 0))
    info["equations"] = [im["latex"] for im in info["images"] if im["latex"]]
    info["images"] = [im for im in info["images"] if im["file"] or im["latex"]]
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
    thumbs, data, cache = {}, {}, {}
    for zi in z.infolist():
        n = member_name(zi)
        m = re.match(r"Data/.*-(\d+)\.\w+$", n)
        if m:
            data[int(m.group(1))] = (z, zi)
        m = re.match(r"Data/st-.*-(\d+)\.\w+$", n)
        if m:
            thumbs[int(m.group(1))] = n
    slides = []

    def walk(nid, depth):
        node = next(b for t, b in doc[nid] if t == 4)
        f = fields(node)
        sid = ref(f[2][0])
        thumb_id = ref(f[16][0]) if 16 in f else None
        s = parse_slide(z, names, sid, data, cache)
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
            "slides": slides, "runs": find_runs(slides),
            "predicted_pdf_pages": sum(s["predicted_pages"] for s in slides)}


def _norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().casefold()


def _content(s: dict) -> tuple[set, set]:
    texts = {re.sub(r"\s+", " ", t).strip() for t in s["texts"]} - {"\ufffc", ""}
    return texts, {im["latex"] or im["file"] for im in s["images"]}


def find_runs(slides: list[dict]) -> list[dict]:
    """Consecutive visible slides with the same title (duplicated-slide builds).

    cumulative: every slide keeps all text and images of the one before it, so
    the run is one frame with one overlay state per slide. Otherwise
    rearranged_at lists the slides that drop or replace earlier content (a
    relayout, a swapped figure, or the start of a new example under the same
    title); look at those slides before deciding how to split the run.
    """
    runs, cur = [], []
    vis = [s for s in slides if not s["skipped"]]
    for s in vis + [None]:
        if cur and (s is None or _norm_title(s["title"]) != _norm_title(cur[-1]["title"])
                    or not _norm_title(s["title"])):
            if len(cur) > 1:
                changed = []
                for a, b in zip(cur, cur[1:]):
                    (ta, ia), (tb, ib) = _content(a), _content(b)
                    if not (ta <= tb and ia <= ib):
                        changed.append(b["number"])
                runs.append({"first": cur[0]["number"], "last": cur[-1]["number"],
                             "title": cur[0]["title"], "cumulative": not changed,
                             "rearranged_at": changed})
            cur = []
        if s is not None:
            cur.append(s)
    return runs


def write_media(key_path: str, outdir: str) -> list[str]:
    """Copy every Data/ file to outdir under safe_name(); return the names."""
    z = zipfile.ZipFile(key_path)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for zi in z.infolist():
        n = member_name(zi)
        if n.startswith("Data/") and not n.endswith("/"):
            dest = out / safe_name(n)
            dest.write_bytes(z.read(zi))
            written.append(dest.name)
    return written


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
    ap.add_argument("--media", metavar="DIR", help="copy embedded media (Data/) to DIR under safe names")
    a = ap.parse_args()
    d = extract(a.key)
    if a.media:
        n = len(write_media(a.key, a.media))
        print(f"copied {n} media files to {a.media}", file=sys.stderr)
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
        for im in s["images"]:
            if im["latex"]:
                tag = "eq" if im["latex_from"] == "equation" else "latexit"
                col = f" [color {im['color']}]" if im["color"] else ""
                print(f"        {tag}: {im['latex'][:100]!r}{col}")
            elif not re.match(r"(pasted-image-)?small-|.*-small-\d+\.", im["file"] or ""):
                print(f"        image: {im['file']}")
        for l in s["links"]:
            print(f"        link: {l}")
    for r in d["runs"]:
        kind = "cumulative" if r["cumulative"] else \
            "content dropped or replaced at slide " + ", ".join(map(str, r["rearranged_at"]))
        print(f"run: slides {r['first']}-{r['last']} {r['title'][:40]!r} ({kind})")
    print(f"predicted build-expanded PDF pages (non-skipped slides): {d['predicted_pdf_pages']}")
    if a.pdf:
        print(f"{a.pdf}: {d['pdf_pages']} pages, created {d['pdf_created']}")
        if d["pdf_pages"] != d["predicted_pdf_pages"]:
            print("  MISMATCH: the .key's skip flags or builds changed after the export, or"
                  " a build model edge case; compare slide by slide.")


if __name__ == "__main__":
    main()
