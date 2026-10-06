# heterogeneity

How unevenly the pores and the Si-like bright phase are spread across one image. For each phase there is a raw
tile CV, and an excess ratio that compares the tile-to-tile variance with what a random medium of the same structure
would give. Adds three columns to `processed/features.csv`; the porosity excess ratio is computed in `feature.py`
only.

| Column | Unit | Meaning |
|---|---|---|
| `porosity_tile_cv` | dimensionless (sd/mean) | Coefficient of variation of the void fraction over 512-px (12.8 µm) tiles of the crop |
| `bright_tile_cv` | dimensionless (sd/mean) | The same for the Si-like bright phase |
| `porosity_excess_het_ratio` | dimensionless | Observed variance of the tile void fractions ÷ the variance a statistically homogeneous medium with the same two-point correlation would give: φ(1−φ)·A_IR/A_tile. ≈ 1 random, > 1 clustered beyond chance, < 1 more even than chance. **Not a features.csv column** (team audit 2026-10-03): blind to lateral patchiness by design (a patchy phantom scores inside the real range) |
| `bright_excess_het_ratio` | dimensionless | The same for the bright phase |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `bright_excess_het_ratio` **up** (above the B3 range) | The Si phase sits in clusters beyond chance: agglomerates from poor mixing or dispersion, or already in the incoming powder. Si-based phases swell strongly on lithiation [R8], so Si-rich patches concentrate the swelling. A SiO/graphite model finds that the uniformity of the SiO distribution changes polarisation and capacity [R4]. Local cracking, contact loss and faster fade are the expected result. In graphite anodes, agglomerated slurries give more resistive electrodes [R9]. Counterpoint: in Si–graphite electrodes the formulation with the *least* evenly dispersed binder cycled best [R11] (binder, not Si) | bad (expected, not shown for this metric) | low–moderate (model and slurry studies; no measured cell link; one counterpoint) |
| `bright_excess_het_ratio` **down** | The Si phase is spread more evenly than in the baseline, towards or below a random dispersion. Fewer swelling hot-spots would be expected, but no study shows a cell benefit, and [R11] warns that "more uniform" is not automatically better | neither: a sign the supplier's process changed (mixing/dispersion, or the Si powder itself) | low |
| `porosity_excess_het_ratio` **up** (not a features.csv column, team audit 2026-10-03: blind to lateral patchiness by design) | Pore-rich and pore-poor patches beyond chance, from uneven calendering or mixing. Dense patches should limit electrolyte transport first: in operando imaging, lower porosity and faster charge make graphite lithiate unevenly in-plane, and plating starts where lithiation runs ahead [R10]. Microstructure at several length scales sets plating propensity [R7]. But in image-based simulations of 14 graphite electrodes, active-material clustering alone had minimal impact on fast charge [R6] | bad, weakly (fast-charge plating risk, not shown for patchiness itself); mainly a process signal | low |
| `porosity_excess_het_ratio` **down** (not a features.csv column, as above) | Pores spread more evenly than in the baseline | neither: a sign the calendering or mixing changed | low |
| `porosity_tile_cv` / `bright_tile_cv` **up** | Mostly a coarser phase or, for the Si phase, less of it; not patchiness. Over all spots the porosity CV follows the pore integral range (r = +0.68 with `s2_void_integral_range_um2`, ≈ 0 with the porosity), and the bright CV falls as the Si fraction rises (r = −0.59 with `bright_frac`). It means patchiness only if the excess ratio rises with it | neither by itself: read it with the fraction, the size columns and the excess ratio | low |
| `porosity_tile_cv` / `bright_tile_cv` **down** | Mostly a finer phase or, for the Si phase, more of it | neither by itself (as above) | low |

**Best value:** as close to the B3 baseline as possible; no direction away from it is known to help. B3 mean ± SD:
bright ratio 0.82 ± 0.14 (about what a random dispersion of particles this size gives, null 0.77), porosity ratio
0.59 ± 0.11. The B3 mean ± 2.86 SD ranges are 0.214–0.551 (porosity CV) and 0.519–1.685 (bright CV); v1 used them
as Tier-2 quality ranges, and v1.1 shows both CVs as diagnostics. Only
above-baseline excess ratios carry an expected risk: low–moderate for the bright ratio (Si hot-spots), weak for the
porosity ratio (fast-charge plating). Neither risk has been measured in cells for this metric.

