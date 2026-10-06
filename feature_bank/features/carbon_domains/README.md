# carbon_domains

Does the electrode contain a second, darker graphite grade, and does it come as whole particles (a blend) or as
contrast inside particles (electron channelling)? BSE grey levels inside the graphite, plus Inlens particle
boundaries. This is a **diagnostic (decision Tier 3)**: compare it within one imaging session only. It adds one
column to `processed/features.csv`; the boundary share is computed in `feature.py` only:

| Column | Unit | Meaning |
|---|---|---|
| `carbon_dark_domain_frac` | area fraction (0–1) | share of the graphite interior that sits in the darker of two graphite grey levels, counted in patches ≥ 25 µm². 0 = one graphite level only |
| `carbon_domain_boundary_on_particle_frac` | fraction (0–1) | share of the dark/main domain interfaces that lie on a particle boundary (within 0.5 µm of a void or bright-phase edge or an Inlens ridge). Chance level ≈ 0.6. nan when there are no domains. **Not a features.csv column** (team audit 2026-10-03): NaN on 22/31 spots, and the missingness carries meaning |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `carbon_dark_domain_frac` up | If the darker level is a second graphite grade (a blend), the electrode holds more of that grade. Grades differ in surface area, and graphite with more accessible surface loses more charge in the first cycle (lower ICE) [6, 7]. The natural/synthetic ratio also changes the slurry's extensional flow, which matters in coating [5]. Natural graphite processes well and takes little energy to make, but needs modification for fast and low-temperature charging [4]. That it also gives more capacity, while synthetic graphite cycles longer and swells less, is common industry knowledge with no verified citation here. If the contrast is channelling [1–3, 9] or pore-back [10], nothing changes in the cell | neither: a sign the supplier's graphite recipe may have changed. If it is confirmed as a natural/synthetic shift, it is a trade-off: natural gives cost and processability, synthetic gives rate [4] (and, by general knowledge, cycle life and less swelling). Which way ICE and capacity move depends on which grade is the darker one, and that needs EDS, Raman or XRD | low |
| `carbon_dark_domain_frac` down (to 0) | less of the darker grade, or only one graphite grade. The level is measured relative to the main graphite peak of each image, so a lot that switched entirely to one *different* grade also reads 0 | neither: the same supplier-recipe signal as "up" when the baseline from the same session shows domains. A 0 alone does not prove the graphite is unchanged | low |
| `carbon_domain_boundary_on_particle_frac` up (towards 1, well above its chance level ≈ 0.6; not a features.csv column, team audit 2026-10-03: NaN on 22/31 spots, and the missingness carries meaning) | the grey level changes at particle boundaries, so whole particles differ. That fits a blend or particles with different internal porosity [8], but also pore-back: sub-surface material seen through a pore is bounded by the pore rim, so it also sits on a boundary [10]. It has no effect on the cell by itself. It makes a dark-fraction change more likely to be a real material difference only once pore-back is ruled out (an SE-relief check, not implemented) | neither: it tells you how to read the dark fraction | low |
| `carbon_domain_boundary_on_particle_frac` down (towards its chance level; not a features.csv column, as above) | the grey level changes inside particles: electron channelling [1–3, 9] rather than a second material, or particle boundaries the Inlens ridge filter missed. A dark-fraction change is then more likely an imaging effect | neither: it tells you how to read the dark fraction | low |

**Best value:** the same as the approved baseline imaged in the same session: a dark fraction inside the baseline's
spot-to-spot range (0–0.28), and a boundary-share excess over chance like the baseline's (≈ +0.22). Neither
column has a "better" direction until the darker grade is identified. The boundary share is not a material
property; it is a reading aid.

