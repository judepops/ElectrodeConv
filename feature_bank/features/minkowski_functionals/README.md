# minkowski_functionals

Interface length and connectivity of the pore phase per unit area (the 2D Minkowski functionals besides porosity),
plus a porosity-corrected interface residual. Adds three columns to `processed/features.csv`; the Euler density is
computed in `feature.py` only.

| Column | Unit | Meaning |
|---|---|---|
| `interface_density_per_um` | 1/µm (µm of boundary per µm²) | L_A: pore/solid boundary length per area, from boundary crossings along rows and columns |
| `interface_density_resid_z` | z (B3 residual SDs) | L_A minus what Batch_3 shows at the same porosity (B3-only line fit, trained, leave-one-out for B3 spots) |
| `pore_n_per_1000um2` | per 1000 µm² | Resolvable pores: 8-connected void objects ≥ 64 px (0.04 µm²) |
| `euler_density_per_1000um2` | per 1000 µm² | Euler characteristic density of the pore phase: those pores minus enclosed solid islands ≥ 64 px. **Not a features.csv column** (team audit 2026-10-03): r 0.99 with `pore_n_per_1000um2` |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `interface_density_per_um` (L_A) **up at the same porosity** (`interface_density_resid_z` > 0) | More pore wall per area: finer particles, more fines or fragmented flakes. More macro electrode/electrolyte surface for the SEI, so more lithium lost at formation (lower ICE) [5, 6]; shorter solid-state diffusion paths, which helps rate [10] | **trade-off**: bad for ICE and formation loss, good for rate | moderate for the ICE direction [5, 6] (relative index: the image sees only the > 50 nm part of the BET surface); low for the rate side and for the size of either effect |
| L_A **down at the same porosity** (`resid_z` < 0) | Less pore wall: coarser or agglomerated material. Less SEI surface (higher ICE) [5, 6], longer solid-state diffusion paths (poorer rate) [10] | **trade-off**: good for ICE, bad for rate | moderate (ICE) / low (rate) |
| L_A up **together with porosity** (`resid_z` ≈ 0) | More pore space, hence more wall: a calendering or coat-density change, not a powder change. Read `porosity_open_frac`: lower energy density, poorer particle contact | see `open_porosity` (trade-off: transport vs energy density) | strong that L_A tracks porosity here (r = 0.81); mechanism as in `open_porosity` |
| L_A down **together with porosity** | Denser electrode: higher ionic tortuosity, poorer rate, more plating risk at fast charge (read `porosity_open_frac`) | see `open_porosity` (trade-off: energy density vs rate) | as above |
| `pore_n_per_1000um2` **up** (`euler_density_per_1000um2` is not a features.csv column, team audit 2026-10-03: r 0.99 with the pore count) | The visible pore space is split into more, smaller gaps: a finer, more divided pore network. No published link to cell performance found | **neither: a sign the supplier's process changed** (PSD, mixing, calendering) | low (one image is a noisy count, split-half r 0.32; no battery citation) |
| pore count **down** | Fewer, larger gaps: a coarser pore network. The 2D Euler number is the pore count here and says nothing about 3D percolation [1, 7] | **neither: a sign the supplier's process changed** | low |

**Best value:** match the approved baseline; neither direction is better in itself (less wall trades ICE for rate).
Batch_3: L_A 0.532 ± 0.047 µm⁻¹ (Tier-2 range 0.396–0.667), `resid_z` ≈ 0 (B3 leave-one-out spread ± 1.50, so a
z of ± 2 is still baseline-like), 96.5 ± 8.0 pores per 1000 µm² (range 73.6–119.4; v1 used it as Tier 2).

