# local_thickness

How wide the pores and the solid are: the area-weighted local-thickness distribution (diameter of the largest
inscribed disc) of the shared void mask and of the solid. Adds three columns to `processed/features.csv`.

| Column | Unit | Meaning |
|---|---|---|
| `pore_lt_d50_um` | µm | Half of the pore area lies in openings at least this wide (area-weighted median pore width) |
| `pore_lt_d90_um` | µm | The widest 10 % of the pore area lies in openings at least this wide (large gaps, macro-pores) |
| `solid_lt_d50_um` | µm | The same median for the solid (graphite + Si phase + carbon-binder web): thickness of the ligaments between pores |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| Pore width down (`pore_lt_d50_um`, `pore_lt_d90_um`; the two move together, r = 0.85), porosity unchanged | More, narrower pores. Narrower pores let liquid through less easily, so the electrolyte takes longer to fill the electrode (the wetting rate depends on the pore-size distribution, not only on porosity [5]). Ionic resistance is set mainly by porosity and tortuosity [8]. It rises only if the narrowing sits at bottlenecks (constrictivity [10]), which a 2D median width cannot show. Typical of a finer graphite or a different particle shape [6] | **bad** for wetting (slower electrolyte filling). A rate or fast-charge plating penalty is possible but not established | moderate for wetting [5]; low for rate. A 2D section width is a relative index, not an MIP throat size [2] |
| Pore width down together with porosity | Denser electrode (harder calendering): more energy per volume, but higher ionic resistance (less porosity, more tortuosity [8]) and, beyond light calendering, slower wetting. In [5] light calendering raised the wetting rate (0.375 → 0.589 mm/s^0.5) and heavier calendering lowered it to 0.206 | **trade-off**: energy density against rate and wetting | moderate |
| Pore d50 up, porosity unchanged | Fewer, wider pores. Filling can be faster, but no rate gain is expected at the same porosity [8], and wider is not better without limit: the uncalendered, most open film in [5] wetted more slowly than a lightly calendered one | **neither**: a sign the supplier's process changed (at most a small gain in wetting), provided d90 stays in the baseline range | low |
| Pore d90 up on its own (d50 unchanged) | A few coarse gaps: under-calendering, delamination between flake stacks, or cracks | **neither**: a sign the supplier's process changed; look at the flagged spots for cracks or delamination | low: no study links a 2D d90 to cell performance |
| Pore d90 down on its own | Fewer coarse gaps; the coarse end of the pore network narrows | **neither**: a sign the supplier's process changed | low |
| Solid thickness up (`solid_lt_d50_um`) | Thicker solid ligaments between pores: larger or agglomerated particles, less fragmented flake stacks or tighter packing. If it is larger particles: longer solid-state diffusion paths (general diffusion physics) and less surface, so less SEI [9]. Size alone does not fix the rate direction: reassembled fine graphite beat loose fine graphite on both first-cycle efficiency and 5C rate [6] | **neither**: a sign the supplier's powder or calendering changed. Only if confirmed as a particle-size change would it be a trade-off (slower solid diffusion and rate against less SEI) | low: 2D index, r = 0.06 with `particle_size_d50_um`; sensitive to gamma, blur and the frame edge (see pitfalls) |
| Solid thickness down | Finer, more divided skeleton: more surface exposed to electrolyte, so more SEI and a lower first-cycle efficiency [6, 9] | **neither**: a sign the supplier's process changed; if confirmed as finer particles, a trade-off (faster solid diffusion against more first-cycle loss) | low |

**Best value:** match the approved baseline (Batch_3: pore d50 0.78 ± 0.12 µm, pore d90 1.96 ± 0.52 µm, solid d50
4.62 ± 0.35 µm). An incoming lot has no "better" direction to aim for: a shift either way means the calendering or the
powder changed. Only narrower pores at the same porosity have a known performance cost, and that cost is slower
wetting.