**Our batches** (final integrated run, `rank_features.py` and `robustness.py`; "SD" = baseline between-spot SD,
0.080 for the dark fraction). Baseline Batch_3: 0.028 ± 0.081, domains in 2 of 17 spots (0.20 and 0.28).
- **Batch_1:** dark fraction 0.013 ± 0.016. Weak domains (≤ 0.045) appear in 4 of 7 spots, and whether they
  count depends on the recipe settings. No difference inside the mixed sessions (within-session p 0.31, a joint
  test of both lots). The two session-2316 spots behind the Si-phase lead both read 0, so the Si-phase anomaly
  comes with no *second* graphite level there. That is one session (n_eff = 1), and a full switch of those spots
  to one other grade would also read 0, so it does not prove the graphite is unchanged.
- **Batch_2:** 0.082 ± 0.107. Domains appear in 3 of 7 spots (0.15–0.25), two of them in session 2048, which
  holds no baseline spot, so they cannot be compared within a session. No difference inside the mixed sessions
  (p 0.31).
- **Why the raw means do not count:** sep 0.46, q 0.33 ("no difference") across spots. The session-adjusted
  effects are not significant (p 0.31) and rest on mostly-zero data with one or two spots per session. Batch_1's
  −1.7 SD comes from session 2080 alone (one spot per batch; −0.2 SD without it). Batch_2's −0.8 SD is spread
  over sessions 2068, 2080 and 2272 (−0.5 SD without 2080). Session R² is 0.63 (chance ≈ 0.40), so spots
  cluster by session: compare within a session only. Perturbation ratio 0.24 (passes the 0.5 bar).
- **Boundary share:** Batch_1 0.88 (n 4), Batch_2 0.80 (n 3), Batch_3 0.81 (n 2). `rank_features.py` flags it
  (sep 1.61, q 0.075), but that test shuffles labels across all spots and ignores the session. It cannot be
  tested inside sessions: within-session p 1.00, because only session 2080 has domains in more than one batch.
  It also fails the perturbation bar (ratio 1.00 against < 0.5). The excess over chance is similar in all three
  batches (+0.23 / +0.21 / +0.22; permutation p 0.80, n 4 / 3 / 2, so only a large difference would show).
  Inside session 2080 it is +0.19 / +0.24 / +0.19. Batch_1's higher raw share comes from its higher chance level:
  more of the graphite around its domains lies within 0.5 µm of a detected boundary (0.65 against 0.59–0.60).
  It is not a different domain geometry, and it is not a batch signal.
- **What the verdict does:** `carbon_dark_domain_frac` is a Tier 3 diagnostic. The certificates show it as the
  raw lot − baseline mean (Batch_1 −0.18 SD, screen q 0.81; Batch_2 +0.67 SD, q 0.70). It never decides and is
  not among the INVESTIGATE reasons. The boundary share is not in `verdict_config.yaml` and is no longer a column.
- **Reading:** no evidence of a graphite blend or grade change in either incoming batch. Confidence is low:
  domains are rare and patchy (split-half r 0.29), and only session 2080 compares all three batches.

## What it measures

