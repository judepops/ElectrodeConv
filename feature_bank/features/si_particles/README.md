# si_particles

Size, shape, alignment, clustering and pore contact of the Si-based bright particles (most likely SiOx) in the
BSE cross-section. Adds seven columns to `processed/features.csv`, all from the shared harmonised bright mask
(`features/_common`); `bright_quadrat_cv` is computed in `feature.py` only.

| Column | Unit | Meaning |
|---|---|---|
| `bright_d50_um` | µm | Area-weighted median equivalent-circle diameter (ECD) of the bright particles, edge-corrected (2D section size) |
| `bright_d90_um` | µm | Area-weighted 90th-percentile ECD: the coarse tail |
| `bright_solidity_aw` | 0–1 | Area-weighted median of particle area / convex-hull area. ≈ 0.9 = compact angular shard; low = ragged, porous or clustered |
| `bright_aspect_aw` | ratio ≥ 1 | Area-weighted median second-moment aspect ratio (1 = round) |
| `bright_orient_order` | −1…+1 | Nematic order ⟨cos 2θ⟩ of particle long axes against the image horizontal: +1 all flat-lying, 0 random, −1 all upright |
| `bright_agglom_d50_um` | µm | Area-weighted median ECD of agglomerates: particles whose outlines are < 1 µm apart count as one |
| `bright_contact_pore_frac` | fraction | Share of the particle outline with a void pixel within 6 px (150 nm) |
| `bright_quadrat_cv` | ratio | Coefficient of variation of the bright area fraction over 10 × 10 µm quadrats (patchiness). **Not a features.csv column** (team audit 2026-10-03): it equals the random-placement null (obs/null 1.01 ± 0.09 in Batch_3), and a grid shift moves it ≈ 1 SD |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `bright_d90_um` / `bright_d50_um` up | Coarser Si particles: higher lithiation stress, so more risk of cracking and loss of electrical contact over cycling; less surface, so less SEI and a slightly higher first-cycle efficiency (ICE). A higher d90 at the same d50 also widens the size distribution, and a narrow PSD cycled best in a micro-sized SiOx/C [3] | trade-off, leaning bad for cycle life: more fracture risk against a small ICE gain | low to moderate [1–4] (size–fracture is established for crystalline Si [2] and only qualitative for micron SiOx; [3] found an optimum at ≈ 22.7 µm, not "smaller is always better") |
| `bright_d90_um` / `bright_d50_um` down | Finer Si product: less cracking, but more surface, more SEI, lower first-cycle efficiency | trade-off: better cycle life, lower ICE | moderate [1, 3, 4] |
| `bright_solidity_aw` down | Ragged, porous or clustered Si objects instead of compact shards. Two readings have opposite signs. Dense micrometric Si aggregates lithiate shell-first; their cores disconnect and their shells pulverise, so they fade fast [5]. Internal mesoporosity instead absorbs the lithiation stress and cycled stably in [5]; porous Si–C composites are built for that (`si_grade`) | neither from BSE alone: a sign the Si product changed. Bad only if EDS or finer imaging shows dense aggregates | low ([5] is nano-Si in graphite, an analogy for micron SiOx) |
| `bright_solidity_aw` up | Even more compact, convex particles; the baseline (0.90) is already near the ceiling of 1 | neither: a sign the supplier's process changed (milling product) | low (no known performance direction) |
| `bright_aspect_aw` up or down | Flakier (up) or rounder (down) shards: a different milling or classification product | neither: a sign the supplier's process changed | low (no verified link to performance) |
| `bright_orient_order` up or down | Shards lie flatter (up) or more upright (down) in the coating, so swelling may map differently onto electrode thickness | neither: a sign the supplier's process changed (Si shape, mixing or calendering; see below) | low (hypothesis; SiOx/graphite swelling itself is real [8, 9]) |
| `bright_agglom_d50_um` up | Si particles packed closer than 1 µm into larger groups: a local excess of Si, so plausible local swelling and cracking hot-spots. It also rises mechanically with the Si fraction (r = 0.46 with `bright_solid_frac` without 2316) | bad if a higher Si fraction does not explain it (inference) | low ([5] is about fused aggregates of nano-Si; swelling scales with Si content [8, 9], but [8] found no clear link from thickness change to the capacity-loss rate) |
| `bright_agglom_d50_um` down | Better-dispersed Si (floor: it cannot fall below the particle d50) | good (same inference) | low |
| `bright_contact_pore_frac` up | More of the Si outline faces pore instead of carbon/binder: weaker electronic wiring, and a risk of isolating Si as it swells and shrinks [6, 10]. The pore next to the Si is also free volume to swell into | trade-off, leaning bad: wiring loss against local room to swell (the upside is not verified) | low (inference from [6, 7, 10]; session-dominated, so read only against a same-session reference) |
| `bright_contact_pore_frac` down | Si better embedded in the carbon/binder web | good, probably (same inference) | low (same) |
| `bright_quadrat_cv` up (not a features.csv column, team audit 2026-10-03: equals the random-placement null; a grid shift moves it ≈ 1 SD) | Mostly mechanical: the CV of a sparse phase rises when the Si fraction falls (r = −0.49 with `bright_solid_frac` without 2316) or the particles coarsen. It means uneven mixing (local capacity and swelling hot-spots) only if the fraction-corrected `bright_excess_het_ratio` (`features/heterogeneity`) rises too | neither by itself; bad only together with a higher excess-heterogeneity ratio | low (hypothesis, no verified citation) |
| `bright_quadrat_cv` down (not a features.csv column, as above) | Mostly more Si or finer particles (the 2316 spots read low for this reason) | neither by itself (read with `bright_solid_frac`) | low (hypothesis) |

**Best value:** match the approved baseline. Batch_3 site mean ± SD (final `features.csv`): d50 4.07 ± 0.76 µm,
d90 6.72 ± 0.93 µm, solidity 0.896 ± 0.016, aspect 1.64 ± 0.14, orientation 0.13 ± 0.10, agglomerate d50
4.56 ± 0.65 µm, pore contact 0.066 ± 0.016, quadrat CV 1.27 ± 0.23. Directions with an inferred risk:
d90 ↑ (cycle life, traded against ICE), agglomerate d50 ↑ beyond what the Si fraction explains, and pore contact ↑
(same-session reference only). Finer sizes trade cycle life for ICE. Solidity ↓ is harmful only if it means dense
aggregates rather than internal porosity. Aspect, orientation and the quadrat CV on its own have no known best
direction, so a shift there only says that the Si powder or the mixing changed.

