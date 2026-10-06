# qc

The decision layer: every spot's material features against the Batch_3 baseline, a frozen accept / investigate /
reject rule, and the battery-property sliders. Plain code and a rule table; no model and no language model reaches
a verdict.

```bash
python qc/depth_profile.py       # -> qc/processed/depth_profile.csv: thin solid + depth profiles from the full image height
python qc/features_table.py      # -> qc/processed/features_table.csv: one row per spot (31 training + 3 test), 19 features
python qc/verdict.py             # -> qc/processed/verdicts.json: Batch_1, Batch_2 and each test spot vs Batch_3
python qc/impacts.py             # -> qc/processed/impacts.json: six battery-property sliders per lot, bands per batch
```

**features_table.py.** The mean of the 13 per-tile features (`cnn/tile_features.py`) over each spot's 26 tiles, plus
the chord ratio, plus the five columns of `depth_profile.py`. The three Polaron test spots
(`~/Downloads/Hackathon-Polaron-test/`, or `LOSSLARP_TEST_DIR`; skipped if missing) are preprocessed and tiled here
with the same recipe, labelled `Test`, and their tiles are cached under `cnn/processed/test_tiles/` for
`cnn/predict.py` and `cnn/explain.py`. The training `tiles.csv` is never touched (it defines the folds).

**depth_profile.py.** The tiles keep a central window, which mixes depths and drops the bottom of the coating. This
runs the same recipe on rows 250 .. H - 25 and measures, in 11.2 µm bands counted up from the bottom edge (read as
the current-collector side; only `epqdaau9` shows the Cu band, so ask Polaron): porosity and interface density of the
bottom band, interface 11-22 µm up, and the interface slope towards the bottom; plus `thin_solid_frac` (solid in
ligaments < 0.5 µm) on the standard window. Ported from the old repo (`features/depth_profile`, `features/thin_solid`,
found by profiling a DINOv2 sparse-autoencoder direction with depth). All five are diagnostics in the verdict.
On this recipe (31 spots, B3 vs rest, spot permutation; "within" = B3 minus the rest inside the 3 sessions that hold
both, labels shuffled inside sessions):

| Column | B1 / B2 / B3 | AUC | p | within signs, p |
|---|---|---|---|---|
| `depth_interface_b0_per_um` | 0.439 / 0.483 / 0.512 | 0.81 | 0.003 | +++, 0.25 |
| `depth_interface_slope_per_10um` | -0.048 / -0.029 / -0.006 | 0.82 | 0.003 | +-+, 0.50 |
| `depth_porosity_b0_frac` | 0.085 / 0.101 / 0.119 | 0.77 | 0.010 | +-+, 0.45 |
| `depth_interface_b1_per_um` | 0.457 / 0.497 / 0.505 | 0.65 | 0.16 | +++, 0.04 |
| `thin_solid_frac` | 0.089 / 0.090 / 0.089 | 0.48 | 0.88 | +++, 0.04 |

Batch_1 and Batch_2 get denser towards the bottom; Batch_3 is flat. The bottom-band columns separate across spots
but not inside sessions (session-confounded, as in the old repo); `thin_solid_frac` lost its across-spot separation
on this recipe (old recipe: 0.069 / 0.074 / 0.080) and keeps only the within-session sign. None separates Batch_1
from Batch_2 (AUC 0.51-0.69, p >= 0.27).

**verdict.py.** A trimmed port of the old repo's rule, same statistics: per feature, delta from the baseline mean, a
session-aware standard error (spots of one imaging session are not independent), a 90 % CI and the margin
1.5 × baseline SD ("normal variation"); zones EQUIV / BEYOND / INCONCL. Tier 1 (`si_solid_frac`, `porosity_frac`)
decides; only `si_solid_frac` may REJECT (porosity moves under a black-level shift, so it leads to INVESTIGATE).
Tier 2 (`si_agglom_d50_um`, `interface_density_per_um`) is a quality range (≥ 6 of 7 spots inside mean ± 2.86 SD).
Everything else is a diagnostic. Fewer than 3 sites: INSUFFICIENT DATA, with the per-feature numbers still shown.
Nothing was tuned on Batch_1 or Batch_2.

**impacts.py + impact_rules.yaml.** The sliders from the old dashboard, renamed to this repo's columns: capacity,
charging speed, lifespan, first-charge loss, swelling, consistency. Each is a weighted (evidence strength × feature
trust), cited combination of the feature shifts in margin units, clipped at ±3, with a Monte Carlo interval. New
here: a point score per spot, so each batch gets a median and interquartile range per property and the baseline its
own band. Every rule carries its mechanism sentence and citation; the page shows them.

## How good is each feature? (`feature_quality.py`)

```bash
python qc/feature_quality.py      # -> qc/processed/feature_quality.{csv,json}; impacts.py then takes the trust levels from it
```

Per feature: the share of spot-to-spot variance the imaging session explains, a split-half reliability (left vs right
half of a spot's tiles), the agreement between the BSE-threshold and seg3 mask recipes, and, descriptively only, the
single-feature batch score. The trust level (high / medium / low) comes from the reliability and mask-agreement gates
alone, never from the batch separation, so it cannot be tuned to the answer. The verdict tiers stay frozen as declared.