**Our batches** (final integrated run, `analysis/rank_features.py` and `analysis/robustness.py`). "Within sessions"
is the exact permutation test inside the 5 mixed sessions (floor ≈ 0.005), the only acquisition-controlled
evidence; effects are in B3-SD units. sep and q permute across all spots and do **not** control for session.
- **Si-phase dispersion, `bright_excess_het_ratio`: lower in both lots, a hint, not an established difference.**
  - B1 0.645 and B2 0.583 vs B3 0.821. Within sessions: B1 −1.54, B2 −1.19 SD, p = 0.031. All 4 lot-vs-B3 contrasts
    are negative, but B1 has only one (2080, −1.24), so B1's estimate leans on B2 through the B1–B2 pairs.
  - Across spots: sep 0.88 (worst leave-one-out 0.82), q = 0.023. Acquisition-robust: perturbation 0.04, leak ρ 0.08.
  - Why only a hint: without one B2 spot (rxax5ozo, session 2068) the within-session p is 0.19. The p is not
    corrected for the 59 non-acquisition columns in `robustness.csv` (BH over them gives q ≈ 0.42) or for the
    ≈ 16 tile and mask variants tried. Per-spot ICC is 0.06. Adjusting for the Si particle aspect ratio, which also
    shifts within sessions, weakens it to p = 0.068 (B1 −1.09, B2 −0.73 SD). These checks were run by this review.
  - Not the 2316 spots: their ratios are normal (z −0.8, −0.7), and B1 without them is 0.615.
  - Reading: **neither good nor bad. If real, it is a sign the supplier's process changed** (mixing/dispersion, or
    a differently shaped Si powder). Worth a question, not a defect. Verdict: **not used** (in none of Tier 1,
    Tier 2 or the diagnostics).
- **Pore patchiness, `porosity_excess_het_ratio`: no difference.** B1 0.572 and B2 0.639 vs 0.590; sep 0.26,
  q = 0.80. Within sessions p = 0.13 (B1 +1.74, B2 +1.79 SD), all from one B2 spot (rxax5ozo, +4.1 SD in 2068).
  Without it p = 0.75 (+0.48 / +0.22). Not used by the verdict, and no longer a column.
- **Tile CVs (diagnostics in the verdict): a raw shift in B1, not confirmed within sessions.**
  - `porosity_tile_cv`: B1 0.458 (+1.3 SD), B2 0.413 (+0.5) vs 0.382. `bright_tile_cv`: B1 0.869 (−1.1),
    B2 1.174 (+0.4) vs 1.102.
  - Across spots: sep 0.66 / 0.79, q = 0.077 for both. The porosity CV's 0.66 is no more than several pure
    acquisition descriptors reach between batches (0.59–0.67).
  - Within sessions: p = 0.27 / 0.40 (B1 +1.18 / −0.83, B2 +0.90 / +0.46 SD). The effect sizes are similar to the
    raw ones, so this means "not established with 5 mixed sessions". It does not prove a session artefact.
  - About half of B1's raw shift is the two 2316 spots, which count as **one session (n_eff = 1)**. They have
    coarser pores (porosity CV z +2.4 and +3.1, ratio normal) and 2.5–3× the B3 Si fraction (bright CV z −2.2 and
    −2.5, mechanical). Without them B1 is 0.424 / 0.965 (+0.7 / −0.7 SD). Session 2316 holds only B1, so these
    spots do not enter the within-session estimate.
  - Both CVs are diagnostics in v1.1: they left Tier 2 because their left/right split-half reliability r_x is 0.08
    (porosity CV) and 0.33 (bright CV), below the 0.35 bar. The certificates show the porosity CV at +1.28 SD (B1)
    and +0.51 SD (B2), the bright CV at −1.14 and +0.36 SD (screen q ≥ 0.18). Neither column drives either
    INVESTIGATE.
- **Bottom line:** no sign of Si agglomeration or pore patchiness (the directions with an expected risk) in either
  incoming lot. At the 13 µm tile scale, the extra Si phase in B1's 2316 spots is dispersed like the normal Si, not
  clumped. That rests on one session.

## What it measures

Cut the BSE crop (33 × 175 µm) into 12.8 × 12.8 µm squares and measure the pore fraction and the Si-phase
fraction in each. In a well-mixed electrode the squares look alike. In a badly mixed or unevenly pressed one, some
squares are pore-rich or Si-rich and others poor. The **tile CV** is the spread of those square-by-square fractions
relative to their mean. It is the image analogue of the field-to-field variation that metallographers report for
volume fractions (ASTM E562/E1245, see research report §2).

A raw CV cannot tell "patchy" from "sparse and coarse". The Si phase covers ≈ 6 % of the area in particles of
2–10 µm, so a 164 µm² square holds only a handful of particles, and its CV is large (≈ 1.1) for an ideally random
dispersion. The **excess ratio** removes that. The two-point correlation of the whole mask gives the integral range
A_IR, the area over which the phase is correlated (≈ 5 µm² for pores, ≈ 15 µm² for the bright phase here). From it
follows the variance a random medium with exactly this short-range structure would show at the tile size
(Lantuéjoul [R1]; ImageRep [R2]; Kanit et al. [R3]). A_IR only counts correlations within the window of
`_common/config.yaml` (|dy| ≤ 4 µm, |dx| ≤ 12 µm). So a ratio above 1 means extra variation on larger scales:
gradients, bands, agglomerate clusters or pressing patches tens of µm across.