In about a third of the spots, some graphite particles are 8–17 % darker in BSE than the main graphite (mixture
component means; the research report's first screen quoted raw ≈ 49 vs 58–62 grey). The dark patches are particle-sized: median equivalent diameter
7–10 µm, the largest ≈ 17 µm. Looking at the images (spots vc2whyaq, avn74qx1,
r17byphk), the darker regions are mostly whole particles, darker in both BSE and SE, with outlines that follow
the particle edges. Elsewhere the graphite has one level.

The first column is the area share of that darker level. The second asks a geometric question that separates
two explanations:
- **Blend of two graphite grades** (e.g. natural + synthetic, or two suppliers). The contrast belongs to whole
  particles, so the level changes at particle boundaries.
- **Electron channelling.** BSE yield depends on how the crystal lattice is oriented to the beam [1–3]. It can
  change inside one particle: bent flakes, or polycrystalline secondary particles of synthetic graphite.

**Caveat.** A whole-particle contrast supports a blend but does not prove it. A single-crystal flake also
channels as a whole. And a particle with sub-resolution internal porosity (typical of spheroidised natural
graphite [8]) reads darker because it is less dense.

The "dark" level is always relative to the main graphite peak of that image. A single-grade image therefore
reads 0, whichever grade it is.

## Why it matters for the battery

- **A classic hidden supplier change.** Anode makers blend natural and synthetic graphite. Natural graphite
  processes well and takes little energy to make, and its market share is growing, but it needs modification
  for high-rate and low-temperature charging [4]. That natural graphite also gives more capacity, while
  synthetic graphite gives longer cycle life and less swelling, is common industry knowledge with no verified
  citation here. The blend ratio is a supplier formulation choice. It already changes how the slurry processes:
  the extensional rheology of anode slurries depends significantly on the natural/synthetic blend ratio [5].
- **Electrochemical consequences.** The grades differ in surface area and surface chemistry. For graphites, the
  first-cycle charge loss scales with the accessible (BET) surface area [6, 7]. A shifted blend ratio can
  therefore move ICE (and capacity) even when every powder CoA item of each grade is in spec.
- **Direction.** None is "better" in general. A dark-grade share outside the baseline's spread, seen against a
  baseline imaged in the same session and over several spots (one spot is noisy, split-half r 0.29), is a sign
  the graphite recipe may have changed. It is neither good nor bad until EDS/Raman shows which grade moved, and
  it is worth a question to the supplier.

## Industry / Polaron use

- **Academic only, as far as we found.** The blend ratio is set and certified by the anode-powder supplier: a
  formulation sheet or change notification. A powder CoA lists PSD, BET, tap density, d002 and capacity per grade,
  not the blend.
- **Today's checks for grade identity** are XRD (crystallinity, d002), Raman (ID/IG) and SEM of particle
  morphology. They work on powders, not on a finished electrode cross-section.
- **Imaging vendors** segment "graphite" as one phase (Avizo four-phase, Polaron's microstructure
  quantification). We found no public cross-section KPI for a two-grade graphite blend.
- **What would move it:** a changed natural/synthetic ratio, a new grade or supplier for one component, a
  different spheroidisation or purification route (internal porosity), and acquisition changes that alter
  channelling (kV, tilt, BSE detector segment).

## How it is computed

Detectors: BSE (grey levels) and Inlens (particle-boundary ridges), harmonised by `features/_common`: the same
central crop of every spot, graphite units, noise-matched, rank-normalised Inlens. Everything is computed at
50 nm/px (`downsample: 2`, area means). All numbers are in `config.yaml`.

1. **Graphite interior** = solid, not bright phase, and more than 0.3 µm from void and bright edges
   (`edge_margin_px: 6`). This keeps out edge halos, the BSE-bright carbon-binder skin and Si-phase blur. Below
   5 % of the crop (`min_graphite_frac`) the columns are nan.
2. **Level map.** Take a Gaussian-weighted mean of `h.bse_blur` over graphite-interior pixels only (normalised
   convolution, σ = 0.5 µm; `level_sigma_px: 10`). This averages noise, polishing striations and nanoscale CBD
   and keeps micron-size domains.
3. **Slow-scan drift (safeguard).** For each of 16 column blocks (`drift_column_blocks`), fit a slope to the
   medians of 6 row bands (`drift_row_bands`). Divide the level map by the median slope. Domains sit in a few
   blocks only, so the median reports the drift, not the domains. On today's 31 spots the robust slope is at most
   0.5 % across the crop (session 2048: −0.3 % and +0.5 %), so the correction changes nothing yet. A plain
   graphite-band median of the *full raw frame* of session 2048 does rise 11–19 % top-to-bottom, but that frame
   includes the rows outside the crop and the median is pulled down by the dark domains in the upper frame.
4. **Two levels.** The main level is the mode of the level map (`mode_bin: 0.005`). Fit a 2-component
   `sklearn.mixture.GaussianMixture` (`gmm_seed: 0`, ≤ 20 000 pixels by fixed stride; `gmm_max_values`) to the
   levels in [mode − 0.25, mode + 0.05] (`band_below`, `band_above`).
   - **Why the window stops just above the peak:** the graphite histogram has a long **bright** tail
     (carbon-binder sponge and debris read brighter than graphite in BSE). That tail is not a graphite grade. A
     window up to ≈ 1.25 makes the mixture fit it in most spots, giving large spurious dark fractions in
     domain-free spots (review spot-check: 71vgq3fw 0.59, i9jiqjwl 0.77; hzumfsms stays 0).
   - **Gate:** the darker component counts as a second level only if it sits ≥ 6 % below the main one
     (`min_contrast: 0.06`) and holds ≥ 2 % of the window (`min_weight`). Otherwise the result is 0.
5. **Dark patches.** A pixel is dark when its level is below the mixture's decision boundary (where the two
   weighted Gaussians cross). Apply a binary opening of radius 0.15 µm (`open_radius_px: 3`). Keep patches
   ≥ 25 µm² (`min_patch_um2`). `carbon_dark_domain_frac` = dark area / graphite-interior area.
