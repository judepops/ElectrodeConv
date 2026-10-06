# si_grade

What the bright, Si-based particles look like inside, from the harmonised BSE image: how bright their cores
are, how much of a second dim-grey population there is, how much dark material sits inside them, and how
textured their cores are. **These columns are diagnostic only (Tier 3).** `bright_contrast_ratio` is also on the
verdict's `not_material` list, so no classifier reads it. `bright_core_cv` is computed in `feature.py` only and is
not a column. Session explains 94 % of the contrast ratio. They explain and route a Si-phase anomaly
(to EDS, to the supplier); they never gate a verdict on their own.

| Column | Unit | Meaning |
|---|---|---|
| `bright_contrast_ratio` | graphite units (black 0, graphite 1) | Median BSE level of the eroded particle cores. Higher = higher mean Z (Si-richer); lower = O- or C-richer, porous, **or a different kV/detector setting** |
| `bright_dim_frac` | fraction of image | Area of compact objects in the dim-grey band between graphite and the bright threshold (`h.dim`) |
| `bright_internal_dark_frac` | fraction of particle interior | Share of the hole-filled particle interior darker than 0.85 × that particle's own core level. Tests for internal pores or carbon (a porous Si–C composite) |
| `bright_core_cv` | dimensionless | Within-particle coefficient of variation of the core BSE, with pixel noise removed. Measures granular or two-phase texture at ≥ 100 nm. **Not a features.csv column** (team audit 2026-10-03): ρ 0.80 with `bright_internal_dark_frac`; half of it comes from ≈ 1 % of the darkest core pixels |

## Battery impact at a glance

Every row compares against a baseline spot imaged in the **same session**. Across sessions these columns
mostly measure the microscope.

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `bright_contrast_ratio` up | Higher mean Z: a Si-richer grade (lower x in SiOx). Less oxide to convert irreversibly gives more reversible capacity and a higher first-cycle efficiency (ICE) [3, 5]. More active Si per particle gives more swelling and faster fade of the Si fraction [1, 2, 4]. Or simply a kV or detector change [8, 9] | **Trade-off** (if EDS confirms a grade change): capacity and ICE against swelling and cycle life | Mechanism moderate [3, 5]; detection low. Session explains 94 % of this column, and grey level → mean Z needs a fixed kV and detector [8, 10] |
| `bright_contrast_ratio` down | Lower mean Z. Four causes fit, with opposite cell effects: (a) an O-richer SiOx: lower capacity and ICE, because the oxide turns irreversibly into Li silicates and Li₂O [3, 5, 6], but less swelling [1, 3]; (b) a C-rich or porous Si–C composite, a different product built for low swelling [11, 12]; (c) a pre-lithiated SiOx: its Li silicates have a low mean Z, so the core reads darker, yet the ICE goes **up** [15]; (d) a kV or detector change [8, 9]. With (a)–(c), the `si_fraction` area → wt% conversion no longer holds | **Trade-off** if EDS confirms (a): lower capacity and ICE against less swelling. (b) and (c) move ICE the other way or by an unknown amount. From BSE alone it is **neither: a sign that the Si grade or the acquisition changed** → EDS | Low (same reasons) |
| `bright_internal_dark_frac` and `bright_core_cv` up (grouped: both read the inside of a particle, and both rise in 2316; `bright_core_cv` is not a features.csv column, team audit 2026-10-03: ρ 0.80 with `bright_internal_dark_frac`, half of it from ≈ 1 % of the darkest core pixels) | Pores, carbon or a second phase inside the Si particles, i.e. a porous or agglomerated Si–C composite [11, 12]. A composite is a different product: it is built to buffer swelling [11], and its carbon changes Li transport and storage behaviour [12]. Cracks or polishing pull-outs give the same signal | **Neither: a sign that the supplier's Si product or process changed.** The cell effect depends on what EDS and SE find. If SE shows real cracks (not polishing pull-outs), that part is **bad**: fresh surface grows SEI and costs Li (shown for graphite surface area [16]; applied to Si by analogy) | Low. BSE cannot tell pores from carbon from cracks. Session R² is 0.79 and 0.63 |
| `bright_internal_dark_frac` and `bright_core_cv` down (core CV: not a column, as above) | Denser, more uniform particles. The baseline already sits near the floor of a dense SiOx shard (≈ 1 %, CV 0.026) | Neither | Low |
| `bright_dim_frac` up or down | More or fewer objects in the grey band between graphite and Si. They can be a lower-Z Si population, dense CBD pockets or partial-volume particle edges [7, 8], and BSE cannot tell these apart | Neither (ambiguous; it does not flag 2316) | Low (session R² 0.64) |