## Why it matters for the battery

- **Si-phase dispersion.** Si-based phases swell strongly on lithiation [R8]; for SiOx up to ≈ 160 % (research
  report §8). Si-rich patches become local swelling and current hot-spots that crack the electrode or isolate
  particles. An electro-chemo-mechanical model of SiO/graphite anodes finds that the uniformity and direction of the SiO
  distribution change the polarisation and the usable capacity [R4]. A through-thickness CBD gradient changes Li
  plating and mechanical risk in the same material [R5]. **Direction:** more clustering than baseline = worse
  dispersion = expected risk. Counterpoint: in Si–graphite electrodes, Armstrong et al. found the formulation with the
  *poorest* binder dispersion cycled best, and the well-dispersed one worst; binder-rich regions appear to take up
  the volume expansion [R11]. That concerns the binder, not the Si, but it is a warning against reading "more
  uniform" as automatically better. The other direction (Si more even than baseline) therefore stays "neither".
- **Porosity uniformity.** Dense, pore-poor patches are expected to be where electrolyte transport limits first at
  fast charge, and where plating starts. Operando imaging shows that lower porosity and faster charge make graphite
  lithiate unevenly in-plane, and that plating starts in the regions that lithiate first [R10]. Microstructure at
  several length scales sets plating propensity [R7]. Neither study measures lateral porosity patchiness itself. The
  honest counterpoint: in an image-based simulation of 14 graphite electrodes,
  Parmananda et al. found that **active-material clustering alone had minimal impact** on extreme fast charging,
  while particle-shape-driven tortuosity anisotropy dominated [R6]. Porosity heterogeneity is a process indicator
  first and a performance driver second.
- **Process meaning.** Uneven tiles point at mixing and dispersion (agglomerates, Si segregation during mixing,
  coating or drying), at binder migration, or at uneven calendering. At the same composition, the binder mixing
  sequence alone changes particle dispersion, and agglomerated slurries give more resistive anodes [R9]. That makes
  this the image-side check of the mixing record.

Confidence in the functional link: low–moderate (research report §8: "hypothesis").

## Industry / Polaron use

- **Polaron** lists "spatial heterogeneity" next to "drift detection and batch-to-batch comparability" and
  "objective acceptance criteria" on its Quality & Qualification page (research report §2, §10). Polaron/Imperial's
  ImageRep predicts the phase-fraction error bar of a single image from its two-point correlation [R2]. The excess
  ratio is the natural "is this more heterogeneous than chance?" test built on it.
- **Metallography** reports the field-to-field SD of area fractions (ASTM E562/E1245, research report §10). Image
  vendors offer RVE / representativity analyses (Avizo, GeoDict, MATBOX).
- **Cell makers** check slurry homogeneity indirectly: viscosity, fineness-of-grind, coat-weight maps. Cross-section
  heterogeneity of the Si phase is academic or vendor practice, not a CoA item.
- **What would move it:** mixing sequence [R9], intensity and time, dispersant or binder change [R11], Si-additive
  agglomeration in the incoming powder or a change of Si powder (size, shape), drying rate (binder/fines migration),
  and calendering uniformity.

## How it is computed

Detector: BSE only, through the shared masks of `features/_common/harmonise.py`:
- `h.void`: Otsu void, noise-matched, cleaned.
- `h.bright`: Si-like phase, midpoint between graphite and the image's own bright mode.

Both are on the same 1336 × 6984 px crop of every spot. Nothing is re-segmented.

1. **Tiles.** Square windows of `tile_px` = 512 px (12.8 µm, 164 µm²) placed every `stride_px` = 64 px
   (`config.yaml`). The windows overlap, so the statistic is averaged over every grid offset. The crop holds
   2 × 13 = 26 non-overlapping tiles and 13 × 102 = 1 326 overlapping windows. Window counts come from an integral
   image (four lookups per window). If fewer than `min_tiles` = 6 non-overlapping tiles fit, the result is nan.
   - Offsets start at 0 and step by 64 px. Because 1336 − 512 = 824 is not a multiple of 64, the last window row
     ends at row 1280: the bottom 56 rows of the crop (4 %), and the last 4–32 columns, are in no window.
   - Edge pixels fall in fewer windows than central ones.
   - This is the same for every spot, so it does not bias batch comparisons. Re-centring the offsets would shift
     every number below slightly; that change is left for v2.
