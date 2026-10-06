# histogram_anomaly

How unusual a spot's whole BSE grey-level histogram is compared with the 17 baseline spots, as one score: the mean
|z| over 32 histogram bins. **Retired:** it is no longer computed and is kept only as an acquisition-novelty display.
Its one column was in `processed/features.csv` until the 2026-10-03 retirement.

| Column | Unit | Meaning |
|---|---|---|
| `histogram_anomaly_z` | dimensionless (mean of 32 per-bin \|z\|) | Mean over 32 grey-level bins of \|(the spot's bin share − baseline mean) ÷ baseline SD\|, on the 1–99 % stretched BSE image. Baseline = the other Batch_3 spots. **Not a calibrated z-score**: a typical baseline spot scores ≈ 0.8, not 0. Display only, never a KPI |

## Status

- **Retired on 2026-10-03** (commit 84cb17c), with the other four original features, to
  `features/_retired/histogram_anomaly/`. The registry reads only `features/*/feature.py` outside `_` folders
  (`features/__init__.py:42`), so the column is no longer computed.
- **There is no material successor, because it never measured a material property.** It was demoted to an
  acquisition-novelty diagnostic. It is listed under `not_material` in `analysis/verdict_config.yaml:28`, so it is
  never fed to a classifier and never ranked, and under `excluded_features` in `dashboard/impact_rules.yaml:70`. What
  a histogram change *could* mean for the material is measured by named, harmonised features:
  - phase proportions: `porosity_open_frac` ([open_porosity](../../open_porosity/README.md)) and
    `bright_solid_frac` ([si_fraction](../../si_fraction/README.md));
  - bright-phase grey level and identity: `si_grade` (`bright_contrast_ratio`, itself a session-sensitive display);
  - imaging novelty: the `acq_` checks in `preprocessing/acquisition.py`;
  - material novelty: the verdict's kNN novelty check on the Tier-1 and Tier-2 KPIs (`analysis/verdict_config.yaml:64`).
- **Its siblings, retired the same day:**
  - `porosity` → `open_porosity` (`porosity_open_frac`);
  - `bright_phase` → `si_fraction` (`bright_solid_frac`);
  - `pore_size` → `local_thickness` (`pore_lt_d50_um`, `pore_lt_d90_um`) and `minkowski_functionals`
    (`pore_n_per_1000um2`);
  - `particle_size` → no full replacement yet (graphite flake-size features are being researched).
- **Why the code is kept.** Older tables quote the column: `notes/feature_screen.md`, `notes/research_report.md`
  §3 and §6.6 (it drove the old Batch_1 T²/SPE alarms), the ledger and the dashboard's legacy group. The code and
  `models/histogram_anomaly.npz` (17 × 32 baseline histograms) reproduce those numbers exactly (audit: max |Δ| 1.4e-14).
  To compute it again, import `features._retired.histogram_anomaly.feature` explicitly (`features/_retired/README.md`).
  It is also the repo's worked example of a trained feature (`features/README.md:57`), and this README records why
  its leave-self-out scoring is not enough.

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `histogram_anomaly_z` up | The spot's BSE grey-level distribution is unlike the baseline spots'. On our data that is mostly *how the image was taken*: the session's tone curve and Si/graphite contrast ratio, focus, and the share of black-clipped pixels. A ±25 % gamma change or a 1 px blur raises it by 0.4–2.2, up to 6 baseline SD. It *can* also mean a real change in phase proportions (more Si phase or fewer pores) or a different bright-phase grade. Those would matter for capacity, first-cycle loss, swelling and ion transport [7–10]. But the score sums \|z\| over bins, so it loses sign and identity: it cannot say which phase moved or which way | **Neither**: a flag that says "imaging or material novelty, check the acquisition first", not a cell property | Strong that it is acquisition-dominated (session R² 0.94, within-session p 0.89). Low for any material reading |
| `histogram_anomaly_z` down | The histogram looks more like the reference set. In practice that means more like the *sessions* the reference spots came from: a Batch_3 spot whose session sibling sits in the reference scores low by construction | **Neither** | Strong (as a statistic) |

**Best value:** none, because it is not a material property. A typical exchangeable baseline spot scores ≈ 0.8, not 0
(theory √(2/π)·√(1 + 1/n) ≈ 0.82 for n = 16; observed B3 mean 0.86). Read a score only against the
leave-one-*session*-out baseline distribution (B3 1.04 ± 0.65, range 0.57–2.65), never against a fixed "2". Every
synthetic phantom scores above 2.3, whatever its porosity.

**Our batches** (audit run2: 31 spots, exact production code):
- **Batch_1: 1.66 ± 1.00 vs Batch_3 0.86 ± 0.36. The whole excess is the two session-2316 spots (3.02, 3.18), so
  n_eff = 1.** The other five read 1.09 ± 0.25, the same as Batch_3 scored session-honestly (1.04). Within mixed
  sessions the coefficient is +0.38 B3-SD, exact p = 0.89. The 2316 score mixes a grey-mapping change (the lowest
  Si/graphite contrast ratio, 1.66) with a bright-phase excess that `bright_solid_frac` already reports (0.16 / 0.20
  vs 0.066). No battery reading comes from this column.
- **Batch_2: 1.02 ± 0.35, equivalent.** It is identical to the session-honest Batch_3 value (1.04); within sessions
  +0.08 B3-SD.

## What it measures

BSE brightness rises monotonically with the mean atomic number of the material under the beam [1]. A polished
graphite–SiOx anode cross-section therefore has three grey populations:
- open pores, black (the raw signal is clipped at 0 in most sessions; session 2060 has a lifted black level);
- graphite plus carbon-binder, mid-grey;
- the Si-based phase, bright (≈ 1.7–2.3 × graphite).

The share of pixels under each population is an area fraction, and the peak positions are the phases' contrast.

The feature takes the 32-bin histogram of the whole BSE image after a 1–99 % percentile stretch. It scores how far
each bin's share lies from the baseline spots' mean, in units of their spread. It ignores the shape, size and
position of everything in the image.

What actually sets the histogram here is the stretch:
- It pins the 1st percentile (the black clip) to 0 and the 99th percentile to 255. The 99th percentile falls inside
  the bright phase: ≈ 10 % of baseline pixels sit at grey ≥ 160.
- Graphite then lands at about 255 × (graphite − p1) ÷ (p99 − p1). That is high on the scale when the session's
  Si/graphite contrast is low, and low when it is high. It also moves with how much bright phase the image holds;
  `preprocessing/process_data.py:169-170` warns about this.
- Across our spots the graphite peak sits at grey 84–140. Its displacement from the baseline mean explains most of
  the score (see *Evidence*).

## Why it matters for the battery

- **What a histogram change could mean.**
  - More pixels in the bright population means more Si phase. That gives more Li stored per gram, but also a larger
    first-cycle loss (low initial coulombic efficiency of SiOx), more electrode swelling, and capacity loss that grows
    with Si content [7–9].
  - Fewer black pixels means lower open porosity. Ionic resistivity, which limits high-rate performance, is set by
    porosity and tortuosity [10].
  - A shifted bright peak could mean a different Si-phase grade.
  - Batch-to-batch differences in a commercial Si-graphite cell do show up as cell-to-cell variation [11], so "the
    image looks different" is worth a look.
- **Why this score cannot carry that meaning.** The score is a sum of unsigned per-bin deviations. A porosity drop, a
  Si rise, a gamma change and a defocus all push it up. On our data the acquisition terms dominate (session R² 0.94,
  perturbation ratio 6.1). Every material term it could see is already measured, with sign, unit and acquisition
  controls, by `porosity_open_frac` and `bright_solid_frac`.
- **Harmful direction:** none. A high score is a reason to check the imaging first and then the named KPIs. It is never
  evidence of a better or worse cell.

## Industry / Polaron use

- **Quantitative BSE practice** treats the grey-level histogram as an acquisition check before anything is measured:
  - grey level converts to mean Z only when the experimental conditions are controlled; Sánchez et al. calibrated on
    standards [1];
  - BSE contrast changes with beam energy, working distance and the detector, and can even invert [2];
  - acquisition settings decide whether the phases can be separated at all, and this can be judged from the
    grey-level histograms (a segmentability index) [3].

  Those are exactly the things this score tracks.
- **Process monitoring.** The principled "something changed" alarm is multivariate SPC: Hotelling T² for "known mode,
  too far" and SPE/Q for "a new kind of change" [6]. `notes/research_report.md` §6.6 plans this on audited KPIs with
  leave-one-session-out limits. It excludes `histogram_anomaly_z`, because in the old version this column drove the
  Batch_1 alarms (T² 32 and 45, SPE 117 and 156).
- **Polaron** combine hand-crafted features with embeddings (`notes/polaron_chat.md`, item 3). They also warned that
  images carry acquisition clues that identify the batch without any material information. A raw grey-level
  histogram distance is the crudest embedding and the one most exposed to that trap.
- **This exact score** (mean per-bin |z| against a baseline set) has no literature source. It is an in-house construct.
- **What would move it:**
  - acquisition: a different detector tone curve (gamma, brightness/contrast mapping), focus or probe size, the black
    clip share, the session's Si/graphite contrast ratio;
  - material: the Si-phase dose or grade, and the porosity.

## How it is computed

Detector: BSE only. It does **not** use the shared harmonisation (`features/_common`): there is no graphite anchoring,
no noise top-up and no common crop. Unlike its siblings `porosity` and `bright_phase`, it has no segmentation and no
multi-Otsu step.

1. **Image** (`sample.bse`, built by `clean()`, `preprocessing/process_data.py:110-112`):
   - read the TIF as 8-bit grey (`load_grey`, :74-77);
   - `trim_border` (:80-97): drop edge rows and columns in which ≥ 95 % of pixels are ≥ 245 or ≤ 10;
   - `normalise_brightness` (:100-107): lo, hi = the 1st and 99th percentiles; compute (img − lo) ÷ max(hi − lo, 1),
     clip to [0, 1], multiply by 255 and cast to uint8. The raw p99 is only 116–135 and p1 is 0–6 (23–25 in session
     2060), so the stretch spans ≈ 90–135 raw levels and each raw level becomes ≈ 2–3 stretched levels. About 1 % of
     pixels end at 255. Between 1.0 and 3.8 % end at 0, because pores are already clipped at 0 in the raw image.
   - The whole trimmed image is used. That includes the top band and the bottom artefact rows that `_common` crops
     away.
2. **Histogram** (`feature.py:23-25`): `bins: 32` equal bins of 8 grey levels over [0, 256), divided by the pixel
   count.
3. **Train** (`feature.py:32-38`): `python features/run_features.py --train` passes the 17 Batch_3 spots
   (`run_features.py:88-90`). Their histograms (17 × 32) and ids are saved to `models/histogram_anomaly.npz`.
4. **Score** (`feature.py:41-49`):
   - the reference is every stored histogram except the spot's own (leave-self-out, :46): 16 histograms for a
     Batch_3 spot, 17 for any other spot;
   - take the per-bin mean and SD of the reference (numpy default, ddof = 0), with the SD floored at
     `std_floor: 0.001` (:47);
   - z_b = (h_b − mean_b) ÷ SD_b, and `histogram_anomaly_z` = the mean over the 32 bins of |z_b| (:48-49). Every bin
     has the same weight, whatever its pixel share.

Tuning: `config.yaml` holds only `bins: 32` and `std_floor: 0.001`; retrain after changing either. The cost is one
histogram per image, which is negligible next to the harmonised features (not timed separately).

## Evidence on our data

All 31 spots, recomputed on Modal from the raw TIFs with the exact production code (audit run2). The column matches
`processed/features.csv` and `processed/robustness.csv`.
- B3-SD = between-spot SD within Batch_3 (0.362).
- Session R² by chance ≈ 0.40 (13 height groups, 31 spots).
- Within-session p = exact permutation of batch labels inside the five mixed sessions (OLS y ~ C(session) +
  C(batch), 192 relabellings, minimum p ≈ 0.005).

### Scorecard

| Quantity | Value | Reading |
|---|---|---|
| Batch means ± SD (B1 / B2 / B3) | 1.663 ± 1.003 / 1.022 ± 0.347 / 0.856 ± 0.362 | B1 is high only through 2316 |
| Without the two 2316 spots | B1 1.088 ± 0.246 (+0.64 B3-SD); B2 +0.46 B3-SD | |
| η²(batch) | 0.27; 0.083 without 2316 | |
| Session R² | **0.944** (0.80 without 2316) | far above the 0.40 chance level |
| Within-session p; B1, B2 coefficients (B3-SD) | **0.89**; +0.38, +0.08 | no batch effect inside mixed sessions |
| Incoming vs baseline within sessions (1 df, 24 arrangements) | p 0.83, +0.13 B3-SD | |
| Raw within-session contrasts (B3-SD) | 2068 B2−B3 −0.52; 2080 B1−B3 +1.43, B2−B3 +0.55; 2148 B1−B2 −0.08; 2156 B1−B2 −0.41; 2272 B2−B3 −0.03 | |
| `analysis/rank_features.py` (production `rankings.csv`) | sep 0.76, sep_loo 0.59, q 0.075 → "separates" | that screen permutes across all spots (`analysis/rank_features.py:176`), so it does not control for session. With the within-session test added, the ledger records it as session-confounded (ws_p 0.89) |
| Leave-one-session-out AUC vs B3 (univariate) | B1 0.75, B2 0.62 | B1's AUC comes from 2316 |
| B3 variance components | σ_site 0.22, σ_session 0.31, ICC 0.66, %GRR upper 81 % | most B3 spread is between sessions |
| Split-half r (left/right; top/bottom) | 0.89; 0.90 (mean \|Δ\| 0.57 / 0.60 B3-SD) | high because both halves share the session's grey mapping, not because of material signal |
| Seed spread (3 noise top-up seeds) | 0.00 | vacuous: this pipeline has no noise top-up |
| Perturbation ratio (worst of 8) | **6.08** (gamma 0.8) | fails the 0.5 invariance gate by ≈ 12× |
| Lifted-black session 2060 | z = −0.50 (spots 0.48–1.13) | offset-invariant, by construction |
| Acquisition leak | ρ 0.44 with `acq_curtain_index` (production: 0.43 with image height) | |
| Phantom error | not applicable (a novelty score has no ground truth); see *Phantoms* | |

### Perturbations

The raw BSE image is perturbed and the full pipeline re-run on the B3 spots 71vgq3fw / cfe5vt7s / hzumfsms /
0grcilhi. The table gives Δz per spot and the ratio max |Δz| ÷ B3-SD.

| Perturbation | Δz per spot | Ratio |
|---|---|---|
| black +25 | 0 / 0 / 0 / 0 | **0.00** |
| gamma 0.8 | +0.54 / +2.20 / +1.78 / +1.34 | **6.08** |
| gamma 1.25 | +1.07 / +1.48 / +0.36 / +1.72 | 4.77 |
| blur σ = 1 px | +1.63 / +1.64 / +1.06 / +0.79 | 4.53 |
| blur along y only | +0.93 / +0.95 / +0.69 / +0.32 | 2.63 |
| blur along x only | +0.88 / +0.90 / +0.66 / +0.30 | 2.48 |
| contrast × 0.85 | +0.53 / +0.14 / +0.11 / +0.21 | 1.47 |
| noise σ = 4 | +0.10 / −0.15 / +0.05 / −0.01 | 0.41 |

- **Offset.** The 1–99 % stretch removes an offset exactly. That is why black +25 changes nothing and why the
  lifted-black 2060 spots look normal. The ledger's "sensitive to acquisition (black level)" is therefore wrong in its
  specifics: the score is blind to the black level and sensitive to every nonlinear change.
- **Linear contrast.** The stretch also removes a linear contrast change. The residual 1.47 comes from re-quantising
  the 8-bit image; a dithered histogram brings it down to 0.47.
- **Gamma and blur.** Gamma moves graphite relative to the two pinned percentiles. Blur sharpens the phase peaks and
  pulls pixels out of the tails. Both raise the score by 0.4–2.2 on every spot.
- **These perturbations are realistic.** Gamma 0.8 moves `bright_contrast_ratio` by −0.16 to −0.29. That is about the
  SD of the real session means of that ratio (0.18; range 1.66–2.28).

### What drives the score

- **Session means of z:**

  | Session | 2316 (B1) | 2088 (B3) | 2156 | 2148 | 2048 | 1880 | 2272 | 2080 | 1904 | 1612 | 2060 | 1780 | 2068 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|---|
  | Mean z | 3.10 | 1.49 | 1.43 | 1.24 | 1.11 | 1.07 | 0.99 | 0.81 | 0.77 | 0.76 | 0.71 | 0.70 | 0.57 |

  The two lowest-contrast sessions score highest: 2316 (contrast ratio 1.66) and 2088 (1.86).
- **Graphite-peak displacement.** The audit tried six reasonable definitions of the graphite peak (it sits at grey
  84–140):
  - the peak position has session R² 0.76–0.94 and Spearman −0.61 to −0.78 with `bright_contrast_ratio`;
  - z correlates with |peak − baseline mean| at ρ 0.62–0.89;
  - |peak displacement| plus `bright_solid_frac` explains R² 0.76–0.92 of z.

  The `bright_solid_frac` term works only through the two 2316 spots. Without them, z ~ `bright_solid_frac` has
  R² 0.0015, while z ~ session still has 0.80.
- **Where the score comes from in the histogram.**
  - Bins 20–31 (grey ≥ 160) hold ≈ 10 % of baseline pixels (B3 10.0 ± 1.0 %). Averaged over the spots they carry
    ≈ 38 % of the score, about their 37.5 % share of the 32 bins. Single spots range from 19 % to 69 %, and the top
    two are the 2316 spots.
  - Bins 29 and 30 have a baseline SD (0.00081, 0.00056) at the 0.001 floor.
  - Bin 0 (the black clip) carries up to 18 % of a spot's score (iv6g2oq0). z correlates ρ +0.52 with the share of
    pixels at 0.
- **Session 2316.** Its two spots are the only large values.
  - Bins 20–31 hold 22–24 % of their pixels (B3 maximum 11.6 %). The largest single-bin |z| is 11.5 and 15.8, and
    63–69 % of their score comes from those bins.
  - Part of this is grey mapping: the 2316 per-bin signature correlates 0.65 with the gamma 0.8 signature (the shape
    of the main peak).
  - Part is probably a real bright-phase excess, because no perturbation reproduces it. Gamma 0.8 moves
    `bright_solid_frac` by ≤ 0.0013. 2316 reads 0.16 / 0.20 on `bright_solid_frac` (B3 0.052–0.086) and 0.12 / 0.17
    on the fixed-threshold `bright_fixed_solid_frac` (B3 maximum 0.111).
  - Either way it is one single-batch session (n_eff = 1), and `si_fraction` / `si_grade` already report it with sign
    and unit.

### The leave-self-out reference flatters the baseline

15 of 17 B3 spots have a same-session B3 sibling in their reference. Only 1 of 7 B1 spots and 3 of 7 B2 spots do. Some
siblings are adjacent tiles of one strip (2088 9luzk4jm–hzumfsms, 1904 mgxahqnk–hawkfj64; `notes/seam_examples/`).
Removing the whole session from the reference changes the picture:

| | Leave-self-out (production) | Leave-session-out |
|---|---|---|
| B3 mean ± SD | 0.856 ± 0.362 | 1.041 ± 0.648 |
| B2 mean | 1.022 | 1.035 |
| B1 without 2316 | 1.088 | 1.088 |
| Session 2088 spots | 1.19 / 1.54 / 1.74 | 1.86 / 2.45 / 2.65 |
| η²(batch); without 2316 | 0.27; 0.083 | 0.14; 0.0013 |

As a control, the audit instead dropped the same number of random *other-session* B3 spots (200 draws). The B3 mean
stays at 0.854, so the rise comes from removing session siblings, not from the smaller reference. Session R² stays at
0.95.

### Redesigns tried by the audit (none fixes it)

| Variant | Session R² | Worst perturbation ratio |
|---|---|---|
| Production | 0.944 | 6.08 (gamma 0.8) |
| Dithered, comb-free histogram (removes the 8-bit re-quantisation comb) | 0.948 | 5.67 (gamma 0.8); contrast 0.47 |
| Harmonised crop `[250:-25, 8:-8]`, reference retrained | 0.915 | 4.61 (gamma 0.8); gamma 1.25 4.51, blur 4.25 |
| Histogram of the harmonised `h.bse` (graphite units) | 0.76 | 3.14 (gamma 1.25); the rest ≤ 0.83 |
| Earth mover's distance [5] to the leave-session-out B3 mean CDF | 0.91 | not run |
| Leave-session-out reference | 0.95 | not run |

The crop changes single values by up to 1.2 B3-SD (r17byphk; Spearman 0.84 with production) but changes no
conclusion.

### Categorisation and phantoms

- **Batch categorisation** (3-class leave-one-session-out balanced accuracy, chance 0.33):
  - `histogram_anomaly_z` alone reaches 0.55 (permutation p 0.07), below the acquisition-only set's 0.58.
  - In the old "all columns" set (59 columns, 0.68), removing this one column drops the accuracy to 0.59. It was
    carrying acquisition information into a set labelled "material".
- **Phantoms.** These are synthetic images: three flat grey levels plus noise, with porosity 0.06–0.09 and Si
  0.06–0.09 of the solid, i.e. inside the real range.
  - Every one scores 2.33–2.71. An image that is merely *rendered* differently already scores above 2.3.
  - The Si-rich phantoms (Si 0.13–0.14 of the solid) score 3.40–3.57, so the score does respond to a doubled bright
    phase (+0.9).
  - Masks play no role here, so the ":ideal" and full-pipeline phantom variants give identical values.

**Verdict: acquisition-dominated.**
- Session explains 94 % of its variance.
- There is no batch effect inside mixed sessions (p 0.89).
- It fails the invariance gate by ≈ 12×.
- The Batch_1 signal is one session, already covered by `bright_solid_frac`.
- Its split-half reliability is real, but it measures the session.

The audit review scored it 1 for explainability and 1 for categorisation. Keep it, at most, as a display-only
acquisition-novelty indicator.

## Uncertainty and pitfalls

- **Not a calibrated z-score.** The docstring's "0 = typical, above ~2 = clearly different" (`feature.py:4-5`,
  repeated in `dashboard/features_meta.yaml`) has no derivation. A typical spot scores ≈ 0.8, and session-honest B3
  values reach 2.65. The 32 bins are correlated (a peak shift moves neighbouring bins together), so the mean |z| has
  no simple null distribution either. Compare a score only with the leave-session-out baseline distribution.
