# ltx-talk notes

Tested with LuaHBTeX 1.24.0 (TeX Live 2026), LaTeX 2026-06-01 and ltx-talk 0.6.10 (2026-10-13). Check the installed version (`\ProvidesExplClass` line of `kpsewhich ltx-talk.cls`) and record it in reports; re-test anything below after an upgrade.

## Compiling

- Compile from the course folder so relative `\graphicspath` entries resolve, with `-output-directory` pointing at scratch space: `lualatex -interaction=nonstopmode -halt-on-error -output-directory=<scratch> deck.tex`. Three passes when tikzmark callouts are used.
- `scripts/build_variants.py` compiles the standard variants from temporary copies, so the source's toggles and class options are never edited.
- Don't remove `\DocumentMetadata` or tagging to make an older engine accept a deck.

## Version quirks (0.6.10)

- **`\maketitle` key** is `frame-style` (the old `framestyle` is now a fatal error).
- **List options are dropped:** only a leading `<...>` spec survives, so `[item-label=\Alph*.]` prints 1., 2. and `[start=4]` restarts at 1. The course template has a marked workaround block (redefining `\__talk_block_set:n`); keep it in every deck, right after the `\tagpdfsetup{role / new-tag = frametitle / H1}` line, and delete it once upstream fixes the bug. Check list labels with `pdftotext`, since pixel diffs miss them.
- **Unknown options are errors:** beamer's `[allowframebreaks]`, enumitem short forms like `[A.]` and `[(a)]`, and keys like `nosep`. Use `item-label=`, `label=` and `start=` only.
- **`\uncover` does not hide a `tcolorbox`.** Reveal boxes with `\only<+->`. That is safe when the box is the last object in its frame or column, so nothing shifts.
- **`alt` on a TikZ picture inside `pollframe`** turns on `remember picture`, which can drop axis labels and shift the figure. Add `remember picture=false` after the alt key there, and compare renders.
- Older versions (≤ 0.6.8) had a handout decoder bug (upstream #284): a `handout:`-qualified overlay hid later unqualified ones. If you must support them, wrap the qualified command in braces.

## Relative overlay arithmetic

- The `pauses` counter starts at 0 in each frame. `+` expands to `pauses+1` and advances `pauses`; `.` is the current value.
- `+(k)` expands to `pauses+1+k` but advances by only 1, so a following `<.->` lands *earlier*. Avoid `+(k)`. `<.(-n)->` (sync with an item n reveals back) is fine with a comment naming the item.
- Idiom when a frame's first state already shows content: wrap that content in `\uncover<+->{...}` so it takes state 1, then use `<+->` and `<.->`.
- A `+` inside a hidden `\only` isn't evaluated, which shifts later numbering. Put counted specs inside `\uncover` bodies, which are always typeset.
- When a figure in one column must appear before text in another, either place it in reading order with a remember-picture overlay, or step the counter with an empty `\only<+->{}` (a `\stepreveal` macro) and sync the figure back with a commented `<.(-n)->`.
- `pdftotext` cannot verify `\uncover` reveals (hidden text stays in the PDF); check renders.

## Handouts

- In handout builds, `\uncover` content outside the shown state is painted **transparent**, still in the file. For answers that must not be in a handout, use `\only<handout:0>{\uncover<+->{answer}}` (or `\only<handout:N>{...}` for a dedicated answer page): projected states are unchanged and the handout omits the text. Inside a fixed-width blank (`\makebox[w]{...}`) the blank keeps its size; in table cells, rows may get shorter.
- Prompt and solution handout pages (`handout:1` / `handout:2`) are fine when the source intends them; make sure no replacement object appears twice on one page.
- If a rasterizer drops content that a native viewer shows, check the PDF in a native viewer before blaming the class. Poppler and Ghostscript have mishandled ltx-talk opacity groups.

## Callouts

```latex
\newcommand{\deckmark}[2]{\expanded{\noexpand\tikzmarknode{#1-\arabic{page}}}{#2}}
% ... \deckmark{target}{\iint_D 1\,dA} ...
\uncover<+->{%
  \begin{tikzpicture}[remember picture, overlay, artifact]
    \draw[->, thick, accentorange] (label.south) -- (target-\arabic{page}.north);
  \end{tikzpicture}}
```

Page-specific marks keep arrows anchored when the callout appears on several states. Don't wrap a `\tikzmarknode` around `\left...\right` under math tagging (compilation aborts); mark the contents instead. A `\deckmark` wrapped *around* an `\uncover` inside an integral limit can advance the overlay counter several times; put the mark inside the `\uncover`.

## Animated builds and accessibility

Each state of an animated (non-handout) build contains the frame's not-yet-revealed text as transparent text, so checkers that model fill opacity report low contrast for animated builds. That is inherent to `\uncover`. Post handout and student builds to an LMS; the animated build is for projecting.