2. **Tile CV** = sd(tile fractions, ddof 1) ÷ mean(tile fractions). nan if the phase is absent.
3. **Predicted variance.** For the whole-crop fraction φ and integral range A_IR from
   `fraction_se(mask)[1]`, the predicted variance is φ(1−φ)·A_IR / A_tile with A_tile = (512 × 0.025 µm)².
4. **Excess ratio** = observed tile variance ÷ predicted variance. nan if A_IR is not finite or not positive.
5. Results are cached per sample, so the four columns cost one pass per phase.

**Why overlapping tiles.** With one fixed non-overlapping grid of 26 tiles, the result depended on where the grid
sat. On the same images, the within-session batch test for `porosity_tile_cv` gave p = 0.010 with a centred grid,
0.84 with the grid in the top-left corner and 0.41 in the bottom-right. Averaging over all offsets removes that
arbitrariness. Compared with the centred grid it also cut the B3 between-spot SD of the porosity CV by 17 % and of
the porosity excess ratio by 42 %. Against the top-left and bottom-right grids the cuts are 25–28 % and 18–28 %.

Runtime of this folder's code: median 0.77 s per spot (max 1.2 s), mostly the two `fraction_se` FFTs.

## Evidence on our data

All 31 spots, final recipe. B3-SD = between-spot SD within Batch_3. Session R² by chance ≈ 0.40. Most sessions
hold a single batch, so session R² also absorbs any real batch effect and cannot by itself separate batch from
session; the within-session test does that.

**Final pipeline numbers** (integrated run: `analysis/rank_features.py` → `processed/rankings.csv` for sep and q;
`analysis/robustness.py` → `processed/robustness.csv` for the within-session test, session R² and perturbations).
The within-session cell gives the exact permutation p (192 relabellings of the 5 mixed sessions, floor ≈ 0.005) and
the B1 / B2 effects in B3-SD. sep and q come from a permutation across all spots that does **not** control for
session, so the within-session p is the acquisition-controlled test.

| Column | B1 / B2 / B3 mean | sep (worst LOO) | q | within-session p (B1 / B2, SD) | session R² | perturbation ratio |
|---|---|---|---|---|---|---|
| `porosity_tile_cv` | 0.458 / 0.413 / 0.382 | 0.66 (0.54) | 0.077 | 0.27 (+1.18 / +0.90) | 0.62 | 0.17 |
| `bright_tile_cv` | 0.869 / 1.174 / 1.102 | 0.79 (0.68) | 0.077 | 0.40 (−0.83 / +0.46) | 0.56 | 0.17 |
| `bright_excess_het_ratio` | 0.645 / 0.583 / 0.821 | **0.88** (0.82) | **0.023** | **0.031** (−1.54 / −1.19) | 0.63 | 0.04 |

Only `bright_excess_het_ratio` passes both bars (q < 0.1 across spots, and within-session p < 0.05), and only
nominally. The within-session p has no multiplicity correction: BH over the 59 non-acquisition columns of
`robustness.csv` gives q ≈ 0.42, and 5 of the 59 reach p < 0.05, about what chance gives. Without rxax5ozo it is
0.19. The two CVs pass q < 0.1 across spots only; within sessions they do not.

**Validation tables** (builder's and reviewer's scripts). They agree with the final run on every mean, η², session
R², ICC and within-session test. They disagree only on the two bright-phase perturbation ratios: corrected in the
table below to the final run, with the validation value in brackets (see Perturbations).

| Column | B1 | B2 | B3 | η²(batch) | session R² | within-session (B3-SD; exact p, 192) | split-half r | perturbation ratio |
|---|---|---|---|---|---|---|---|---|
| `porosity_tile_cv` | 0.458 ± 0.075 | 0.413 ± 0.022 | 0.382 ± 0.059 | 0.24 | 0.62 | b1 +1.18, b2 +0.90; p = 0.27 | 0.09 | 0.17 |
| `bright_tile_cv` | 0.869 ± 0.206 | 1.174 ± 0.196 | 1.102 ± 0.204 | 0.25 | 0.56 | b1 −0.83, b2 +0.46; p = 0.40 | 0.33 | 0.17 (1.05) |
| `porosity_excess_het_ratio` | 0.572 ± 0.126 | 0.639 ± 0.193 | 0.590 ± 0.109 | 0.03 | 0.43 | b1 +1.74, b2 +1.79; p = 0.13 | 0.30 | 0.09 |
| `bright_excess_het_ratio` | 0.645 ± 0.158 | 0.583 ± 0.110 | 0.821 ± 0.144 | 0.38 | 0.63 | b1 −1.54, b2 −1.19; **p = 0.031** | −0.27 | 0.04 (0.29) |

