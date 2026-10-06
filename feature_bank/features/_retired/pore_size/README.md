# pore_size (retired)

The original team's pore-size feature. It reports the size of the connected dark regions in the multi-Otsu pore mask
of the 1–99 % stretched BSE image (median and 90th percentile of their areas) and how many there are per area. It
added three columns to `processed/features.csv`. **Retired: these columns are no longer computed.**

| Column | Unit | Meaning |
|---|---|---|
| `pore_size_median_um2` | µm² | Median area of the 8-connected pore objects ≥ 20 px. Number-weighted: every object counts once, however small |
| `pore_size_p90_um2` | µm² | 90th percentile of the same object areas (number-weighted, not area-weighted) |
| `pore_size_count_per_1000um2` | objects / 1000 µm² | Number of those objects ÷ area of the whole frame × 1000 |

## Status

**Retired on 2026-10-03 and superseded.** The folder moved to `features/_retired/pore_size/`. The registry skips
folders that start with `_`, so these columns no longer appear in a fresh `processed/features.csv`. They are not in
the verdict (`analysis/verdict_config.yaml`).

| Old column | Use instead | Why the replacement is better |
|---|---|---|
| `pore_size_median_um2` | [`pore_lt_d50_um`](../../local_thickness/README.md) (Tier 2 in the verdict) | Area-weighted local thickness on the shared harmonised void mask. It does not depend on how the pore network splits into objects. Perturbation ratio 0.27 vs 2.95, session R² 0.54 vs 0.92 |
| `pore_size_p90_um2` | [`pore_lt_d90_um`](../../local_thickness/README.md) | Same reasons. Perturbation ratio 0.21 vs 1.19, session R² 0.46 vs 0.87 |
| `pore_size_count_per_1000um2` | [`pore_n_per_1000um2`](../../minkowski_functionals/README.md) (diagnostic only) | Objects ≥ 64 px on the harmonised mask over a fixed crop. Perturbation ratio 0.66 vs 1.58, session R² 0.44 vs 0.81. It is still noisy (split-half r 0.25) and has no battery link |

`features/_retired/README.md` and `ledger/entries/pore_size.yaml` also list
[`s2_void_corrlen_x_um`](../../two_point_correlation/README.md) as a pore-scale length.

**Why it is kept:** for comparison with earlier runs, `notes/research_report.md` and `notes/feature_screen.md`. To
recompute it, import `features._retired.pore_size.feature` explicitly before `features.compute_all(sample)`
(`features/_retired/README.md`).

**Why it was retired:**
- The columns follow the imaging session: session R² 0.81–0.92, against ≈ 0.40 by chance.
- No batch effect survives inside the mixed sessions (within-session p 0.31–0.51).
- A 25 nm blur or a gamma change moves them by 1.2–3.0 baseline SD.

The raw Batch_1 deficit in pore size comes from two sessions that hold no baseline spot.

## Battery impact at a glance

These rows say what a *real* change in pore size would mean. On our data these columns mostly read how the image was
taken, so none of the rows applies to the numbers below.

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `pore_size_median_um2` / `pore_size_p90_um2` up (larger pore sections) | *If real:* wider pores. At the same porosity the electrolyte wets the electrode faster: the wetting rate scales with porosity × √(effective pore radius) [6]. Ionic resistance is set by porosity, tortuosity and bottlenecks, not by mean pore size, so no rate gain is expected [7, 8]. A rise in p90 alone could mean cracks or under-calendering (no verified link). *On our data:* a 1 px (25 nm) blur raises the median by 1.7 B3-SD on average, and gamma 0.8 raises it by 0.8 | **Neither.** Legacy column; read `pore_lt_d50_um` / `pore_lt_d90_um` | Low (column); moderate for the wetting mechanism [6] |
| `pore_size_median_um2` / `pore_size_p90_um2` down | *If real:* narrower pores and slower wetting. In heavily calendered graphite anodes the mean MIP pore diameter fell from 0.90 to 0.33 µm and the wetting rate from 0.589 to 0.206 mm/s^0.5 [6]. *On our data:* it mostly means more of the smallest objects (20–40 px) were counted. That happens in the curtained session 2316, in the noisiest session 2148, and under gamma 1.25 (−1.1 B3-SD) | **Neither** on this column. Bad for wetting only if `pore_lt_d50_um` confirms it | Low |
| `pore_size_count_per_1000um2` up | More separate 2D pore sections. Either the pore space is more fragmented, or there are more small dark specks, or lower porosity breaks the network into more pieces (session 2148: lowest porosity, highest count). A 2D section count says nothing about 3D connectivity [12]. No battery link found | **Neither** | Low |
| `pore_size_count_per_1000um2` down | Fewer, merged sections: higher porosity or blur. A 1 px blur lowers the count by 0.9 B3-SD on average | **Neither** | Low |

