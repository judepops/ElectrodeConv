# dashboard

The team page: one real spot walked through the pipeline, then the results. `site/index.html` opens straight from
disk (no server, no dependencies) and every picture and number on it comes from a file the code wrote: nothing on
the page is typed in.

```bash
LOSSLARP_MASKS=harmonise LOSSLARP_DATA_DIR=../losslarp/data python3.11 dashboard/build.py --run supcon/v2/full   # -> site/pipeline.js + site/img/  (~1 min)
python3.11 dashboard/build.py --run supcon/v2/full --spot Batch_2/avn74qx1 --tile 1,3   # a different spot / tile for the walkthrough
python3.11 dashboard/build.py --run v_k7_con02                                          # the old V1 model (MaterialNet) instead
python3.11 literature/batch_outlook.py        # after every build: regenerates site/literature.js for section 08
open dashboard/site/index.html                # or serve site/ with any static server
LOSSLARP_DATA_DIR=../losslarp/data python3 dashboard/lanes.py                 # section 00 -> site/lanes.js + site/img/lanes/  (~1 min, numpy + pillow only)
```

`build.py` needs torch (it runs the checkpoint on the CPU); on the team Mac that is `python3.11`. Parts 1 and 2 need
the raw TIFs and the run's checkpoint: `last.pt` for a V2 FusionNet run (`cnn/supcon.py` writes only that),
`best.pt` for an old MaterialNet run; `LOSSLARP_CKPT=<file>` overrides. Part 3 only reads JSON and CSV files, so run
these first:

```bash
python3.11 qc/features_table.py && python3.11 qc/verdict.py && python3.11 qc/impacts.py
python3.11 cnn/supcon.py run --name v2         # on the GPU box: 13 folds + the full model -> cnn/processed/supcon/v2/
python3.11 cnn/supcon.py score --name v2       # -> cnn/processed/supcon/v2/score.json (nested leave-one-session-out)
python3.11 cnn/difference.py --name v2         # -> cnn/processed/supcon/v2/full/difference.json
python3.11 cnn/baselines.py                    # -> dashboard/data/baselines.json (committed; holds the V1 row)
python3.11 cnn/probe_features.py --name <run> --n-perm 200   # optional: probe.json for the run shown
python3.11 cnn/predict.py --run <run> && python3.11 cnn/explain.py --run <run> --subset   # optional: sections 04 / 07 details
```

Section 04 compares V2 (`score.json`), V1 (the "V1 CNN embedding" row of `baselines.json`) and the baselines; V1's
test-spot calls and the session caveat come from `cnn/processed/v_k7_con02/predictions.json`. `score.json` is looked
for in the run's parent folder and `difference.json` in the run folder, then at the canonical `cnn/processed/supcon/v2/`
location, so a page built against the old run still shows V2 once it is scored.

If a result file is missing, its block says "not run yet" or is hidden and the rest of the page still works. With a
FusionNet run section 03 (cross-detector matching) is hidden: there is no per-detector embedding to match.

## What the page shows