**Raw within-session contrasts** (B3-SD):

| Column | 2068 B2−B3 | 2080 B1−B2 | 2080 B1−B3 | 2080 B2−B3 | 2148 B1−B2 | 2156 B1−B2 | 2272 B2−B3 |
|---|---|---|---|---|---|---|---|
| `porosity_tile_cv` | +0.52 | +0.73 | +2.45 | +1.72 | −0.93 | +0.36 | +0.06 |
| `bright_tile_cv` | +0.54 | −0.92 | +0.35 | +1.28 | −3.16 | −0.46 | −1.00 |
| `porosity_excess_het_ratio` | +4.09 (rxax5ozo) | +1.21 | −0.06 | −1.28 | −0.52 | +0.78 | +1.58 |
| `bright_excess_het_ratio` | −1.62 | −0.61 | −1.24 | −0.64 | −1.15 | +0.42 | −1.11 |

**Calibration: what a random medium gives.** Boolean disc media were simulated on the crop size with the final code.
The first four rows have 12 realisations each. The two rows marked "review" were added by the reviewer, with other
seeds, at the A_IR actually seen on our data.

| Medium | A_IR | Realisations | Mean ratio | SD |
|---|---|---|---|---|
| void-like (φ 0.10, disc r 20 px) | 0.7 µm² | 12 | 1.02 | 0.14 |
| void-like (φ 0.10, r 35 px) | 2.2 µm² | 12 | 0.93 | 0.13 |
| void-like (φ 0.10, r 55 px; review) | 5.7 µm² | 44 | 0.93 (per set of 8–12: 0.90–0.98) | 0.14–0.27 |
| bright-like (φ 0.05, r 60 px) | 6.5 µm² | 12 | 0.92 | 0.14 |
| bright-like (φ 0.05, r 100 px) | 18.8 µm² | 12 | 0.82 | 0.14 |
| bright-like (φ 0.05, r 100 px; review, pooled with the row above) | 18.4 µm² | 56 | **0.77** (per set: 0.68–0.82) | 0.14–0.16 |

The 12-realisation means scatter by ± 0.05–0.07 between seeds. The pooled 0.77 ± 0.02 (SE) is the better
bright-phase null.

- **Downward bias.** For random media the ratio sits below 1: from 1.02 down to 0.77. The bias grows as the
  correlation area approaches the tile size. φ(1−φ)·A_IR/A_tile is the large-tile limit, and a 12.8 µm tile is
  only 2–3 correlation lengths across. A triangle-weighted finite-tile prediction (prototype, non-overlapping grid)
  moves B3 to 0.82 (void) and 1.06 (bright).
- **Single-image precision.** The per-image sampling SD of the ratio itself is ≈ 0.14. That is the same size as the
  whole B3 between-spot SD (0.11 void, 0.14 bright).

**What the data say:**
- **Single-spot values are mostly noise.** The split-half reliability (left vs right half of each crop) is ≈ 0 for
  every column (−0.27 to 0.33; within B3 −0.47 to 0.25). The B3 session ICC is 0.11 for porosity CV, 0.08 for
  bright CV, 0.42 for the porosity ratio and 0.06 for the bright ratio. Twenty-six independent tiles per image are
  not enough to pin down a variance. These columns can only carry a **batch-mean** signal.
- **Bright phase, B3:** ratio 0.82 ± 0.035 (SE). That is about what a random dispersion of particles of this size
  gives: the pooled A_IR ≈ 18 µm² disc null is 0.77 ± 0.02, so B3 is at most slightly above it. The between-site
  version agrees: B3 bright fractions vary between spots by *less* than one image's sampling error (between-site
  variance ÷ mean se² = 0.72). B3's Si phase is randomly dispersed and the
  site-to-site scatter of `bright_frac` is pure sampling noise, matching the screen's split-half finding for SiOx.
