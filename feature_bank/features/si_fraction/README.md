# si_fraction

How much of the electrode is the bright, Si-based phase (most likely SiOx), measured on the harmonised BSE
image. The decision KPI is `bright_solid_frac`. The other three columns are its error bar, a cross-check
with a fixed threshold, and a particle count. `bright_frac` is computed in `feature.py` only.

| Column | Unit | Meaning |
|---|---|---|
| `bright_solid_frac` | fraction of solid | Bright-phase area ÷ solid (non-void) area. **Tier-1 decision KPI**, a first-order proxy for the Si-phase weight fraction of the active material |
| `bright_frac` | fraction of image | Bright-phase area ÷ total crop area. **Not a features.csv column** (team audit 2026-10-03): ρ > 0.9 with `bright_solid_frac`, same profile |
| `bright_frac_ci95` | fraction (half-width) | 1.96 × the single-image standard error of `bright_frac`, from the two-point correlation (ImageRep idea). Sampling error only; on the verdict's `not_material` list (never fed to a classifier) |
| `bright_fixed_solid_frac` | fraction of solid | `bright_solid_frac` using the fixed-threshold mask (1.45 × graphite). Sensitivity recipe: it must move in the same direction as the primary |
| `bright_n_per_1000um2` | objects / 1000 µm² | Bright objects ≥ 1 µm equivalent-circle diameter, Miles–Lantuéjoul edge-corrected |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `bright_solid_frac` up (the fixed-recipe `bright_fixed_solid_frac` reads the same way) | More Si phase in the active material. The anode stores more Li per gram [1, 2, 4], but loses more Li for good in the first cycle, because SiOx turns partly into Li silicates and Li₂O (lower ICE) [3, 6, 13]. The electrode also swells more [1, 2] and takes more mechanical damage [1, 14]. Early fade is faster, because the Si fraction loses capacity first [2, 5, 14]. In a cell built for the baseline the cathode loading is fixed: the extra anode capacity mostly goes unused (higher N/P), while the extra first-cycle Li loss comes out of the cathode's Li (design arithmetic, no direct citation) | **Trade-off** at the material level: more anode capacity against worse ICE, swelling and life [5]. **Bad** for an incoming lot, because in a fixed cell design the costs land and the gain mostly does not | Strong for each direction, *if* the bright phase is Si-based (EDS not done yet). Moderate for the full-cell net effect and for the size: reading area as wt% assumes the same Si material and density |
| `bright_solid_frac` down | Less Si phase: the anode holds less capacity than the cell design assumes, so the N/P margin shrinks (design arithmetic) [2, 4]. ICE, swelling and Si-driven fade improve slightly [2, 3, 5] | **Trade-off, out of spec**: a capacity shortfall against the design (bad against the spec), with slightly better ICE, swelling and life | Strong for each direction; moderate for the net cell effect, which depends on the design's N/P margin (not known here). Same identity caveat |
| `bright_fixed_solid_frac` moves against `bright_solid_frac` | Not a cell property. Either the session tone curve (the fixed cut follows it, see "How it is computed") or a bright phase with a different grey level, i.e. possibly a different Si material (as in 2316, `si_grade`) | **Neither**: a warning about the measurement or the phase identity. It blocks a REJECT until EDS | Moderate |
| `bright_n_per_1000um2` up at the same fraction | More, smaller Si-phase objects: finer or broken Si powder, or agglomerates that broke up. If the Si is finer: more surface, so more SEI and lower ICE, but less lithiation stress per particle [1]. Si particle size is one of the levers that set Si–graphite degradation [14] | **Neither** on its own: a sign the supplier's process changed (milling, classification or mixing). Check `bright_d90_um` / `bright_agglom_d50_um` (`si_particles`) before naming a direction | Low (session-sensitive: ICC 0.44, lifted-black z +2.0) |
| `bright_n_per_1000um2` down at the same fraction | Fewer, larger objects: coarser Si or agglomerates. Larger Si particles carry more lithiation stress [1, 14]. If agglomerated, they plausibly create local swelling hot-spots and electrode cracking (mechanism only, no quantitative link) [1] | **Neither** on its own (same reason). **Bad** only once `si_particles` confirms coarsening or agglomeration | Low |
| `bright_frac_ci95` up or down | Not a material property. It is the 95 % sampling error of a single spot, and it grows with the bright fraction and with how large or clustered the Si features are (integral range) [7, 8] | **Neither**: it only says how far one spot can be trusted | Strong (as a statistic) |

**Best value:** match the baseline, Batch_3: 0.066 ± 0.011 of the solid. The verdict allows ±0.0166 (1.5 baseline
SD). An incoming lot has no "better" direction. Up trades anode capacity for ICE, swelling and life, and in a fixed
design the costs win. Down is a capacity shortfall against the design, with slightly better ICE.