**Best value:** none for this column, because it is retired. For pore width, match the baseline on `pore_lt_d50_um`
(Batch_3 0.78 ± 0.12 µm). An incoming lot has no better direction: only narrower pores at the same porosity have a
known cost, which is slower wetting [6].

**Our batches** (independent audit, 31 spots; B3-SD = between-spot SD within Batch_3):
- **Batch_1: no material difference shown. The raw deficit is two sessions.**
  - Raw values against Batch_3:
    - median 0.0545 ± 0.0133 µm² vs 0.0670 ± 0.0038 (−3.3 B3-SD);
    - p90 0.82 ± 0.38 vs 1.16 ± 0.14 µm² (−2.5);
    - count 165 ± 31 vs 149 ± 11 (+1.4).
  - Almost all of this comes from sessions 2316 (B1 only, curtained) and 2148 (B1 + B2, the noisiest and least porous
    session). In 2148, Batch_2 is just as extreme.
  - Within the mixed sessions the B1 coefficients are +0.64 / +0.10 / −0.83 B3-SD, with exact p 0.51 / 0.31 / 0.46.
- **Batch_2: no difference.**
  - Median 0.0630 ± 0.0071 (−1.0 B3-SD), p90 1.08 ± 0.21 (−0.6), count 147 ± 19 (−0.1).
  - Within sessions: +0.26 / +0.59 / −1.22 B3-SD, same p values.
- The replacements agree: `pore_lt_d50_um` shows no change for either lot (within-session p 0.56;
  `local_thickness` README).

## What it measures

The BSE detector shows open pores as black, graphite as mid-grey and the Si-based phase as bright. This feature finds
the black regions, cuts the pore mask into 8-connected objects, and measures each object's area. An object is a
patch of black pixels whose neighbours, diagonals included, are also black.

A materials expert should picture **islands, not pores**. A 2D section through a 3D-connected pore network cuts it
into separate patches. Our 2D pore phase does not percolate in any of the 31 spots; the largest cluster holds 3–27 % of the pore area (`notes/research_report.md` §7 item 9).
Each patch can be any of three things:
- one pore body;
- several pores merged through a 1–2 px neck;
- a small speck of dark texture.

So an object area is neither a pore diameter nor an MIP throat size. Image-based and intrusion pore sizes measure
different things even when both are done well [3].

The numbers on the baseline:

| Quantity | Batch_3 value | In pixels | Equivalent-circle diameter |
|---|---|---|---|
| Median object | 0.067 µm² | ≈ 107 px | ≈ 0.29 µm |
| 90th percentile object | 1.16 µm² | ≈ 1860 px | ≈ 1.2 µm |
| Objects per 1000 µm² | 149 | – | – |
| Smallest object counted | 0.0125 µm² | 20 px | 0.13 µm |

The statistics are number-weighted, so the median is pulled down by the many smallest objects. Objects of 20–40 px
make up 20–34 % of all counted objects: 22 % in a typical B3 spot, 34 % in session 2316. The p90 is set by the
largest merged clusters.