6. **Blend vs channelling.** Interface pixels are dark pixels that touch main-level graphite.
   - **Particle boundaries:** void and bright pixels plus Inlens ridges, i.e. the top 10 % (`ridge_percentile:
     90`) of the minus-smaller-Hessian-eigenvalue ridge filter at σ = 75 nm (`ridge_sigma_px: 1.5`).
   - `carbon_domain_boundary_on_particle_frac` (computed in `feature.py`, not a column) = share of interface pixels within 0.5 µm of a particle boundary
     (`boundary_tolerance_px: 10`; this matches the smoothing scale). Below 200 interface pixels
     (`min_interface_px`) it is nan.
   - The same share for an arbitrary graphite-interior pixel is the chance level (≈ 0.6). The code computes it as
     `chance_frac`, but it is not a column.

Runtime: 1.07 ± 0.39 s per spot on top of the harmonised spot.

## Evidence on our data

The final code was run on all 31 spots (`preprocessing.iter_samples()`, shared harmonisation) with stdout-only
scripts; the per-spot values, batch statistics and perturbations were reproduced by an independent review run.
The integrated pipeline run (`analysis/rank_features.py` → `processed/rankings.csv`, `analysis/robustness.py` →
`processed/robustness.csv`) reproduces these numbers. Where it adds or corrects one, the text below says so.
"SD" = Batch_3 between-spot SD (dark fraction: 0.080; boundary share: 0.039, from 2 spots).

**Final pipeline numbers** (integrated run; `rank_features.py` for sep and q, `robustness.py` for the rest):

| Column | B1 / B2 / B3 means | sep | q | within-session p | session R² | perturbation ratio |
|---|---|---|---|---|---|---|
| `carbon_dark_domain_frac` | 0.013 / 0.082 / 0.028 (n 7 / 7 / 17) | 0.46 (worst leave-one-out 0.29) | 0.33 | 0.31 (192 relabellings; B1 −1.70, B2 −0.79 SD) | 0.63 | 0.24 (gamma 1.25, cfe5vt7s) |

- `rank_features.py` verdicts: dark fraction "no difference"; boundary share "separates". Acquisition leakage
  is low for both (leak_rho 0.10 with black level, 0.34 with image height; bar < 0.6).
- The "separates" verdict for the boundary share is not a batch signal. That test shuffles labels across all
  spots and ignores the session. The share also tracks its own chance level (Pearson r 0.67 over the 9 spots,
  p 0.05), and the chance level is higher around the Batch_1 spots (0.65 against 0.59–0.60). Subtracting it
  removes the batch difference (one-way permutation p 0.015 → 0.80; 20 000 shuffles). This is a stdout-only check
  on the chance values in the per-spot table below, which are rounded to 0.01; `chance_frac` is not a column in
  `features.csv`. Inside session 2080, the only acquisition-controlled comparison, the raw share differs by
  +2.20 SD (B1 − B3), but the excess over chance does not (+0.19 / +0.24 / +0.19 for B1 / B2 / B3).