- **Leave-self-out is not enough.** Same-session siblings share the grey mapping (see above). If the column is ever
  revived, score it against a leave-one-session-out reference (audit patch HA-2).
- **Equal bin weight.** Near-empty bright-tail bins weigh as much as the graphite peak, and bins 29–30 sit at the SD
  floor. The SD uses ddof = 0 with n = 16–17.
- **Sampling noise per phase.** Each phase's histogram mass is a phase fraction with its own single-image sampling
  error (integral range; ImageRep [4]). For the bright phase that error is about the size of the B3 between-spot SD
  (`si_fraction`), so even a perfectly harmonised histogram would be noisy in its bright-tail bins.
- **The stretch couples the phases.** The 99th percentile sits inside the bright phase, so a change in the Si-phase
  dose moves where graphite lands, and a change in clipped pore pixels moves bin 0. A material change and a
  grey-mapping change look alike.
- **8-bit comb.** About 90–135 raw grey levels are stretched over 256, so each raw level becomes ≈ 2–3 stretched
  levels (in sessions 2088 and 2272 only every second raw level is occupied in some spots). Some 8-level bins
  therefore get an extra occupied level. B3's bin-17 SD (3.9 % of pixels) is 2.5–4.6× that of its neighbours. The
  dithered test shows this is a nuisance, not the cause.