**Best value:** match the baseline, i.e. read the same as a baseline spot imaged in the same session. The B3
values are contrast 2.13 ± 0.15 (spots 1.84–2.29; session means 1.86–2.28), internal dark 0.011 ± 0.005, core CV
0.026 ± 0.004 and dim 0.025 ± 0.021. Neither direction is better in itself.

**Our batches** (final integrated run, `rank_features.py` and `robustness.py`):
- **Batch_1: a Si-grade lead in two spots from one session, not a lot-wide change.**
  - *Lot means vs B3 (raw, not session-controlled).* Contrast 1.92 vs 2.13 (−1.34 SD), internal dark 0.018
    vs 0.011 (+1.54 SD), core CV 0.030 vs 0.026 (+0.92 SD), dim 0.013 vs 0.025 (−0.57 SD). The lot's spread
    is 3.4× (internal dark) and 2.8× (CV) the baseline's.
  - *Where it comes from.* The mean shifts come from the two session-2316 spots: cores 1.65 and 1.67 (z −3.2
    and −3.0), internal dark +7.5 and +4.1 SD, CV +5.0 and +2.7 SD. Without them, sep falls to 0.34
    (contrast), 0.10 (internal dark), 0.13 (CV) and 0.21 (dim). The other five B1 spots match the baseline on
    the means (2.03 ± 0.13, 0.010, 0.025). Their spread is still 1.6× (internal dark) and 2.2× (CV) the
    baseline's. f1vzngrs (2148) reads high (0.022, 0.041; +2.5, +3.5 SD), but so does its B2 neighbour in the
    same session (0.020, 0.030), and ffwubibz (2080) reads low.
  - *Acquisition-controlled test.* Session 2316 holds only B1, so the within-session test cannot see it
    (n_eff = 1 session). Inside the mixed sessions, B1 is if anything brighter and smoother than its
    neighbours, but nothing is significant. The within-session effects are +0.31 SD (contrast), −1.46 SD
    (internal dark), −1.25 SD (CV) and +1.33 SD (dim), with within_p 0.71, 0.42, 0.60 and 0.20. The
    internal-dark and CV effects lean on one B3 spot in 2080 (cfe5vt7s), which itself reads high.
  - *Screen.* The contrast ratio has sep 0.66, no better than the ≈ 0.65 that acquisition alone reaches (worst
    leave-one-out 0.53), and q 0.100, at the 0.1 bar but not below it. The other three have sep 0.32–0.48 and
    q 0.31–0.62. rank_features calls all four "no difference".
  - *What the verdict does with it.* Contrast, dim and internal dark are Tier 3 diagnostics on the certificate,
    with screen q 0.22, 0.50 and 0.50. A Si-phase reason would need q < 0.05. `bright_core_cv` is no longer a
    column. The INVESTIGATE comes from Tier 1 `bright_solid_frac`, the Tier 2 `bright_agglom_d50_um` and the 5.4×
    lot spread of `bright_solid_frac`, all carried by the same two spots. These columns
    support the certificate's action: EDS plus the supplier's Si-phase CoA.
  - *Battery reading.* Only EDS can say what the 2316 particles are, and the candidates pull the cell in
    different directions. An O-richer SiOx would give lower capacity and ICE per unit of bright area but less
    swelling, a trade-off [3, 5, 6]. A porous Si–C composite is built for low swelling and stable cycling [11];
    its ICE and capacity per bright area depend on its Si : C ratio and porosity. A pre-lithiated grade would
    raise the ICE [15]. In every case the `si_fraction` area → wt% conversion fails for those spots, so their
    capacity cannot be read from the bright area.
- **Batch_2: matches the baseline.**
  - *Lot means.* Contrast 2.10, dim 0.027, internal dark 0.011, CV 0.027, against B3 2.13 / 0.025 / 0.011 /
    0.026 (−0.17 to +0.09 SD).
  - *Within mixed sessions.* +0.23, +1.25, −1.09 and −1.39 SD (contrast, dim, internal dark, CV), with
    within_p 0.71, 0.20, 0.42 and 0.60. None is significant by the exact permutation test. The internal-dark
    and CV effects rest on the single B3 spot in 2080. The dim coefficient's parametric 95 % CI just clears 0
    ([+0.14, +2.35] B3-SD). It rests on two sessions with one B2 spot each (2272: +2.22, 2068: +1.44), in a
    session-structured column, so we do not read it as a difference.
  - *Verdict.* Screen q is 0.96 for all three certificate diagnostics. There is no sign of a Si-grade change,
    and these columns play no part in B2's INVESTIGATE.