**Our batches** (final integrated run; sep and q from `rank_features.py`, which does not control for session;
within-session exact p and effect in B3-SD from `robustness.py`, five mixed sessions; B1 meets B3 directly only in
session 2080, B2 meets B3 in 2068, 2080 and 2272):
- **Batch_1: a Si-phase anomaly in 2 of 7 spots, all from session 2316 (n_eff = 1 session). It cannot be tested
  within sessions, and its battery direction is unknown until EDS.**
  - Site means: solidity 0.798 vs 0.896 (sep 0.71, q 0.072), agglomerate d50 6.27 vs 4.56 µm (sep 0.62, q 0.15),
    pore contact 0.078 vs 0.066 (sep 0.61, q 0.17), d90 7.10 vs 6.72 µm (sep 0.42, q 0.48). All of it comes from
    the two 2316 spots: solidity −29 / −12, agglomerate +9 / +10, pore contact +4.7 / +5.3 and d90 +5.4 / +3.4
    B3-SD. Without them B1 sits at or below B3 (solidity 0.887, agglomerate 4.43 µm, d90 5.62 µm, contact 0.052).
  - Why it is not established: 2316 holds only B1, so the within-session test cannot see it. Its p (solidity
    0.33, agglomerate 0.20) only tests the three B1 spots in the mixed sessions 2080, 2148 and 2156. 2316 is
    also the only curtained session (`acq_curtain_index` 1.68 / 1.64 vs B3 1.05 ± 0.07; G-C under
    `preprocessing/acquisition.py` `gate_status`). A batch change, a session artefact and a local patch cannot be told
    apart.
  - What it probably is: the bright mask there holds a different, granular, intermediate-grey population
    (`si_grade`, whose best fit is a porous or agglomerated Si–C composite), at 2.5–3× the baseline Si fraction.
    The higher density alone inflates the agglomerate size, and the fraction-corrected clustering ratio is
    normal there (`features/heterogeneity`, z −0.8 / −0.7). Pore contact cannot be compared across sessions.
  - Battery reading: neither from BSE alone, a sign that the Si product changed. It is bad if EDS shows dense
    aggregates [5] and possibly benign if it is an engineered porous composite.
  - Within shared sessions B1 reads *finer*: d50 −2.0 SD and d90 −1.8 SD (omnibus within-session p 0.021 and
    0.026, carried by B1). B1 meets B3 directly in only one spot pair (2080), split-half r ≈ 0, and the
    direction was found post hoc among 8 columns, so this is thin. If real, it is the ICE-for-cycle-life
    trade-off.
  - **Verdict:** Tier 2 `bright_agglom_d50_um` fails (5/7 inside, with the two 2316 spots outside;
    P(|δ| > margin) 0.75). That feeds the INVESTIGATE "Si-phase anomaly" reason: EDS, the supplier CoA, and
    re-imaging beside a retained reference. `bright_d90_um` is now a diagnostic (it left Tier 2 because its
    left/right split-half reliability r_x is −0.13, bar 0.35); it reads +0.41 SD (screen q 0.81). The other five
    columns are not in the verdict.
- **Batch_2: no change is established within sessions; there is a thin hint of a shape/alignment change, neither
  good nor bad.**
  - Agglomerate 4.60 vs 4.56 µm passes Tier 2 (7/7). d90 5.91 vs 6.72 µm (−0.87 SD; within sessions −0.66 SD,
    one-sided p 0.17) is a diagnostic (screen q 0.50). Solidity 0.896 = 0.896.
  - Orientation 0.276 vs 0.132: B2 > B3 in all three shared sessions (+1.7 SD within), but the within-session
    p is 0.17 (one-sided 0.094 for a direction picked on these data); sep 0.62, q 0.088. This is a hint that the
    shards lie flatter, not a finding.
  - Area-weighted aspect 1.87 vs 1.64: +1.6 SD within sessions (omnibus p 0.036; B1 is also +1.6); sep 0.69,
    q 0.077. But the number-weighted aspect shows nothing (p 0.98) and split-half r is −0.16, so a few large
    particles carry it.
  - Reading of both: neither good nor bad, a sign that the supplier's Si milling or mixing may have changed.
  - Quadrat CV 1.48 vs 1.27 has the folder's highest sep (0.88, q 0.071). It is not established within sessions
    (+0.87 SD, p 0.25), and it goes with B2's lower Si fraction (`bright_solid_frac` 0.055 vs 0.066), which raises
    the CV mechanically. The fraction-corrected clustering ratio reads B2 *more even* than B3 (`features/heterogeneity`:
    −1.19 SD within, p 0.031), and the verdict's diagnostic `bright_tile_cv` reads +0.36 SD (screen q 0.93). This is
    not a patchiness defect.
  - Pore contact 0.048 vs 0.066 (−1.0 SD within, p 0.073; B1 the same) is the benign direction but
    session-dominated (session R² 0.93).
  - **Verdict:** none of these is used, so they do not move B2 off "most likely equivalent".

**How to use the columns (details below).**
- Only `bright_agglom_d50_um` can move the batch verdict (Tier 2 quality range in `analysis/verdict_config.yaml` v1.1). `bright_d90_um` is a diagnostic: shown, never decisive (split-half reliability r_x −0.13, below the 0.35 bar). The verdict does not read the other five (README-level descriptors only).
- Caveat on `bright_agglom_d50_um`: its between-batch signal and its reliability come almost entirely from the two session-2316 spots (η² without them ≈ 0); the panel stays frozen at v1.1 because the test set has been released, so any re-tiering is only a proposal for after the blind test is scored.
- No column is a site-level decision KPI. With 30–80 measurable particles per spot, most site-to-site spread is counting noise. Compare batches on particles pooled per batch, with site-bootstrap CIs.
- `bright_orient_order` is the one thin new-batch lead (a hint that B2 lies flatter than B3; within-session p 0.17). `bright_aspect_aw` points the same way but rests on a few large particles. Neither has a known performance direction.
- Solidity, agglomerate size and pore contact flag the session-2316 anomaly at 5–29 B3-SDs. They flag that the Si product differs; they do not say in which direction performance moves.
- Pore contact is session-dominated: read it only against a same-session reference.
- Clark–Evans and Ripley clustering indices are a negative result and were not built.