Measurements cover the whole trimmed frame. That frame is 175 µm wide and 40–58 µm high (7 050–10 130 µm²,
depending on the session's image height). It includes the top 250 rows, which carry a top-of-frame artefact, and the
bottom 25 rows. Both are excluded by the harmonised crop that the replacements use. Objects cut by the frame edge are
kept at their truncated size.

## Why it matters for the battery

The question behind the feature is sound: the same porosity can come as many narrow pores or a few wide ones, and that
matters to the cell. The connected-component area is a poor answer to it.

- **Wetting and formation.** Sheng et al. calendered graphite anodes from 59 to 41 µm and measured pore sizes by
  mercury intrusion [6].
  - The mean pore diameter went 0.78 → 0.90 → 0.33 µm.
  - The wetting rate went 0.375 → 0.589 → 0.206 mm/s^0.5.
  - The authors relate the wetting rate to porosity × √(effective pore radius).

  Narrower pores at the same porosity therefore mean slower electrolyte filling. In production that means longer
  wetting and formation times, and a risk of poorly wetted regions.
- **Ionic transport and rate.** Effective electrolyte transport follows porosity and tortuosity [7], which is
  anisotropic in flake-graphite electrodes [13]. It also follows constrictivity, i.e. bottlenecks [8]. A mean pore
  size, let alone a 2D object area, is not one of these. A pore-size shift at fixed porosity has no established rate
  effect unless it changes the bottlenecks.
- **Fast-charge plating.** Microstructure at several length scales together sets transport and kinetic limits, and
  with them the lithium-plating propensity [9]. A single median pore area cannot say which way the risk moves.
- **What changes pore size in a supplier's process:**
  - calendering (pore diameter falls sharply under heavy calendering [6]);
  - graphite particle-size distribution: in assembled fine graphite, the size mix set the packing porosity, the
    first-cycle efficiency (92.3 %, +4.7 points) and the 5C capacity (1.9×) [10]. That study measured porosity
    *inside* the assembled particles, so it supports the chain from particle size to pore structure to performance
    only qualitatively;
  - binder and carbon content, and the Si-phase dose.
- **Pore count.** The number of 2D pore sections per area is a fragmentation index of the section. It is not a 3D
  pore count, which would depend on the size distribution [12]. We found no study that links it to cell
  performance.

## Industry / Polaron use

- **Industry** measures electrode pore-size distributions by mercury intrusion porosimetry (MIP) on electrode
  coupons, as Sheng et al. did for graphite anodes [6]. MIP reports throat (entry) sizes. Image analysis sees pore
  bodies. The two differ in principle [3].
- **Image-based pore size** in porous-media and electrode work is usually a *continuous* pore-size distribution,
  i.e. local thickness [4], as implemented in toolkits such as PoreSpy [5]. That is what `local_thickness`
  (`pore_lt_d50_um`, `pore_lt_d90_um`) computes.
- **Connected-component areas of a 2D section:** we found no standard, CoA item or vendor KPI that uses them, so this
  is academic / ad hoc only. Pores do not come up in our Polaron chat notes (`notes/polaron_chat.md`).
- **What would move a real pore-size KPI:** calendering line load or gap, coat density, graphite PSD and shape, slurry
  dispersion, and binder or carbon content.

## How it is computed

Detector: BSE only. **None of the shared harmonisation applies:** no crop, no black/graphite anchoring, no noise
matching. The segmentation is shared with the retired `porosity_frac` (and was shared with `bright_phase` and
`particle_size`).

1. **Load** (`preprocessing/process_data.py:74-77`): first channel of the raw TIF, uint8.
2. **Trim** (`process_data.py:80-98`): drop edge rows and columns in which ≥ 95 % of the pixels are ≥ 245 or ≤ 10.
   On our 31 spots this removed no rows: image height = session height for all 31, so the top-of-frame artefact rows
   stay in.
3. **Stretch** (`process_data.py:100-107`): the 1st and 99th percentiles of the whole image map to 0 and 255, and
   the result is clipped and cast to uint8.
   - The 1st percentile lies inside the pore population (porosity ≈ 9–11 %). The 99th lies inside the bright phase
     (≈ 6 % of the area).
   - So the grey scale depends on how much pore and Si phase the image itself holds (`process_data.py:169-170`).
4. **Blur** (`features/_retired/porosity/feature.py:24`): Gaussian, σ = 2 px = 50 nm (`blur_sigma_px` in
   `features/_retired/porosity/config.yaml`). scipy keeps the uint8 type, so the blurred image is rounded to integer grey levels.
5. **Threshold** (`porosity/feature.py:25-27`): skimage `threshold_multiotsu` with 3 classes (`classes: 3`) on every
   4th pixel in each direction (`subsample: 4`), giving two integer thresholds (low, high).
   - This is Otsu's between-class-variance criterion [1] extended to two thresholds, as implemented in scikit-image
     [2].
   - The thresholds are cached per image (`porosity/feature.py:21-28`).
6. **Pore mask** (`porosity/feature.py:31-34`): blurred < low. No speck removal and no hole filling.
7. **Objects** (`features/_retired/pore_size/feature.py:23-26`): `skimage.measure.label` with its default full
   connectivity, i.e. 8-connected in 2D [2]. Areas come from `np.bincount`. Objects < `min_pore_px` = 20 px
   (0.0125 µm², `config.yaml`) are dropped.
8. **Columns** (`pore_size/feature.py:27-35`):
   - median and `np.percentile(·, 90)` (linear interpolation) of the areas × 0.025² µm²/px;
   - count ÷ (all pixels of the frame × 0.025²) × 1000.

   Objects touching the frame edge are kept at their cut size; there is no edge correction [11]. With no object at
   all, the result is NaN, NaN, 0.

## Evidence on our data

**Source.** Independent audit of 2026-10-03: a Modal re-computation from the raw TIFs with the production code
(commit b0b5841, before the move to `_retired`; only an import path changed since). The 31 per-spot values equal the
old `processed/features.csv`.

**Statistics used:**
- Within-session test: OLS y ~ C(session) + C(batch), exact permutation over the 192 relabellings inside the 5 mixed
  sessions (minimum p ≈ 0.005). "Incoming" is the same test with B1 + B2 vs B3 as 1 df (24 arrangements, minimum
  p 0.042).
- Session R² is read against ≈ 0.40 by chance (13 sessions, 31 spots).
- Perturbation ratio: max |shift| over 4 B3 spots ÷ B3-SD. Kinds: black +25, gamma 0.8 and 1.25, contrast × 0.85,
  noise σ 4, blur σ 1, x-only blur, y-only blur.
- LOSO AUC: univariate logistic, leave one session out, each lot vs Batch_3.

### Scorecard

| | `pore_size_median_um2` | `pore_size_p90_um2` | `pore_size_count_per_1000um2` |
|---|---|---|---|
| B1 / B2 / B3 mean | 0.0545 / 0.0630 / 0.0670 | 0.821 / 1.076 / 1.161 | 164.7 / 147.5 / 148.6 |
| SD B1 / B2 / B3 | 0.0133 / 0.0071 / 0.0038 | 0.377 / 0.210 / 0.136 | 31.0 / 19.0 / 11.2 |
| Marginal Δ B1, B2 (B3-SD) | −3.27, −1.04 | −2.50, −0.63 | +1.43, −0.10 |
| … without the two 2316 spots | −1.46, −1.04 | −1.23, −0.63 | +0.76, −0.10 |
| … also without 2148 | −0.99, −0.44 | −0.33, −0.12 | −0.55, −0.67 |
| η²(batch) (without 2316) | 0.33 (0.18) | 0.29 (0.12) | 0.13 (0.04) |
| Session R² | **0.92** | **0.87** | **0.81** |
| Within-session p (b1, b2 in B3-SD) | 0.51 (+0.64, +0.26) | 0.31 (+0.10, +0.59) | 0.46 (−0.83, −1.22) |
| Incoming-vs-baseline p (b) | 0.38 (+0.33) | 0.46 (+0.50) | 0.13 (−1.15) |
| B3 σ_site / σ_session (ICC) | 0.0038 / 0.0002 (0.00) | 0.136 / 0 (0.00) | 9.5 / 6.4 (0.31; %GRR upper 56 %, ndc 2.1) |
| Split-half r, left/right (mean \|Δ\|) | 0.76 (1.39 SD) | 0.72 (1.32 SD) | 0.60 (1.46 SD) |
| Split-half r, top/bottom (mean \|Δ\|; top − bottom) | 0.50 (2.27 SD; −0.49) | 0.51 (1.88 SD; −0.62) | 0.63 (1.51 SD; **+1.26**) |
| Noise-seed spread | 0 (by construction: no noise top-up) | 0 | 0 |
| Perturbation ratio (worst) | **2.95 (blur 1)** | **1.19 (gamma 1.25)** | **1.58 (gamma 1.25)** |
| Lifted-black session 2060, z | +0.36 | +0.13 | +1.42 |
| LOSO AUC B1 / B2 | 0.82 / 0.66 | 0.73 / 0.59 | 0.55 / 0.16 |
| Pipeline phantom error, mean (max \|·\|) | +2.3 % (6.2 %) | +7.1 % (16 %) | −2.8 % (6.2 %) |
| `rank_features.py`: sep, q (verdict) | 0.85, 0.039 ("separates") | 0.79, 0.068 ("separates") | 0.51, 0.28 ("no difference") |

**Perturbation ratios by kind** (B3-SD; mean signed shift in brackets):

| Kind | median | p90 | count |
|---|---|---|---|
| black +25 | 0.00 | 0.00 | 0.00 |
| gamma 0.8 | 1.48 (+0.78) | 0.50 | 0.98 (−0.39) |
| gamma 1.25 | 1.48 (−1.09) | 1.19 | 1.58 (+0.63) |
| contrast × 0.85 | 0.33 | 0.32 | 0.17 |
| noise σ 4 | 0.82 | 0.23 | 0.30 |
| blur σ 1 | **2.95 (+1.68)** | 1.05 | 1.02 (−0.88) |
| x-only blur | 1.15 | 0.92 | 0.59 |
| y-only blur | 1.80 | 0.52 | 0.62 |

- Black +25 is 0 by construction: the percentile stretch removes any offset.
- Contrast × 0.85 is not 0 only because of uint8 re-quantisation.
- Blur merges and erases the smallest objects, so the median rises and the count falls. Gamma 1.25 does the
  opposite. A 25 nm change in focus moves the median by up to 3 baseline SD.

**Within-session contrasts** (B3-SD):

| Session | median | p90 | count |
|---|---|---|---|
| 2068 B2 − B3 | +0.87 | +0.96 | −0.94 |
| 2080 B1 − B3 | +0.33 | +0.05 | −2.08 |
| 2080 B2 − B3 | +0.33 | −0.11 | −1.20 |
| 2148 B1 − B2 | +1.31 | −1.18 | +2.70 |
| 2156 B1 − B2 | −0.08 | −0.18 | −0.25 |
| 2272 B2 − B3 | −0.49 | +0.52 | −0.81 |

The marginal B1 deficit in median and p90 does not appear where B1 meets B3 in the same session (2080: +0.33 and
+0.05).

**Per session**, median µm² (p90 µm²; count):

| Session | Batch | Median | p90 | Count |
|---|---|---|---|---|
| 1612 | B3 | 0.064 | 1.09 | 147 |
| 1780 | B1 | 0.073 | 1.25 | 135 |
| 1880 | B1 | 0.057 | 1.10 | 149 |
| 1904 | B3 | 0.069 | 1.22 | 142 |
| 2048 | B2 | 0.066 | 1.21 | 135 |
| 2060 | B3 | 0.068 | 1.18 | 160 |
| 2068 | B2 | 0.073 | 1.21 | 131 |
| 2068 | B3 | 0.069 | 1.08 | 141 |
| 2080 | B1 / B2 / B3 | 0.063 / 0.063 / 0.062 | 1.06 / 1.04 / 1.05 | 137 / 147 / 161 |
| 2088 | B3 | 0.066 | 1.29 | 142 |
| **2148** | B1 / B2 | **0.054 / 0.049** | **0.50 / 0.67** | **216 / 186** |
| 2156 | B1 / B2 | 0.060 / 0.060 | 1.05 / 1.08 | 148 / 151 |
| 2272 | B2 / B3 | 0.064 / 0.066 | 1.12 / 1.05 | 148 / 157 |
| **2316** | B1 (2 spots) | **0.037** | **0.39** | **183** |

Two sessions hold every extreme value, and neither contains a B3 spot:
- **2316:** curtain index 1.64–1.68, against ≤ 1.16 elsewhere. It also has the Si-rich bright phase (`si_fraction`).
- **2148:** the highest raw BSE noise (0.211 graphite units, CNR 4.76, lowest of all sessions) and the lowest porosity
  (`porosity_open_frac` 0.076).

Both are B1/B2-only sessions, so these images cannot say whether their pore objects differ because of the material or
the imaging.

**Supporting checks** (verification of the porosity family):
- **Minimum object size.** Raising `min_pore_px` from 20 to 40 / 80 / 160 px gives:

  | `min_pore_px` | B1 marginal (B3-SD) | Session R² | Within-session b1 (p) |
  |---|---|---|---|
  | 20 | −3.3 | 0.92 | +0.64 (0.51) |
  | 40 | −2.8 | 0.89 | −0.43 (0.88) |
  | 80 | −2.1 | 0.77 | −1.45 (0.06) |
  | 160 | −1.1 | 0.56 | −0.08 (0.34) |

  The within-session coefficient changes sign with an arbitrary cut-off. The one near-significant value (80 px) is one
  of four cut-offs tried. **There is no stable batch content.**
- **Noise matching does not remove it.** Topping the raw BSE up to the harmonised noise level (σ = 0.235 graphite
  units) before the same pipeline leaves:
  - session R² 0.89 / 0.88 / 0.81;
  - the B1 marginal gap at −2.9 / −3.0 / +1.8 B3-SD;
  - within-session p 0.21 / 0.44 / 0.49.

  So the raw noise *level* is not the driver. The research report's "noise-driven (r = −0.71 with processed σ)"
  (`notes/research_report.md` §3) is an association across sessions, not the mechanism. The Spearman ρ with raw BSE
  noise is −0.32 / −0.45 / +0.42.
- **Edge objects.** Objects touching the frame edge hold 4–32 % of the pore area (B3 range). Dropping them leaves the
  picture unchanged: median session R² 0.91, within-session p 0.23; p90 0.84, p 0.92.
- **Phantoms** (18 synthetic images with known pores: isotropic ellipses, horizontal slits, 30°-tilted slits,
  non-overlapping disks of r = 16 px, Si-rich, patchy). Pipeline values were compared with the same statistics on the
  true pore mask, over the same frame and with the same 20 px rule:

  | Phantom | median | p90 | count |
  |---|---|---|---|
  | Disks | +1.2 % (true area 0.503 µm²) | +1.7 % | −0.5 % |
  | Isotropic / Si-rich | −3 to +2 % | +1 to +4 % | −1 to −2 % |
  | Slits / tilted slits | +3 to +6 % | +9 to +16 % | −3 to −5 % |
  | Patchy | +3 to +6 % | +5 to +14 % | −4 to −6 % |

  Slits bias the p90 up and the count down because nearly touching slits merge after the σ = 2 px blur. Against the
  scorecard's truth (all components on the harmonised crop) the count error is −5.5 % on average, max −8.7 %.

  **Limit:** fewer than 2 % of the true phantom objects are below 200 px, and almost none are 20–40 px. So the
  phantoms test resolved pores only, never the 20–40 px regime that sets the real median. At the phantom noise
  (≈ 0.16 graphite units) no excess of small objects appeared: every count error is negative.
  The audit's ":ideal" variant does not apply here, because these columns always segment the image themselves.
- **Categorisation.** A leave-one-session-out 3-class logistic model on these three columns alone reaches balanced
  accuracy 0.54 (permutation p 0.025). That is about what the 10 acquisition descriptors reach (0.58). The three
  replacements (`pore_lt_d50_um`, `pore_lt_d90_um`, `pore_n_per_1000um2`) reach 0.33 (p 0.46), i.e. chance.
  - The permutation shuffles labels across sessions. In this design batch and session are confounded, so this score
    measures session information, not material.
  - The high LOSO AUC of the median for B1 (0.82) is the same thing: the B1 sessions 2316 and 2148 happen to be the
    low-median sessions.

**What the evidence supports:**
- The three columns describe the imaging session (focus, tone curve, curtaining, noise texture) and the 2D connectivity
  of the pore section more than any pore size of the material.
- The B1 "smaller pores" signal that `rank_features.py` flags (median sep 0.85, q 0.039) is the two sessions 2316
  and 2148.
- The one weak hint that survives within sessions is the count. B1 and B2 read 0.8–1.2 B3-SD *lower* than B3 in the
  same session, the opposite sign to the marginal gap. It is not significant (p 0.46; incoming p 0.13). Its successor
  `pore_n_per_1000um2` shows the same lean (b1 −0.52, b2 −1.35, p 0.41; incoming p 0.17). Not established.

## Uncertainty and pitfalls

- **Object area is not pore size.** Merges through 1–2 px necks change an object's area by orders of magnitude, so the
  p90 measures the largest merged clusters. A continuous (local-thickness) definition avoids this [3, 4].
- **The median is set at the cut-off.** It is number-weighted, and 20–40 px objects are 20–34 % of all objects, so the
  arbitrary 20 px minimum and anything that creates or erases tiny objects move it. That includes focus, gamma,
  curtaining and noise texture.
  - The B3-SD of the median is 0.0038 µm² = 6 px of area per object.
  - Whether the 20–40 px objects are real small pores or imaging texture was not tested.
- **Focus and tone curve.** A 25 nm blur moves the median by up to 2.95 B3-SD. Gamma moves all three by 1.2–1.6.
  - A pure black-level offset is removed by the stretch (ratio 0). Black-level *clipping* of the pore floor, which
    differs between sessions (raw clip-at-0 share 0.000–0.036), changes the stretch and was not tested on these
    columns.
- **Image-dependent grey scale.** The 1–99 % stretch depends on the image's own pore and Si content, so the multi-Otsu
  threshold is not comparable between spots (`process_data.py:169-170`).
- **Seed spread 0 is not robustness.** These columns never see the harmonised noise top-up, so the seed test cannot
  move them.
- **Window and edges.**
  - The whole frame is used. That includes the top 250 artefact rows and the bottom 25 rows, and the area varies with
    session height (7 050–10 130 µm²).
  - The top half of each frame reads 1.26 B3-SD more objects than the bottom half.
  - Edge-cut objects (4–32 % of the pore area) are kept at their truncated size, with no minus-sampling correction
    [11].
- **No speck cleanup.** The mask is used raw: no minimum-size opening and no hole filling. Only the 20 px area rule
  removes specks.
- **Baseline variance is small and session-free, but that does not make the column safe.** In B3, sessions do not
  differ (ICC ≈ 0 for the median and p90). The "session" verdict therefore rests on the reversal inside mixed
  sessions, on the B1/B2-only sessions 2316 and 2148, and on the blur and gamma sensitivity, not on B3 variance
  components.
- **2D → 3D.**
  - The area distribution of section profiles is not the 3D pore-size distribution (Wicksell-type unfolding would be
    needed, and it assumes isolated convex pores) [12].
  - Number per area is not number per volume [12].
  - For a 3D-connected network, a "3D pore count" is not even defined.

## References

DOIs, titles, authors, years and volume/pages were checked against the Crossref API on 2026-10-03. Refs 9 and 10
were found with `literature.load_papers` (abstracts read there). The numbers quoted from ref 6 come from its
Frontiers full text (Table 2 and discussion), read on 2026-10-03.

1. Otsu N. (1979) A threshold selection method from gray-level histograms. *IEEE Trans. Syst. Man Cybern.*
   9(1):62–66. https://doi.org/10.1109/tsmc.1979.4310076
2. van der Walt S., Schönberger J. L., Nunez-Iglesias J., Boulogne F. et al. (2014) scikit-image: image processing in
   Python. *PeerJ* 2:e453. https://doi.org/10.7717/peerj.453 (`threshold_multiotsu`, `label`). The multilevel
   algorithm it implements, Liao, Chen & Chung (2001) *J. Inf. Sci. Eng.* 17:713, has no DOI: **[unverified]**.
3. Münch B., Holzer L. (2008) Contradicting geometrical concepts in pore size analysis attained with electron
   microscopy and mercury intrusion. *J. Am. Ceram. Soc.* 91(12):4059–4067.
   https://doi.org/10.1111/j.1551-2916.2008.02736.x
4. Hildebrand T., Rüegsegger P. (1997) A new method for the model-independent assessment of thickness in
   three-dimensional images. *J. Microsc.* 185(1):67–75. https://doi.org/10.1046/j.1365-2818.1997.1340694.x
5. Gostick J. T., Khan Z. A., Tranter T. G. et al. (2019) PoreSpy: a Python toolkit for quantitative analysis of
   porous media images. *J. Open Source Softw.* https://doi.org/10.21105/joss.01296
6. Sheng Y., Fell C. R., Son Y. K., Metz B. M. et al. (2014) Effect of calendering on electrode wettability in
   lithium-ion batteries. *Front. Energy Res.* 2:56. https://doi.org/10.3389/fenrg.2014.00056 (graphite anode
   59 → 53 → 41 µm: porosity 47.6 → 45.0 → 37.4 %, MIP mean pore diameter 0.78 → 0.90 → 0.33 µm, wetting rate
   0.375 → 0.589 → 0.206 mm/s^0.5)