- The dark fraction does not work as a gauge. In the baseline, 63 % of the variance lies between sessions
  (`icc` 0.63 in `robustness.csv`, the session share, so high is bad here). That gives an upper %GRR of 0.80
  (AIAG: ≥ 0.30 is not usable) and ndc 1.1. This is consistent with its Tier 3 (diagnostic) role.
- Session-adjusted effects, leaving one mixed session out: without 2080, Batch_1 −1.70 → −0.21 SD and
  Batch_2 −0.79 → −0.49 SD. The other drops move them by ≤ 0.55 SD. So Batch_1's effect is session 2080 alone.

**Per spot.** Domains were found in 9 of 31 spots:

| Batch | Spot | Session | Dark fraction | Boundary share | Chance |
|---|---|---|---|---|---|
| B1 | ffwubibz | 2080 | 0.017 | 0.87 | 0.68 |
| B1 | fzrt2k6r | 2156 | 0.045 | 0.86 | 0.66 |
| B1 | iv6g2oq0 | 1780 | 0.018 | 0.87 | 0.63 |
| B1 | uhdslk0o | 1880 | 0.013 | 0.93 | 0.64 |
| B2 | 3806gxp0 | 2048 | 0.177 | 0.79 | 0.59 |
| B2 | avn74qx1 | 2048 | 0.147 | 0.79 | 0.61 |
| B2 | r17byphk | 2080 | 0.253 | 0.81 | 0.57 |
| B3 | cfe5vt7s | 2080 | 0.280 | 0.79 | 0.60 |
| B3 | vc2whyaq | 2068 | 0.196 | 0.84 | 0.59 |

All other 22 spots read 0.000. The second level sits 8.2–17 % below the main graphite peak in these spots. In
20 of the 22 spots without domains, the mixture's "second component" is a split of one broad peak (≤ 4.3 % away,
11–74 % weight). The other two have a small tail component: epqdaau9 5.7 % (2.6 % weight) stays below the gate;
b3esycq1 6.9 % (4.8 % weight) passes it and is kept at 0 only by the 25 µm² patch floor.

| | `carbon_dark_domain_frac` | `carbon_domain_boundary_on_particle_frac` |
|---|---|---|
| Batch_1 | 0.013 ± 0.016 (n 7) | 0.880 ± 0.031 (n 4) |
| Batch_2 | 0.082 ± 0.107 (n 7) | 0.796 ± 0.009 (n 3) |
| Batch_3 | 0.028 ± 0.081 (n 17) | 0.812 ± 0.039 (n 2) |
| η²(batch) | 0.10 | 0.75 (9 spots; robustness.py) |
| session R² (chance ≈ 0.40) | 0.63 (perm. p ≈ 0.06; B3 only 0.75, p ≈ 0.09; free relabelling of sessions, 50 000 draws, recomputed; an earlier draft gave 0.07 and 0.08) | 0.78 (9 spots in 6 sessions, chance ≈ 0.63, not interpretable; robustness.py, earlier draft 0.79) |
| within-session test, exact p | **0.31** (192 relabellings) | not testable: only session 2080 has domains in > 1 batch (robustness.py reports p 1.00 over 6 relabellings) |
| perturbation ratio | **0.24** (gamma 1.25) | max \|Δ\| 0.0385 (gamma 1.25). robustness.py divides by the B3 SD (0.039, 2 spots): **1.00**, which fails the < 0.5 bar. Against the SD across all 9 domain spots (0.048) it is 0.81. It is 0.18 of the mean excess over chance (0.22) |
| split-half r | 0.29 (domain presence agrees in 27 of 31 spots) | — |
| minimum detectable shift, 7 vs 17 spots | ≈ 1.26 SD = 0.10 (approximate: zero-inflated) | — |