## What it measures

The bright BSE phase is the Si-based additive. It appears as angular, faceted 2–10 µm shards covering ≈ 6 % of the area. Each 8-connected object of the harmonised bright mask counts as one particle; the mask's minimum object size is 0.1 µm². Over the common 1336 × ~6980 px crop (≈ 5800 µm², 33 µm high), these columns describe:

- **Size:** how large the particles are (area-weighted ECD d50 and d90, so the quantiles describe where most of the Si *volume* sits, not the count of fines).
- **Shape:** how compact (solidity) and elongated (aspect ratio) the particles ≥ 0.5 µm² are.
- **Alignment:** whether the long axes of the elongated particles (aspect ratio > 1.3) lie flat, i.e. parallel to the current collector, or stand upright.
- **Agglomeration:** how large the clusters are once neighbours closer than 1 µm are merged.
- **Pore contact:** what share of the particle outline faces open pore rather than carbon.
- **Patchiness:** how unevenly the bright phase is spread at the 10 µm scale.

All sizes are **2D section sizes**. A polishing plane cuts most particles away from their equator, so section ECDs come out smaller than the 3D diameter, and the section-size distribution is a mixture over cut positions (the Wicksell corpuscle problem [12]). They are relative indices for comparing batches imaged the same way, **not laser-diffraction D50 values**.

## Why it matters for the battery

- **Size (`d50`, `d90`).** Lithiation strain in a Si-based particle grows with size. Large particles crack, pulverise and lose electrical contact; small ones carry more surface, so more SEI and a lower first-cycle (initial Coulombic) efficiency [1, 2, 4]. For micron SiOx the size–fracture link is qualitative: the ≈ 150 nm critical size applies to crystalline Si [2]. Sieving a commercial micro-sized SiOx/C powder into three PSDs changed its cycling stability, and the narrow-PSD fraction at ≈ 22.7 µm cycled best [3]: at the micron scale there is an optimum, not a monotonic "smaller is better". So both directions are trade-offs. A coarser tail (`d90` ↑, which also widens the PSD) leans towards more fracture and contact loss. A finer product (`d50` ↓) means more SEI and lower ICE.
- **Shape (`solidity`, `aspect`).** Low solidity means ragged, porous or clustered bright objects rather than compact shards. In graphite/Si electrodes, micrometric Si agglomerates and the Si micro- and mesoporosity were the main physical properties affecting cycling, with opposite signs [5]. In micrometric aggregates the shell lithiates first, the core disconnects and the shell pulverises, giving rapid fade. Stress in mesoporous Si was "well managed", giving stable cycling. A 2D solidity drop cannot tell these apart, so it is a sign that the Si product changed, not a harmful direction by itself; EDS or finer imaging decides. [5] used nano-Si, so for micron SiOx it is an analogy. Aspect ratio mainly reports a different milling product (flakier shards).
- **Alignment (`orient_order`).** If the elongated shards lie flatter, their swelling may be split differently between in-plane and through-thickness directions, which could change electrode thickness growth. Neither the size nor the sign of this effect is known: it is a hypothesis with no verified citation. Electrode swelling with SiOx/graphite anodes is real and scales with the SiOx content [8, 9].
- **Agglomeration (`agglom_d50`).** An agglomerate is a local excess of Si. Electrode thickness change rises with Si content [8, 9], so agglomerates are plausible local swelling and cracking hot-spots; but [8] found no clear correlation between thickness change and the capacity-loss rate. Micrometric aggregates of nano-Si cycle worse than dispersed particles [5]; for micron shards that merely sit < 1 µm apart this is an inference. The column also rises mechanically with the Si fraction, so read it together with `bright_solid_frac` and the fraction-corrected `bright_excess_het_ratio` (`features/heterogeneity`). Harmful direction: ↑, if it is not explained by more Si.
- **Pore contact (`contact_pore_frac`).** Repeated volume change detaches Si from its conductive surroundings. Loss of electrical contact and of active Si is a main fade mode of graphite–Si electrodes [6, 10]. Conductive wiring is what enabled stable cycling of graphite–SiO blends [7]. Particle–binder detachment shows up statistically in imaging (cathode work, used here as an analogy) [11]. An outline that already faces pore rather than carbon after calendering starts with less electronic contact. That pore is also free volume for the Si to swell into, an upside with no verified citation. Leaning harmful direction: ↑ (a trade-off, inferred).
- **Patchiness (`quadrat_cv`).** Uneven Si loading means uneven local capacity and swelling, which points to the mixing or dispersion step. But a raw CV of a sparse phase rises mechanically when the Si fraction falls or the particles coarsen (r = −0.49 with `bright_solid_frac` without 2316). It reads as patchiness only when the fraction-corrected `bright_excess_het_ratio` (`features/heterogeneity`) rises with it. The link to cell failure is a hypothesis.

See also `notes/research_report.md` §3 rank 2 and §8.

## Industry / Polaron use

- **Particle size distribution.** D10/D50/D90 by laser diffraction (ISO 13320) is a certificate-of-analysis item for anode powders, including the Si–carbon standard GB/T 38823-2020 (research report §2). The image version is an in-electrode, after-mixing-and-calendering proxy. It can see what a powder certificate cannot: breakage, agglomeration and segregation in the coating. It cannot reproduce the powder D50 itself (Wicksell; touching particles).
- **Shape.** Solidity and aspect ratio are ISO 9276-6 descriptors. Supplier data sheets describe morphology only qualitatively.
- **Dispersion and agglomeration.** Imaging vendors segment four phases (Avizo, GeoDict, MATBOX). Polaron sells "spatial heterogeneity" and "batch-to-batch comparability" on its Quality & Qualification page. Representativity of a single image is the ImageRep idea [16].
- **Orientation of the Si phase, and Si–pore contact:** academic only.
- **What would move these columns:** a change in the Si powder's milling or classification (size, shape, aspect); in mixing intensity or order (agglomerates, CV, contact); or a different Si grade or composite (solidity; see `si_grade`).