**Our batches** (final numbers: `processed/rankings.csv`, `processed/robustness.csv`, `analysis/verdicts/`):
- **Batch_1: INVESTIGATE (Si-phase anomaly) in two spots from one session (2316, n_eff = 1). The other five spots
  match the baseline.**
  - The raw mean is 0.100 ± 0.060 against 0.066 ± 0.011 (+3.0 SD). All of that comes from the two
    session-2316 spots: they read 0.162 and 0.204 (+8.7 and +12.5 SD). The fixed recipe agrees (+2.2 and +4.8 SD),
    and those spots hold 2.5× the baseline count of objects ≥ 1 µm. The other five spots read 0.067 ± 0.016 (+0.0 SD).
  - The screen gives sep 0.79 and q 0.077, which passes the 0.1 bar. But that test permutes across sessions, and
    without the 2316 spots sep falls to 0.53.
  - **The within-session test cannot see the 2316 excess.** Session 2316 holds only B1 spots, so the session term
    absorbs it. These images therefore cannot separate a material change from a session effect there
    (n_eff = 1 session). On the three B1 spots that share a session with other batches (2080, 2148, 2156) there is no
    increase: the coefficient is −1.66 SD, exact p = 0.24, noise-level.
  - In the Tier-1 verdict, δ = +0.034 with P(|δ| > margin) = 0.79, but the 90 % CI [−0.011, +0.078] spans zero and
    reaches inside the margin (INCONCL). That alone keeps REJECT closed. Two more blocks would apply. For R1, the
    only session-matched contrast (2080, −2.70 SD) points the other way, which the certificate flags as
    "acquisition-confounded". For both paths, the fixed-recipe identity check is "not confirmed", because its 90 % CI
    includes 0. The lot spread is 5.4× the baseline's (Brown–Forsythe q 0.024), carried by the same two spots.
  - Battery reading: if 2316 is Si-based, those regions hold 2.4–3× the Si-phase area, which would mean locally
    more anode capacity, lower ICE and more swelling. But the phase there is darker and more textured (`si_grade`),
    so the area excess cannot be read as 2.4–3× the Si mass. Run EDS first.
- **Batch_2: INVESTIGATE, most likely equivalent. Reads ≈ 1 SD low, not confirmed within sessions. This KPI is the
  one that blocks CONDITIONAL ACCEPT.**
  - The raw mean is 0.055 ± 0.013: δ = −0.012 (−1.05 SD, 17 % relative), 90 % CI [−0.022, −0.001], margin 0.0166. The
    fixed recipe agrees in direction (−1.07 SD; identity check passes).
  - Part of the raw gap may be session. The two lowest B2 spots (0.046, 0.042) come from 2048, a B2-only session.
    Without them, B2 reads 0.059 (−0.66 SD). On B2 against B3 alone, sep is 0.70 (own recomputation). That is not far
    above the ≈ 0.65 the acquisition settings reach in the three-batch screen.
  - Within sessions the coefficient is −1.50 SD (exact p = 0.24, noise-level). It comes from 2080 (−2.54 SD, one
    spot per side) and 2068 (−1.58 SD, one B2 spot against three B3). 2272 reads +0.01 SD.
  - In the Tier-1 verdict P(|δ| > margin) = 0.24, just above the 0.2 bar for CONDITIONAL ACCEPT. That alone keeps B2
    at INVESTIGATE. The other Tier-1 KPI, `porosity_open_frac`, is at 0.06, and there are no Tier-2 or heterogeneity
    flags.
  - Battery reading: if real, the lot has about 1.2 percentage points (≈ 17 % relative) less Si phase in the solid.
    That is a small capacity shortfall against the design, with slightly better ICE, and it is inside the margin.
    Not established.

## What it measures

In BSE the signal rises with mean atomic number, so the Si-based particles (Si Z = 14, O Z = 8) show up clearly
brighter than graphite (C, Z = 6). On every spot the shared harmonisation (`features/_common`) anchors BSE so
that black = 0 and graphite = 1. It then marks a pixel as bright when the 1.5 px-blurred BSE is above the
midpoint between graphite and that image's own bright-phase mode. In Batch_3 the mode sits at 1.88–2.32 ×
graphite, and the threshold therefore at 1.44–1.66.

The particles are angular 2–10 µm shards that cover ≈ 6 % of the solid. `bright_solid_frac` is the share of
the solid cross-section they occupy. By the Delesse principle a random section's area fraction is an unbiased
estimate of the volume fraction [10, 11]. SiOx and graphite have similar densities (both ≈ 2.2 g/cm³), so to
first order this is also the Si-phase weight fraction of the active material. That reading holds only while the
bright phase stays the same material (see pitfalls).

