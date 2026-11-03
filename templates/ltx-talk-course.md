# Course profile for keynote-to-ltx-talk

Copy this file to the root of your course folder as `ltx-talk-course.md` and
fill it in. The skill reads it before every conversion; anything you leave
blank falls back to the default shown. Claude updates it (with your OK) when
you give a lasting preference, so later decks inherit it.

## Course

- Course name (title-slide author line): `Math 101`
- Deck title format: `\S<section> <title>`  (e.g. `\S3.4 Applications of double integrals`)
- Language: `en-US`

## Sources

- Keynote folder: `keynote/`
- Build-expanded PDF export next to each `.key`: `<name>-anim-qr.pdf`
  (Keynote: File > Export To > PDF, with "Print each stage of builds" on).
  If you have no export, conversions reconstruct builds from the `.key` alone.
- Figure folders to search: `fig/`
- Do not modify anything in the Keynote folder.

## Output

- Write `<name>.tex`, `<name>.pdf` and `<name>-conversion-report.txt` to: the course folder root
- Template (preamble and environments): `course-template.tex`
- Model decks to imitate once you have approved one: (none yet)

## Features

- Instructor toggle (`\toggletrue{instructor}`): yes.
  Instructor build: full title slide (reminders + poll code) and poll frames.
  Student build: title-only first slide, no poll frames.
- Solutions toggle (`instructorsolutions`, off by default): yes.
  Worked solutions on skipped Keynote slides become solution frames that replace their prompt frames when the toggle is on.
- Live polls: yes.
  - Keynote slides to convert into `pollframe`: titles starting with `Quick Check`, `Poll` (case-insensitive)
  - Poll code macro `\pollcode`, placeholder `XYZXYZ` (never copy an old term's code)
  - Polling site `\pollsite`: `polling.example.edu`
- Handouts: answers revealed in class are omitted from handout builds: yes.

## Term-specific slides

Archive (keep as comments after `\end{document}`, don't compile): welcome /
attendance slides, daily check-in slides, dated exam announcements, QR codes.
Old dates and reminders become `\alert{Update ...}` placeholders.

## Palette (text colors; each must be >= 4.5:1 on white)

| Name | RGB | Use for Keynote colors |
|---|---|---|
| `accentred` | 208, 0, 0 | red, pink-red |
| `accentgreen` | 0, 110, 0 | green |
| `accentorange` | 190, 75, 0 | orange, yellow |
| `blue` (xcolor) | 0, 0, 255 | blue, cyan, teal |
| `violet` (xcolor) | 128, 0, 128 | purple, magenta, pink |
| black | | white/gray text on dark themes |

## Figures

- Redraw simple diagrams (axes, regions, curves, vector fields, sketches) in TikZ/pgfplots: yes
- Keep as images: photos, screenshots, complex 3D renderings
- Every figure gets alt text.

## Builds and checks

- Build command: `python3 <skill>/scripts/build_variants.py --solutions <name>.tex`
  (or your own tool, e.g. `slidemake --compile 3 <name>.tex`)
- Builds to check: `instr-anim`, `instr-handout`, `student` (+ solutions builds when the deck has solutions)
- Accessibility target: `a11y_audit.py` clean on handout and student builds
  (optional extra checker, e.g. an Ally predictor: `pdfcheck --canvas <pdf>`)

## House style

- Separate frames with `%%%----------------------------------------------------------------------------`
- Readable source: one item / equation / overlay per line; no compressed preambles.
- (add your own: macros for bold vectors, theorem environments, title conventions, ...)
