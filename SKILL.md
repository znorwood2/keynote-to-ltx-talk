---
name: keynote-to-ltx-talk
description: Convert Apple Keynote lecture slides (.key, optionally with a PDF export that prints each build stage) into editable, accessible ltx-talk LaTeX decks that reproduce the slides' wording, math and build order, with optional live-poll frames (poll code), instructor/student and worked-solution toggles, handouts, and a conversion report. Use when someone asks to convert, transcribe or port Keynote slides to LaTeX, ltx-talk or beamer-style slides, or to revise or accessibility-check a converted deck.
---

# Keynote to ltx-talk

Turn a Keynote deck into an `ltx-talk` source file the instructor can teach from and keep editing. The result says exactly what the Keynote says, in the same build order, using the course's own template and conventions, and passes LMS accessibility checks.

## 0. Course profile

Look for `ltx-talk-course.md` in the course folder (the folder holding the decks). It names the template, palette, poll settings, file layout and build command. If there is none:
- copy [templates/ltx-talk-course.md](templates/ltx-talk-course.md) there and ask the instructor the few questions it needs (course name, where the Keynote files and exports are, whether they use polls and what site, whether they want instructor/solution toggles);
- if they have no template, copy [templates/course-template.tex](templates/course-template.tex) as `course-template.tex` and adapt its `COURSE` lines.

The profile overrides the defaults in this skill. When the instructor states a lasting preference ("always redraw plots in TikZ", "keep my poll title"), apply it and offer to add it to the profile.

## 1. Read the references

Before the first conversion in a session, read:
- [references/conversion-standard.md](references/conversion-standard.md): fidelity, title slide, polls, toggles, prompt/worked pairs, builds and overlays, source style, verification, report. Binding.
- [references/keynote-format.md](references/keynote-format.md): reading `.key` files with `scripts/keynote_extract.py`, the build model, skip flags, and how to reconcile with a PDF export.
- [references/ltx-talk-notes.md](references/ltx-talk-notes.md): class quirks and tested overlay idioms.
- [references/accessibility.md](references/accessibility.md): colors, alt text, tables, hidden text.

## 2. Inventory the sources

Never modify the `.key`, its export, or the template. Work in a scratch folder.

```bash
python3 <skill>/scripts/keynote_extract.py keynote/3.4.key --pdf keynote/3.4-anim-qr.pdf --media <scratch>/media
```

This lists every slide in show order with its skip flag, title, text, equation LaTeX (Keynote equations and LaTeXiT images), images, links, builds and click count. It also lists runs of duplicated slides used in place of builds, and checks the predicted page count against the export. `--media` copies the embedded images under safe names; don't `unzip` the `.key`. Render the export pages you need (`pdftoppm -scale-to-x 800 -scale-to-y -1 -f N -l N`) and look at them. Text extraction alone misses layout, color and what each build reveals.

Build a source-to-output map before writing LaTeX: for each slide, whether it is converted, a poll, a solution alternative, collapsed (title-only first state) or archival, and how many output states it gets.

## 3. Write the deck

Start from the course template's preamble verbatim. Follow the conversion standard. In short:
- exact wording and math, native LaTeX (from the equation objects), inline vs. display as in the source;
- one output state per substantive Keynote build state, relative overlays (`<+->`, `<.->`); a run of duplicated slides is one frame with one state per slide;
- poll slides become `pollframe` with `\pollcode`;
- worked solutions on skipped slides go behind `instructorsolutions`;
- term-specific slides become archival comments after `\end{document}`;
- simple diagrams are redrawn in TikZ with alt text; images keep specific alt text;
- every text color comes from the profile's palette;
- the source is readable, with one frame per source slide and a `% Source slide N; k states.` comment.

## 4. Verify

```bash
python3 <skill>/scripts/build_variants.py --solutions --outdir <scratch> 3.4.tex
python3 <skill>/scripts/src_check.py --palette black,blue,violet,accentred,accentgreen,accentorange 3.4.tex
python3 <skill>/scripts/a11y_audit.py <scratch>/3.4-student.pdf <scratch>/3.4-instr-handout.pdf
python3 <skill>/scripts/contact_sheet.py <scratch>/review.png keynote/3.4-anim-qr.pdf <scratch>/3.4-instr-anim.pdf --map map.txt
```

View the review sheets yourself and fix every mismatch. Check polls, dense slides, callouts and final states at full size, plus both handouts. Use the profile's build command and checker if it names them. `a11y_audit.py` needs `pypdf` (`pip install pypdf`).

## 5. Deliver

Write `<name>.tex`, `<name>.pdf` (the instructor animated build) and `<name>-conversion-report.txt` where the profile says. The report covers counts reconciled to the source, the slide map, skip flags, what was collapsed or archived, figures redrawn or kept, links, polls, solutions, source errors kept as written, ambiguities and verification. Never claim a check you didn't run.

## Converting many decks

Do one deck first and wait for the instructor's feedback. Apply it to the profile, then convert the rest in parallel, one subagent per deck, each given this skill, the profile and the approved deck as a model. Review every deck's source-vs-output sheets yourself before reporting it done.