Dividing by solid rather than by total area removes the porosity: a lot that is pressed harder has less void
but the same recipe. All values come from the same central crop on every spot: 1336 rows × 6944–6984 columns
(5798–5832 µm², 33 × 174–175 µm; the width follows the image width).

## Why it matters for the battery

- **Capacity.** The Si phase stores several times more Li per gram than graphite (Si alloys up to Li₁₅Si₄;
  SiOx sits between Si and graphite) [1, 3]. A small change in Si-phase weight fraction moves the anode's
  specific capacity, and therefore the N/P balance the cell was designed for [2, 4].
- **First-cycle efficiency.** In SiOx the oxide part reacts irreversibly into Li silicates and Li₂O, so more
  SiOx means more Li lost in the first cycle (lower ICE) [3, 6, 13].
- **Swelling and mechanical damage.** Si expands by up to ≈ 280 % on lithiation; SiOx expands less but still
  far more than graphite (≈ 10 %) [1]. More Si means more electrode thickness change [2], and more particle
  and electrode damage [1, 14].
- **Fade.** In Si–graphite composites the Si fraction loses capacity faster than graphite does: rapid loss of
  active Si dominates early fade [5, 14], and capacity loss rises with Si content [2]. More Si phase looks good
  at formation and worse after cycling ("fine now, worse later", `notes/research_report.md` §8).

Harmful directions: **higher** gives more anode capacity but lower ICE, more swelling and faster fade. In a cell
designed for the baseline the costs outweigh the gain. **Lower** gives a capacity shortfall against the cell
design, with slightly better ICE and swelling. Both are trade-offs and out-of-spec supplier changes. The number
density adds the size and dispersion side, but on its own it is only a sign that the process changed. For the
same area, more, smaller objects mean finer Si or broken particles (more surface, more SEI). Fewer, larger
objects mean coarser Si or agglomerates (more stress per particle, plausibly local swelling hot-spots)
[1, 14].

## Industry / Polaron use

- **Powder CoA.** Si content and grade are checked on the powder (ICP/TGA, capacity and ICE classes in
  GB/T 38823-2020 for Si–C anode materials; `notes/research_report.md` §2). A cross-section measures what
  actually ended up in the electrode, after mixing and coating.
- **Cell makers.** Commercial graphite–SiOx negative electrodes are standard (e.g. the LG M50 cell
  parameterised by Chen et al. [12]; the "3–10 wt% SiOx" figure often quoted for it is **[unverified]**).
- **Polaron/Imperial.** Phase fractions with a single-image error bar are the core of ImageRep [7] and of
  Polaron's "objective acceptance criteria / batch-to-batch comparability" offering.
- **What would move it:** a different Si-phase dosing in the slurry, a substituted Si grade (different density
  or particle size), segregation during mixing or coating, or a blend-ratio error at the supplier. Number
  density additionally moves with Si powder milling or classification and with agglomeration.

## How it is computed

1. `h = harmonised(sample)` (shared, cached, `features/_common/harmonise.py`). It crops, anchors BSE to graphite
   units and tops up the noise to σ = 0.235. It builds `h.void` (Otsu between pore and graphite), `h.bright`
   (adaptive midpoint) and `h.bright_fixed` (fixed 1.45 × graphite). Both bright masks are opened by 1 px, holes
   < 0.25 µm² are filled, objects < 0.1 µm² are dropped, and an object is kept only if it exceeds its threshold
   by 0.1 somewhere. No re-segmentation here.
2. `bright_solid_frac` = |bright ∧ solid| / |solid|, with solid = ¬void. `bright_frac` = |bright| / |crop| (computed,
   not a column).