## How it is computed

Detector: BSE only, through `features._common.harmonise.harmonised(sample)`:
- `h.bright` is the adaptive-midpoint Si-phase mask: open 1 px, fill holes < 0.25 µm², drop objects < 0.1 µm², core check.
- `h.void` is the Otsu pore mask on the noise-matched, graphite-anchored BSE.
- Both cover the same 1336-row crop for every spot. Nothing is re-segmented here.

1. **Particles.** 8-connected labelling of `h.bright`. ECD = 2·√(area/π) × 0.025 µm.
2. **Edge correction (Miles–Lantuéjoul [13, 14]).** A particle whose bounding box touches the crop edge gets weight 0. Every other particle gets weight H·W / ((H − h)(W − w)), the inverse probability that a particle of that box size lies wholly inside the window.
3. **Size.** `d50`/`d90` are weighted quantiles of ECD with weight = area × edge weight (mid-point cumulative weights, linear interpolation).
4. **Shape** (interior particles with area ≥ `shape_min_px` = 800 px = 0.5 µm²):
   - **Aspect ratio:** √(λ₁/λ₂) of the pixel second-moment matrix.
   - **cos 2θ:** (μ₂₀ − μ₀₂) / √(4μ₁₁² + (μ₂₀ − μ₀₂)²), with x = image columns.
   - **Solidity:** pixel area ÷ area of the `scipy.spatial.ConvexHull` of the outline pixels' corners. This lies in (0, 1]; a digitised ellipse of 2 × 1 µm reads 0.966.
   - Solidity and aspect are summarised as area × edge-weighted medians.
5. **Orientation.**
   - Only particles with aspect > `orient_min_aspect` (1.3) enter; a near-round particle has no defined long axis.
   - Order = Σ v·cos 2θ / Σ v, with vote v = edge weight (`orient_weighting: number`): each particle votes once.
   - **Deviation from the task wording (area-weighted).** Area weighting leaves ≈ 14 effective particles per spot. Its within-spot particle-bootstrap SE (0.165) exceeds the B3 between-spot SD (0.142), and its split-half r is −0.06. Number weighting has ≈ 45 effective particles, SE 0.106 and split-half r 0.34, and it is the recipe the screen flagged. Area weighting stays available as `orient_weighting: area`.
6. **Agglomerates.**
   - Grow the mask by `agglom_dilate_px` = 20 px (0.5 µm) using a Euclidean distance transform, relabel 8-connected, and assign each original bright pixel its group label. Particles closer than 1 µm edge-to-edge join one agglomerate.
   - Measure ECD on the **original** bright pixels of each group, then take the area-weighted d50.
   - **No edge correction** (`agglom_edge_correction: false`): an agglomerate network can be as large as the 33 µm window. With Miles weights, 87 % of 4ih2ggld's bright area sits in edge-touching groups. The corrected d50 then collapses to 2.1 µm, below the particle d50 and in the wrong direction. Edge-touching groups therefore count at their visible size, a lower bound.
7. **Pore contact.**
   - Outline = bright pixels with a non-bright 8-neighbour, crop-edge pixels excluded.
   - `contact_pore_frac` = share of outline pixels whose Euclidean distance to the nearest `h.void` pixel is ≤ `contact_radius_px` = 6 px (150 nm).
   - At 3 px the share is ≈ 0.001: the BSE edge spread puts the void threshold 4–5 px from the bright-mask edge (radius table below).
8. **Patchiness** (computed in `feature.py`, not a column). Centred grid of `quadrat_px` = 400 px (10 µm) quadrats (3 × 17 on the crop); CV = SD/mean of the per-quadrat bright fraction (population SD).
9. **NaN rules.** NaN when there are no particles, every particle touches the crop edge (size columns), no shape-set particles (shape columns), no elongated particles (orientation) or no bright pixels (CV).

Every number is in `config.yaml`. Runtime of this module, without the shared harmonisation: median 1.1–1.2 s per spot, max 1.5–2.7 s depending on machine load (the 600-particle 2316 spots are the slowest).

## Evidence on our data

**Final pipeline numbers** (integrated run: means from `processed/features.csv`; sep and q from
`analysis/rank_features.py`, `processed/rankings.csv`; the rest from `analysis/robustness.py`, `processed/robustness.csv`).

| Column | B1 / B2 / B3 mean | sep | q | within-session p | within-session effect B1 / B2 (B3-SD) | session R² | perturbation ratio |
|---|---|---|---|---|---|---|---|
| `bright_d50_um` | 4.35 / 3.99 / 4.07 | 0.22 | 0.83 | 0.021 | −1.97 / −0.36 | 0.49 | 0.08 |
| `bright_d90_um` | 7.10 / 5.91 / 6.72 | 0.42 | 0.48 | 0.026 | −1.80 / −0.66 | 0.79 | 0.03 |
| `bright_solidity_aw` | 0.798 / 0.896 / 0.896 | 0.71 | 0.072 | 0.33 | −1.49 / −0.81 | 0.83 | 0.46 |
| `bright_aspect_aw` | 1.73 / 1.87 / 1.64 | 0.69 | 0.077 | 0.036 | +1.61 / +1.64 | 0.46 | 0.21 |
| `bright_orient_order` | 0.213 / 0.276 / 0.132 | 0.62 | 0.088 | 0.17 | +0.39 / +1.73 | 0.41 | 0.40 |
| `bright_agglom_d50_um` | 6.27 / 4.60 / 4.56 | 0.62 | 0.15 | 0.20 | −1.68 / −0.43 | 0.91 | 0.26 |
| `bright_contact_pore_frac` | 0.078 / 0.048 / 0.066 | 0.61 | 0.17 | 0.073 | −1.18 / −1.03 | 0.93 | 0.52 |