| Section | Visual | Data |
|---|---|---|
| 00 Where the data comes from | the 31 spots as three batch folders; the joins that cross a folder, as close-ups with their edge-match scores; the spots sliding into 13 lanes; the lanes that mix batches; and the open question, which lane a new spot came from | `dashboard/data/lanes.csv` (lane, order and joins per spot) and the raw BSE TIFs, read by `dashboard/lanes.py` -> `site/lanes.js`, `site/img/lanes/` |
| 01 Make every image fair | one raw spot through crop → anchor → noise → rank → segment → tiles, before / after | `preprocessing/preprocess.py` replayed step by step on the raw TIFs, checked against `preprocess()` itself |
| 02 One tile, three detectors in, one kernel | the first-layer kernel (7×7×3 for V2: one patch per detector plane, three weight grids, one map pixel) sweeping the tile, the deeper stages, the 128-d `z` of the tile. For an old MaterialNet run: the shared kernel over the BSE and Inlens planes separately, one `z` per detector | the run's checkpoint, the real conv weights and activations |
| 03a V1: do the two detectors agree? | the label-free loss: BSE `z` × Inlens `z` cosine matrix over 8 tiles, before and after training, diagonal = same tile; from the old MaterialNet checkpoint (`--v1-run`, default `v_k7_con02`; skipped if missing) | `cnn/processed/v_k7_con02/best.pt` vs a seed-0 random init |
| 03b V2: same batch together, other batches apart | the batch-supervised loss: `z` × `z` cosine matrix over 18 tiles (3 spots per batch, 2 tiles each, the walkthrough tile first), before and after training; each pair marked as the loss sees it (same batch + other spot = positive, same spot = ignored, other batch = negative); per row the share of the softmax on positives against chance | the run's checkpoint vs a seed-0 random init (`build.py` `contrast_part`) |
| 04 Can it tell the batches apart? V1, V2 and the baselines | V1, V2 and V1+2 side by side on the same 5 spot folds with their deltas (`cnn/results/compare.json`, written by `cnn/compare.py`); losess bars with 90 % session-bootstrap whiskers for V2 (nested: 13 retrained encoders), V1 and the baselines against chance and the imaging-only bar; V2's confusion matrix with per-batch recall and Wilson intervals; the three test spots with V1's, V2's and V1 + V2's calls, each with its stability over 31 refits (`cnn/results/test_calls.json`), and the session caveat | `cnn/processed/supcon/v2/score.json`, `dashboard/data/baselines.json`, `cnn/processed/v_k7_con02/predictions.json` |
| 05 Accept, investigate or reject | each feature of Batch_1 / Batch_2 against the Batch_3 margin (delta, 90 % CI, zone) with its trust badge; the verdict with its reasons and actions; the test spots one at a time | `qc/processed/verdicts.json`, `feature_quality.json` |
| 06 What the science expects | six battery-property sliders: Batch_3 band, Batch_1 / Batch_2 median + IQR, model score + interval; click a row for the cited recipe | `qc/processed/impacts.json` |
| 07 Why the network said that | for any spot: share of the call explained by named features and each feature's push; the tile heat grid with the strongest tiles and their material maps; pixel attribution; nearest spots; ablations and imaging perturbations; and the embedding differences (batch vs batch, test spot vs Batch_3) read through the named features | `cnn/processed/<run>/explain.json`, `attribution.json`, `probe.json`, `cnn/processed/supcon/v2/full/difference.json` |
| 08 Production literature | feature × outcome grid of what full-text papers report (more / less / optimum / mixed), the quoted sentences with DOIs, the batch outlook built from it, and the section-06 slider rules checked against the counts | `site/literature.js`, written by `python literature/batch_outlook.py` (reads `literature/evidence.json` and this page's `pipeline.js`) |

Section 00 in plain terms: Polaron told us the training data comes from 13 lanes (one huge line, cut into blocks), that a batch
is variation inside a lane, and that its in-house model assigns the batches. `data/lanes.csv` is our reconstruction of that: a lane
is one imaging session (spots of the same image height), and two spots are joined when the last pixel columns of one match the first
of the next (`lanes.py` scores this as the first repo's `analysis/embeddings/reverse_engineer/seams.py` does: 4 columns, BSE,
best Pearson r over a vertical slide of up to 40 px; unrelated pairs for comparison are 80 random spots from different lanes).
Two things to know. The order of spots that do not touch is not known; the page draws them in an arbitrary order with a dashed gap.
And the scores differ from `notes/seam_examples/README.md` in the first repo (0.83-0.97 there): running that repo's own `seams.py`
on the current data gives 0.75-0.92 for the same 12 joins, the numbers shown here. The pictures are display-only (a linear stretch per
lane); nothing in the data changes.

The top bar is the pipeline map; it follows the scroll and every node is clickable. Each section has a step card
with Prev / Play / Next; `→`, `←` and space step too. Scroll position is the single source of truth, so the controls
just scroll.

`site/pipeline.js` and `site/img/` are committed (≈4 MB; section 00 adds `site/lanes.js` and `site/img/lanes/`, ≈1 MB) so the page works without the raw data or a checkpoint;
`build.py` clears the loose files in `site/img/` before it writes the walkthrough pictures, and leaves two kinds alone: `site/img/lanes/` (section 00, written by `lanes.py`) and `site/img/lit_*.jpg` (the example tiles of section 08, written by `python literature/feature_cards.py` and merged into `literature.js` by `batch_outlook.py`). Commit those pictures with the `.js` that points at them.
rerun `build.py` after retraining or when the result files change. A new stage is one `<section>` in `index.html`
(with an `<aside id="<id>-card">`), one `register()` block and one entry in `extraNodes` / `extraThumbs` in `app.js`
(a stage that comes before 01 goes in `firstNodes` / `firstThumbs`, and its `register()` must run before `register("prep")`).
