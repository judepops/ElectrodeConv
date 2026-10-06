# Session map: how the 31 spots line up

**Files:**
- `session_map.py`: the generator.
- `session_map.svg` and `session_map_dark.svg`: Inkscape layers, live text.
- `session_map.png` and `session_map_dark.png`: renders.

I used draw-xml rather than draw-tikz because the figure goes on the team page and the slides, and gets edited in Inkscape.

## Caption

Polaron cut about 20 large images into spots and grouped the spots into three batch folders using its own features. Batch_3 is the baseline. The 31 spots we have come from 13 sessions. Each row is one session: spots that touch are drawn edge to edge in the order found by matching image edges.

In 5 sessions (13 spots), neighbouring spots sit in different folders, and 4 of the touching pairs cross a folder boundary. In the other 8 sessions (18 spots), every spot is in one folder, so the folder can be guessed by recognising the session.

## Reading the glyphs

| Glyph | Meaning |
|---|---|
| Coloured box with B1/B2/B3 and an ID | one spot and its batch folder (team-page colours: Batch_1 `#4f5bd5`, Batch_2 `#d9622b`, Batch_3 `#12937f`) |
| Boxes edge to edge | touching spots, found by matching image edges |
| ◆ on a seam | touching spots in different batch folders: the 4 pairs scored by the "joins" test |
| Dashed box with ? | same session but not touching: order and distance unknown |
| Black bar at a row end | edge of the source image, inferred from a marker line in the file |
| ··· | the image continues beyond the spots we have |
| Dashed brown line under a spot | copper collector visible on its bottom edge (`epqdaau9` only) |
| Grey band | the 5 mixed sessions: the 13 spots scored by the "mixed" test |
| Bracket on 2060, 1904, 2088, 1612 | these sessions were imaged more quietly than the others |

## Numbers on the figure and their sources

Every count is computed from the table in the script and checked by `assert` on every run:

- 31 spots: Batch_1 7, Batch_2 7, Batch_3 17.
- 13 sessions: 5 mixed (13 spots) and 8 single-folder (18 spots). The single-folder sessions split as Batch_3 only 4 sessions (12 spots), Batch_2 only 1 (2), Batch_1 only 3 (4).
- 12 touching pairs, 4 of them across folders.
- 13 image-edge markers.
- 1 spot showing the copper collector.

Adjacency comes from exhaustive edge matching (`Track_4/provenance/edge_match.py`): 930 ordered pairs at every vertical shift.
- Joins score r 0.68–0.85, all at zero shift and all within one session. Nothing else scores above 0.44.
- The team's detrended edge check gives 0.73–0.92 for the joins against ≤ 0.23 for the other spots of the same session.

The session notes (lifted black level, SE-named files, quieter imaging, bright population roughly 15–20% of area) are the team's measurements, as listed in `SCHEMATIC_BRIEF.md`.

Accuracies are deliberately not on the figure. The page reads them from `dashboard/site/pipeline.js` at build time.

## What to say out loud

1. "Polaron's batches are clusters cut through large images. We can see 13 of them."
2. "So the batch can be answered by recognising the image, not the material: 18 of 31 spots sit in sessions with one folder."
3. "So we hold out whole sessions, test inside the mixed sessions and on the 4 cross-folder joins, and show the imaging-only bar next to every accuracy."

## Not established (the figure says so; don't fill the gap)

- Where the sessions sit on an electrode, or in what order. The rows are not on any axis.
- Which edge is the collector for 30 of 31 spots, and the coating thickness.
- What "in between is pore" includes.
- Whether a batch difference is material, imaging or both.
- Whether the final two images come from sessions we have seen.

The three test spots are not drawn, as the brief sets by default.

## Editing

- **In Inkscape:** move, restyle or retype anything. Each class of element is its own layer (spots, gaps, edges, joins, labels, box, legend). Save the result as `session_map_final.svg`.
- **In the script:** change `CONFIG`, then re-run with `python3 session_map.py out.svg [light|dark]`. Use this for systematic changes: the `TEXT` level (`none`, `minimal`, `labelled`, `full`), the theme, sizes, the order of sessions, or the box text. Re-running overwrites the SVG, so polish in Inkscape last.
