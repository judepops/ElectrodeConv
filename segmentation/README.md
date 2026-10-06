# segmentation (branch `seg3-masks`)

A multi-detector pore / graphite / Si-like segmentation ("seg3") that replaces the BSE-only thresholds as the source
of `tile.void` and `tile.bright`. Everything downstream picks it up unchanged: the CNN's material-map target
(`cnn/common.material_map`), the 13 tile features, the QC table, the verdict and the battery sliders. The BSE / Inlens /
SE planes the CNN sees are not changed.

```bash
export LOSSLARP_DATA_DIR=/path/to/data            # Batch_* folders
export LOSSLARP_TEST_DIR=/path/to/test            # the 3 test spots (default ~/Downloads/Hackathon-Polaron-test)
python segmentation/run_seg3.py --test            # segment the 3 test spots once (~2.5 min each, CPU, in parallel)
python pipeline.py --name k7_seg3 ...             # same arguments as the run you compare against
LOSSLARP_MASKS=harmonise python pipeline.py --name k7_harmonise ...   # the original masks, same code and machine
```

`LOSSLARP_MASKS=seg3` (the default on this branch) or `harmonise` (the original recipe). Each writes to its own folders
(`preprocessing/processed_seg3/`, `cnn/processed_seg3/`, `qc/processed_seg3/` vs `processed/`), so tiles and runs of
the two never mix. The label maps of the 31 training spots are committed in `labels/` (uint8 PNG, full raw size:
0 pore, 1 graphite/carbon, 2 Si-like, 255 not electrode). Other spots are segmented on first use and cached in
`processed/labels/` (`masks.py`); the on-the-fly path reproduces the committed maps pixel for pixel.

## Why

The cross-sections are not resin-filled, so material behind the cut plane (pore back walls, sub-surface particles)
shows through the pores at graphite-like BSE grey. A BSE threshold calls it graphite. The flat, smooth cut plane is
what separates solid from pore, and it is visible in Inlens (texture, edge rims) and SE (relief), not in BSE. BSE stays
the decisive detector for Si vs graphite (atomic-number contrast).

## Method (`segment_phases.py`)

Per image, no batch or session information: BSE anchored to the image's own black level and local graphite level, Inlens
rank-normalised (texture only), SE destriped (curtains) and expressed as deviation from the cut plane. Five features per
pixel (BSE level, BSE / Inlens / SE roughness, SE relief) feed an ensemble of 48 Gaussian mixtures whose components are
named pore or solid by physical rules (soft naming), then Potts smoothing and region rules (recesses grown into pores,
smooth cut plane never pore, tilted back walls to pore). Si-like = BSE above the midpoint between graphite and the
image's own Si mode, vetted object by object (seen through a pore, rough debris, granular carbon-binder, edge slivers).
Foreign phase (Cu current-collector foil in `epqdaau9`) = 255, counted as neither pore nor Si here.
~2.5 min per full image on 4 CPU threads, ~1.5 GB.

## Evidence

- **Blind comparison of five methods** (BSE-only baseline, multi-detector rules, pseudo-label pixel classifier, DINOv2
  features + classifier, per-image clustering) on 15 crops covering all 13 sessions, three judges blind to method (pore
  boundaries, Si vs graphite, artefacts). The base of this method ranked first under every lens (mean rank 1.67 of 5;
  6 major and 0 critical errors). The BSE-only recipe used on `main` ranked 4th (3.84; 32 major/critical errors), mostly
  back walls labelled graphite.
- **Stability:** deterministic; 0.1-2.5 % of pixels change under noise (sigma 4), blur (sigma 1) or a +20 BSE
  black-level lift.
- **This repo's fairness check** (`preprocessing/check_fairness.py`, material = porosity + Si, leave one spot out):

  | | session from material (chance 0.08) | batch from material (chance 0.33) |
  |---|---|---|
  | `harmonise` masks | 0.24 | 0.46 |
  | **`seg3` masks** | **0.17** | **0.57** |

- **13 tile features averaged per spot, scored like `cnn/baselines.py`** (evalkit, logistic regression C = 0.1,
  balanced accuracy; 100 permutations):

  | | losess (p) | mixed | joins |
  |---|---|---|---|
  | 13 features, `harmonise` masks | 0.45 (0.12) | 0.51 | 0.75 |
  | **13 features, `seg3` masks** | **0.49** (0.07) | **0.62** | 0.50 |
  | porosity only, `harmonise` | 0.20 (0.93) | 0.29 | 0.38 |
  | **porosity only, `seg3`** | **0.45** (0.19) | **0.56** | 0.63 |
  | imaging-only bar | 0.66 (0.01) | 0.29 | 0.38 |

  Porosity in the V2 window: median 0.159 (`seg3`) vs 0.115 (`harmonise`); by batch B1 < B2 < B3 with `seg3`, no
  order with `harmonise`. Whether the better target also helps the CNN embedding is what this branch tests.

## Limitations

- Tilted back walls facing the detector can read as Si (about 0.7 % of all Si pixels; worst `kbdh4tri`, ~6 % of its Si).
- Some back-wall bodies inside narrow gaps stay graphite; carbon-binder is merged into graphite.
- 2D section, pores not filled: porosity is a comparative index, not a 3D volume fraction.

Libraries: NumPy, SciPy, scikit-image, scikit-learn, Pillow. No pretrained model is used.