**Our batches** (final integrated run, `analysis/rank_features.py` and `analysis/robustness.py`; SD = Batch_3 SD):
- **Pore width, both batches: no detectable change.** d50 / d90: Batch_1 0.806 / 1.96 µm, Batch_2 0.789 / 1.82 µm,
  against Batch_3 0.780 / 1.96 µm. Within sessions (the acquisition-controlled test) d50 is B1 −0.85 SD and B2
  −0.40 SD, exact p = 0.56, and d90 is B1 −0.53 SD and B2 −0.38 SD, p = 0.55. The same-session differences have both
  signs. Across all spots sep is 0.11 / 0.18 and q is 0.97 / 0.91. The test has little power, though. The pooled
  within-session shift on d50 is −0.48 SD, with a 95 % CI of −1.86 to +0.90 SD (−0.22 to +0.11 µm). So the
  within-session data alone cannot rule out a narrowing as large as the 1.5-SD verdict margin. B1's raw d50 mean is
  above B3 only because of the Si-rich session 2316 (4ih2ggld +2.6 SD). That is one session (n_eff = 1) with no B3
  spot in it. Without its two spots B1 reads 0.74 µm. **Verdict:** `pore_lt_d50_um` is a Tier-2 KPI. Both lots have
  7/7 spots inside the baseline range of 0.44–1.12 µm (pass), and the certificates give P(|δ| > margin) = 0.06 for B1
  and 0.02 for B2. `pore_lt_d90_um` is not used in the verdict.
- **Solid thickness, both batches: weak lead, not established.** Batch_1 4.88 µm and Batch_2 4.85 µm against Batch_3
  4.62 µm. Within sessions it is B1 +1.20 SD and B2 +1.52 SD, exact p = 0.068, and all four same-session differences
  against B3 are positive (+0.5 to +2.5 SD). Against that, sep is 0.44 (below the ≈ 0.65 acquisition bar), q is 0.26,
  and the perturbation ratio is 0.63 (gamma 1.25), above the 0.5 invariance gate. B1 has only one same-session pair
  with B3 (session 2080). The lead does not rest on 2316: those spots are in no mixed session, and without them B1
  still reads 4.79 µm. If real, it means a slightly coarser solid skeleton: **neither good nor bad, a sign the
  supplier's process changed.** **Verdict:** not used. It points the same way as the Tier-1 `solid_chord_y_um`, but
  the two are correlated (r = 0.62 over the 31 spots), so it does not independently confirm it.

## What it measures

Take the open-void mask from the BSE image (black = pore, after the shared harmonisation). For every pore pixel, find
the largest circle that fits entirely inside the pore space and still covers that pixel; its diameter is that pixel's
*local thickness* (Hildebrand & Rüegsegger [1]). The distribution of this diameter over the pore area is a continuous
pore-size distribution: no pore has to be cut out as an object, so touching or merged pores, which make object sizes
jump, do not matter [1, 2]. `pore_lt_d50_um` is its area-weighted median, `pore_lt_d90_um` its 90th percentile. The
same construction on the solid phase gives `solid_lt_d50_um`, the typical thickness of the particle/flake stacks
between pores.

Scale on this material (Batch_3): pores 0.78 µm (d50) and 2.0 µm (d90), i.e. 30–80 pixels across, well above the
25 nm pixel and the 50 nm segmentation blur. Solid 4.6 µm. The solid is not a particle size: touching flakes, the
carbon-binder web and Si particles are one connected solid, and the measure reports how far you can go into it
before meeting a pore.

## Why it matters for the battery

- **Pore width → wetting; ionic resistance only through bottlenecks.** The electrolyte has to fill the pore network
  before formation. Narrower pores let liquid through less easily, so filling takes longer. Sheng et al. tie the
  wetting rate to porosity, pore-size distribution and pore geometry. They also found the effect of calendering is
  not monotonic: light calendering raised the wetting rate and heavier calendering lowered it [5]. Ionic resistance is
  set mainly by porosity and tortuosity. In electrodes of platelet-shaped particles, the through-plane tortuosity
  exceeds the in-plane one because the platelets align [8]. Pore width adds to the resistance through constrictivity,
  i.e. narrow bottlenecks between wider pores [10]. In SiOx/graphite anodes, the arrangement of the pores changes
  Li-ion transport: alternating high- and low-porosity domains improved the 5C rate by 20 % [7]. So a drop in pore
  width at the same porosity means slower wetting, plus a possible but unproven rate and fast-charge plating penalty.
  A rise in d90 means coarse gaps (under-calendering, delamination between flake stacks, cracks).
- **Solid thickness → packing and diffusion length.** Thicker solid ligaments mean larger or agglomerated particles,
  or less fragmented flake stacks (longer solid-state diffusion paths, fewer pore access points). The graphite
  particle-size distribution controls the pore characteristics and, with them, initial Coulombic efficiency and rate
  [6]. First-cycle loss rises with the exposed surface [9].