- **Bright phase, B1/B2:** lower ratios (0.65 / 0.58), below the random-disc null (0.77), i.e. *more even than
  random*.
  - Within sessions, all 4 contrasts against B3 are negative (−0.6 to −1.6 B3-SD). The exact permutation gives
    p = 0.031.
  - The three B1−B2 contrasts (−0.61, −1.15, +0.42) say nothing about B3, and they are mixed.
  - The direction holds for the fixed-threshold mask `h.bright_fixed` (b1 −1.48, b2 −1.05 SD; p = 0.036) and at
    384-px tiles (p = 0.036). It weakens at 256 px (b1 −1.03, b2 −0.48; p = 0.12) and 768 px (−0.98 / −0.70;
    p = 0.38). At 1024 px (only 6 independent tiles) B2 flips sign (b1 −0.54, b2 +0.25; p = 0.33). With a single
    non-overlapping grid, B1 stays negative at all three placements (−0.79 to −2.45 SD) but B2 flips at one of them
    (p = 0.07–0.42).
  - It is not explained by the bright fraction (r = −0.00) or by A_IR (r = +0.06), and the lifted 2060 session is
    unshifted (z = +0.53).
  - It does move with Si particle shape. Across spots (without 2316) r = −0.52 with `bright_aspect_aw` and +0.41
    with `bright_d90_um`, but only −0.06 / +0.14 inside B3. Both columns also shift within sessions
    (`bright_aspect_aw` B1 +1.61, B2 +1.64 SD, p = 0.036; `bright_d90_um` B1 −1.80, B2 −0.66 SD, p = 0.026).
    With the aspect ratio as a covariate, the within-session batch effect drops to B1 −1.09, B2 −0.73 SD
    (p = 0.068); with d90 it is −1.31 / −1.11 (p = 0.036). Part of the lower ratio may therefore come from a
    differently shaped Si powder, not from mixing.
  - **This is the most interesting result of the folder, and it is thin.** p = 0.031 after looking at about 16
    tile/mask variants and 59 columns (BH q ≈ 0.42). It rises to 0.19 without the one B2 spot of session 2068
    (rxax5ozo); no other single spot raises it above 0.08. Per-spot reliability is ≈ 0, and n_eff = 5 mixed sessions.
    The leave-one-out, covariate and BH checks were run by this review on `processed/features.csv` with
    `robustness.py`'s own test.
  - Read it as a hypothesis: "the incoming Si phase is more uniformly dispersed than the baseline's", from a
    different mixing or dispersion step or a different Si powder. That is a change worth asking about, not a defect.
- **The two 2316 spots** (B1, the Si-phase lead) have low `bright_tile_cv` (z = −2.2 and −2.5). That is mechanical:
  they hold 2.5–3× the B3 bright fraction, and a CV falls as the fraction rises (r(CV, fraction) = −0.59 over all
  spots). Their excess ratios are normal (z = −0.8 and −0.7). **The extra bright phase there is dispersed like the
  normal one, not agglomerated into patches** at the 13 µm scale (one session, n_eff = 1).
- **Porosity:**
  - **No batch effect survives:** p = 0.27 (CV) and 0.13 (ratio). The ratio's 2068 contrast (+4.1 SD) is one spot,
    B2 rxax5ozo (ratio 1.00, the highest void ratio of all 31). Without it the ratio's within-session p is 0.75
    (B1 +0.48, B2 +0.22 SD).
  - **An earlier p = 0.010 for the tile CV was a grid artefact.** It came from one particular non-overlapping grid
    and vanished when the grid moved (see How it is computed).
  - The 2316 spots have high `porosity_tile_cv` (z = +2.4 and +3.1) but normal ratios. Their pores are coarser
    (A_IR 11.5 and 7.3 µm² vs a median of 5.3 over all spots and 4.2 in B3). The ratio correctly puts the uneven
    tiles down to coarseness, not patchiness.
  - Void ratios sit well below 1: B3 0.59, below the ≈ 0.93 random-disc null at A_IR ≈ 5.7 µm². Pores here are *more
    evenly spread than random*. That is expected for pores packed between particles. Flat, elongated pores may add
    to the finite-tile bias.