## What it measures

`si_fraction` measures how much Si phase there is. This folder measures what kind of particle it is.

All four measures (three columns plus the core CV) work on the particles of the shared bright mask (`h.bright`),
in the anchored BSE image:

- **Core** = bright pixels at least 6 px (150 nm) from the particle edge, so the BSE edge blur (4–5 px) is
  excluded. Particles need ≥ 100 core pixels; 41–128 particles per spot qualify (median 60).
- **Contrast ratio**: the median core level, in units where the graphite mode = 1 and black = 0.
- **Dim-grey band** (`h.dim`, from the harmonisation): compact objects ≥ 0.5 µm² whose blurred level lies
  between 1.15 × graphite and min(1.45, the bright threshold), more than 7 px from bright edges.
- **Internal dark share**: each particle's holes up to 4 µm² are filled. Pixels in its interior (6 px in from
  the outline) that read below 0.85 × the particle's own core median are counted as dark. A dense SiOx shard
  gives ≈ 1 %. A particle with internal pores, carbon filler or cracks gives more.
- **Core texture**: plain pixel variance inside a core is mostly noise. On 7 spots checked, 93–98 % of it is
  noise: within-particle core variance is 0.08–0.12, against a lag-4 texture covariance of 0.002–0.009 graphite
  units². The noise-free variance is therefore taken as the covariance of pixel pairs 4 px (100 nm) apart in
  the same core. Pixel noise (its level is measured by Immerkær's method in the shared harmonisation [14]) is
  uncorrelated at that distance. In graphite interiors the lag covariance falls to its texture floor by 2 px.
  Inside particle cores, the x (scan) lag covariance is higher than the y one at 1 px (a scan-direction noise
  correlation), and the two agree from 3–4 px on. Real texture stays correlated. CV = √cov ÷ core level.

## Why it matters for the battery

The same area of Si phase can be a different material:

- **SiOx stoichiometry.** More oxygen means a lower mean Z, so a darker BSE core [8, 10]. It also means lower
  reversible capacity and lower first-cycle efficiency, because the oxide converts irreversibly to Li silicates
  and Li₂O [3, 5, 6]. Less oxygen means more capacity and more swelling [1].
- **Si–C composites.** Pitch-impregnated porous Si, or SiOx/C granules, are a different product class. They
  have internal porosity and carbon, a lower mean Z per pixel, and a granular interior [11, 12]. They are made
  to buffer swelling [11], and their carbon microstructure changes Li transport and storage behaviour [12]. An
  unannounced switch changes capacity, ICE and swelling all at once.
- **Pre-lithiated SiOx.** Industrial high-ICE grades put Li silicate into the SiOx before use [15]. Li has a very
  low Z, so these cores also read darker, while the ICE goes up.
- **Composition or porosity is not the only cause of a darker core.** A darker core can also be a coating, or a
  different beam energy or detector segment [7, 8, 9]. That is why these columns are diagnostic.

Direction: a darker, more internally dark and more textured Si phase than baseline means the Si product changed.
The candidates are an O-richer grade (lower capacity and ICE, less swelling [3, 5, 6]), a porous Si–C composite
(built for low swelling [11]; ICE and capacity depend on the design) and a pre-lithiated grade (higher ICE [15]).
It can also mean an acquisition change. In every case the `si_fraction` wt% proxy no longer holds, and the ICE
direction is not known from BSE alone. A brighter, smoother phase points to a Si-richer grade: more capacity and
ICE, more swelling and fade [1, 2, 3, 4].

## Industry / Polaron use

- **Powder side.** Si-phase grade is a CoA matter: O content and carbon content (TGA, combustion), plus
  capacity and ICE classes for Si–C materials in GB/T 38823-2020 (`notes/research_report.md` §2; grade details
  **[partly verified]**).
- **Electrode side.** Particle identity is normally confirmed by SEM-EDS. Automated, statistically sampled
  SEM-EDS of battery electrodes has been demonstrated [13].
- **BSE contrast.** Turning grey levels into mean Z needs controlled conditions (fixed kV, detector and gain,
  calibration standards) [8, 9]. Our images carry no such metadata (`notes/research_report.md` §9.1).
- **Industry use.** Using BSE contrast and internal texture as incoming-QC numbers is, as far as we know,
  **academic only**. In a vendor workflow it would sit in Tier 3 next to the EDS request.
- **What would move them:** a change of Si-phase supplier or grade (x in SiOx, carbon coating, porous Si–C), a
  change of milling or classification, or an acquisition change. The acquisition change is the alternative that
  must be ruled out first.

## How it is computed

1. `h = harmonised(sample)` (shared; `features/_common/harmonise.py`): anchored, noise-matched BSE `h.bse`,
   blurred copy `h.bse_blur` (σ = 2 px), masks `h.bright` and `h.dim`. No re-segmentation.
2. `particle_cores()` (cached per sample), all on `h.bright`:
   - fill holes ≤ `max_hole_px` (6400 px = 4 µm²) and label the particles (8-connected);
   - erode `h.bright` by a disk of `core_erosion_px` (6) to get the cores;
   - keep particles with ≥ `min_core_px` (100) core pixels;
   - core level of each particle = median of `h.bse_blur` over its core.
3. `bright_contrast_ratio` = median of `h.bse` over all core pixels (pooled, so area-weighted).
4. `bright_dim_frac` = mean of `h.dim`.
5. `bright_internal_dark_frac`:
   - interior = filled particles eroded by `rim_px` (6), valid particles only;
   - dark = interior pixels with `h.bse_blur` < `dark_fraction_of_core` (0.85) × that particle's core level;
   - result = dark pixels ÷ interior pixels, pooled over particles.
6. `bright_core_cv` (computed in `feature.py`, not a column):
   - residuals of `h.bse` from each particle's core mean;
   - pooled covariance of residual pairs `texture_lag_px` (4) apart in x and in y, both pixels in the same core;
   - result = √max(cov, 0) ÷ median core level.

Every number is in `config.yaml`. Sensitivity was checked: core erosion 3/10 px, dark threshold 0.80/0.90, rim
4/10 px, lag 3/6 px (below).

## Evidence on our data

**Final pipeline numbers.** These come from `analysis/rank_features.py` and `analysis/robustness.py` on the
integrated run (`processed/rankings.csv`, `processed/robustness.csv`). The bars:

- sep is the between/within ratio. Acquisition columns alone reach ≈ 0.65.
- q is BH-corrected; it must be < 0.1.
- Within-session p is an exact permutation inside the 5 mixed sessions (minimum ≈ 0.005).
- Session R² is read against a chance level of ≈ 0.40.
- The perturbation ratio is the maximum shift under 6 raw-image perturbations ÷ B3 SD; the target is < 0.5.

| Column | B1 / B2 / B3 mean | sep | q | Within-session p | Session R² | Perturbation ratio (worst) |
|---|---|---|---|---|---|---|
| `bright_contrast_ratio` | 1.92 / 2.10 / 2.13 | 0.66 | 0.100 | 0.71 | 0.94 | 2.77 (gamma 1.25, 0grcilhi) |
| `bright_dim_frac` | 0.013 / 0.027 / 0.025 | 0.35 | 0.61 | 0.20 | 0.64 | 1.16 (gamma 1.25, 0grcilhi) |
| `bright_internal_dark_frac` | 0.018 / 0.011 / 0.011 | 0.48 | 0.31 | 0.42 | 0.79 | 1.23 (gamma 1.25, cfe5vt7s) |

How to read the table:

- rank_features calls all three "no difference". Their worst leave-one-out sep is 0.53 / 0.29 / 0.22,
  and their leak_rho (with image height) is 0.48 / 0.26 / 0.39. With both 2316 spots left out, sep is
  0.34 / 0.21 / 0.10 (recomputed with `rank_features.separation`).
- rank_features permutes across all spots, so its p and q do not control for session. The within-session p
  does, but session 2316 (B1 only) is outside it.
- All three fail the 0.5 perturbation target, through gamma only; the other perturbations move them ≤ 0.31.
- The builder's analysis below agrees with this run, except for the gamma 1.25 column of the perturbation
  table, which is corrected there.

All 31 spots, computed with this code on the shared harmonisation. The within-session test is OLS
y ~ C(session) + C(batch), with an exact permutation over 192 relabellings. Session R² is read against a chance
level of ≈ 0.40.

| Column | B1 | B2 | B3 | B1 without 2316 | η² | Session R² (without 2316) | Within-session p; coef B1, B2 (B3-SD) | Lifted 2060 z | 2316 spots |
|---|---|---|---|---|---|---|---|---|---|
| `bright_contrast_ratio` | 1.92 ± 0.21 | 2.10 ± 0.16 | 2.13 ± 0.15 | 2.03 ± 0.13 | 0.21 | **0.94 (0.91)** | 0.71; +0.31, +0.23 | +0.68 | 1.65, 1.67 (z −3.2, −3.0) |
| `bright_dim_frac` | 0.013 ± 0.010 | 0.027 ± 0.030 | 0.025 ± 0.021 | 0.018 ± 0.006 | 0.06 | 0.64 (0.62) | 0.20; +1.33, +1.25 | −0.26 | 0.0004, 0.0011 (z −1.2, −1.1) |
| `bright_internal_dark_frac` | 0.018 ± 0.015 | 0.011 ± 0.006 | 0.011 ± 0.005 | 0.010 ± 0.007 | 0.12 | 0.79 (0.56) | 0.42; −1.46, −1.09 | +0.49 | 0.045, 0.029 (z +7.5, +4.1) |
| `bright_core_cv` | 0.030 ± 0.012 | 0.027 ± 0.006 | 0.026 ± 0.004 | 0.025 ± 0.010 | 0.06 | 0.63 (0.44) | 0.60; −1.25, −1.39 | +0.49 | 0.048, 0.038 (z +5.0, +2.7) |

**Within-session contrasts** (B3-SD units):

| Session | `bright_contrast_ratio` | `bright_dim_frac` | `bright_internal_dark_frac` | `bright_core_cv` |
|---|---|---|---|---|
| 2068 B2 − B3 | +0.74 | +1.44 | +0.71 | +0.88 |
| 2080 B1 − B2 | +0.77 | +0.81 | −0.13 | −0.53 |
| 2080 B1 − B3 | +0.15 | +0.75 | −2.93 | −3.90 |
| 2080 B2 − B3 | −0.62 | −0.06 | −2.80 | −3.38 |
| 2148 B1 − B2 | +0.04 | −0.49 | +0.45 | +2.50 |
| 2156 B1 − B2 | −0.22 | +0.56 | −0.37 | −0.04 |
| 2272 B2 − B3 | +0.13 | +2.22 | −1.66 | −1.69 |

The 2080 contrasts for internal dark and CV come from one B3 spot (cfe5vt7s: 0.017 and 0.033) against one
spot each of B1 and B2. The parametric 95 % CIs of the within-session coefficients include 0 everywhere but one
case, e.g. contrast ratio B1 [−0.50, +1.12] and B2 [−0.38, +0.84] B3-SD. The exception is B2 on `bright_dim_frac`,
[+0.14, +2.35]. It rests on 2272 and 2068 (one B2 spot each), and the exact permutation p of the batch term is
0.20, so it is not read as a difference.

**Perturbation** (|Δ| ÷ B3 SD, max over 71vgq3fw, cfe5vt7s, hzumfsms, 0grcilhi; final `robustness.py` run):

| Column | black +25 | contrast ×0.85 | noise σ 4 | blur σ 1 | gamma 0.8 | gamma 1.25 |
|---|---|---|---|---|---|---|
| `bright_contrast_ratio` | 0.00 | 0.05 | 0.20 | 0.09 | 1.92 | 2.77 |
| `bright_dim_frac` | 0.00 | 0.02 | 0.10 | 0.31 | 0.33 | 1.16 |
| `bright_internal_dark_frac` | 0.00 | 0.01 | 0.21 | 0.25 | 1.07 | 1.23 |
| `bright_core_cv` | 0.00 | 0.02 | 0.19 | 0.27 | 1.32 | 1.59 |

The builder's earlier run gave 2.31, 1.22, 3.58 and 4.16 in the gamma 1.25 column. There the shared bright-mode
finder jumped to a secondary peak on 0grcilhi. In the final run it did not jump: `bright_frac` moves at most
0.17 there, against 1.94 before. The worst cases are now plain gamma effects: the contrast ratio and the dim
band on 0grcilhi, internal dark and CV on cfe5vt7s.

**Reading.** The four columns are robust to offset, linear contrast, noise and blur (≤ 0.31 SD). They are not
robust to a change of tone curve:

- Gamma maps a core at 2.1 × graphite to 2.1^γ. By construction the contrast ratio moves 1.9–2.8 SD, and the
  dim and texture columns 0.3–1.6 SD.
- In the builder's run the extreme values (3.6, 4.2) came from the same shared bright-mode jump as in
  `si_fraction`. On 0grcilhi at gamma 1.25 the threshold dropped from ≈ 1.73 to 1.55, which pulled dimmer
  material into the particles. The final run did not reproduce it.
- Only same-session comparisons are meaningful. That is the reason for "diagnostic only".

Further checks:

- **Contrast ratio follows the session.** It correlates r = 0.995 with the harmonisation's bright mode. B3
  method-of-moments: σ_sess = 0.145, σ_w = 0.064, ICC 0.84. It ranges 1.84–2.29 within B3, but within each
  mixed session the batches agree to ≤ 0.8 SD. Apart from session 2316, the Si phase looks the same in all
  three batches.
- **Variant robustness.** Changing the core erosion to 3 or 10 px moves the contrast-ratio z of every spot by
  ≤ 0.08. For
  `bright_internal_dark_frac`, the 2316 excess holds at a 0.80 threshold (+8.8, +5.4), 0.90 (+6.4, +2.8),
  rim 4 px (+7.5, +4.6) and rim 10 px (+6.2, +2.7). For `bright_core_cv` it holds at lag 3 (+5.1, +2.9) and
  lag 6 (+5.4, +3.2).
- **What `h.dim` holds.**
  - Objects with a median area of 0.5–0.8 µm² and a BSE level of 1.23–1.30 × graphite.
  - Inlens rank 0.63–0.89: graphite reads 0.30–0.54, bright particles 0.66–0.94.
  - SE rank 0.60–0.89: graphite reads 0.43–0.59, bright particles 0.92–0.96.
  - So they are intermediate on every detector. That fits dense CBD pockets, thin or sub-surface Si fragments
    (partial volume) or a low-Z grade; BSE cannot tell these apart.
  - It is session-structured: 2068 has 0.068–0.079 on three of four spots, but 0.009 on vc2whyaq, whose bright
    mode is 2.07 vs 2.28–2.34. 1904 has 0.034–0.048.
  - It does **not** flag 2316. There the dominant population is itself dim (core ≈ 1.6), so the adaptive
    midpoint (1.33) classes it as bright and the dim band (1.15–1.33) is nearly empty.
- **Runtime** of this folder's code: 0.55–0.79 s per spot, excluding the shared harmonisation. A review re-run
  on the loaded shared machine measured 0.8–1.9 s.
- **Screen** (`analysis/rank_features.py`, final integrated run):
  - contrast ratio: sep 0.66, p 0.035, q 0.100;
  - internal dark: sep 0.48, p 0.16, q 0.31;
  - dim: sep 0.35, p 0.41, q 0.61;
  - core CV: sep 0.32, p 0.44, q 0.62.

  All four are "no difference". The contrast ratio's sep is carried by session 2316 (worst leave-one-out 0.53),
  and the screen does not control for session.

### The session-2316 lead, honestly

The B1 spots 4ih2ggld and 5n1q8atc are the only imaging session 2316 (n_eff = 1 session, 2 spots). Together with
`si_fraction` they show a consistent, multi-feature difference from every other spot:

| | 2316 (4ih2ggld, 5n1q8atc) | B3 (17 spots) |
|---|---|---|
| Bright share of solid (`si_fraction`) | 0.162, 0.204 | 0.066 ± 0.011 |
| ≥ 1 µm bright objects per 1000 µm² | 20.5, 20.8 | 8.3 ± 1.6 |
| Core level (`bright_contrast_ratio`) | 1.65, 1.67 | 2.13 ± 0.15 (range 1.84–2.29) |
| Share of particle area with core 1.5–1.7 × graphite | 78 %, 85 % | median 0 %; max 19 % (ufdvpb81, in 2088, the lowest-contrast session); every other non-2316 spot ≤ 2.5 % |
| Internal dark share | 0.045, 0.029 | 0.011 ± 0.005 |
| Core texture CV | 0.048, 0.038 | 0.026 ± 0.004 |

The screen data add four points:

- In 5n1q8atc a few particles (4 of 119, ≈ 6 % of core area) have normal SiOx cores at 1.9–2.3 × graphite,
  next to the dominant ≈ 1.6 population in the same image. The screen's histogram found modes at 1.59 and 2.00.
- The graphite and void levels, noise, CNR and black clipping of session 2316 are inside the range of the other
  sessions. The one exception is the curtain index: 1.64–1.68 against ≤ 1.16 elsewhere. For that reason the
  acquisition module's own gate (`preprocessing/acquisition.py` `gate_status()`) marks both spots G-C. Milling curtains
  depend on phase hardness, so `verdict_config.yaml` does not gate on the curtain index (it follows
  `bright_solid_frac`, r 0.83). It neither confirms nor excludes a kV change.
- Within one image, the dim particles have a different SE/Inlens signature from the SiOx particles (ETD rank
  0.85 vs 0.95) (`phase_fractions.json`).
- The 2316 particles are granular, with low solidity and more direct pore contact. The screen's
  `siox_particles.json` gives solidity 0.68–0.70 vs 0.90 and 3× the pore contact. The pipeline's `si_particles`
  columns give `bright_solidity_aw` 0.45 and 0.71 vs 0.90 ± 0.02, and `bright_contact_pore_frac` 0.14 and 0.15
  vs 0.066 ± 0.016 (≈ 2.2×).

Explanations that fit, and what each predicts:

1. **Different dense Si grade (higher O content, or pre-lithiated).** A lower mean Z gives a darker core
   [8, 10]. More O means lower ICE [3, 5]; Li silicate from pre-lithiation means higher ICE [15]. Neither by
   itself explains the granular texture, the internal dark share or the 2.5× object count.
2. **Porous or agglomerated Si–C composite.** Internal pores and carbon lower the average signal and create
   exactly the texture and dark inclusions measured here, with no change of kV [11, 12]. It also explains low
   solidity, pore contact and the high object count. This explanation fits **all** the observations.
3. **A different coating** (thicker carbon shell). It would darken the rim more than the 150 nm-eroded core and
   should not double the area fraction. It fits poorly.
4. **kV, BSE detector segment or mode change in that session.** It would change the Si/graphite contrast for
   every particle. Two observations argue against it: a few normal-contrast (1.9–2.3) SiOx particles coexist in
   5n1q8atc, and the morphology differs (texture, solidity, count), which grey-level changes cannot create.
   But the 2316 core level (1.66) lies only ≈ 0.2 below the lowest other session (2088: 1.84–1.88), and the kV
   is unknown. **Not excluded.**
5. **Local segregation** (one electrode piece or field rich in a minor Si component). Both spots come from one
   session and the other five B1 spots look like baseline, so a local cause cannot be separated from a batch
   cause. **Not excluded.**

**Verdict for the certificate:** Si-phase anomaly in 2 of 7 B1 spots, one session, → **INVESTIGATE**, not
REJECT.

**Recommended actions:**

- **EDS.** Point or short-map EDS at a fixed kV on ≥ 3 dim-cored particles in 4ih2ggld/5n1q8atc, on the
  normal-contrast particles in 5n1q8atc, and on ≥ 3 particles at a B3 reference site. Measure Si : O : C.
  Automated, sampled SEM-EDS [13] makes this objective.
- **Metadata.** Record kV, detector, segment and mode for session 2316.
- **Re-imaging.** Re-image 2316-type fields in a session that also holds a retained B3 reference.
- **Supplier.** Ask for the Si-phase CoA: grade, O and C content, coating, porosity
  (`notes/research_report.md` §6.5, "Si-phase anomaly").

## Uncertainty and pitfalls

- **Session dominates the contrast ratio** (R² 0.94, ICC 0.84; B3 range 1.84–2.29). Black is clipped in 27/31
  images, so "black = 0" is a clip floor, not a physical zero. Gamma changes move it 1.9–2.8 SD (final
  `robustness.py` run). Compare only spots from the same session, or against a retained reference re-imaged in
  that session. Never compare across sessions on this column.
- **Mode-jump coupling.** All columns sit on `h.bright`, whose threshold follows the shared bright-mode finder.
  If the finder jumps to another peak, the particle set changes and the texture columns jump by 3–4 SD. This
  was seen once, in the builder's gamma 1.25 test, and was not reproduced in the final `robustness.py` run. Guard: the median core level and `h.acq['bright_mode']` should agree within
  ≈ 0.1. They agree on all 31 real spots (r = 0.995).
- **Few particles.** 41–128 particles per spot. Particle-level statistics are dominated by a handful of large
  particles: the B3 SD of the internal dark share is ≈ 45 % of its mean. Single-spot values are noisy: a
  one-spot-vs-one-spot difference within a session has an SD of √2 σ_w ≈ 1.3–1.5 B3-SD for internal dark and
  CV (σ_w from `robustness.py`), so their single-pair within-session contrasts of 2–4 SD are not individually
  meaningful. Use session-matched batch means, and treat only 2316-scale
  effects (|z| 2.7–7.5 in this folder) as signals.
- **What "dark inside" can be.** Internal pores, carbon or CBD filling, cracks, pull-outs from polishing, or
  pore-back seen through a thin particle. BSE alone cannot separate these. Inlens/SE cross-checks or EDS can.
- **Noise correction.** The lag-4 covariance assumes the noise decorrelates within 4 px. That holds here:
  - the graphite lag covariance is at its floor by 2 px;
  - in particle cores the x (scan) and y lag covariances differ at 1 px and agree from 3–4 px on (7 spots checked).

  A strongly low-passed new session (scan-direction blur) would leak noise into it: blur σ 1 moved it up to 0.27
  SD (final run). On a new session, check the lag profile and the x/y agreement at lag 4.
- **The dim band is ambiguous.** It mixes CBD pockets, partial-volume particle edges and any lower-Z
  population, and depends on the graphite anchor. It is session-structured (R² 0.64).
- **3D.** Core levels, texture and internal dark shares are per section. A section through the edge of a
  particle reads darker (partial volume, interaction depth [7, 8]). Eroding by 150 nm limits this but cannot
  remove it for small particles.

## References

1. Obrovac; Chevrier (2014) Alloy Negative Electrodes for Li-Ion Batteries. *Chem. Rev.*
   https://doi.org/10.1021/cr500207g
2. Moyassari et al. (2022) The Role of Silicon in Silicon-Graphite Composite Electrodes Regarding Specific
   Capacity, Cycle Stability, and Expansion. *J. Electrochem. Soc.* https://doi.org/10.1149/1945-7111/ac4545
3. Liu et al. (2019) Silicon oxides: a promising family of anode materials for lithium-ion batteries.
   *Chem. Soc. Rev.* https://doi.org/10.1039/c8cs00441b
4. Kirkaldy et al. (2022) Lithium-Ion Battery Degradation: Measuring Rapid Loss of Active Silicon in
   Silicon–Graphite Composite Electrodes. *ACS Appl. Energy Mater.* https://doi.org/10.1021/acsaem.2c02047
5. Wu et al. (2024) Fundamental Understanding of the Low Initial Coulombic Efficiency in SiOx Anode for
   Lithium-Ion Batteries: Mechanisms and Solutions. *Adv. Mater.* https://doi.org/10.1002/adma.202405751
6. Li et al. (2021) SiOx Anode: From Fundamental Mechanism toward Industrial Application. *Small.*
    https://doi.org/10.1002/smll.202102641
7. Kanaya; Okayama (1972) Penetration and energy-loss theory of electrons in solid targets. *J. Phys. D.*
    https://doi.org/10.1088/0022-3727/5/1/308 (interaction volume, so edge and partial-volume darkening)
8. Goldstein et al. (2018) *Scanning Electron Microscopy and X-Ray Microanalysis*, 4th ed. Springer.
    https://doi.org/10.1007/978-1-4939-6676-9 (BSE atomic-number contrast; detector and kV dependence)
9. Čalkovský, Müller, Gerthsen (2022) Quantitative analysis of backscattered-electron contrast in scanning
    electron microscopy. *J. Microsc.* https://doi.org/10.1111/jmi.13148
10. Sánchez, Deluigi, Castellano (2012) Mean Atomic Number Quantitative Assessment in Backscattered Electron
    Imaging. *Microsc. Microanal.* https://doi.org/10.1017/S1431927612013566 (grey level → mean Z needs
    controlled conditions)