- **No crop.** The bottom rows of some images are artefacts: in epqdaau9 the row means climb from 57 to 138 over the
  last 25 rows. The harmonised crop changes values by up to 1.2 B3-SD.
- **Confounding.** Batch and session are confounded:
  - 18 of 31 spots have an image height found in only one batch (`notes/polaron_chat.md`);
  - three of the five mixed sessions are one strip split across batch folders (`features/BATTERY_IMPACT.md`).

  No histogram score can separate 2316's material from its imaging.
- **2D → 3D.** A phase's histogram mass is an area fraction, which is valid as a volume fraction for a random section.
  But the score mixes it with grey mapping, so nothing about the score transfers to 3D.
- **Stale notes elsewhere.** The ledger's "sensitive to acquisition (black level)" and the dashboard's "black
  clipping" wording point at an offset, the one perturbation it is immune to. Its real sensitivities are gamma, focus
  and the session's contrast ratio. This folder's code is left unchanged (retired).

## References

DOIs resolved through the Crossref API on 2026-10-03; titles, authors, years and volumes were checked. Abstracts were
read through Crossref or Semantic Scholar unless a reference says otherwise. "Amass" = also found with
`literature.load_papers`. No DOI comes from memory.

1. Sánchez, Deluigi, Castellano (2012) Mean atomic number quantitative assessment in backscattered electron imaging.
   *Microsc. Microanal.* 18:1355–1361. https://doi.org/10.1017/S1431927612013566 (BSE signal monotonic in mean Z;
   grey → Z only under controlled experimental conditions, checked on standards)