- Direction of harm: only narrower pores at the same porosity carry a known cost (slower wetting). Any other shift
  against the baseline means the calendering, the graphite powder or the Si-phase dose or dispersion changed. Read it
  together with porosity (`porosity_open_frac`).

## Industry / Polaron use

- **Pore size**: electrode makers measure it by mercury intrusion porosimetry on punched electrodes. MIP reports
  *throat* (entry) sizes, which is a different geometric quantity: Münch & Holzer show that image-based continuous
  pore-size distributions and MIP contradict each other in a predictable way [2]. So this column is not a substitute
  for an MIP specification; it is a relative index measured on the cross-section.
- **Image-based local thickness / continuous PSD** is a standard output of microstructure tools: PoreSpy [3]
  (open source), and in commercial packages (GeoDict, Avizo) and NREL's MATBOX (research report §2). A fast
  approximate variant exists [4]; we compute the exact Euclidean opening.
- **Polaron**: their platform pitches drift detection and batch-to-batch comparability of microstructure metrics
  (Quality & Qualification page, research report §2). We found no public statement that names local thickness
  specifically.
- **Particle size**: laser-diffraction D10/D50/D90 of the powder is the first CoA item (GB/T 24533, research report §2).
  `solid_lt_d50_um` is not that number (see above): use it only as a relative "coarseness of the solid skeleton".

## How it is computed

- **Input**: `features._common.harmonise.harmonised(sample).void` (BSE: same 1336-row central crop for every spot,
  black/graphite anchors, noise topped up to one level, Otsu void threshold 0.62–0.71 graphite units, pore specks
  < 16 px dropped and solid pin-holes < 16 px filled). Solid = `~void`.
- **Opening granulometry by Euclidean discs** (`OpeningCurve`). `dist = scipy.ndimage.distance_transform_edt(mask)`.
  For an integer radius R, the disc centres are the pixels with `dist > R` (a disc of radius R fits there), and the
  opened set is every pixel within R of a centre (`distance_transform_edt(~centres) <= R`). That set is exactly the
  union of all discs of radius R that fit in the phase. F(R) = opened area / phase area falls from 1 (R = 0) to 0.
- **Quantiles** (`thickness_quantile_um`): d50 is where F = 0.5, d90 where F = 0.1 (10 % of the area is at least that
  thick). F is monotone, so a bisection over integer radii finds the bracket F(R) ≥ q > F(R+1) with about 6
  evaluations per quantile; R is then interpolated linearly inside the bracket, and diameter = (2R + 1) × 25 nm.
- **Exact speed-ups**: a disc that fits in one pore cannot reach another pore, so each 8-connected pore is opened in
  its own crop, shrunk to its disc centres ± R. Checked against a brute-force granulometry over all 62 radii on
  cfe5vt7s: identical d50 and d90 (0.7921 / 1.8839 µm), 1 s instead of 29 s. Synthetic checks: a 10 px stripe gives
  exactly 10 px; a disc of radius 20 px gives 42 px (the linear interpolation between integer radii adds up to 1 px
  for a single-size object; real distributions are smooth).
- **Solid on a 2× mask** (`solid_downsample: 2` in `config.yaml`): a 2×2 block is solid only if all four pixels are,
  so 1-px pore gaps survive. Against full resolution on all 31 spots: |change| ≤ 0.030 µm (0.09 B3-SD), r = 0.999,
  1.1 s instead of 5.3 s per spot.
