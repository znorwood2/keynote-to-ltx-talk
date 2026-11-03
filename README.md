# keynote-to-ltx-talk

A [Claude Code](https://claude.com/claude-code) skill that converts Apple Keynote lecture slides into editable, accessible LaTeX decks using the [`ltx-talk`](https://ctan.org/pkg/ltx-talk) class.

It is built for instructors who teach from Keynote and want their slides in LaTeX without retyping them. The converted deck:
- **matches the Keynote:** the same wording, math (as real LaTeX, taken from Keynote's equation objects or the source LaTeXiT embeds in pasted equations) and build order. Each click, or each duplicated slide, is an overlay;
- **follows your course template**, fonts and colors;
- **has the teaching features many instructors use:**
  - **live-poll slides** (`pollframe`) showing a session `\pollcode` you set once per deck;
  - an **instructor/student toggle**: a full title slide with reminders and the poll code for you, title-only with no polls for students;
  - a **solutions toggle** that swaps prompt slides for worked versions;
- **builds handouts** in which hidden answers are left out, not just made invisible;
- **passes LMS accessibility checks** (Anthology Ally and similar): tagged PDF/UA, alt text on every figure, table headers, and palette-only text colors;
- **comes with a report** listing every difference from the Keynote and every source error it kept as written.

The conversion is done by Claude following the instructions in [SKILL.md](SKILL.md) and [references/](references/). The scripts in [scripts/](scripts/) do the mechanical parts and also work on their own.

## Requirements

- Claude Code (CLI, desktop app or IDE extension).
- TeX Live 2026 or later with `ltx-talk` 0.6.10 or later, compiled with LuaLaTeX.
- Poppler (`pdftoppm`, `pdfinfo`, `pdftotext`) and ImageMagick 7 (`magick`), for renders and contact sheets.
- Python 3.10+. `a11y_audit.py` also needs `pypdf` (`pip install pypdf`). The Keynote reader has no dependencies.
- Keynote itself is **not** required: the skill reads `.key` files directly.

## Install

```bash
git clone https://github.com/znorwood2/keynote-to-ltx-talk ~/.claude/skills/keynote-to-ltx-talk
```

Claude Code picks up skills in `~/.claude/skills/` automatically. Update later with `git -C ~/.claude/skills/keynote-to-ltx-talk pull`.

## Set up a course (once)

1. Put your `.key` files in a folder, e.g. `keynote/`. For the best fidelity, also export each one to PDF with **File → Export To → PDF** and **Print each stage of builds** turned on, named `<deck>-anim-qr.pdf`. Without an export, builds are reconstructed from the `.key` alone.
2. Copy [templates/course-template.tex](templates/course-template.tex) into the course folder, then edit its `COURSE` lines: fonts, figure folders, colors, polling site, and your macros.
3. Copy [templates/ltx-talk-course.md](templates/ltx-talk-course.md) into the course folder and fill it in. It records your course name, file layout, which features you use, your palette and your build command. If you skip this step, Claude asks the questions and writes the file for you.

## Use

In Claude Code, from your course folder:

> Convert keynote/3.4.key to ltx-talk.

Claude reads the Keynote, writes `3.4.tex`, builds and checks it, and reports what it did. For a whole course, convert one deck, give feedback ("redraw the plots in TikZ", "keep my poll title"), and then ask for the rest. Your feedback goes into the course profile so later decks follow it.

## Scripts

| Script | What it does |
|---|---|
| `scripts/keynote_extract.py deck.key [--pdf export.pdf] [--json -] [--media DIR]` | Slide order, skip flags, text, equation LaTeX (Keynote equations and LaTeXiT images), images, links, builds and click counts from a `.key`. Also detects duplicated-slide builds and checks the predicted page count against an export. `--media` copies embedded images under safe file names. |
| `scripts/latexit.py file.pdf ...` | Prints the LaTeX source that LaTeXiT embeds in its equation images. |
| `scripts/build_variants.py deck.tex [--solutions] [--outdir DIR]` | Builds the instructor-animated, instructor-handout and student PDFs, and optionally the solutions variants, without editing the source. |
| `scripts/src_check.py deck.tex [--palette ...]` | Flags unclassified TikZ pictures, images without alt text, tables without header tagging, off-palette text colors, transparent handout answers, and absolute overlay numbers. |
| `scripts/a11y_audit.py deck.pdf ...` | Checks a compiled PDF for low-contrast, very light or transparent text, figures without alt text, tables without headers, and missing language or title. |
| `scripts/contact_sheet.py out.png source.pdf output.pdf [--map map.txt]` | Pairs source and output pages side by side, in source order, for review. |

## Limitations

- Keynote's file format is undocumented; the reader was reverse-engineered from Keynote 13/14 files (2023–2026). Its `--pdf` check shows when its prediction and an export disagree.
- Motion paths and other animations become plain reveals at the final positions; animated GIFs become their still frame.
- Animated (non-handout) builds keep not-yet-revealed text as transparent text, which some checkers flag. Post the handout and student builds to your LMS.

## Credits

Developed by [@znorwood2](https://github.com/znorwood2) with Claude while converting a multivariable-calculus course, and generalized for colleagues. Issues and pull requests are welcome.

## License

[MIT](LICENSE).