2. Kowoll, Müller, Fritsch-Decker et al. (2017) Contrast of backscattered electron SEM images of nanoparticles on
   substrates with complex structure. *Scanning* 2017:4907457. https://doi.org/10.1155/2017/4907457 (Amass; BSE
   contrast varies with primary energy and working distance and can invert; the detector's characteristics matter)
3. Chatzigeorgiou, Constantoudis, Katsiotis et al. (2024) Segmentability evaluation of back-scattered SEM images of
   multiphase materials. *Ultramicroscopy* 257:113892. https://doi.org/10.1016/j.ultramic.2023.113892 (Amass; an
   acquisition-quality index built from grey-level histograms and a Minkowski functional)
4. Dahari, Docherty, Kench, Cooper (2025) Prediction of microstructural representativity from a single image.
   *Adv. Sci.* 12:e14149. https://doi.org/10.1002/advs.202414149 (Amass; single-image phase-fraction error from the
   two-point correlation)
5. Rubner, Tomasi, Guibas (2000) The Earth Mover's Distance as a metric for image retrieval. *Int. J. Comput. Vis.*
   40:99–121. https://doi.org/10.1023/A:1026543900054 (abstract not read; cited only for the definition of the EMD
   variant the audit tested)
6. MacGregor, Kourti (1995) Statistical process control of multivariate processes. *Control Eng. Pract.* 3:403–414.
   https://doi.org/10.1016/0967-0661(95)00014-L (abstract not available; cited for the T²/SPE monitoring scheme)
