# preprocessing

Step 1 of the pipeline: turn every raw SEM spot into arrays that are comparable across microscope sessions,
so that whatever is built on top (features, embeddings, verdicts) measures the material and not the imaging.

```bash
python preprocessing/preprocess.py          # all spots in data/ -> processed/<Batch>/<id>/tile_rRcCC.npz + processed/tiles.csv  (~4 min)
python preprocessing/preprocess.py 4ih2ggld # just one spot
python preprocessing/check_fairness.py      # does any session cue survive? (~2 min)
```

The output is **512 x 512 px tiles** (12.8 x 12.8 um), a centred non-overlapping grid of 2 rows x 13 columns = 26 tiles
per spot, 806 in all. Every tile is fully inside the fair window and carries the same five planes:

```python
from preprocessing.preprocess import load_tile, load_tiles, list_processed
tile = load_tile("Batch_1", "4ih2ggld", row=0, col=5)   # ~5 ms
tile.bse      # float32 (512, 512), graphite units: 0 = black level, 1 = graphite, Si phase ~2
tile.inlens   # float32 0..1, rank-normalised
tile.se       # float32 0..1, rank-normalised (ETD / SE detector)
tile.void     # bool, open pores          tile.solid = ~void
tile.bright   # bool, Si-like bright phase
tile.row, tile.col, tile.y, tile.x        # grid position and top-left corner in the window
tile.meta     # the spot's session fingerprints + this tile's porosity / Si fraction: for audits, never model inputs

tiles = load_tiles("Batch_3", "71vgq3fw")               # all 26, grid order
```

`processed/tiles.csv` is the index: one row per tile with batch, sample_id, session, position, tile porosity and
Si fraction, and the spot-level metadata. **Split train / test by `sample_id` (or by `session`), never by tile**:
tiles of one spot are the same material.

To work on the whole spot instead, `preprocess(load_spot(...))` recomputes it in ~4 s (the full arrays are not stored).

## What it does, and why each step is there

| Step | What | Removes |
|---|---|---|
| crop | the same central 1336-row window of every image, away from the top-of-frame artefact and the bottom band | image height (the strongest session cue), unequal areas |
| anchor | BSE -> graphite units: 0 = the image's own black level, 1 = its graphite peak | black-level lift (session 2060: +23 grey levels) and contrast setting |
| noise | top every image up with Gaussian noise to one fixed level (BSE 0.235, Inlens 0.105) | "quiet" sessions looking cleaner: edge and particle counts depend on noise |
| rank | Inlens and SE mapped to their rank (0..1) | any brightness / contrast curve on the secondary-electron detectors |
| segment | void by Otsu between pore and graphite peaks; bright by the midpoint between graphite and the image's own Si peak | fixed thresholds that mean different things in different images |

Deliberately **not** done: per-image percentile stretch (depends on Si content), rescaling (pixel size is physical),
vertical flips or rotations (the material is anisotropic). All constants are at the top of `preprocess.py`; nothing is
tuned per batch or per label. The recipe is the team's `features/_common/harmonise.py`, distilled into one file;
masks agree with it on 98-99 % of pixels (the only differences are the random noise draws).

## Fairness check (31 spots, leave-one-spot-out, balanced accuracy)

| Predict | from raw image levels / noise | from preprocessed levels / noise | chance |
|---|---|---|---|
| session (13 image heights) | **0.71** | 0.29 | 0.08 |
| batch | **0.70** | 0.48 | 0.33 |

The raw images give the session away; the preprocessed ones mostly do not. The 0.29 that remains comes from
`pp_bse_p99` and `pp_inlens_noise` (each 0.26-0.27 on its own), i.e. the brightest few pixels and the Inlens
noise floor. Those are partly real: crops of one large image share material, and Inlens noise is sometimes already
above the target so cannot be matched upward. Two Inlens spots (`i9jiqjwl`, and session 2316) sit at the target; a
higher `INLENS_NOISE_TARGET` would close that gap at the cost of adding noise everywhere.

`processed/` is git-ignored (2 MB per tile, 1.6 GB for all 806). `tiles.csv` is small and could be committed.