11. Chae et al. (2021) A Micrometer-Sized Silicon/Carbon Composite Anode Synthesized by Impregnation of
    Petroleum Pitch in Nanoporous Silicon. *Adv. Mater.* https://doi.org/10.1002/adma.202103095
12. Sun et al. (2023) Carbon Microstructure Dependent Li-Ion Storage Behaviors in SiOx/C Anodes. *Small.*
    https://doi.org/10.1002/smll.202300759
13. Kato et al. (2025) A comprehensive and quantitative SEM–EDS analytical process applied to lithium-ion
    battery electrodes. *Sci. Rep.* https://doi.org/10.1038/s41598-025-89362-w
14. Immerkær (1996) Fast Noise Variance Estimation. *Comput. Vis. Image Underst.*
    https://doi.org/10.1006/cviu.1996.0060 (noise level used by the shared harmonisation; the lag-covariance
    noise removal here is our own standard device, no specific source)
15. Yan, Li, Zhang et al. (2020) Enabling SiOx/C Anode with High Initial Coulombic Efficiency through a Chemical
    Pre-Lithiation Strategy for High-Energy-Density Lithium-Ion Batteries. *ACS Appl. Mater. Interfaces.*
    https://doi.org/10.1021/acsami.0c05153 (Li silicate pre-generated in SiOx/C raises ICE: a darker, lower-Z
    grade that is not worse on ICE)
16. Winter, Novák, Monnier (1998) Graphites for Lithium-Ion Cells: The Correlation of the First-Cycle Charge Loss
    with the Brunauer-Emmett-Teller Surface Area. *J. Electrochem. Soc.* https://doi.org/10.1149/1.1838281
    (first-cycle loss scales with exposed surface; applied to cracked Si particles by analogy)

DOIs come
from `literature.load_papers` (Amass) or were confirmed by Crossref lookup through `ledger/ledger.py`'s HTTP
helper. OpenAlex search was rate-limited (HTTP 429) during this work.