- `rank_features.py` calls CV, solidity, aspect and orientation "separates" (q < 0.1) and the rest "no difference". It permutes across all spots, so it does not control for session. Solidity's separation is entirely the two 2316 spots (B2 = B3; within p 0.33), and the CV's comes from B2 being high plus 2316 being mechanically low (within p 0.25). Worst leave-one-out sep: CV 0.78, solidity 0.61, aspect 0.56, orientation 0.52, contact 0.50, agglomerate 0.41, d90 0.33, d50 0.05. The image-height / black-level / contrast leak is ≤ 0.38 for every column (bar 0.6).
- The within-session p is the omnibus for both batches (192 exact relabellings, minimum ≈ 0.005). For d50 and d90 it is carried by B1.
- Every perturbation ratio is ≤ 0.46 except pore contact, 0.52 (gamma 1.25 on 0grcilhi), just above the 0.5 invariance bar.
- Measurement system (B3 variance components): %GRR upper 32 % for d90 and solidity, 20 % for aspect, 87 % for pore contact (ICC 0.75, session-dominated), 0 % for the rest (session component estimated at 0).
- These numbers reproduce the builder's validation below to the printed precision, except the perturbation ratios (see the gamma 1.25 note).

**Data and tests** (builder's validation).
- All 31 spots, harmonised masks computed with the repo `_common` code; scratch scripts printed to stdout only.
- Session = image height (13 groups; chance R² ≈ 0.40).
- Within-session test: OLS y ~ C(session) + C(batch). The statistic is the RSS drop from adding batch, with exact permutation over the 192 distinct relabellings within the five mixed sessions (minimum p ≈ 0.005).
- Split-half: the left and right image halves, measured independently on the same masks.
- Perturbation ratio = max |Δ| / B3 between-spot SD over B3 spots 71vgq3fw, cfe5vt7s, hzumfsms and 0grcilhi. Perturbations were applied to the raw BSE, Inlens and SE: black +25, gamma 0.8 and 1.25, contrast ×0.85, noise σ 4, blur σ 1. The real feature functions were then called on a rebuilt `Sample`.

**Particle counts per spot.**
- All objects ≥ 0.1 µm²: 62–228 outside session 2316; 612 and 576 in 4ih2ggld and 5n1q8atc.
- Shape set (≥ 0.5 µm², interior): 33–79 particles; 148–153 in 2316.
- Orientation set (aspect > 1.3): 29–75 particles; 139–142 in 2316.

| Column | B1 mean ± sd | B2 | B3 | η²(batch) | session R² (no 2316) | within-session exact p | split-half r (no 2316) | perturbation ratio (final run) | noise-seed shift |
|---|---|---|---|---|---|---|---|---|---|
| `bright_d50_um` | 4.35 ± 1.22 | 3.99 ± 0.59 | 4.07 ± 0.76 | 0.03 | 0.49 (0.39) | 0.021 | −0.10 (−0.03) | 0.08 | 0.03 |
| `bright_d90_um` | 7.10 ± 2.70 | 5.91 ± 0.61 | 6.72 ± 0.93 | 0.08 | 0.79 (0.53) | 0.026 | 0.05 (−0.18) | 0.03 | 0.01 |
| `bright_solidity_aw` | 0.798 ± 0.169 | 0.896 ± 0.015 | 0.896 ± 0.016 | 0.23 | 0.83 (0.28) | 0.33 | 0.82 (−0.22) | 0.46 | 0.30 |
| `bright_aspect_aw` | 1.73 ± 0.17 | 1.87 ± 0.23 | 1.64 ± 0.14 | 0.25 | 0.46 (0.47) | 0.036 | −0.16 (−0.17) | 0.21 | 0.32 |
| `bright_orient_order` | 0.213 ± 0.108 | 0.276 ± 0.155 | 0.132 ± 0.102 | 0.23 | 0.41 (0.41) | 0.17 (one-sided B2 > B3: 0.094) | 0.34 (0.35) | 0.40 | 0.36 |
| `bright_agglom_d50_um` | 6.27 ± 3.18 | 4.60 ± 0.69 | 4.56 ± 0.65 | 0.18 | 0.91 (0.35) | 0.20 | 0.70 (−0.12) | 0.26 | 0.52 |
| `bright_contact_pore_frac` | 0.078 ± 0.046 | 0.048 ± 0.007 | 0.066 ± 0.016 | 0.16 | 0.93 (0.79) | 0.073 | 0.64 (0.24) | 0.52 | 0.19 |
| `bright_quadrat_cv` | 1.08 ± 0.26 | 1.48 ± 0.19 | 1.27 ± 0.23 | 0.28 | 0.60 (0.43) | 0.25 | 0.37 (0.23) | 0.20 | 0.01 |

Notes on the table:
- The perturbation ratios are from `robustness.py` on the integrated run (6 perturbations × 4 B3 spots, nothing excluded). The builder's scratch run gave 2.54 / 1.03 / 1.39 for solidity / aspect / CV and 0.37 / 0.27 / 0.57 for d50 / d90 / contact, all from the one gamma 1.25 / 0grcilhi case below.
- The noise-seed shift is the max |Δ| / sdB3 when the harmonisation's noise top-up is re-drawn with two other seeds (same 4 spots; builder's run).
- **The gamma 1.25 / 0grcilhi case was a `_common` effect, not this module's, and is fixed in the integrated run.**
  - In the builder's run, gamma 1.25 lifted 0grcilhi's bright mode from 2.155 to ≈ 2.6 g, outside the then `bright_mode_clamp: [1.6, 2.6]`.
  - The shared recipe then fell back to the default mode of 2.1: the threshold dropped to 1.55 instead of rising to ≈ 1.75 as at the other three spots. The bright fraction went from 0.051 to 0.070 and the particle count from 113 to 279.
  - The integrated `features/_common/config.yaml` widens the clamp to [1.5, 3.2]. On the final run, gamma 1.25 moves solidity by at most 0.46 sdB3 (on 71vgq3fw), aspect by 0.03 and CV by 0.20; the largest remaining gamma 1.25 shift in this folder is pore contact on 0grcilhi (0.52).

**Session 2316, the only large signal (B1 4ih2ggld, 5n1q8atc; n_eff = 1 session).** Its bright mask is dominated by the granular intermediate-grey population (`si_grade`).