**Raw within-session contrasts** for the dark fraction (SD units): 2068 B2−B3 −0.81; 2080 B1−B2 −2.94,
B1−B3 −3.27, B2−B3 −0.33; 2148 B1−B2 0.00; 2156 B1−B2 +0.56; 2272 B2−B3 0.00. Session 2080 is the only session
that holds all three batches: B1 0.017, B2 0.253, B3 0.280. The session-adjusted OLS gives B1−B3 = −1.7 SD, but
that rests on one site per cell and zero-inflated data. The exact permutation p (0.31) is the honest number.

**Perturbations** were applied to the raw BSE/Inlens/SE of B3 spots 71vgq3fw, cfe5vt7s, hzumfsms and 0grcilhi.
- The three spots without domains stay at exactly 0 under all six perturbations, so the gate does not flip.
- cfe5vt7s moves from 0.280 to 0.279–0.299: black +25 0.071, gamma 0.8 0.156, gamma 1.25 0.239, contrast 0.016,
  noise 0.163, blur 0.006 SD (`robustness.csv`; an earlier review rerun gave blur 0.007). Both gammas raise it slightly (0.293 and 0.299). Gamma 0.8 also compresses the
  level contrast (8 % → 6.6 %), and that is what would push a weak domain spot towards the 6 % gate.
- Its boundary share moves from 0.785 to 0.782–0.824.
- These numbers are from the repo code on the shared harmonisation (review rerun). An earlier draft quoted
  0.16 from a private scratch cache of the harmonisation, whose cfe5vt7s baseline was 0.283.

**Recipe sensitivity** (all 31 spots, repo code on the shared harmonisation; review rerun):
- **Robust:** patch size 10/50 µm² (r 0.997), smoothing σ 5/20 px (0.998), edge margin 3/12 px (0.999/0.986) and
  a fit window up to mode + 0.08 (0.993) all track the default closely.
- **What does move:** lowering the gate to 4 % creates a false positive (9luzk4jm 0.18; r 0.93). A 10 µm² patch
  floor makes b3esycq1 positive (0.01). A 50 µm² floor, or a 12 px margin, drops the weakest Batch_1 spots
  (iv6g2oq0, uhdslk0o) to 0, and it lowers the strong spots by about a third (r17byphk 0.25 → 0.17). The weak
  Batch_1 "presence" is therefore recipe-dependent.
- An earlier draft, run on a private scratch cache of the harmonisation, reported false positives for window
  mode + 0.08 (5n1q8atc, x77cy643) and σ 1 µm (rxax5ozo). These do not reproduce on the repo harmonisation.
- **Why the gate is 6 %:** it sits above the broad-peak splits (≤ 4.3 %) and epqdaau9's 5.7 % tail, and below the
  smallest real contrast (8.2 %, which gamma 0.8 squeezes to ≈ 6.6 %). The margin is thin on both sides:
  b3esycq1's 6.9 % tail passes the gate and is stopped only by the patch floor, and a real 8 % domain survives
  gamma 0.8 by only 0.6 percentage points.

**Blend-vs-channelling test.**
- **Whole-particle contrast:** the dark/main interfaces lie on particle boundaries in 84 ± 5 % of cases (9 spots),
  against a chance level of 62 % (excess +0.22 ± 0.04).
- **Morphology-preserving null** (the same dark mask shifted circularly 20 times): the observed share exceeds the
  shifted-mask mean by z ≈ 3–8 in the five strong-domain spots (avn74qx1 3.0–5.7, r17byphk 6.9–8.0, depending on
  the random shifts; z from 20 shifts is itself noisy), and by z ≈ 1–2.3 in the four weak Batch_1 spots.
- **Reading:** the darker graphite mostly comes as whole particles. That favours a blend, a second grade, or
  particles with different internal porosity over channelling inside particles. Pore-back would also sit on
  boundaries, though, and is not tested (see Pitfalls). And 15–20 % of the interfaces lie inside particles or at
  boundaries we do not detect, so channelling cannot be excluded.
