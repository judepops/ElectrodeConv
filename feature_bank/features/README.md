# features/

One folder per feature: `feature.py` (the code) and `config.yaml` (its tuning numbers). Each feature turns a `Sample` (one microscope spot) into one or more columns of `processed/features.csv`.

**What each feature means for the battery** (good, bad, neither or a trade-off, and where our batches sit): [BATTERY_IMPACT.md](BATTERY_IMPACT.md). Each folder's own `README.md` has the research behind it.

## Adding a feature

```bash
cp -r features/_template features/my_feature      # edit feature.py and config.yaml
python features/run_features.py --batches Batch_3 # quick check: no "[my_feature] failed" lines?
python analysis/inspect_feature.py my_feature     # does it separate the batches? stats + plot in processed/plots/
```

```python
from features import feature, load_config
from preprocessing import PIXEL_SIZE_UM

CFG = load_config(__file__)                # config.yaml in this folder

@feature                                   # one column, named after the function
def pore_fraction(sample):
    return float((sample.bse < CFG["threshold"]).mean())

@feature                                   # dict -> one column per key: pore_size_um_mean, pore_size_um_p90
def pore_size_um(sample):
    return {"mean": ..., "p90": ...}
```

`sample` has:

| Field | What it is |
|---|---|
| `sample.bse` | 2D `uint8`, backscattered electrons. Brightness = atomic weight. Best for telling materials apart |
| `sample.se` | 2D `uint8`, secondary electrons (file suffix `ETD` or `SE`). Surface texture |
| `sample.inlens` | 2D `uint8`, in-lens detector. Edges and the binder network |
| `sample.batch`, `sample.sample_id` | e.g. `"Batch_1"`, `"4ih2ggld"` |
| `sample.is_baseline`, `sample.split` | `True` for Batch_3; `"train"` / `"val"` / `"test"` |
| `sample.shape` | `(height, width)`, same for all three images |
| `PIXEL_SIZE_UM` | 0.025 µm per pixel. Measure in pixels, multiply by this |
| `tiles(img, size, stride=None, scale=1.0)` | list of `(y, x, tile)` if the feature works on patches |

Images are already greyscale, border-trimmed and brightness-normalised, so a threshold means the same thing in every image.

## Tuning

Magic numbers go in the feature's `config.yaml`, read with `CFG = load_config(__file__)`. Change a number, re-run `run_features.py`, compare with `inspect_feature.py`. The shared void / Si-phase segmentation is tuned in `_common/config.yaml` (see below); every current feature uses it.

## Trained features

Add `train(baseline_samples)` to `feature.py`. It gets the 17 baseline spots and saves what it learns to `models/<feature_name>.<ext>` (small files only, commit them). The feature loads that file. Run with:

```bash
python features/run_features.py --train
```

Score a baseline spot without its own contribution (see `minkowski_functionals`), otherwise the baseline looks artificially normal and every new batch looks different.

## Rules

- One folder per feature, named after the feature. Don't edit someone else's folder.
- Return a `float` or a `dict` of floats. Unit in the name: `_frac`, `_um`, `_um2`, `_per_1000um2`, `_z`.
- Normalise counts by image area, not per image. The images have different heights.
- Short docstring at the top of `feature.py`: what it measures, which image, unit, why it matters.
- Under ~10 s per spot. Subsample if needed. Reuse the `harmonised(sample)` masks instead of re-segmenting.
- Return `nan` for "could not measure". A feature that raises gives NaN and the run continues.
- No test scripts, notebooks or trial output in the repo.
- Every folder has a `README.md` (copy `_template/README.md`): the battery impact at a glance (what a rise or a fall
  means for the cell, good / bad / neither), the research and citations behind the feature, and how it does on our data.

## The shared harmonised segmentation (`_common/`)

The features below `_template` in the table are built on `features/_common/harmonise.py`, not on `sample.bse`.
Image height marks 13 microscope sessions, and session explains most of the variance of a threshold on the
stretched images. `harmonised(sample)` measures every spot the same way: the same central area, BSE in graphite
units (0 = black, 1 = graphite), noise matched to one level, then cached masks `void`, `bright` (Si-like phase),
`bright_fixed`, `dim`, plus rank-normalised Inlens / SE and the acquisition values in `h.acq`. It is cached on disk
in `processed/harmonised/` (0.3 s per spot after the first run). The recipe is frozen in `_common/config.yaml`.

```python
from features._common.harmonise import harmonised, fraction_se, PX_UM
h = harmonised(sample)
porosity = h.void.mean()                        # same area in every spot: h.area_um2
se, integral_range_um2 = fraction_se(h.void)    # single-image error bar from the two-point correlation
```

## Folders

| Folder | Columns | Image |
|---|---|---|
| `_template/` | copy this to start | |
| `_retired/` | the five original features (`porosity`, `bright_phase`, `pore_size`, `particle_size`, `histogram_anomaly`), no longer computed; see `_retired/README.md` for what replaced each | BSE |
| `si_fraction/` | `bright_solid_frac` (Tier-1 KPI), `bright_frac_ci95`, `bright_fixed_solid_frac`, `bright_n_per_1000um2` | BSE |
| `si_particles/` | `bright_d50_um`, `bright_d90_um`, `bright_solidity_aw`, `bright_aspect_aw`, `bright_orient_order`, `bright_agglom_d50_um`, `bright_contact_pore_frac` | BSE |
| `si_grade/` | `bright_contrast_ratio`, `bright_dim_frac`, `bright_internal_dark_frac` (diagnostics) | BSE |
| `open_porosity/` | `porosity_open_frac` (Tier-1 KPI), `porosity_open_ci95_frac`, `porosity_fixed060_frac`, `porosity_void_threshold` | BSE |
| `local_porosity/` | `local_porosity_q25_frac`, `local_porosity_dense_window_frac` | BSE |
| `local_thickness/` | `pore_lt_d50_um`, `pore_lt_d90_um`, `solid_lt_d50_um` | BSE |
| `chord_length/` | `solid_chord_x_um`, `solid_chord_y_um`, `solid_chord_hv_ratio` (pore spacing; diagnostics) | BSE |
| `two_point_correlation/` | `s2_{void,bright}_corrlen_{x,y}_um`, `s2_void_integral_range_um2`, `s2_bright_integral_range_um2` | BSE |
| `minkowski_functionals/` | `interface_density_per_um`, `interface_density_resid_z` (trained), `pore_n_per_1000um2` | BSE |
| `heterogeneity/` | `porosity_tile_cv`, `bright_tile_cv`, `bright_excess_het_ratio` | BSE |
| `flake_orientation/` | `flake_orient_order`, `flake_tilt_deg` | BSE |
| `carbon_domains/` | `carbon_dark_domain_frac` | BSE, Inlens |
| `flake_morphology/` | `flake_d50_um`, `flake_d50_aw_um`, `flake_thick_d50_um`, `flake_aspect_median`, `flake_n_per_1000um2` (graphite fragments, bright phase excluded) | BSE (harmonised, `_common`) |
| `thin_solid/` | `thin_solid_frac_{0p3,0p5,0p8}` (share of solid in ligaments thinner than 0.3 / 0.5 / 0.8 um; from the SAE interpretability work) | BSE (harmonised, `_common`) |
| `tortuosity_2d/` | `tortuosity_2d_solid_tau_y`, `_solid_tau_x`, `_solid_anisotropy` (2D solid-phase tortuosity, through-plane vs in-plane) | BSE (harmonised, `_common`) |

`run_features.py` runs every feature on every spot → `processed/features.csv`. Flags: `--train`, `--batches Batch_4`, `--csv`.