| Column | 4ih2ggld | 5n1q8atc | In B3-SD units (z) |
|---|---|---|---|
| Solidity | 0.45 | 0.71 | −29 / −12 |
| Agglomerate d50 | 10.6 µm | 11.1 µm | +9 / +10 |
| Pore contact | 0.14 | 0.15 | +4.7 / +5.3 |
| d90 | 11.7 µm | 9.9 µm | +5.4 / +3.4 |
| Patchiness CV | 0.67 | 0.79 | −2.6 / −2.1 (mechanical: a 3× larger fraction lowers the CV of a sparse phase) |

Without these two sites, B1's site means are close to B3's or on the benign side (B3-SD in brackets):
- d50 3.91 ± 1.07 µm (−0.2);
- d90 5.62 ± 0.92 µm (−1.2, the "finer" reading below);
- solidity 0.887 ± 0.010 (−0.6);
- agglomerate d50 4.43 ± 0.63 µm (−0.2);
- contact 0.052 ± 0.012 (−0.9);
- CV 1.21 ± 0.13 (−0.2);
- orientation 0.233 (+1.0) and aspect 1.77 (+0.9) are the exceptions, between sessions only (see below).

This matches the screen (`siox_particles.json`, findings 2), with the same morphological pattern under the shared mask.

What the 2316 numbers can and cannot say:
- **Not testable within sessions.** 2316 holds only B1, so no acquisition-controlled test exists. It is also the only curtained session: `acq_curtain_index` 1.68 / 1.64 against B3 1.05 ± 0.07, and both spots are G-C under `preprocessing/acquisition.py` `gate_status`. Curtains bias orientation and the void mask, so the 2316 pore contact (+5 SD) is the least trustworthy of these numbers; pore contact is session-dominated anyway (session R² 0.79 even without 2316). Curtains are unlikely to create a 2.5–3× Si fraction or a granular texture (`si_grade`, `features/acquisition`).
- **Partly mechanical.** The Si fraction there is 0.16 / 0.20 against 0.066. Agglomerate d50 rises with the fraction (r = 0.46 without 2316): a linear extrapolation gives ≈ 6.7 / 7.7 µm at the 2316 fractions, against 10.6 / 11.1 µm observed, so part of the +9 / +10 SD comes from density alone. The fraction-corrected clustering ratio in `features/heterogeneity` is normal in both spots (z −0.8 / −0.7). The 2316 Si is denser, not more clustered than chance.
- **Battery reading.** The mask picks up a different material (most likely a porous or agglomerated Si–C composite, `si_grade`). Its low solidity is most likely the signature of that product, and curtaining may add to it. Read it as neither good nor bad (a sign that the Si product changed); it is harmful only if EDS shows dense aggregates [5].

Site means mix batch with session, though. Within shared sessions the picture changes:
- The B1 orientation excess is between-session only. In B1's one session shared with B3 (2080), B1 sits 1.3 sdB3 *below* B3, and the within-session B1 coefficient is +0.04 (+0.4 sdB3; one-sided p 0.40).
- B1 reads smaller instead: B1 coefficients for d50 −2.0, d90 −1.8, agglomerate d50 −1.7 and contact −1.2 sdB3 (one-sided p 0.021 / 0.010 / 0.031 / 0.042).
- These are post-hoc one-sided p values among 8 columns × 2 batches, and split-half r is ≈ 0 for the sizes (see Sizes).

**Orientation (`bright_orient_order`), the thin new-batch lead.**
- **Within shared sessions:** B2 > B3 in all three (2068 +1.5, 2080 +1.9, 2272 +3.1 sdB3). Exact omnibus p = 0.17; one-sided p for the pre-stated B2 > B3 direction from the screen = 0.094.
- **Pooled particles per batch** (site-bootstrap 90 % CI): B2 0.277 [0.19, 0.36] vs B3 0.141 [0.10, 0.18]; B1 without 2316 0.241 [0.15, 0.32] (between-session only; see above).
- A session-cluster bootstrap, which resamples sessions instead of sites, gives practically the same intervals for every pooled CI in this README: within 0.01 for orientation and within 0.08 µm for the sizes.
- **Reliability:** split-half r 0.34, session R² at chance (0.41). The within-spot particle-bootstrap SE (≈ 0.106) is about the B3 between-spot SD (0.102), so the site values are mostly counting noise and the batch means carry the signal.
- **Agreement with the screen:** these numbers reproduce its "promising" verdict (screen: B3 0.12, B1 0.22, B2 0.27; exact p 0.10). The screen's verifier found that the effect survives when restricted to solid particles and at a fixed aspect ratio, so it is not a side effect of shape.
- **Calendering not excluded:** graphite alignment shows no significant batch effect, but it cannot rule calendering out. B2's graphite order points the same way as the Si-orientation lead (B2 − B3 positive in all three shared sessions; `flake_orientation` README), and its 90 % CI reaches about +2 baseline SD. The candidates are Si shard morphology, how the Si is mixed in, or slightly stronger compaction.
- **Caveats:** the direction was found on these same data, with about 30 tests in the screen family, and there are only three B2-vs-B3 sessions.
- **Status:** a hypothesis for the new batch, not a finding. Its strongest correlation with another column here is r = 0.38, with `bright_aspect_aw`; with every other column |r| ≤ 0.17.

**Sizes.**
- d50 and d90 reach within-session p of 0.02–0.03 (B1 smaller in 2080, 2148 and 2156). But split-half r ≈ 0, so one spot cannot rank its own halves. That p-level is expected by chance among the 8 columns here and the many variants screened.
- Pooled d50 is the same across batches: B1 without 2316 3.78 [3.32, 4.94], B2 4.01 [3.67, 4.35], B3 4.00 [3.77, 4.46] µm. Pooled, nothing points to a Si powder-size change. The within-session B1 deficit (above) is the only hint, and with split-half r ≈ 0 it is as likely to be particle sampling.
- Pooled d90 hints that B3 has a slightly coarser tail: B3 6.86 [6.60, 7.15] vs B2 6.01 [5.60, 6.61] and B1 without 2316 5.98 [5.38, 6.55] µm. The screen also saw this (6.7 vs 6.0–6.2). These are pooled values, so session is not controlled: within sessions B2 is only −0.66 SD (one-sided p 0.17). It is thin and should be re-tested on the new batch.