7. Landesfeind J., Hattendorff J., Ehrl A., Wall W. A., Gasteiger H. A. (2016) Tortuosity determination of battery
   electrodes and separators by impedance spectroscopy. *J. Electrochem. Soc.* 163(7):A1373–A1387.
   https://doi.org/10.1149/2.1141607jes
8. Holzer L., Wiedenmann D., Münch B., Keller L. et al. (2013) The influence of constrictivity on the effective
   transport properties of porous layers in electrolysis and fuel cells. *J. Mater. Sci.* 48(7):2934–2952.
   https://doi.org/10.1007/s10853-012-6968-z (cited for what its title states: bottlenecks change effective
   transport; Crossref holds no abstract)
9. Kabra V., Parmananda M., Fear C., Usseglio-Viretta F. et al. (2020) Mechanistic analysis of microstructural
   attributes to lithium plating in fast charging. *ACS Appl. Mater. Interfaces* 12(50):55795–55808.
   https://doi.org/10.1021/acsami.0c15144
10. Choi Y., Lee Y., Kim J., Im J. et al. (2023) Optimization of pore characteristics of graphite-based anode for
    Li-ion batteries by control of the particle size distribution. *Materials* 16(21):6896.
    https://doi.org/10.3390/ma16216896
11. Miles R. E. (1978) The sampling, by quadrats, of planar aggregates. *J. Microsc.* 113(3):257–267.
    https://doi.org/10.1111/j.1365-2818.1978.tb00104.x (edge-corrected object counting)
12. Russ J. C., DeHoff R. T. (2000) *Practical Stereology*, 2nd ed. Springer. https://doi.org/10.1007/978-1-4615-1233-2
    (section profiles vs 3D size distributions; number per area vs per volume)
13. Ebner M., Chung D.-W., García R. E., Wood V. (2014) Tortuosity anisotropy in lithium-ion battery electrodes.
    *Adv. Energy Mater.* 4(5):1301278. https://doi.org/10.1002/aenm.201301278
14. Project sources:
    - `notes/research_report.md` §3 ("Existing features: keep or fix") and §7 item 9 (2D pore percolation in 0 of 31 spots);
    - `notes/feature_screen.md` (exact rebuild of these columns; session R² and blur ratios);
    - `features/BATTERY_IMPACT.md` §5;
    - `features/_retired/README.md`;
    - `ledger/entries/pore_size.yaml`. Its two refs (Torquato 2002; Lee et al. 2023) are general pore-description
      and segmentation background and are not used here.