7. Obrovac, Chevrier (2014) Alloy negative electrodes for Li-ion batteries. *Chem. Rev.* 114:11444–11502.
   https://doi.org/10.1021/cr500207g (abstract not available through these APIs; review of Si capacity and volume
   change)
8. Liu, Yu, Zhao et al. (2019) Silicon oxides: a promising family of anode materials for lithium-ion batteries.
   *Chem. Soc. Rev.* 48:285–309. https://doi.org/10.1039/c8cs00441b (high capacity, large volume change and low
   initial coulombic efficiency of SiOx)
9. Moyassari, Roth, Kücher et al. (2022) The role of silicon in silicon-graphite composite electrodes regarding
   specific capacity, cycle stability, and expansion. *J. Electrochem. Soc.* 169:010504.
   https://doi.org/10.1149/1945-7111/ac4545 (0–20 wt% Si: initial thickness change rises with Si; capacity loss
   correlates with Si content)
10. Landesfeind, Hattendorff, Ehrl et al. (2016) Tortuosity determination of battery electrodes and separators by
    impedance spectroscopy. *J. Electrochem. Soc.* 163:A1373–A1387. https://doi.org/10.1149/2.1141607jes
    (high-rate performance set by ionic resistivity; porosity-dependent MacMullin numbers and tortuosities)
11. Schindler, Sturm, Ludwig et al. (2021) Evolution of initial cell-to-cell variations during a three-year production
    cycle. *eTransportation* 8:100102. https://doi.org/10.1016/j.etran.2020.100102 (Amass; three batches of one
    commercial Si-graphite/NMC cell differ significantly in cell-to-cell variation)
12. Project sources:
    - audit run2 scorecard and the verified audit findings HA-1 to HA-5 and PIPE-3/4 (2026-10-03);
    - `notes/research_report.md` §3 and §6.6;
    - `notes/feature_screen.md`;
    - `notes/polaron_chat.md`;
    - `features/BATTERY_IMPACT.md` §5;
    - `features/_retired/README.md`.