**Our batches** (final integrated run: sep/q from `analysis/rank_features.py`, which permutes across all spots and so
does not control for session; within-session test and perturbations from `analysis/robustness.py`; verdicts from
`analysis/verdicts/`):
- **Batch_1: lower interface density, not established; no pore-count change shown.**
  - L_A 0.453 ± 0.044 vs B3 0.532 ± 0.047 µm⁻¹ (−0.079, −1.67 B3-SD). Over all spots it separates (sep 0.87,
    q 0.023), but L_A clusters by session (R² 0.72, baseline %GRR upper 86 %) and a gamma 0.8 change moves it
    0.60 B3-SD (bar 0.5), so that session-blind result overstates it.
  - Within the mixed sessions: −2.11 B3-SD, joint 3-batch p 0.057 (192 relabellings), which misses 0.05. B1 meets
    B3 directly in one session only, one spot each (2080: −2.65). In 2148 and 2156 B1 reads the same as B2 (−0.03,
    +0.03), so the rest of B1's −2.11 is carried over from B2's −1.42.
  - **2316 caveat (n_eff = 1 session):** the two 2316 spots have the lowest L_A of all 31 (0.386, 0.409). Session
    2316 holds no other batch, so the within-session test cannot use them. Their low values cannot be told apart from
    that session or from the Si-phase anomaly in the same two spots. Without them B1 is 0.475 (−1.2 B3-SD).
  - About half the shift is B1's lower porosity: `resid_z` −1.35 ± 1.25 (−0.74 without 2316), within sessions
    −0.86 B3-SD, p 0.18 (sep 0.48, q 0.20). Pore count 92.4 ± 13.6: within sessions −0.52 B3-SD, p 0.41 (sep 0.38,
    q 0.41).
  - Reading, if real: half of it is a denser electrode (see `open_porosity`: a trade-off of energy density against
    rate). The other half is a slightly coarser network at the same porosity, also a trade-off: less SEI surface
    (higher ICE) against longer diffusion paths (poorer rate).
  - **Verdict:** L_A is Tier 2 (quality range) and passes with 6/7 inside (outside: 5n1q8atc (2316), low). The
    certificate ranks it 3rd of B1's drivers, with P(|Δ| > margin) = 0.60 (Δ −0.079 against a 1.5-SD margin of
    0.071 µm⁻¹). Without the two 2316 spots the shift, −1.2 SD, would sit inside the margin. The pore count is a
    diagnostic in v1.1 (it left Tier 2 because its left/right split-half reliability r_x is 0.25, bar 0.35); it
    reads −0.51 SD (screen q 0.70). Neither column is among the reasons for B1's INVESTIGATE; the Si phase is.
    `resid_z` is not used, and the Euler density is no longer a column.
- **Batch_2: same direction, smaller, not established.**
  - L_A 0.497 ± 0.041 µm⁻¹ (−0.034, −0.73 B3-SD). Within sessions −1.42 B3-SD (same joint p 0.057), and all three
    B2–B3 contrasts are negative (2068 −1.78, 2080 −0.46, 2272 −1.17), each with one B2 spot against one to three B3
    spots.
  - `resid_z` −0.77 ± 0.64 (within sessions −0.81 B3-SD, p 0.18). Pore count 89.6 ± 6.4 (within sessions
    −1.35 B3-SD, p 0.41; sep 0.38, q 0.41).
  - **Verdict:** L_A is Tier 2, 7/7 inside, P(|Δ| > margin) 0.13. The pore count is a diagnostic: −0.86 SD
    (screen q 0.50). Neither is among the reasons for B2's INVESTIGATE.
- Pooled incoming vs B3 within sessions, using the only sessions where they meet (4 incoming spots against 5 B3
  spots in 3 sessions; 24 arrangements, floor p 0.042): L_A −1.54 B3-SD (p 0.083), `resid_z` −0.82 (p 0.083), pore
  count −1.20 (p 0.17). None reaches 0.05.

## What it measures

A 2D phase has three Minkowski functionals (additive measures): its **area** (here porosity, `porosity_open_frac` of
`open_porosity`), its **boundary length** and its **Euler characteristic** (number of objects minus number of holes)
[1, 2]. By Hadwiger's theorem any additive, motion-invariant and continuous measure of a shape is a combination of
these three, so together they are a complete, compact description of "how much, how much surface, how connected" [3].

- `interface_density_per_um`: walk along every image row and column and count where the pixel switches between pore
  and solid. P_Lx and P_Ly are the crossings per µm of test line. For an isotropic section the boundary length per
  area is L_A = (π/2) P_L (Crofton / Smith–Guttman [4]); averaging the two directions gives
  L_A = (π/4)(P_Lx + P_Ly) [2]. B3: 0.53 µm⁻¹, i.e. about one µm of pore wall in every 2 µm².
- In 3D, for isotropic structure, the surface area per volume is S_V = (4/π) L_A = 2 P_L [4]. B3: S_V ≈ 0.68 µm⁻¹ of
  electrode volume.
