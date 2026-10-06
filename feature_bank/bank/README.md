# bank/ — the frozen feature bank

Goal: the largest trustworthy set of frozen features we can compute for the 31 crops, with only a small metric learned from the batch labels. The full brief is `Track_4/CLAUDE_CODE_PROMPT_feature_bank.md` in the hackathon folder (one level above the repo); this file is the working contract.

| File | What it is |
|---|---|
| `core.py` | The contract: `Crop`, `FeatureResult`, the helpers, where results are written. Frozen: ask for changes in `CONTRACT_REQUESTS.md`. |
| `run.py` | Runner: make crop versions, run a family, show what is done. |
| `families/<name>.py` | One file per feature family. `_example.py` is a template. |
| `../meta/crops.csv` | crop, folder (the batch label), source image. For splits and scoring. |
| `../meta/analysis_only.csv` | Image height, chain order, the 12 joins. For nulls and diagnostics only. |
| `../cloud/modal_bank.py` | The same jobs on Modal. Paid: only the lead launches cloud runs. |

## Writing a family

Copy `families/_example.py`. A family is a module with `FAMILY` (equal to the file name), `TIER`, `RUNS_ON`, `DEFAULT_CFG` and `extract(crop, cfg) -> FeatureResult`. Add values with `res.scalar(...)`, `res.block(...)` (one array per crop) and `res.tile_block(...)` (an `(n_tiles, d)` array). Each call also writes the catalog row, so give it the detector, view, `scale_nm`, the physical length the statistic probes (`length_um`, or `None`) and a tag:

| Tag | Use it for |
|---|---|
| `material` | measured on phase maps or anchored intensities; should not care how the picture was taken |
| `imaging` | describes the acquisition (black level, noise, focus, drift). Kept out of the material model. |
| `mixed` | could be either (most fine texture, most embeddings) |
| `leakrisk` | anything from the SE/ETD detector. Excluded from the default models. |

Then, in this order:

```bash
python -m bank.run fam <name> --sites smoke --perts P0              # 2 crops: must pass
python -m bank.run fam <name> --sites all --perts P0 --workers 4    # all 31 crops
python -m bank.run fam <name> --sites all --perts imaging --workers 4   # the six imaging changes (or leave to the lead's cloud run)
python -m bank.run fam <name> --sites inject --perts inject         # the injected material changes
pytest tests/test_bank_contract.py -q -k <name>
python -m bank.run status
```

## What a Crop gives you

Every crop is the same window: 1336 x 6944 px at 25 nm, i.e. 33.4 x 173.6 um.

| Call | Returns |
|---|---|
| `crop.view(det, view, scale)` | `det` in `BSE`, `Inlens` (`SE` is leakrisk). `scale` 1, 2, 4, 8 is a block mean; `scale_nm = 25 * scale`. |
| view `raw` | uint8 grey levels |
| view `anchored` | BSE in graphite units (0 = black level, 1 = graphite); Inlens rank-normalised 0..1. No noise added. |
| view `harmonised` | anchored plus noise up to one fixed level. Use it for fine texture below 500 nm. |
| view `smoothed` | anchored blurred by sigma 2.5 px. Use it for phase work, never for fine texture. |
| `crop.phase(name)` | bool map: `void`, `bright`, their `_lo` / `_hi` versions (threshold moved by 0.05 g / 0.15 g), `bright_fixed`, `dim` |
| `crop.valid` | False where the raw BSE is saturated |
| `crop.anchors` | black level, graphite level, noise, thresholds. Imaging quantities: tag features built on them `imaging`. |
| `core.tiles(arr, size)`, `core.block_mean(arr, k)`, `core.quantise(arr, kind, levels)` | helpers; quantisation always uses the fixed global range |

Crop versions: `P0` is the crop as acquired. The six imaging changes (`black25`, `gamma0.8`, `gamma1.25`, `contrast0.85`, `noise4`, `blur1`) and the five injected material changes (`pore_r2`, `pore_r4`, `pore_r8`, `bright_rm50`, `bright_rm100`, on 6 crops) are applied to the raw image and then harmonised. A good material feature barely moves under the first set and clearly moves under the second.

## Rules (the tests enforce these)

- A family sees only the Crop. Never the crop id, a file or folder name, image height or width, the source image, tile positions, or anything in `meta/`.
- Names are `family|det|view|scale_nm|stat`. No name part may be a provenance word (`core.FORBIDDEN_TOKENS`).
- No NaN or infinity. Decide what an empty mask returns and return a finite number.
- Deterministic: any random draw is seeded from the crop content (`crop.anchors["seed"]`).
- Do not use `Sample.bse` / `.inlens`, `processed/full`, `processed/tiles` or `split_of()`. They are percentile-stretched or leak.
- Physics: no vertical flip, no 90 degree rotation, no interpolated rescale. Keep x and y (and angle-resolved) statistics separate; vertical is through-thickness.
- Intensities are graphite-anchored with fixed global quantisation. No per-image min/max, no 3-class Otsu. A bright fraction is always reported lo / mid / hi.
- Say "void fraction", never porosity. Anything from TauFactor is named `tau2d_section_*`. No thickness claims.
- Nothing fitted here. Scalers, PCA, codebooks and weights are fitted inside training folds by the harness.
- Never flag crops x7u69zsw, kbdh4tri, tuy3zymq, 71vgq3fw as material outliers (their black level is lifted; it is imaging).

## Working together

- You own your family files and nothing else. Do not edit `core.py`, `run.py` or another lane's files.
- Branch `feat/feature-bank`. Never switch branch, pull, rebase or push. Commit only your own files: `git add <your files> && git commit -m "..." -- <your files>`. If git reports a lock, wait a few seconds and retry.
- Never commit `data/`, `processed/` or arrays.
- Modal costs money: do not run `modal run` or any other paid command. Smoke-test locally; the lead launches cloud runs.
- If you are blocked for 20 minutes, write what blocked you in `processed/bank/BLOCKED.md` and move on.
