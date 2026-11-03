# Reading Keynote files

A `.key` file is a zip archive. `scripts/keynote_extract.py` reads it in memory (never modify the original) and prints what a conversion needs:

```bash
python3 scripts/keynote_extract.py deck.key                       # report
python3 scripts/keynote_extract.py deck.key --pdf deck-export.pdf # + reconcile
python3 scripts/keynote_extract.py deck.key --json -              # everything as JSON
```

For each slide in show order you get the skip flag, thumbnail file, title and text, the LaTeX source of each equation, links, builds (delivery such as "By Paragraph", effect, and click steps), and the predicted number of export pages (`clicks + 1` for visible slides). No dependencies beyond Python 3.

Don't drive Keynote itself through AppleScript: it is slow, can hang, and isn't needed.

## What is where

- `Index/Document.iwa`: the show and its slide list. Each slide node has the skip flag and a thumbnail data ID.
- `Index/Slide-<id>.iwa`: one per slide. Text storages hold the slide's text, with U+FFFC (`￼`) marking each inline object, usually an equation; equation objects hold their LaTeX source; hyperlink fields hold URLs; the build list holds the click order.
- `Data/`: embedded media. Slide thumbnails are `Data/st-<uuid>-<id>.jpg`; images keep their original names plus `-<id>`. Animated GIFs come with a `posterImage-*.png` still frame.
- `Metadata/`, `preview*.jpg`: document metadata and the first-slide preview.

The `.iwa` format is Snappy-compressed protobuf without a published schema. The field meanings in `keynote_extract.py`'s docstring were reverse-engineered from Keynote 13/14 files, 2023–2026. They were checked by predicting the page count of 8 build-expanded exports exactly. If a future Keynote changes the format, the `--pdf` check is what will tell you.

## The build model

- A build animates one object. "By Paragraph" or "By Bullet" builds have one step per paragraph; "All at Once" has one.
- Each step is either **on click** or **automatic** ("with previous" / "after previous"). Only clicks create new states in a build-expanded export, so a visible slide exports `clicks + 1` pages; the first is the state before any click. Automatic steps join the previous state.
- When the first state shows only the title, collapse it (conversion standard), so that slide becomes `clicks` output states.
- The click count is reliable for slides that were never exported (prompt copies, skipped solutions). Use it, and the slide's thumbnail (its final state), to build those frames.

## Reconciling with an export

`--pdf` compares the predicted page count with the export and prints the export's creation date next to the `.key`'s save time. A mismatch almost always means one of these:
- **Skip flags changed after export.** This is common: the instructor re-flagged prompt/worked pairs or exported with skipped slides shown. See "Prompt/worked slide pairs" in the conversion standard.
- **The export included skipped slides.** Keynote can print skipped slides; their pages appear in the PDF.
- **The deck was edited after export** (builds added or removed). Trust the `.key` for content, and the export for what was shown at the time; record the difference.

Find the exact slide by comparing per-slide predictions with the export pages' titles (`pdftotext -f N -l N`).

## Rendering exports

Keynote exports are 1920×1080 points and slow to rasterize at high resolution. Render only the pages you need, scaled to a width: `pdftoppm -scale-to-x 800 -scale-to-y -1 -f N -l N -png export.pdf out`. If `pdftoppm` stalls on a page, Ghostscript works (`gs -sDEVICE=png16m -r40 -dFirstPage=N -dLastPage=N -o out.png export.pdf`), though it may drop shading.

## Other notes

- Many decks contain several prompt-only copies of a worked slide (same title, fewer objects). Match them by title and content; the extractor's JSON makes this easy.
- Presenter notes and off-slide objects are content to preserve as comments, not to show.
- Old poll codes, attendance codes and QR codes are term-specific; see the conversion standard.