- `interface_density_resid_z`: L_A rises with porosity (more pores, more wall). The residual asks whether a spot has
  more or less wall than Batch_3 has *at the same porosity*, i.e. whether its pore network is finer or coarser.
- `pore_n_per_1000um2` / `euler_density_per_1000um2`: how finely the visible pore space is split into separate gaps.
  In these sections the pores are isolated (no void cluster spans the crop in any of the 31 spots; the largest holds
  4–13 % of the pore area) and the solid always percolates, so the Euler characteristic is the pore count minus the
  few solid islands sitting inside pores (3 % of the count on average, 0.8–8.8 %; r = 0.99 between the two columns).

## Why it matters for the battery

- **Surface → SEI → first-cycle loss.** The solid-electrolyte interphase forms on the electrode/electrolyte surface
  during the first cycles and consumes lithium: for graphites the first-cycle charge loss scales with the BET surface
  area [5], and which part of that surface and pore structure is exposed matters [6]. More interface per volume at
  the same porosity points to finer particles, more fines or more fragmented flakes, and so to a lower ICE and more
  SEI growth. Less interface points to coarser or agglomerated material: less SEI surface, but longer solid-state
  diffusion paths and so poorer rate [10] (shown only for nano-graphite, so direction only). Neither direction is
  better in itself: it is a trade-off.
- **Link to BET (macro part only).** BET counts surface down to nanometres (internal and edge-plane surface,
  carbon-binder nanopores); the image sees only boundaries coarser than the 25 nm pixel and 50 nm blur. Back-of-envelope
  for B3: S_V = 0.68 µm⁻¹ per electrode volume, 0.76 µm⁻¹ per solid volume, ≈ 0.34 m²/g at 2.2 g/cm³, against a few
  m²/g on a graphite CoA (research report §2: SSA ≤ 5.8 m²/g). The image interface is therefore a relative index of
  the macro surface, not a BET estimate.
- **Pore count → network fineness.** At equal porosity, fewer resolvable pores means fewer, larger gaps (a coarser
  pore network), the "coarser skeleton" pattern that also shows as thicker solid ligaments (`solid_lt_d50_um`).
  Possible causes: changed mixing/dispersion, calendering or particle-size distribution. We found no published link
  from a 2D gap count to cell performance, so a change in either direction is a sign the supplier's process changed,
  not good or bad in itself.
- **What the Euler number does *not* tell you here.** In 3D the Euler characteristic measures pore connectivity
  (redundant loops) that governs percolation and transport [1, 7]. A 2D section of a 3D-connected pore network shows
  isolated pore cuts, so χ in 2D ≈ pore count and says nothing about 3D percolation.

## Industry / Polaron use

- **Specific surface area (BET, m²/g)** is a standard CoA item for anode powders (GB/T 24533, supplier data sheets;
  research report §2). The image interface density is the closest image proxy, but only for the macro part.
- Image-based specific surface area is a standard output of microstructure software (GeoDict, Avizo, NREL MATBOX;
  research report §2) and of Polaron-type microstructure quantification; we found no public Polaron statement naming
  Minkowski functionals.
- Minkowski functionals and Euler characteristic as microstructure descriptors: academic (porous media [1], soil
  science [7], statistical physics [3]). Pore number density as a QC KPI: academic only.

## How it is computed

- **Input**: `features._common.harmonise.harmonised(sample).void`, the shared BSE void mask (same 1336-row crop of every
  spot ≈ 5800 µm², black/graphite anchors, noise topped up to one level, Otsu void threshold, pore specks < 16 px
  dropped, solid pin-holes < 16 px filled). No extra opening or smoothing.
- **L_A** (`interface_density`): crossings = count of horizontally / vertically adjacent pixel pairs that differ;
  P_Lx = crossings_x / (H·(W−1)·0.025 µm), P_Ly likewise; L_A = (π/4)(P_Lx + P_Ly). Adding the two diagonal directions
  changes L_A by less than 0.3 % on every spot (r = 1.000), so two directions are enough here.