**Aspect ratio.**
- **The batch signal:** within-session p = 0.036. B2 > B3 in all three shared sessions (+1.6, +1.6, +1.8 sdB3). Pooled, B2 is 1.82 [1.74, 1.97] vs B3 1.60 [1.53, 1.71].
- **Why it is still not a KPI:** the signal comes from a few large particles that dominate the area weighting. Split-half r is −0.16, and the number-weighted median aspect ratio shows no batch difference (site means 2.04 / 2.04 / 1.91 for B1 / B2 / B3; within-session p 0.98). The screen's verifier judged it "unreliable".
- **Use:** descriptive only, as support for the orientation lead (r = 0.38 with `bright_orient_order`), not as an independent piece of evidence.

**Pore contact, radius trade-off** (B3 mean; session R² without 2316; perturbation ratio; within-session p):

| Radius | 4 px | 5 px | **6 px** | 8 px | 10 px | 12 px |
|---|---|---|---|---|---|---|
| B3 mean | 0.009 | 0.038 | **0.066** | 0.131 | 0.207 | 0.268 |
| Session R² (no 2316) | 0.67 | 0.72 | **0.79** | 0.86 | 0.88 | 0.89 |
| Perturbation ratio | 1.84 | 1.06 | **0.52** | 0.39 | 0.38 | 0.39 |
| Within-session p | 0.65 | 0.17 | **0.073** | 0.042 | 0.042 | 0.12 |