- No extra size filter: the shared cleanup already removed specks, and area weighting gives small specks little
  weight. The image edge is treated as "unknown" (scipy's default): the phase is assumed to continue beyond the frame.
- Runtime (own code, shared machine, harmonisation excluded): `pore_lt` 1.3 s mean (max 2.3 s), `solid_lt_d50_um`
  0.9 s.

## Evidence on our data

### Final pipeline numbers

From the integrated run: `analysis/rank_features.py` (`processed/rankings.csv`: sep, q) and `analysis/robustness.py`
(`processed/robustness.csv`: within-session test, session R², perturbations). The rank_features permutation mixes
all spots and does not control for session; the within-session p is the acquisition-controlled test (exact over 192
batch relabellings inside the five mixed sessions, smallest attainable ≈ 0.005).

| Column | B1 / B2 / B3 mean (µm) | sep | q | Within-session p (B1 / B2 effect, SD) | Session R² (chance ≈ 0.40) | Perturbation ratio (worst) |
|---|---|---|---|---|---|---|
| `pore_lt_d50_um` | 0.806 / 0.789 / 0.780 | 0.11 | 0.97 | 0.56 (−0.85 / −0.40) | 0.54 | 0.27 (gamma 1.25) |
| `pore_lt_d90_um` | 1.960 / 1.820 / 1.957 | 0.18 | 0.91 | 0.55 (−0.53 / −0.38) | 0.46 | 0.21 (gamma 0.8) |
| `solid_lt_d50_um` | 4.884 / 4.848 / 4.624 | 0.44 | 0.26 | **0.068 (+1.20 / +1.52)** | 0.50 | **0.63** (gamma 1.25) |

All three get the verdict "no difference" in `rank_features.py`. Worst leave-one-out sep: 0.06 / 0.11 / 0.40. Leak
rho: 0.51 with the black level for pore d50 (below 0.6; a black-level shift itself moves the column by exactly 0, so
this is session coupling, not a black-level response), 0.40 for d90, 0.41 with image height for solid. ICC
0.17 / 0.07 / 0.45 and %GRR upper bound 42 % / 26 % / 67 %. These final numbers match the validation run below to
the digits shown; the only additions are sep, q and the leak/MSA figures.

### Validation run

All 31 spots, computed with the feature functions themselves (builder's validation run 2026-10-03, before
integration; sep/q are in the table above). B3-SD = SD of the 17 Batch_3 spots. Session = image height (13 groups;
chance R² ≈ 0.40). Within-session test: OLS y ~ C(session) + C(batch), exact permutation over the 192 distinct batch
relabellings inside the five mixed sessions; "incoming vs B3" pools B1 + B2 (24 arrangements, smallest attainable p =
0.042).

| | `pore_lt_d50_um` | `pore_lt_d90_um` | `solid_lt_d50_um` |
|---|---|---|---|
| Batch_1 (7) | 0.806 ± 0.16 | 1.96 ± 0.44 | 4.88 ± 0.21 |
| Batch_2 (7) | 0.789 ± 0.095 | 1.82 ± 0.23 | 4.85 ± 0.31 |
| Batch_3 (17) | 0.780 ± 0.12 | 1.96 ± 0.52 | 4.62 ± 0.35 |
| η²(batch), ANOVA p | 0.008, 0.90 | 0.018, 0.78 | 0.138, 0.13 |
| Session R² (permutation p) | 0.54 (0.13) | 0.46 (0.30) | 0.50 (0.23) |
| Within-session coef. B1 / B2 (B3-SD), exact p | −0.85 / −0.40, p 0.56 | −0.53 / −0.38, p 0.55 | **+1.20 / +1.52, p 0.068** |
| Incoming vs B3 (B3-SD), exact p | −0.48, p 0.42 | −0.41, p 0.42 | **+1.47, p 0.083** (2/24) |
| Raw contrasts (B3-SD): 2068 B2−B3; 2080 B1−B3, B2−B3; 2272 B2−B3 | −1.00; −0.47, +1.11; −0.76 | −0.54; +0.18, +0.73; −1.36 | **+2.49; +1.43, +0.68; +0.49** |
| Raw contrasts: 2080 B1−B2; 2148 B1−B2; 2156 B1−B2 | −1.58; −1.37; +0.96 | −0.54; −0.62; +0.09 | +0.75; −1.21; −0.30 |
| Perturbation ratio, max over 4 B3 spots: black+25 / γ0.8 / γ1.25 / contrast / noise / blur | 0 / 0.19 / 0.27 / 0.04 / 0.04 / 0.15 | 0 / 0.21 / 0.18 / 0.03 / 0.03 / 0.05 | 0 / 0.27 / **0.63** / 0.13 / 0.10 / 0.43 |
| Split-half r (left vs right half), mean \|L−R\| | 0.47, 0.93 B3-SD | 0.64, 0.65 B3-SD | 0.42, 1.02 B3-SD |
| Correlation with porosity (all / B3) | 0.60 / 0.78 | 0.64 / 0.80 | −0.45 / −0.38 |

Reading:
- **Pore width is the robust monitoring KPI (now Tier 2 in the verdict) and shows no detectable batch
  difference.** Session R² is close to chance (0.54 / 0.46 against 0.40; permutation p 0.13 / 0.30). A black-level
  shift gives exactly 0 and a contrast change ≤ 0.04; every perturbation stays ≤ 0.27 B3-SD (the target is < 0.3–0.5), and no batch contrast has
  a consistent sign. The final run agrees: sep 0.11 / 0.18, q 0.97 / 0.91. The replaced `pore_size_median_um2` /
  `_p90_um2` had session R² 0.92 / 0.87 and a 1 px blur moved them 3.0 / 1.0 B3-SD (screen `pore_morphology.json`):
  they mostly counted noise specks. Within sessions the incoming-vs-B3 shift is −0.48 B3-SD with a 95 % CI of [−1.86,
  +0.90] B3-SD (OLS, df 17), i.e. −0.06 µm [−0.22, +0.11] µm on d50: a pore-width change larger than that is
  unlikely, a smaller one cannot be excluded with 7 cross-batch pairs.
- **Solid thickness is a weak lead.** Incoming batches are thicker in all four contrasts that contain B3
  (+0.5 to +2.5 B3-SD, ≈ +0.17 to +0.88 µm); the pooled within-session effect is +1.47 B3-SD (+0.52 µm, parametric
  95 % CI [+0.12, +0.91] µm, df 17) with exact permutation p = 0.083, the second-smallest p the design allows. The
  B1–B2 pairs disagree. It tells the same "coarser skeleton" story as the lower interface density and pore count
  (`minkowski_functionals`), and is correlated with them (r = −0.70 with `interface_density_per_um`), so these are
  not independent confirmations. The screen found the same direction on a different recipe (fixed 0.5 threshold:
  +1.14 B3-SD, p = 0.083). About 30 morphology variants were tried in the screen, so treat it as a hypothesis to
  confirm with more sites per session. The final run does not strengthen it: across all spots sep 0.44 and q 0.26
  (no difference), and the gamma perturbation (0.63 B3-SD) exceeds the verdict's 0.5 invariance gate, so the column
  cannot carry a decision even if the within-session lead held.
- Absolute values agree with the screen within the recipe difference: B3 pore d50 0.78 µm here vs 0.72 µm with the
  screen's lower void threshold (thinner pores), solid d50 4.6 vs 5.5 µm.
- Notable spots: Batch_1/4ih2ggld (Si-rich session 2316) has the widest pores (d50 +2.6 B3-SD); B3 has a heavy d90
  tail (hzumfsms 3.27 µm, 0grcilhi 3.04 µm), so use a robust z for d90. The four spots of the lifted session 2060
  read d50 −0.3 to −1.25 B3-SD (mean −0.8) and d90 −0.7 to −1.0 (mean −0.9), together with porosity (−0.3 to −1.2,
  mean −0.9): physics or acquisition cannot be told apart there. Against the other 13 B3 spots in their own SD
  (`robustness.py` lifted_z) the session reads −1.10 (d50), −1.13 (d90) and −0.39 (solid).

## Uncertainty and pitfalls

- **Sampling**: split halves of one image differ by 0.65–1.0 B3-SD on average, so one full image carries roughly
  0.4–0.6 B3-SD of sampling error (about 17–41 % of the B3 between-spot variance, rough estimate assuming independent
  halves). Site-to-site and session variation come on top; average several images per lot.
- **Gamma / detector non-linearity** is the main acquisition risk for the solid (0.63 B3-SD at γ = 1.25, above the
  0.5 invariance gate): any threshold between two anchors moves with gamma. Linear changes are largely absorbed by the
  shared harmonisation (offset exactly 0; contrast ≤ 0.13 and added noise ≤ 0.10 B3-SD on the solid). Pore width is
  barely affected (≤ 0.27).
- **Blur / focus**: a 1 px blur moves the solid 0.43 B3-SD (thin gaps close and ligaments merge); pores only 0.15.
- **Segmentation recipe**: absolute widths depend on the void threshold (0.72 vs 0.78 µm for the screen's fixed 0.5
  vs our Otsu threshold). Compare spots only under the frozen `features/_common` recipe.
- **Pore-back**: pores that show the material behind them read as solid, so partially filled pores look narrower;
  sub-resolution pores in the carbon-binder web are invisible (< ~0.1 µm). Absolute pore widths are lower bounds.
- **Frame edge**: the solid ligaments are 4–5 µm on a 33 µm tall crop. If the frame edge is treated as a pore
  boundary instead of "unknown", `solid_lt_d50_um` drops by 0.19–0.63 µm (4–12 %; r = 0.95 with the default). Every
  spot uses the same crop size, so comparisons are fair, but the absolute solid value carries this ±10 % frame bias.
- **2D vs 3D**: local thickness of a section is not the 3D local thickness. Randomly cut 3D bodies show smaller
  sections (the Wicksell problem); flat inter-flake slits cut at right angles show their true width. Read the
  columns as relative indices, never as 3D pore diameters, and never as MIP throat sizes [2].
- **Session coupling**: pore d50 correlates with the image's bright-phase mode (Spearman −0.61), driven by the
  Si-rich 2316 session; native BSE noise correlates −0.28 to −0.33. Within-session comparisons are the honest test.

## References

1. Hildebrand T., Rüegsegger P. (1997) A new method for the model-independent assessment of thickness in
   three-dimensional images. *J. Microsc.* 185:67. https://doi.org/10.1046/j.1365-2818.1997.1340694.x
2. Münch B., Holzer L. (2008) Contradicting geometrical concepts in pore size analysis attained with electron
   microscopy and mercury intrusion. *J. Am. Ceram. Soc.* 91:4059. https://doi.org/10.1111/j.1551-2916.2008.02736.x
3. Gostick J. et al. (2019) PoreSpy: a Python toolkit for quantitative analysis of porous media images. *JOSS*.
   https://doi.org/10.21105/joss.01296
4. Dahl V. A., Dahl A. B. (2023) Fast local thickness. *CVPR Workshops*. https://doi.org/10.1109/cvprw59228.2023.00456
5. Sheng Y. et al. (2014) Effect of calendering on electrode wettability in lithium-ion batteries. *Front. Energy Res.*
   2:56. https://doi.org/10.3389/fenrg.2014.00056
6. Choi et al. (2023) Optimization of pore characteristics of graphite-based anode for Li-ion batteries by control of
   the particle size distribution. *Materials*. https://doi.org/10.3390/ma16216896
7. Lim et al. (2025) Regularly arranged micropore architecture enables efficient lithium-ion transport in
   SiOx/artificial graphite composite electrode. *Nano-Micro Lett.* https://doi.org/10.1007/s40820-025-01929-4
8. Ebner M. et al. (2014; online 2013 per Crossref) Tortuosity anisotropy in lithium-ion battery electrodes.
   *Adv. Energy Mater.* 4:1301278. https://doi.org/10.1002/aenm.201301278
9. Winter M., Novák P., Monnier A. (1998) Graphites for lithium-ion cells: the correlation of the first-cycle charge
   loss with the Brunauer-Emmett-Teller surface area. *J. Electrochem. Soc.* 145:428.
   https://doi.org/10.1149/1.1838281
10. Holzer L., Wiedenmann D., Münch B., Keller L., Prestat M., Gasser Ph., Robertson I., Grobéty B. (2013; online
    2012 per Crossref) The influence of constrictivity on the effective transport properties of porous layers in
    electrolysis and fuel cells. *J. Mater. Sci.* 48:2934. https://doi.org/10.1007/s10853-012-6968-z

All DOIs, titles, authors and years were checked against Crossref on 2026-10-03 (OpenAlex was rate-limited); refs 6
and 7 come from `literature.load_papers`; volume/page numbers for refs 1, 2, 5 and 8 are copied from
`notes/research_report.md` §10. Industry statements without a reference (MIP practice, vendor software, GB/T 24533)
are taken from `notes/research_report.md` §2 and are not independently verified here. Ref 9 (title, authors, year,
volume, pages) was checked against Crossref on 2026-10-03; the same DOI is in the ledger entries
`carbon_domains.yaml` and `minkowski_functionals.yaml`. Ref 10 (title, authors, year, volume, pages) was found and
checked on Crossref on 2026-10-03. Crossref holds no abstract for it, so it is cited only for what its title states:
constrictivity, i.e. bottlenecks, changes effective transport. The wetting statements from ref 5 (light calendering
raised the wetting rate from 0.375 to 0.589 mm/s^0.5, heavier calendering lowered it to 0.206) and from ref 7 (+20 %
rate at 5C) are taken from their OpenAlex and `literature` abstracts.