- **Counts** (`object_counts`, cached per spot): pores = 8-connected void components with ≥ `min_object_px` = 64 px
  (0.04 µm²); islands = 4-connected solid components ≥ 64 px that do not touch the crop edge (a piece touching the edge
  is not known to be enclosed). The 8/4 pairing is the dual connectivity the digital Euler number needs [8]. (The
  Euler density is still computed in `feature.py` but is not a column.)
  Pores cut by the crop edge are counted; every spot has the same crop size, so this edge bias is the same for all.
  Normalised by the crop area (`h.area_um2`), per 1000 µm².
- **Residual (trained)**: `train(baseline_samples)` stores every baseline spot's porosity (`void.mean()`, identical to
  `porosity_open_frac`) and L_A, with its id, in `models/minkowski_functionals.npz` (2 KB). The feature fits
  L_A = a + b·porosity by least squares on the baseline spots, leaving the scored spot out if it is one of them, and
  returns (L_A − fit) / residual SD (n − 2 degrees of freedom). It needs ≥ `min_baseline_spots` = 5 baseline spots.
  On all 17 B3 spots: L_A = 0.309 + 2.065·porosity, residual SD 0.029 µm⁻¹, R² 0.64. The model also stores the
  hash of the `features/_common` recipe it was trained on, and the feature returns NaN with a retrain message when
  the hash differs. Retrain with `python features/run_features.py --train` after any change to `features/_common`.
- Runtime (own code, harmonisation excluded): L_A 3 ms, residual 9 ms, the two counts 0.18 s together.

## Evidence on our data

All 31 spots, computed with the feature functions (validation run 2026-10-03; the residual model was trained on the 17
B3 spots into a scratch file, `models/` untouched). The integrated pipeline run (`analysis/rank_features.py` and
`analysis/robustness.py` on the final `processed/features.csv`) reproduces the means, correlations, session and
within-session statistics and perturbation ratios below (re-checked against `processed/*.csv`; the session-R²
permutation p varies by ± 0.01 with the random draw) and adds sep/q (table "Final pipeline numbers"). Split-half r
and the ≥ 16 px count comparison come from the builder's run only. B3-SD = SD of the 17 Batch_3 spots (for the residual: SD of the leave-one-out z among B3
spots, 1.50). Session = image height, 13 groups, chance R² ≈ 0.40. Within-session
test: OLS y ~ C(session) + C(batch), exact permutation over the 192 distinct batch relabellings inside the five mixed
sessions; "incoming vs B3" pools B1 + B2 (24 arrangements, floor p = 0.042). The 95 % CI is the parametric OLS
interval (df 17).

**Final pipeline numbers** (integrated run; sep and q from `rank_features.py`, which does not control for session;
within-session p (3-batch, 192 relabellings), session R² and perturbation ratio from `robustness.py`):

| Column | B1 / B2 / B3 mean | sep | q | within-session p (B1 / B2, B3-SD) | session R² | perturbation ratio |
|---|---|---|---|---|---|---|
| `interface_density_per_um` | 0.453 / 0.497 / 0.532 | **0.87** | **0.023** | 0.057 (−2.11 / −1.42) | **0.72** | **0.60** (gamma 0.8) |
| `interface_density_resid_z` | −1.35 / −0.77 / −0.09 | 0.48 | 0.20 | 0.18 (−0.86 / −0.81) | 0.54 | 0.38 (blur) |
| `pore_n_per_1000um2` | 92.4 / 89.6 / 96.5 | 0.38 | 0.41 | 0.41 (−0.52 / −1.35) | 0.44 | **0.66** (gamma 1.25) |

`rank_features.py` calls L_A "separates" (p 0.001, worst leave-one-out sep 0.77, leak ρ 0.18 with black level) and
the other two "no difference". Because L_A clusters by session (baseline ICC 0.75, %GRR upper 86 %) and moves 0.60
B3-SD under gamma, the session-blind sep/q overstate it; the acquisition-controlled evidence is the within-session
p = 0.057. Session R² chance ≈ 0.40; perturbation bar 0.5.