- **By batch** (added from the integrated run): the excess over chance is similar in all three batches
  (+0.23 / +0.21 / +0.22; n 4 / 3 / 2), and inside session 2080 too (+0.19 / +0.24 / +0.19). The higher raw share
  in Batch_1 (0.88 against 0.80–0.81) comes from its higher chance level, not from more whole-particle contrast
  (see "Final pipeline numbers").

**Reading.**
1. Two graphite grey levels are real image contrast in 9 spots. They are whole-particle in character. They
   survive acquisition perturbations, although only one domain spot (cfe5vt7s) was perturbed. They are not
   drift: avn74qx1's dark patches sit in the left columns, 0.62 → 0.00 across the width.
2. **They are not a batch marker.** All three batches contain them. The baseline itself spans 0–0.28. Within
   session 2080, B2 and B3 are similar and B1 lower, and nothing is significant (p = 0.31). The final
   `rank_features.py` run agrees (sep 0.46, q 0.33). Its boundary-share flag (q 0.075) is explained by the
   chance level, see above.
3. The session clustering (R² 0.63, p ≈ 0.06; both 2048 spots, all three 2080 spots) is what channelling or a
   shared electrode piece would produce. It is why this column must be compared within sessions.
4. The research report's "≈ 10 sites" is reproduced (9 spots), but the patches are particle-sized (median
   equivalent diameter 7–10 µm, largest ≈ 17.6 µm; 1–17 patches per spot) rather than 25 µm areas.

## Uncertainty and pitfalls

- **Sampling.** Domains are patchy on the scale of the field: split-half r = 0.29. In r17byphk the halves read
  0.32 vs 0.04; in cfe5vt7s, 0.00 vs 0.33. One spot is a poor estimate of a blend ratio. Pool many spots and
  report how many spots show domains at all.
- **Acquisition.** Channelling contrast depends on kV, specimen tilt and the BSE detector geometry [1–3, 9].
  Session R² is 0.63, so compare a new lot only against a retained baseline sample imaged in the same session.
- **Slow-scan drift.** It is corrected robustly, and inside the crop it is ≤ 0.5 % today. 3806gxp0's dark pixels
  are skewed to the top of the frame (0.24 → 0.10 down the image, in thirds); its robust slope is only −0.3 %, so
  drift is an unlikely cause, but an uncorrected non-linear ramp cannot be excluded.
- **Pore-back.** Sub-surface material seen through pores is also mid-grey (≈ 0.7–0.9 g) and bounded by void, so
  it can mimic a dark particle and inflate both columns [10]. The 0.3 µm edge margin and the patch-size floor
  reduce this but do not remove it. An SE-relief test is not implemented.
- **Bright tail.** CBD and debris are BSE-brighter than graphite and are deliberately outside the fit window. A
  brighter second graphite grade, as opposed to a darker one, would therefore be missed when it is the minority.
  When the darker grade is the majority, the anchor falls on it and the brighter minority is not counted.
- **Relative measure.** Without an absolute BSE reference (black is clipped in most sessions), a single-grade
  image reads 0 whichever grade it is. The column measures the presence and share of a *second, darker* level.
- **Boundary detection.** Inlens ridge density varies by session (it sets the chance level, 0.57–0.68), so
  compare the boundary share with its chance level and within sessions. Interfaces are located only to the
  0.5 µm smoothing scale. "Ridges" are a quantile (the top 10 % of solid pixels), not an absolute ridge strength:
  in an Inlens image with little real ridge structure they fall on noise and, with the 0.5 µm tolerance, cover
  almost all graphite. In a synthetic test both the share and its chance level then read 1.0 for whole-particle
  and for intra-particle domains alike. The chance level is returned as `chance_frac` by `carbon_domains(sample)`
  but is not a column, so a downstream reader of `features.csv` cannot apply this check.
