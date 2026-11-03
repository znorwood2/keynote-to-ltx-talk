# Accessibility

Learning-management systems increasingly score uploaded PDFs; Anthology Ally (Canvas, Blackboard, Moodle, D2L) is common. A converted deck must pass on its handout and student builds: `scripts/a11y_audit.py` reports no problems, and the profile's extra checker (if any) gives full marks. These rules also make the slides usable with screen readers.

## Tagged PDF

The template's `\DocumentMetadata` (PDF/UA-2, tagging on, MathML for math) and `\tagpdfsetup{role / new-tag = frametitle / H1}` give a tagged PDF with language, title and headings. Keep them in every deck.

## Text colors

- Text (including labels, tick labels and callouts inside TikZ/pgfplots) uses only the profile's palette. Every color must reach 4.5:1 contrast on white (3:1 for text ≥ 18pt). xcolor's `black`, `blue` and `violet` pass. `red` (4.0), `orange`, `green`, `cyan`, `teal`, `magenta`, `yellow`, `gray` and light mixes fail.
- Map Keynote's dark-theme colors to the palette: red/pink → the red accent; orange/yellow → the orange accent; green → the green accent; cyan/teal → blue; magenta/purple → violet; white/gray text → black. Keep distinct colors distinct within a slide.
- Don't lighten pgfplots tick labels (`black!80` and the like); keep them black.
- Fills, shading and lines may be lighter, as long as any text on a fill still has 4.5:1 against the fill.
- **No white or very light text**, even on a dark box: checkers flag it. A check mark is a green ✓ on white, not white on green.
- `\alert` in ltx-talk 0.6.10 renders #C80000, which passes.

## Figures

Classify every `tikzpicture` and `\tikz`, including those inside macros, with one option:
- **Content figure** (plot, diagram, region, icon that carries meaning): `alt={...}`, one or two sentences saying what it shows and what matters. For a quiz or poll figure, describe without giving away the answer. A macro used for several figures can take its alt text as an argument.
- **Decoration with no text** (callout arrows, highlight rectangles, underlines, strike-throughs, spacers): `artifact`.
- **Picture whose nodes hold real text or math** (boxed answers, callout labels): `tagging-setup=text`, so the text stays readable.

Every `\includegraphics` has `alt={...}` with a specific description: never "image", a file name, or "Alt text here". ltx-talk tags each frame once, so a figure repeated across one frame's states is one Figure element.

## Tables

- A data table declares its headers just before the tabular: `\tagpdfsetup{table/header-rows={1}}`, `table/header-columns={1}`, or both. End the line with `%` if a stray space would shift the table.
- A tabular used only for layout or alignment is tagged as a plain block: `{\tagpdfsetup{table/tagging=div}\begin{tabular}...\end{tabular}}`. Don't use `table/tagging=presentation`, which still emits a Table element that checkers count as a table with no headers.
- Math arrays and matrices are part of the formula, not tables.

## Hidden text

Answers hidden from handouts must be omitted, not made transparent (see ltx-talk-notes.md, "Handouts"). `a11y_audit.py` reports transparent text per page. On handout and student builds, any finding is a leak.

## Links

Keep hyperlinks with descriptive link text (the Keynote's, e.g. "GeoGebra"); `hyperref`'s settings in the template make them blue and tagged.