3. `bright_frac_ci95` = `ci_z` (1.96) × `fraction_se(h.bright)`. The standard error is computed as follows: the
   mask is block-averaged 4 × 4 px, its FFT autocovariance is summed over |dy| ≤ 4 µm and |dx| ≤ 12 µm, and
   var = ∫C(r)dr / A_image (Lantuéjoul's integral range [8], the idea behind ImageRep [7]). For
   `bright_solid_frac` divide it by (1 − porosity) (≈ 0.9).
4. `bright_fixed_solid_frac`: same as step 2 with `h.bright_fixed`.
5. `bright_n_per_1000um2`: 8-connected objects of `h.bright` with area ≥ π(`min_object_ecd_um`/2)² (1 µm ECD =
   1257 px). Objects touching the crop edge get weight 0. Every other object gets weight H·W / ((H − b_h)(W − b_w)),
   where b_h × b_w is its bounding box: the inverse probability that an object of that size fits fully inside the
   window (Miles–Lantuéjoul minus-sampling [9, 11]). The weight sum is divided by the crop area. Touching
   particles are not split.

**Why the adaptive midpoint is the primary recipe and the fixed threshold only a sensitivity check.** In this
data the bright/graphite mode ratio is set by the session, not by the material. It runs from 1.88 (2088) to 2.34
(2068) across sessions, while within mixed sessions it agrees across batches to ≤ 0.8 B3-SD (see `si_grade`).
A fixed threshold in graphite units therefore sits at a different place on the particle-edge ramp in every
session:

- **High-ratio sessions read high.** 2060 (mode 2.25–2.29), 1612 and 2148 come out high on the fixed recipe.
  Fixed − adaptive is +0.031 in 2060, +0.023 in 1612, +0.018 in 2148 and ≈ 0 in 2088/2156.
- **The difference follows the mode.** Across sites (2316 excluded), fixed − adaptive correlates r = 0.79 with
  the bright mode. The fixed KPI itself correlates r = 0.57 with the mode; the adaptive one r = 0.17.
- **The fixed recipe carries a session component.** On B3 alone (7 sessions, method of moments), the fixed
  recipe has σ_sess = 0.014 and ICC = 0.58. The adaptive recipe has σ_sess ≈ 0 and ICC ≈ 0.00. The old
  multi-Otsu fraction had ICC 0.73 (`notes/research_report.md` §6.1).
- **The lifted-black session.** It reads z = +2.0 on the fixed recipe and +0.6 on the adaptive one.

The midpoint follows each image's own bright mode, so it cancels the session tone curve. It fails in one way: if
the image's dominant bright population is itself a different, darker material (as in session 2316), the midpoint
moves down with it. That is why the fixed recipe is kept, and why **both recipes must agree in direction** before
a Si-dose change is called. They do on this data (below).

Tuning (`config.yaml`): `ci_z: 1.96`, `min_object_ecd_um: 1.0`. Every mask number is in
`features/_common/config.yaml`. The frozen recipe of the integrated run is `bright_blur_sigma_px` 1.5,
`bright_mode_range` [1.25, 3.4], `bright_mode_clamp` [1.5, 3.2], `bright_min_peak_frac` 0.002, `bright_fixed_k`
1.45, `bright_core_margin` 0.1, `min_bright_px` 160 and `fill_bright_holes_px` 400. The mode is the tallest
*prominent* histogram peak inside the clamp. The builder's run used range [1.25, 3.2] and clamp [1.6, 2.6]. The
31 real per-spot values in `processed/features.csv` reproduce the builder's tables below (to the digits shown),
so the change only affects perturbed images.

## Evidence on our data

**Final pipeline numbers.** These come from the integrated run: `analysis/rank_features.py` → `processed/rankings.csv`
and `analysis/robustness.py` → `processed/robustness.csv`. Means are per batch, n = 7 / 7 / 17. Sep and q come from a
permutation across all spots, so they do **not** control for session. The within-session p is the exact permutation
inside the five mixed sessions, the acquisition-controlled test, with the B1 and B2 coefficients in B3-SD. Session R²
is read against a chance level of ≈ 0.40. The perturbation ratio is the largest shift under 6 synthetic acquisition
perturbations ÷ B3 SD, where < 0.5 is good.

| Column | B1 / B2 / B3 mean | sep (worst LOO) | q | Within-session p (B1, B2 coef) | Session R² | Perturbation ratio (worst case) |
|---|---|---|---|---|---|---|
| `bright_solid_frac` | 0.100 / 0.055 / 0.066 | 0.79 (0.65) | 0.077 | 0.24 (−1.66, −1.50) | 0.90 | 0.14 (gamma 1.25, 0grcilhi) |
| `bright_frac_ci95` | 0.027 / 0.021 / 0.023 | 0.51 (0.32) | 0.31 | 0.09 (−1.33, −0.60) | 0.71 | 0.03 (gamma 0.8, 0grcilhi) |
| `bright_fixed_solid_frac` | 0.093 / 0.061 / 0.081 | 0.64 (0.55) | 0.15 | 0.59 (−0.68, −0.71) | 0.83 | **1.83** (gamma 1.25, 0grcilhi; gamma 0.8: 0.96) |
| `bright_n_per_1000um2` | 11.6 / 6.7 / 8.3 | 0.77 (0.62) | 0.087 | 0.13 (+0.18, −1.02) | 0.92 | 0.34 (gamma 0.8, 71vgq3fw) |

How to read the final table:
- **Screen.** `rank_features.py` calls `bright_solid_frac` and `bright_n_per_1000um2` "separates" and
  the other two "no difference". Every leak_rho is < 0.6: 0.33, 0.26, 0.35 and 0.52 in table order.
- **The screen passes are carried by session 2316.** Recomputing sep with the same formula and the two 2316 spots left
  out gives 0.53, 0.21, 0.52 and 0.53, and what is left is mostly B2 sitting ≈ 1 SD low. The within-session
  test does not confirm any column (all p ≥ 0.09; the smallest p this design can give is ≈ 0.005). It also cannot
  test 2316 itself, because that session holds only B1.
- **Session R² 0.90 is also mostly 2316.** Without those two spots, R² falls to 0.50 for `bright_solid_frac`,
  against a chance level of ≈ 0.39 for 12 sessions on 29 spots (builder's table below). This matches ICC 0.00 on B3.
- **Measurement system on B3** (`robustness.py`). `bright_solid_frac` has σ_w = 0.0122, σ_sess = 0, ICC 0.00 and
  %GRR upper 0 %. The MSA passes only because σ_sess is estimated at 0; its upper bound is ≈ 0.008 (item 5). The
  fixed recipe has ICC 0.58 and %GRR upper 76 %. `bright_n_per_1000um2` has ICC 0.44 and %GRR upper 67 %.
- **Perturbations.** Only the fixed recipe fails the 0.5 bar, which is why it is a direction check only (item 6).

**Builder's validation** (all 31 spots, computed with this code on the shared harmonisation; the per-spot values are
the same in the integrated run). The sd is between spots. "Within-session"
means OLS y ~ C(session) + C(batch); the statistic is the RSS drop from adding batch, with an exact permutation
over the 192 distinct within-mixed-session relabellings (minimum p ≈ 0.005). Session R² is read against a chance
level of ≈ 0.40 (13 groups, 31 spots).

| Column | B1 (n = 7) | B2 (n = 7) | B3 (n = 17) | B1 without 2316 | η²(batch) | Session R² (without 2316) | Within-session p; coef B1, B2 (B3-SD) | Lifted 2060 z | 2316 sites z |
|---|---|---|---|---|---|---|---|---|---|
| `bright_solid_frac` | 0.100 ± 0.060 | 0.055 ± 0.013 | 0.066 ± 0.011 | 0.067 ± 0.016 | 0.25 | 0.90 (0.50) | 0.24; −1.66, −1.50 | +0.60 | +8.7, +12.5 |
| `bright_frac` | 0.091 ± 0.056 | 0.049 ± 0.013 | 0.059 ± 0.010 | 0.061 ± 0.015 | 0.25 | 0.90 (0.53) | 0.29; −1.44, −1.37 | +0.77 | +8.6, +12.9 |
| `bright_frac_ci95` | 0.027 ± 0.010 | 0.021 ± 0.004 | 0.023 ± 0.004 | 0.022 ± 0.005 | 0.12 | 0.71 (0.43) | 0.09; −1.33, −0.60 | −0.74 | +3.0, +4.9 |
| `bright_fixed_solid_frac` | 0.093 ± 0.042 | 0.061 ± 0.016 | 0.081 ± 0.018 | 0.073 ± 0.024 | 0.17 | 0.83 (0.77) | 0.59; −0.68, −0.71 | **+2.03** | +2.2, +4.8 |
| `bright_n_per_1000um2` | 11.6 ± 6.4 | 6.7 ± 1.0 | 8.3 ± 1.6 | 7.9 ± 1.7 | 0.23 | 0.92 (0.57) | 0.13; +0.18, −1.02 | +2.00 | +7.5, +7.7 |

**Within-session contrasts** (mean difference ÷ B3 between-spot SD):

| Session | `bright_solid_frac` (SD 0.0110) | `bright_fixed_solid_frac` (SD 0.0180) | `bright_n_per_1000um2` (SD 1.63) |
|---|---|---|---|
| 2068 B2 − B3 | −1.58 | −0.46 | −0.72 |
| 2080 B1 − B2 | −0.16 | −0.02 | −0.00 |
| 2080 B1 − B3 | −2.70 | −1.70 | −0.69 |
| 2080 B2 − B3 | −2.54 | −1.67 | −0.69 |
| 2148 B1 − B2 | +1.23 | +1.32 | +2.49 |
| 2156 B1 − B2 | −0.85 | −0.55 | +1.28 |
| 2272 B2 − B3 | +0.01 | +0.22 | −1.11 |

**Per spot** (`bright_solid_frac`, by session):
- 1612 (B3): 0.062, 0.064
- 1780 (B1): 0.061
- 1880 (B1): 0.079
- 1904 (B3): 0.058, 0.054, 0.082
- 2048 (B2): 0.046, 0.042
- 2060 (B3): 0.079, 0.070, 0.055, 0.082
- 2068: B2 0.053; B3 0.062, 0.064, 0.086
- 2080: B1 0.042, B2 0.044, B3 0.072
- 2088 (B3): 0.075, 0.061, 0.052
- 2148: B1 0.083, B2 0.070
- 2156: B1 0.067, B2 0.077
- 2272: B2 0.052, B3 0.052
- **2316 (B1): 0.162, 0.204**

**What the numbers say**

1. **The one large signal is session 2316** (B1 4ih2ggld, 5n1q8atc).
   - Its bright share of solid is 2.4–3.1× baseline: 0.162 and 0.204 vs 0.066 ± 0.011.
   - It has 2.5× the number of ≥ 1 µm objects: 20.5–20.8 vs 8.3 per 1000 µm².
   - The fixed recipe agrees in direction: 0.120 and 0.167 vs 0.081 (+2.2 and +4.8 SD).
   - This is not a threshold artefact of 2316's lower midpoint (1.33). At the common fixed 1.45 cut, 2316 still
     holds 1.5–2× the baseline share.
   - The other five B1 spots are indistinguishable from B3 (0.067 ± 0.016 vs 0.066 ± 0.011).
   - B1 is therefore heterogeneous: 2 of 7 spots, from one session, n_eff = 1. 2316 holds no other batch, so no
     test on these images can separate a material change from a session effect. Verdict: Si-phase anomaly →
     INVESTIGATE (see `si_grade`).
2. **Outside 2316 there is no established batch effect.**
   - Within mixed sessions, B1 and B2 lean 1.5–1.7 SD lower than B3 (exact p = 0.24). That lean comes mainly from
     session 2080: B1 0.042 and B2 0.044 against a single B3 spot (cfe5vt7s, 0.072, itself only +0.5 SD above the B3
     mean), giving −2.70 and −2.54 SD. 2068 adds B2 −1.58 SD, against three B3 spots.
   - One spot per side has a contrast SD of ≈ 1.4–1.7 B3-SD from sampling noise alone, so this is noise-level.
   - 95 % CIs of the within-session coefficients (OLS, df 16): B1 − B3 [−0.045, +0.009], B2 − B3
     [−0.037, +0.004].
   - Reading: within sessions, an increase of more than ≈ +0.01 in B1 or B2 is unlikely. A decrease of up to
     ≈ 0.04 cannot be excluded: the design is that weak. Batch-mean differences elsewhere are ≤ 0.012.
3. **Adaptive and fixed agree in direction** everywhere they can be compared:
   - batch means: B1 > B3 and B2 < B3 on both;
   - both within-session coefficients are negative;
   - the 2316 excess appears on both;
   - r = 0.86 across spots.

   They disagree in size where the fixed recipe tracks the session mode (2060, 1612, 2148).
4. **Site-to-site scatter in B3 is pure sampling noise.**
   - The median single-image se (`bright_frac_ci95` / 1.96) is 0.012, against a B3 between-spot SD of 0.010
     (`bright_frac`), so the ratio se/SD = 1.18.
   - The integral range is 15 µm² (IQR 12–17).
   - For `bright_solid_frac`, the B3 within-session SD is σ_w = 0.012 with σ_sess ≈ 0.
   - Split halves (left/right halves of the same harmonised crop) agree only through the 2316 outliers: r = 0.64
     on all spots, −0.19 without 2316. The observed RMS(L − R) of 0.031 is close to the 0.026–0.028 predicted from
     `fraction_se`, so the single-image error bar is about right (≈ 15 % optimistic).
   - The screen found the same with the same midpoint recipe on a 1600-row crop (`siox_particles.json`,
     `siox_area_frac`): B3 0.059 ± 0.010, perturbation 0.20, split-half −0.18 without 2316. In
     `phase_fractions.json`, `siox_frac` se ≈ the B3 SD.
5. **Detectable shift.** For 7 new spots vs 17 baseline spots, with σ ≈ 0.012 and no session component, the
   SE of a batch difference is ≈ 0.0055. A 90 % CI is then ≈ ±0.009 and the 80 %-power detectable shift is
   ≈ 0.015 absolute (≈ 23 % relative, about 1.5 wt% Si phase) (back-of-envelope). A δ of 1.5·SD = 0.0165 is
   therefore decidable with ≈ 7 spots. A gross change like 2316 (+0.1) is detected from a single spot.
   - Caveat: "no session component" rests on a truncated method-of-moments estimate from 7 B3 sessions
     (F = 0.51). Its one-sided 95 % upper bound is σ_sess ≈ 0.008.
   - If a new batch arrives in one new session and σ_sess is that large, the SE becomes ≈ 0.010 and the
     detectable shift ≈ 0.03.
   - Image the new batch in a session that also holds a retained B3 reference spot. That removes the session
     term.
6. **Perturbation** (raw BSE/Inlens/SE perturbed, full harmonisation re-run, |Δ| ÷ B3 SD; B3 spots 71vgq3fw,
   cfe5vt7s, hzumfsms, 0grcilhi).
   - **Final run** (`robustness.py`, integrated `_common`): `bright_solid_frac` moves 0.00 under black +25, 0.12
     under gamma 0.8, 0.14 under gamma 1.25, 0.02 under contrast ×0.85, 0.01 under noise σ 4 and 0.03 under blur σ 1.
     The worst case is **0.14**, so it passes the 0.5 invariance gate.
   - The other columns' worst cases are `bright_frac` 0.17, `bright_frac_ci95` 0.03 and `bright_n_per_1000um2` 0.34
     (gamma 0.8 on 71vgq3fw).
   - `bright_fixed_solid_frac` moves **1.83** at gamma 1.25 and 0.96 at gamma 0.8. A fixed cut in graphite units moves
     with the tone curve, so it fails the gate.
   - *Builder's run, now superseded:* the worst case was 2.10, on 0grcilhi at gamma 1.25. The old mode finder jumped
     from the SiOx peak (≈ 2.47 after gamma) to a secondary peak at 2.10. The threshold dropped from ≈ 1.73 to 1.55
     and the fraction rose from 0.058 to 0.081. The same jump drove `bright_frac` to 1.94, `bright_frac_ci95` to 0.66
     and `bright_n_per_1000um2` to 3.09. The integrated mode finder takes the tallest *prominent* peak inside the wider
     clamp [1.5, 3.2] and no longer jumps.
   - No real session is that far out (the real modes are 1.67–2.34), but a new session could be. The acquisition check
     in preprocessing should also flag a bright mode outside the known range (see pitfalls).
7. **Runtime** of this folder's code: 0.34–0.58 s per spot, most of it the FFT standard error (≈ 0.3 s). On
   the loaded shared machine a review re-run measured 0.5–1.3 s. That excludes the shared harmonisation, which
   is ≈ 5–8 s uncached and 0.2–0.5 s from the disk cache.
8. **q from `analysis/rank_features.py`** is now in the final table at the top of this section:
   `bright_solid_frac` has q = 0.077 (sep 0.79). That screen permutes across sessions and is carried by the two 2316
   spots. The within-session p (0.24) is the number to quote for an acquisition-controlled batch effect.

## Uncertainty and pitfalls

- **Error budget per spot.**
  - Sampling: ±0.024 (95 %) per spot. One 5800 µm² field cannot resolve changes below ≈ 40 % relative.
    Use batch means over ≥ 5–7 spots.
  - Segmentation: the gap between the adaptive and fixed recipes is ≈ 0.00–0.03 depending on session. This is a
    systematic bracket, not random noise.
  - Session: ≈ 0 for the adaptive recipe on B3 (7 sessions).
- **The wt% reading needs the same material.** "Area fraction ≈ Si-phase wt%" assumes the bright phase is SiOx
  of density ≈ graphite. A porous Si–C composite (lower density, less Si per unit volume) at the same area
  would carry less Si mass. A denser grade would carry more.
  - In 2316 the bright phase is darker and more textured (`si_grade`), so its 2.4–3× area excess cannot be
    read as 2.4–3× Si.
  - Report `bright_solid_frac` together with `bright_contrast_ratio` and require EDS before converting to wt%.
- **Bright-mode jump.**
  - The midpoint depends on the shared mode finder choosing the right peak. In the builder's run, 0grcilhi under
    gamma 1.25 picked a secondary peak. No real spot did, and all 31 modes were found.
  - Guard: flag a spot whose `h.acq['bright_mode']` falls outside the known-session envelope (1.85–2.35 here)
    or disagrees with the median core level (`bright_contrast_ratio`) by > 0.1. In this run they agree to
    r = 0.995.
  - The integrated `_common` has hardened the finder (prominent peak, clamp [1.5, 3.2], minimum peak share 0.2 %). The
    worst perturbation case fell from 2.10 to 0.14 (`robustness.py`). Keep the guard anyway: a new session can
    still fall outside the range that was tested.
- **The fixed recipe reads session tone curves** (2060 z = +2.0). Use it only for the direction check, never
  as the KPI.
- **Lifted black (2060).** The adaptive recipe is clean (z = +0.6). The ≥ 1 µm object count is not (z = +2.0):
  that session also has more small bright objects (the screen found z = +4.3 for ≥ 0.1 µm² objects), from an
  acquisition property the synthetic perturbations do not reproduce. Treat `bright_n_per_1000um2` as Tier 2 at
  most. The frozen v1.1 verdict panel leaves it out and uses `bright_agglom_d50_um` (Tier 2) for Si size and
  dispersion instead; `bright_d90_um` is now a diagnostic (split-half r_x −0.13).
- **Touching particles are not split.** Agglomerates count as one object, so the count is a lower bound on
  particle number and partly measures agglomeration. Particles cut by the 33 µm crop height are excluded and
  reweighted: 8–26 % of the ≥ 1 µm objects touch the crop edge and are dropped. Weights reach at most 1.47 on
  the non-2316 spots (objects up to ≈ 10 µm tall). In 2316 the merged particle networks are 17–20 µm tall and
  get weights of 2.1–2.7, which adds variance there.
- **2D → 3D.** Area fraction is valid in 3D (Delesse; unbiased for a random section) [10, 11]. Number per
  area is not a number per volume: it depends on particle size (Wicksell), so compare it only between
  batches with similar size distributions.
- **Pore-back and void segmentation.** These enter only through the denominator (solid area). A 0.01 porosity
  error moves `bright_solid_frac` by ≈ 1 % relative. This is negligible.
- **Identity.** BSE brightness does not prove Si. The phase is "Si-based, most likely SiOx" from morphology and
  contrast (`notes/research_report.md` §7.14). Confirm with EDS before quoting wt%.

## References

1. Obrovac; Chevrier (2014) Alloy Negative Electrodes for Li-Ion Batteries. *Chem. Rev.*
   https://doi.org/10.1021/cr500207g
2. Moyassari et al. (2022) The Role of Silicon in Silicon-Graphite Composite Electrodes Regarding Specific
   Capacity, Cycle Stability, and Expansion. *J. Electrochem. Soc.* https://doi.org/10.1149/1945-7111/ac4545
3. Liu et al. (2019) Silicon oxides: a promising family of anode materials for lithium-ion batteries.
   *Chem. Soc. Rev.* https://doi.org/10.1039/c8cs00441b
4. Kirner et al. (2020) Optimization of Graphite–SiO blend electrodes for lithium-ion batteries.
   *J. Power Sources.* https://doi.org/10.1016/j.jpowsour.2020.227711
5. Kirkaldy et al. (2022) Lithium-Ion Battery Degradation: Measuring Rapid Loss of Active Silicon in
   Silicon–Graphite Composite Electrodes. *ACS Appl. Energy Mater.* https://doi.org/10.1021/acsaem.2c02047
6. Wu et al. (2024) Fundamental Understanding of the Low Initial Coulombic Efficiency in SiOx Anode for
   Lithium-Ion Batteries: Mechanisms and Solutions. *Adv. Mater.* https://doi.org/10.1002/adma.202405751
7. Dahari, Docherty, Kench et al. (2025) Prediction of Microstructural Representativity
   From A Single Image (ImageRep). *Adv. Sci.* https://doi.org/10.1002/advs.202414149
8. Lantuéjoul (1991) Ergodicity and integral range. *J. Microsc.*
   https://doi.org/10.1111/j.1365-2818.1991.tb03099.x
9. Miles (1978) The Sampling, By Quadrats, of Planar Aggregates. *J. Microsc.*
   https://doi.org/10.1111/j.1365-2818.1978.tb00104.x (edge-corrected particle counting)
10. Taiwo et al. (2016) Comparison of three-dimensional analysis and stereological techniques for
    quantifying lithium-ion battery electrode microstructures. *J. Microsc.* https://doi.org/10.1111/jmi.12389
11. Russ; DeHoff (2000) *Practical Stereology*, 2nd ed. Springer.
    https://doi.org/10.1007/978-1-4615-1233-2 (Delesse A_A = V_V; minus-sampling)
12. Chen et al. (2020) Development of Experimental Techniques for Parameterization of Multi-scale
    Lithium-ion Battery Models (LG M50, graphite–SiOx negative electrode; composition figure **[unverified]**).
    *J. Electrochem. Soc.* https://doi.org/10.1149/1945-7111/ab9050
13. Li et al. (2021) SiOx Anode: From Fundamental Mechanism toward Industrial Application. *Small.*
    https://doi.org/10.1002/smll.202102641
14. Moon et al. (2021) Interplay between electrochemical reactions and mechanical responses in
    silicon–graphite anodes and its impact on degradation. *Nat. Commun.* https://doi.org/10.1038/s41467-021-22662-7

DOIs from `literature.load_papers` (Amass) or confirmed by Crossref lookup through `ledger/ledger.py`'s HTTP
helper; OpenAlex search was rate-limited (HTTP 429) during this work. GB/T 38823-2020 grade details:
**[partly verified]** (`notes/research_report.md` §10).