- **Between-site excess (the research report's §3 rank-8 definition)** is a batch-level number for the decision
  layer, not a column. It is the variance of the spot porosity fractions ÷ mean single-image se²:
  - porosity: 3.7 in B3, 2.7 in B1, 3.3 in B2. Spots differ about 2× more than their sampling error; excess SD
    0.016, mostly the session component.
  - bright phase: 0.72 in B3, **14.3 in B1** (driven by the two 2316 spots; 1.8 without them), 1.3 in B2.

  This is where heterogeneity is detected best on our data: across spots, not within one image.
- **Perturbations** (B3 71vgq3fw, cfe5vt7s, hzumfsms, 0grcilhi; max |Δ| ÷ B3-SD; final run, `robustness.py`):

  | Column | Worst case | Ratio | Validation run |
  |---|---|---|---|
  | `porosity_tile_cv` | gamma 0.8 on 0grcilhi | 0.17 | 0.17 |
  | `porosity_excess_het_ratio` | gamma 0.8 on hzumfsms | 0.09 | 0.09 |
  | `bright_excess_het_ratio` | gamma 0.8 on 0grcilhi | 0.04 | 0.29 |
  | `bright_tile_cv` | gamma 1.25 on 0grcilhi | 0.17 | 1.05 |

  All four are well inside the 0.5 bar. Black +25, contrast, noise and blur are all ≤ 0.07; gamma is the worst
  case for every column.
  - The validation run's `bright_tile_cv` failure (1.05) was upstream. Under gamma 1.25 the shared `_bright_mode`
    found no bright peak on 0grcilhi and fell back to a fixed 2.1. The bright fraction rose from 0.051 to 0.070, the
    CV fell mechanically with it (1.09 → 0.88), and the excess ratio absorbed most of it (0.89 → 0.85).
  - `features/_common/harmonise.py` now falls back first to the median of the image's own bright cores, not a
    fixed level, so that a gamma or contrast change moves the threshold with the phase. The final run no longer
    shows the failure.
  - The ratio is still the less fraction-sensitive of the two, which is one more reason to prefer it.

**Verdict:**
- `bright_excess_het_ratio`: the builder recommends it as a candidate on batch means only, with a thin hint that
  B1/B2 are more evenly dispersed than B3. The frozen v1.1 rule (`analysis/verdict_config.yaml`) does not use it.
  Note that Tier 2 is a per-site range test, which a column with per-spot ICC 0.06 cannot support. It would need a
  batch-mean test (v2), and the "lower" direction would raise a process question, not a defect.
- `porosity_*` heterogeneity: no batch signal (negative result). `porosity_excess_het_ratio` is no longer a column.
- Both CVs: descriptive only. They are confounded by the phase's coarseness and, for the bright phase, by its
  fraction. v1.1 shows both as diagnostics (shown, never decisive): they left Tier 2 because their split-half
  reliability r_x is 0.08 (porosity CV) and 0.33 (bright CV), below the 0.35 bar. They do not affect either
  certificate.
  - With no `_tile_cv` column left in Tier 2, the `heterogeneity_suffix: _tile_cv` rule in `verdict.py` (a Tier-2
    miss reported as "Heterogeneity", action "check the mixing and dispersion record") has nothing to act on.
    B1's "Heterogeneity" reason comes from the Brown–Forsythe spread test on `bright_solid_frac` (5.4×), not from
    a tile CV.
  - On these data a high porosity CV would more likely mean coarser pores than patchiness (5n1q8atc: 2316, coarse
    pores, normal ratio). Check the excess ratio before reading it as patchiness.

## Uncertainty and pitfalls

- **Per-spot precision.** The ratio's own sampling SD is ≈ 0.14 per image, and CV estimates from 26 independent
  tiles have ≈ 15–20 % relative error. Compare batch means over ≥ 5–7 spots, never single spots. A single image
  with ratio > 1.3–1.5 is notable (≈ 3 null SDs above the random-medium value), but nothing on our data reaches it
  (max 1.18).
- **The baseline is not 1.** The large-tile formula reads up to ≈ 25 % low for tiles only 2–3 correlation lengths
  across (random-disc null 0.93 void, 0.77 bright), and real pores are more evenly packed than random. Always read
  the ratio against the B3 distribution (median 0.58 void, 0.81 bright), not against 1. A finite-tile prediction
  would fix the bias. It needs the covariance from `_common` (see the final report).
- **Overlapping windows** are correlated. Do not count the 1 326 windows as independent samples.
  - The estimate has less placement noise than a non-overlapping grid.
  - It is ≈ 4 % lower in expectation: ddof = 1 over 1 326 windows does not correct for the ≈ 26 independent tiles.
  - The random-medium null above already includes this.
- **Integral-range window.** A_IR sums the covariance over |dy| ≤ 4 µm only. The largest Si particles (up to
  ≈ 10 µm) are correlated over longer vertical lags, and that part of their own correlation counts as "excess".
  - Much coarser Si could therefore raise `bright_excess_het_ratio` without any clustering.
  - The coarser-cored 2316 spots read normal (z −0.8 / −0.7), so the effect is small at the sizes seen so far.
  - Shape matters too. Across spots the ratio follows the Si aspect ratio (r = −0.52) and d90 (+0.41), and part of
    the B1/B2 drop goes with their shape shift (see Evidence). Read a ratio change together with `bright_aspect_aw`
    and `bright_d90_um` before calling it a dispersion change.
- **Only two rows of tiles.** The crop is 1336 px tall, so the tiles see vertical (through-thickness) variation only
  between two 12.8 µm bands. A depth gradient counts as heterogeneity here. The top-minus-bottom tile-row difference
  shows no batch effect (p = 0.62 void, 0.77 bright), so this does not drive the results.
- **Inherits the masks' errors.** Pore-back hides part of the void. A session tone curve that moves the bright-mode
  detection changes the bright mask and, through the fraction, the CV. This was the gamma 1.25 case of the validation
  run; the fallback is now fixed upstream (final ratio 0.17).
- **Scale-specific.** 12.8 µm tiles see heterogeneity between ≈ 13 µm and the 33 × 175 µm crop. Electrode-scale
  variation (mm, coat-weight streaks) needs many spots: that is the between-site excess above.
- **3D validity.** Area-fraction variances are unbiased for volume-fraction variances of the section plane only
  under isotropy. Elongated flakes make the 2D integral range direction-dependent, so heterogeneity in 2D and 3D can
  differ.

## References

DOIs resolved through the Crossref API on 2026-10-03, because the OpenAlex search quota behind `ledger.py search`
was exhausted that day. "Amass" marks papers also found with `literature.load_papers`. DOIs came from the research
report (§10) or the Amass literature, never from memory.

1. [R1] Lantuéjoul (1991) Ergodicity and integral range. *J. Microsc.* 161:387.
   https://doi.org/10.1111/j.1365-2818.1991.tb03099.x
2. [R2] Dahari, Docherty, Kench et al. (2025) Prediction of microstructural representativity from a single image
   (ImageRep). *Adv. Sci.* 12. https://doi.org/10.1002/advs.202414149 (Amass; the "validated up to ~70 px feature
   size" limit is **[unverified]**)
3. [R3] Kanit, Forest, Galliet et al. (2003) Determination of the size of the representative volume element for
   random composites: statistical and numerical approach. *Int. J. Solids Struct.* 40:3647.
   https://doi.org/10.1016/S0020-7683(03)00143-4
4. [R4] Gao, Xu et al. (2024) Impedance inhomogeneity in SiO/Gr composite anode. *Small Science*.
   https://doi.org/10.1002/smsc.202300291 (Amass; model study)
5. [R5] Gao, Xu et al. (2024) Carbon binder domain inhomogeneity in silicon-monoxide/graphite composite anode by 2D
   multiphysics modeling. *Adv. Sci.* https://doi.org/10.1002/advs.202400729 (Amass; model study)
6. [R6] Parmananda, Norris, Roberts et al. (2022) Probing the role of multi-scale heterogeneity in graphite electrodes
   for extreme fast charging. *ACS Appl. Mater. Interfaces* 14:18335. https://doi.org/10.1021/acsami.1c25214 (Amass)
7. [R7] Kabra, Parmananda, Fear et al. (2020) Mechanistic analysis of microstructural attributes to lithium plating in
   fast charging. *ACS Appl. Mater. Interfaces* 12:55795. https://doi.org/10.1021/acsami.0c15144 (Amass)
8. [R8] Obrovac & Chevrier (2014) Alloy negative electrodes for Li-ion batteries. *Chem. Rev.* 114:11444.
   https://doi.org/10.1021/cr500207g (Crossref-checked 2026-10-03; same DOI in the ledger entries `si_fraction`,
   `si_particles`)