Notes on pore contact:
- The 6 px column is the final integrated run (`robustness.py`; the builder's run gave a perturbation ratio of 0.56); the other radii are from the builder's scratch run, with the old bright-mode clamp.
- Below 6 px the share is set by the edge spread. Above 6 px it is increasingly a "pore nearby" measure, more session-driven and no more robust. 6 px stays the pre-registered setting.
- B1 and B2 sit 1.0–1.2 sdB3 below B3 within sessions (p = 0.073).
- Contact correlates only weakly with the spot's void fraction: r = 0.27 without 2316, −0.08 with it.
- Adjusting for the void fraction moves the within-session p to 0.04–0.28 depending on the method (covariate in the OLS 0.11; residual of a fit without 2316 0.28). So porosity neither explains the contrast away nor firms it up.
- Session R² of 0.79 without 2316 means it can be read only against a reference imaged in the same session.

**Patchiness.**
- B2 reads higher than B3 within shared sessions (+0.3 to +1.2 sdB3), but p = 0.25 and split-half r = 0.37.
- The CV is mechanically anti-correlated with the bright fraction (r = −0.49 with `bright_solid_frac` without 2316). B2 has less Si (0.055 vs 0.066), and its fraction-corrected `bright_excess_het_ratio` reads *more even* than B3 within sessions (−1.19 SD, p 0.031, `features/heterogeneity`). B2's higher CV is therefore most likely the fraction effect, not uneven mixing.
- It overlaps `heterogeneity/bright_tile_cv` (different tile size); prefer that column for the ImageRep-referenced heterogeneity reading.

**Negative result kept from the screen: point-pattern clustering is not usable at site level.**
- Clark–Evans R [17] on particle centroids, with Donnelly's edge correction, is ≈ 1 everywhere: B1 1.01, B2 1.00, B3 0.95 ± 0.06. Split-half r 0.18, perturbation ratio 0.87, nothing within sessions (p 0.18).
- Ripley L(10 µm) − 10, with translation correction [18], gives split-half r −0.21 and perturbation 0.90; the 33 µm window is only 3.3 r high.
- With 50–100 points per field, the sampling SE of R (≈ 0.05–0.07) equals the between-site SD. Neither index was built. Agglomerate size and the quadrat CV replace them.

**Verdicts.**
- `bright_orient_order`: promising, thin.
- `bright_d50_um`, `bright_d90_um`: weak at site level; use batch-pooled.
- `bright_solidity_aw`, `bright_agglom_d50_um`: anomaly flags (2316-type).
- `bright_contact_pore_frac`: session-dominated; paired-session only.
- `bright_aspect_aw`: unreliable at site level; descriptive support for the orientation lead.
- `bright_quadrat_cv`: weak, redundant with `bright_tile_cv`; no longer a column.
- In the batch verdict (`analysis/verdict_config.yaml` v1.1): `bright_agglom_d50_um` is Tier 2 (quality range); `bright_d90_um` is a diagnostic (split-half r_x −0.13); the other five are not used.

## Uncertainty and pitfalls

- **Counting noise dominates.**
  - A 5800 µm² field holds 30–80 shape-measurable particles, and area-weighted quantiles are set by a handful of large ones.
  - Split-half r is ≈ 0 for d50, d90 and aspect. For orientation, the within-spot particle-bootstrap SE (≈ 0.11) is about the B3 between-spot SD.
  - Report batch values from particles pooled across sites, with a site bootstrap, never a single site against a tolerance. The unit of evidence is still the session (research report §6): n_eff ≈ 7 sessions for B3.
- **Session.** Pore contact (session R² 0.93; 0.79 without 2316) follows the session's edge spread and void threshold. The other columns sit near the chance level of 0.40 once 2316 is removed.
- **Acquisition.**
  - On the final integrated run (`robustness.py`), the six perturbations move every column by ≤ 0.46 sdB3 except pore contact (0.52, gamma 1.25 on 0grcilhi), just above the 0.5 invariance bar.
  - The bright-mode fallback of the builder's run (solidity 2.5, CV 1.4, aspect 1.0 sdB3) no longer fires with the widened `_common` clamp [1.5, 3.2]. It stays a gate-relevant failure mode of the shared recipe: an image whose bright mode leaves the clamp still gets the default, possibly too-low, threshold.
  - The noise top-up seed alone moves agglomerate d50 by up to 0.52 sdB3 (one sub-micron gap merges or not) and orientation, aspect and solidity by 0.30–0.36 sdB3.
  - **Curtaining.** The synthetic perturbations do not include ion-milling curtains. The only curtained images are the two 2316 spots (`acq_curtain_index` 1.68 / 1.64, G-C under `preprocessing/acquisition.py` `gate_status`), where the large signal of this folder sits. Vertical stripes bias orientation and the void mask (so pore contact), and can roughen the bright-mask outline (so solidity). Re-image 2316-type fields beside a retained reference before reading their shape numbers as material.
- **Segmentation.**
  - Touching particles are not split (no watershed), so `d90` and solidity are biased slightly towards clusters.
  - In 2316 the adaptive mask picks up the ≈ 1.6 g granular population, so that session's particle statistics describe a different bright population, not bigger SiOx.
  - Pore-back regions are mid-grey and not in `h.void`, so pore contact is a lower bound.
  - The 1 µm merge distance for agglomerates is a convention; agglomerates touching the crop edge are lower bounds.
- **2D vs 3D.**
  - Section ECDs under-size the 3D particles (Wicksell [12]), and 2D stereology of non-convex, interconnected particles is ambiguous [15].
  - Sizes, shapes and orientation are *apparent 2D* values, valid only for comparing batches cut and imaged the same way. The area fraction is the only Si quantity valid in 3D (see `si_fraction`).
  - Orientation assumes the image vertical is through-thickness and no sample rotation. The screen's verifier found graphite and pore directors within ≈ 10° of horizontal at every site, but a rotated mount would bias the reading.
- **Window.** The 33 µm crop height caps the observable particle size, and Miles weights reach ≈ 1.5 for 10 µm particles. Particles over ≈ 15 µm would be badly under-sampled; the largest seen is 8.7 µm ECD outside 2316 and 11.7 µm in 2316.

## References

1. Obrovac, Chevrier (2014) Alloy negative electrodes for Li-ion batteries. *Chemical Reviews*. https://doi.org/10.1021/cr500207g
2. Liu, Zhong, Huang et al. (2012) Size-dependent fracture of silicon nanoparticles during lithiation. *ACS Nano*. https://doi.org/10.1021/nn204476h
3. Wu, Yu, Wu et al. (2018) Effect of particle size distribution on the electrochemical performance of micro-sized silicon-based negative materials. *RSC Advances*. https://doi.org/10.1039/c8ra00539g
4. Li, Li, Yang et al. (2021) SiOx anode: from fundamental mechanism toward industrial application. *Small*. https://doi.org/10.1002/smll.202102641
5. Schott, Robert, Benito et al. (2017) Cycling behavior of silicon-containing graphite electrodes, Part B: effect of the silicon source. *J. Phys. Chem. C*. https://doi.org/10.1021/acs.jpcc.7b08457
6. Son, Cao, Yoon et al. (2018) Interfacially induced cascading failure in graphite–silicon composite anodes. *Advanced Science*. https://doi.org/10.1002/advs.201801007
7. Kirner, Qin, Zhang et al. (2020) Optimization of graphite–SiO blend electrodes for lithium-ion batteries: stable cycling enabled by single-walled carbon nanotube conductive additive. *J. Power Sources*. https://doi.org/10.1016/j.jpowsour.2020.227711 (claim taken from the title; abstract not read)
8. Moyassari, Roth, Kücher et al. (2021) The role of silicon in silicon–graphite composite electrodes regarding specific capacity, cycle stability, and expansion. *J. Electrochem. Soc.* https://doi.org/10.1149/1945-7111/ac4545
9. Zhen, Meng, Gao et al. (2023) Asymmetric swelling behaviors of high-energy-density lithium-ion batteries with a SiOx/graphite composite anode. *Small*. https://doi.org/10.1002/smll.202300500
10. Kirkaldy, Samieian, Offer et al. (2022) Lithium-ion battery degradation: measuring rapid loss of active silicon in silicon–graphite composite electrodes. *ACS Appl. Energy Mater.* https://doi.org/10.1021/acsaem.2c02047
11. Jiang, Li, Yang et al. (2020) Machine-learning-revealed statistics of the particle–carbon/binder detachment in lithium-ion battery cathodes. *Nature Communications*. https://doi.org/10.1038/s41467-020-16233-5 (cathode; analogy only)
12. Wicksell (1925) The corpuscle problem: a mathematical study of a biometric problem. *Biometrika*. https://doi.org/10.1093/biomet/17.1-2.84
13. Miles (1978) The sampling, by quadrats, of planar aggregates. *Journal of Microscopy*. https://doi.org/10.1111/j.1365-2818.1978.tb00104.x
14. Lantuéjoul (1978) Computation of the histograms of the number of edges and neighbours of cells in a tessellation. *Lecture Notes in Biomathematics*. https://doi.org/10.1007/978-3-642-93089-8_27
15. Taiwo, Finegan, Eastwood et al. (2016) Comparison of three-dimensional analysis and stereological techniques for quantifying lithium-ion battery electrode microstructures. *Journal of Microscopy*. https://doi.org/10.1111/jmi.12389
16. Dahari, Docherty, Kench et al. (2025) Prediction of microstructural representativity from a single image (ImageRep). *Advanced Science*. https://doi.org/10.1002/advs.202414149
17. Clark, Evans (1954) Distance to nearest neighbor as a measure of spatial relationships in populations. *Ecology*. https://doi.org/10.2307/1931034
18. Ripley (1977) Modelling spatial patterns. *J. R. Stat. Soc. B*. https://doi.org/10.1111/j.2517-6161.1977.tb01615.x

Standards and pages without a DOI (from `notes/research_report.md` §10): ISO 9276-6:2008 (particle shape descriptors), ISO 13320 (laser diffraction), GB/T 38823-2020 (Si–carbon anode materials; grade numbers **[partly verified]**), and the Polaron Quality & Qualification page (https://www.polaron.ai/applications/quality-and-qualification).

All DOIs above were resolved with the ledger's own OpenAlex lookup (`ledger.lookup_doi`) or found with a Crossref bibliographic search and then resolved the same way. None was typed from memory. The claim from [7] rests on its title only. The orientation→swelling, patchiness→failure and pore-as-free-volume links are marked as hypotheses in the text. The readings of [3], [5] and [8] were checked against their abstracts: [3] reports a PSD optimum (narrow PSD at ≈ 22.7 µm), not a monotonic size trend; [5] (nano-Si in graphite) finds that micrometric aggregates fade fast while mesoporosity manages stress; [8] finds no clear correlation between thickness change and the capacity-loss rate.