- **Edge brightening.** Graphite 0.3–0.5 µm from a pore reads 1.6–5.5 % brighter than the interior > 2 µm from a
  pore (CBD skin, edge effect; domain-free spots 71vgq3fw, hzumfsms, 5n1q8atc). This biases domain edges *away* from void boundaries, so the on-particle excess is if anything
  conservative.
- **2D vs 3D.** The area fraction of a phase is an unbiased estimate of its volume fraction (Delesse), *if* the
  classification is right. The boundary share is a 2D geometric statement only.
- **Identity.** Confirming a blend needs EDS (impurities), Raman ID/IG or EBSD/tilt series on dark vs main
  particles. A tilt series is the direct channelling test, since channelling contrast changes with tilt and a
  material difference does not.

## References

1. Goldstein, Newbury, Michael et al. (2018). *Scanning Electron Microscopy and X-Ray
   Microanalysis*, 4th ed., Springer (BSE atomic-number contrast; electron-channelling contrast).
   https://doi.org/10.1007/978-1-4939-6676-9
2. Identifying threading dislocations in GaN films and substrates by electron channelling (2011). *J. Microsc.*
   (channelling contrast with a conventional pole-piece BSE detector; dependence on kV and diffraction vector).
   https://doi.org/10.1111/j.1365-2818.2011.03538.x
3. Observation and quantitative analysis of dislocations in steel using electron channeling contrast imaging
   method with precise control of electron beam incident direction (2024). *Microscopy* (BSE intensity depends
   on the beam direction relative to the crystal planes and on kV). https://doi.org/10.1093/jmicro/dfad061
4. Zhao, Ding, Qin et al. (2022). Revisiting the roles of natural graphite in ongoing lithium-ion batteries.
   *Adv. Mater.* 34, e2106704 (review; the abstract, read via Crossref/PubMed, covers natural graphite's
   processability, low production energy and growing share, and strategies to improve its high-rate and
   low-temperature charging). https://doi.org/10.1002/adma.202106704
5. Extensional rheology of anode slurries for Li-ion batteries containing natural and synthetic graphite (2024).
   *J. Colloid Interface Sci.* https://doi.org/10.1016/j.jcis.2024.02.152
6. Winter, Novák, Monnier (1998). Graphites for lithium-ion cells: the correlation of the first-cycle
   charge loss with the BET surface area. *J. Electrochem. Soc.* 145, 428. https://doi.org/10.1149/1.1838281
7. Joho, Rykart, Blome et al. (2001). Relation between surface properties, pore structure and
   first-cycle charge loss of graphite as negative electrode in lithium-ion batteries. *J. Power Sources* 97–98, 78.
   https://doi.org/10.1016/S0378-7753(01)00595-X
8. Quantitative FIB/SEM tomogram analysis of closed and open porosity of spheroidized graphite anode materials for
   LIBs applications (2022). *Micron.* https://doi.org/10.1016/j.micron.2022.103398
9. Čalkovský, Müller, Gerthsen (2022). Quantitative analysis of backscattered-electron contrast in
   scanning electron microscopy. *J. Microsc.* https://doi.org/10.1111/jmi.13148
10. Prill et al. (2013). Morphological segmentation of FIB-SEM data of highly porous media (shine-through /
    pore-back). *J. Microsc.* 250, 77. https://doi.org/10.1111/jmi.12021

DOIs 1, 6, 7 and 9 are tool-verified ledger entries; 2–5, 8 and 10 come from `literature.load_papers`. The authors,
volume and abstract of [4] were read from Crossref and PubMed. Author lists not retrieved by a tool are omitted;
the first author and volume of [10] follow
`notes/research_report.md`. OpenAlex search was rate-limited (HTTP 429) during this build, and neither Crossref
nor the literature corpus gave a natural-vs-synthetic electrochemistry comparison. [4]'s abstract supports only
the processability, production-energy and rate parts of the trade-off. The capacity, cycle-life and swelling
differences between natural and synthetic graphite are general knowledge with no verified citation here.