9. [R9] Kitamura, Tanaka, Mori (2022) Effects of the mixing sequence on the graphite dispersion and resistance of
   lithium-ion battery anodes. *J. Colloid Interface Sci.* 625:136. https://doi.org/10.1016/j.jcis.2022.06.006
   (Amass; Crossref-checked 2026-10-03)
10. [R10] Choi, Kim, Muralidharan et al. (2026) Depth-to-areal staging heterogeneity preceding lithium plating in
    graphite anodes revealed by operando imaging. *Adv. Sci.* e77918. https://doi.org/10.1002/advs.77918 (Amass;
    Crossref-checked 2026-10-03; experiment plus electrode-scale simulation; varies electrode porosity, not lateral
    patchiness)
11. [R11] Armstrong, Hays, Ruther et al. (2022) Role of silicon-graphite homogeneity as promoted by low molecular
    weight dispersants. *J. Power Sources* 517:230671. https://doi.org/10.1016/j.jpowsour.2021.230671 (DOI from the
    OSTI record 1840193 cited in research report §10, Crossref-checked 2026-10-03; claim taken from the OSTI
    abstract. This resolves the report's **[unverified]** "least-dispersed binder performed best" note)
12. Polaron, Quality and Qualification page ("spatial heterogeneity", "drift detection and batch-to-batch
    comparability"). https://www.polaron.ai/applications/quality-and-qualification (URL from the research report;
    no DOI)
13. ASTM E562-19e1 and ASTM E1245-03(2023): field-to-field variation of area fractions (URLs in the research
    report §10; no DOI)
14. Project sources: `notes/research_report.md` §2 (heterogeneity row), §3 rank 8, §6.2 (error budget: ImageRep vs
    site and session variance), §8 (tile CVs / excess heterogeneity row); screen results `siox_particles.json`
    (`siox_quadrat_cv_10um`: CV of a sparse phase is mechanically tied to its fraction), `cbd.json`
    (`cbd_quadrat_cv`), `phase_fractions.json` (`siox_frac_se`, `porosity_I060_se`).