**Validation detail** (builder's run; every row except split-half r re-checked against the integrated run):

| | `interface_density_per_um` | `interface_density_resid_z` | `pore_n_per_1000um2` | `euler_density_per_1000um2` |
|---|---|---|---|---|
| Batch_1 (7) | 0.453 ± 0.044 | −1.35 ± 1.3 | 92.4 ± 14 | 90.2 ± 14 |
| Batch_2 (7) | 0.497 ± 0.041 | −0.77 ± 0.64 | 89.6 ± 6.4 | 86.3 ± 6.6 |
| Batch_3 (17) | 0.532 ± 0.047 | −0.09 ± 1.50 (LOO) | 96.5 ± 8.0 | 93.5 ± 8.8 |
| η²(batch), ANOVA p | **0.35, 0.002** | 0.15, 0.10 | 0.10, 0.23 | 0.09, 0.27 |
| Session R² (permutation p) | **0.72 (0.003)** | 0.54 (0.16) | 0.44 (0.38) | 0.46 (0.31) |
| Within-session coef. B1 / B2 (B3-SD), exact p | −2.11 / −1.42, p 0.057 | −0.86 / −0.81, p 0.18 | −0.52 / −1.35, p 0.41 | −0.32 / −1.25, p 0.38 |
| Incoming vs B3 (B3-SD) [95 % CI], exact p | **−1.54 [−2.49, −0.60], p 0.083** | −0.82 [−2.00, +0.37], p 0.083 | −1.20 [−2.87, +0.46], p 0.17 | −1.08 [−2.67, +0.50], p 0.21 |
| Raw contrasts (B3-SD): 2068 B2−B3; 2080 B1−B3, B2−B3; 2272 B2−B3 | −1.78; −2.65, −0.46; −1.17 | −0.79; −1.31, −1.07; −0.36 | −0.87; −1.41, −2.08; −0.98 | −0.72; −1.13, −2.08; −0.94 |
| Raw contrasts: 2080 B1−B2; 2148 B1−B2; 2156 B1−B2 | −2.20; −0.03; +0.03 | −0.24; +0.75; −0.44 | +0.66; +3.68; −1.31 | +0.95; +3.45; −1.07 |
| Perturbation ratio, max over 4 B3 spots: black+25 / γ0.8 / γ1.25 / contrast / noise / blur | 0 / **0.60** / 0.58 / 0.08 / 0.08 / 0.37 | 0 / 0.28 / 0.27 / 0.05 / 0.04 / 0.38 | 0 / 0.24 / **0.66** / 0.11 / 0.17 / 0.41 | 0 / 0.35 / **0.64** / 0.08 / 0.21 / 0.41 |
| Split-half r, mean \|L−R\| | 0.66, 0.90 B3-SD | 0.35, 0.83 B3-SD | 0.32, 1.34 B3-SD | 0.35, 1.25 B3-SD |
| Correlation with porosity (all / B3) | 0.81 / 0.80 | 0.10 / −0.06 | −0.33 / −0.36 | −0.43 / −0.50 |
| Spearman with native BSE noise (all / B3) | −0.58 / −0.44 | −0.20 / −0.14 | +0.08 / +0.35 | +0.20 / +0.45 |

Reading:
- **Interface density carries the clearest batch ordering of this family, B3 > B2 > B1** (η² 0.35, ANOVA p 0.002;
  integrated `rank_features.py`: sep 0.87, q 0.023, 8th-highest sep of 69 columns), but the values also cluster strongly by session (R² 0.72, permutation p 0.003), and outside the five mixed sessions
  session and batch are confounded, so the raw ANOVA overstates the evidence. Within sessions the sign holds:
  incoming spots have less interface in all four contrasts with B3 (−0.5 to −2.7 B3-SD), pooled −1.54 B3-SD
  (−0.073 µm⁻¹, parametric 95 % CI [−0.118, −0.028]), exact permutation p = 0.083 (2/24) and 3-batch p = 0.057. It
  agrees with the research report's earlier recipe (0.487 / 0.521 / 0.542 µm⁻¹, p ≈ 0.004 raw, ≈ 0.09 session-matched).
- **Much of it is porosity.** L_A correlates 0.81 with porosity, and B1 has the lowest porosity. After removing the
  B3 porosity trend, `interface_density_resid_z` keeps the same sign in all four B3 contrasts (−0.36 to −1.31) but
  the pooled effect halves (−0.82 B3-SD, CI [−2.00, +0.37]). The residual is also nearly free of the native-noise
  coupling that L_A and porosity show (Spearman −0.14 within B3 vs −0.44 / −0.60).
- **Pore count: the screen's lead weakens under the shared harmonisation.** All four B3 contrasts are still
  negative (incoming −0.9 to −2.1 B3-SD), pooled −1.20 B3-SD, p 0.17 (screen, fixed 0.5 threshold: −1.65, p 0.042).
  The B1–B2 pairs disagree (2148 +3.7, 2156 −1.3). The Si-rich 2316 sites are no longer far below everything else:
  4ih2ggld is still the lowest of the 31 spots but only just (79.8 vs 81.6 for the next, z −2.1), and 5n1q8atc is
  mid-range (z −0.5). In the screen they read 57 / 52 per 1000 µm² against a B3 mean of 81, so the screen's reading of
  those two sites depended on its threshold.
- Together with `solid_lt_d50_um` (incoming +1.47 B3-SD, p 0.083; `robustness.py` on the integrated run:
  B1 +1.20 / B2 +1.52 B3-SD, 3-batch within_p 0.068) the family points one way: incoming batches may have a
  coarser pore/solid network (less wall, fewer gaps, thicker ligaments). None of the three reaches p < 0.05 within
  sessions (L_A 0.057, `solid_lt_d50_um` 0.068, pore count 0.41). Across the 31 spots `solid_lt_d50_um`
  correlates with both L_A (r = −0.70) and the pore count (r = −0.51), and `interface_density_resid_z` with both
  (r = −0.59 and +0.60), so these are not independent confirmations; treat them as one lead. L_A and the pore count themselves
  are nearly uncorrelated (r = 0.15), so they are not simply the same measurement either. About 30 morphology
  variants were tried in the screen. Evidence is thin: 4 incoming spots against 5 B3 spots in 3 sessions.

## Uncertainty and pitfalls

- **Sampling**: the counts are the least reliable columns here. Split-half r is 0.32–0.35 and the halves differ by
  1.25–1.34 B3-SD, so one image carries roughly 0.8 B3-SD of sampling error (≈ 60–70 % of the B3 between-spot
  variance; rough, assuming independent halves). L_A is better (≈ 0.56 B3-SD, ≈ 30 %). Average several images per lot.
- **Noise and blur (why the noise matching matters)**: every count and every boundary length depends on how many
  noise-sized specks pass the threshold and on how sharp the edges are. Counting objects ≥ 16 px instead of ≥ 64 px
  gives 164 instead of 94 pores per 1000 µm² and only r = 0.62 with the 64 px count; the screen measured split-half
  r 0.44 and a 0.72 blur ratio for that version. With the shared noise matching and the 64 px floor, added noise
  moves the counts ≤ 0.21 B3-SD, but a 1 px blur still moves them 0.41 (and L_A 0.37). Focus or resolution changes
  between sessions are a real risk; compare within a session when you can.
- **Gamma**: 0.58–0.66 B3-SD for L_A and the counts (thresholds between two anchors move with detector
  non-linearity). A black-level shift gives exactly 0; a 0.85× contrast change gives ≤ 0.11.
- **Session coupling**: L_A and porosity correlate with the native BSE noise of the image (Spearman −0.58 overall,
  −0.44 within B3). B1/B2 sessions are noisier, so part of the raw batch ordering could be acquisition. The
  within-session contrasts (same noise) keep the sign, which argues for material, but cannot prove it.
- **Residual model**: one B3 spot, 0grcilhi (porosity 0.128 with coarse pores, pore d90 3.0 µm), scores −5.2 when
  left out; with it in the fit the residual SD is 0.029 µm⁻¹, without it 0.019 µm⁻¹. The leave-one-out z of B3 spots
  therefore has SD 1.50 (0.76 without 0grcilhi): |z| ≈ 2 is not unusual for the baseline. Calibrate thresholds on the
  leave-one-out baseline distribution, not on N(0, 1). The z divides by the residual SD of the fit only, as specified,
  not by the prediction SD of a new point (that would add the leverage factor √(1 + 1/n + (x − x̄)²/Sxx)). Using the
  prediction SD would shrink |z| by 3 % near the B3 mean porosity and by more at the porosity extremes: 13–14 % on the
  low-porosity B1 spots f1vzngrs and 5n1q8atc, 20 % on hzumfsms (porosity 0.148), 7 % on 0grcilhi (−4.8 instead of
  −5.2). The B3 leave-one-out SD would be 1.39 instead of 1.50. So the most extreme |z| values are somewhat overstated.
- **Stale model**: the stored baseline values depend on the shared void recipe. `train()` stamps the
  `features/_common` recipe hash into the model, and the feature refuses a model trained on another recipe
  (NaN plus a "retrain" message), so a change in `features/_common` cannot silently shift the residuals.
- **Two test directions**: (π/4)(P_Lx + P_Ly) is unbiased for isotropic boundaries but reads a perfectly horizontal
  boundary π/4 (−21 %) too short. For fully horizontal boundaries the 2- and 4-direction estimates would differ by
  about 17 %; here they agree within 0.3 % on every spot, so the boundary orientations are close enough to isotropic
  that this bias is small.
- **2D vs 3D**: S_V = (4/π) L_A assumes isotropy. The structure is anisotropic (P_Ly / P_Lx = 1.18, 1.08–1.27: more
  crossings through the thickness, flattened pores), and an unbiased S_V of an anisotropic material needs vertical
  sections with cycloid test lines [9]. The 2D Euler number says nothing about 3D connectivity (see above).
- **Pore-back and resolution**: pores that show material behind them read as solid (less boundary); interface finer
  than ~50 nm and the carbon-binder nanopores are invisible. Absolute values depend on the segmentation recipe (the
  screen's fixed 0.5 threshold gives B3 L_A 0.39 µm⁻¹ instead of 0.53).

## References

1. Armstrong R. T. et al. (2018) Porous media characterization using Minkowski functionals: theories, applications
   and future directions. *Transp. Porous Media*. https://doi.org/10.1007/s11242-018-1201-4
2. Legland D., Kiêu K., Devaux M.-F. (2007; Crossref's record says 2011) Computation of Minkowski measures on 2D and
   3D binary images. *Image Anal. Stereol.* 26:83. https://doi.org/10.5566/ias.v26.p83-92
3. Mecke K. R. Additivity, convexity, and beyond: applications of Minkowski functionals in statistical physics.
   *Lecture Notes in Physics* (year not in the Crossref record). https://doi.org/10.1007/3-540-45043-2_6
4. Smith C. S., Guttman L. (1953) Measurement of internal boundaries in three-dimensional structures by random
   sectioning. *JOM*. https://doi.org/10.1007/bf03397456 (see also Russ & DeHoff (2000) *Practical Stereology*,
   https://doi.org/10.1007/978-1-4615-1233-2)
5. Winter M., Novák P., Monnier A. (1998) Graphites for lithium-ion cells: the correlation of the first-cycle charge
   loss with the Brunauer-Emmett-Teller surface area. *J. Electrochem. Soc.* 145:428. https://doi.org/10.1149/1.1838281
6. Joho F. et al. (2001) Relation between surface properties, pore structure and first-cycle charge loss of graphite
   as negative electrode in lithium-ion batteries. *J. Power Sources* 97–98:78.
   https://doi.org/10.1016/s0378-7753(01)00595-x
7. Vogel H.-J., Weller U., Schlüter S. (2010) Quantification of soil structure based on Minkowski functions.
   *Comput. Geosci.* https://doi.org/10.1016/j.cageo.2010.03.007
8. Gray S. B. (1971) Local properties of binary images in two dimensions. *IEEE Trans. Comput.*
   https://doi.org/10.1109/t-c.1971.223289
9. Baddeley A. J., Gundersen H. J. G., Cruz-Orive L. M. (1986) Estimation of surface area from vertical sections.
   *J. Microsc.* 142:259. https://doi.org/10.1111/j.1365-2818.1986.tb04282.x
10. Liu W., Zong K., Li Y. et al. (2022) Nano-graphite prepared by rapid pulverization as anode for lithium-ion batteries.
    *Materials* 15:5148. https://doi.org/10.3390/ma15155148 (smaller graphite particles, larger surface, better rate;
    10–300 nm particles, and the authors also credit surface oxygen (wetting) and mesopores, so it supports the
    direction only, not the size of the effect at µm scale)

All DOIs, titles, authors and years were checked against Crossref on 2026-10-03 (OpenAlex was rate-limited); the
volume/page numbers given for refs 2, 5, 6 and 9 are copied from `notes/research_report.md` §10. Ref 10 was
found with `literature.load_papers` and checked against Crossref (title, authors, year, volume, article number). Industry
statements (BET on the CoA, vendor software) come from `notes/research_report.md` §2 and are not independently
verified here.
