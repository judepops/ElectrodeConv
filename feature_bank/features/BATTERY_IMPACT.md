# Battery impact of the image features

## 1. What this is and how to read it

This page translates every column in `features/` into what it means for the cell. It also shows where the incoming
lots sit against the approved baseline: Batch_1 and Batch_2 have 7 spots each, and Batch_3 has 17 spots from 7
sessions. The material is a calendered graphite anode with three other components: a bright Si-based phase (most
likely SiOx, EDS pending) at ≈ 6 % of the area, a carbon-binder web, and ≈ 10 % open void in 2D.

How to read the calls:
- **Good** or **bad**: that direction helps or hurts the cell, through a named mechanism with a citation.
- **Trade-off**: it helps one property and hurts another. Both are named.
- **Neither**: there is no known performance direction. The change is only a sign that the supplier's process
  changed (for `acq_` columns, that the imaging changed). Ask the supplier why; do not grade the change.

For an incoming lot the best value is almost always "match the baseline".

Two caveats apply to every number on this page.
- **Every number is a 2D section measurement and a relative index.**
  - Porosity reads low: pore-back and the sub-resolution pores of the binder web are counted as solid [37].
  - Sizes are section sizes, not laser-diffraction D50.
  - Reading Si-phase area as wt % assumes the Si material is the same.
  - So compare batches imaged the same way. Do not read absolute levels.
- **The microscope session explains much of the spot-to-spot variance.**
  - There are 13 sessions, each marked by its image height. Session R² reaches 0.95 for material columns; chance is
    ≈ 0.40.
  - Only 5 sessions hold more than one batch.
  - The screen's `sep` and `q` (`rank_features.py`) shuffle batch labels across all spots, so they do not control
    for session.
  - The evidence that counts is the **within-session test** (`robustness.py`): an exact permutation test of the
    batch effect inside the mixed sessions. It is weak: the smallest p it can give is ≈ 0.005, and it rests on few
    spot pairs.
  - It cannot see session 2316. That session holds only two Batch_1 spots (4ih2ggld, 5n1q8atc), which carry the
    main Si-phase lead. It counts as one session (n_eff = 1).
- **Three of the five mixed sessions are one continuous strip each, split across batch folders**
  ([`experiments/data_audit/seam_examples/`](../../experiments/data_audit/seam_examples/README.md), pixel-level joins scoring 0.89–0.92):
  - 2080 is one strip filed as Batch_3, Batch_2 and Batch_1 (`cfe5vt7s`, `r17byphk`, `ffwubibz`);
  - 2068 is a strip of three Batch_3 tiles and one Batch_2 tile;
  - 2148 is one Batch_1 tile next to one Batch_2 tile.

  Inside those strips a "batch contrast" compares neighbouring pieces of one sample. It measures variation along
  the strip, not a difference between supplier lots. The within-session p-values on this page rest mostly on
  these strips, so read every within-session lead as weaker still, and ask Polaron how tiles were assigned to
  batches before claiming any batch difference from them. The 2316 Si-phase anomaly is not affected: its two
  spots have no neighbour in another folder.

Notation used in the tables:
- "SD" is the Batch_3 between-spot SD.
- "within" is the within-session effect in SD units, with its exact p.
- "2316" means the two spots from that session.
- The tiers are the v1.1 panel (`analysis/verdict_config.yaml`), chosen before the released test set was examined.
- **Tier 1**: an equivalence test (TOST) on the lot mean. It decides ACCEPT or REJECT. v1.1: `porosity_open_frac`
  and `bright_solid_frac`.
- **Tier 2**: a quality range. At least 6 of 7 spots must sit inside the baseline mean ± 2.86 SD. v1.1:
  `bright_agglom_d50_um`, `pore_lt_d50_um` and `interface_density_per_um`.
- **Tier 3**: a diagnostic. It is shown on the certificate and never decides. v1.1 moved `solid_chord_y_um` here
  from Tier 1 (it fails the Batch_3-only MSA gate, %GRR upper 82 %, ndc 0.97, and the invariance gate, 0.62). It
  moved six columns here from Tier 2 because their left/right split-half reliability r_x is below 0.35:
  `flake_orient_order` 0.10, `porosity_tile_cv` 0.08, `bright_d90_um` −0.13, `bright_tile_cv` 0.33,
  `solid_chord_hv_ratio` 0.26, `pore_n_per_1000um2` 0.25.
- **Gate**: an identity companion of a Tier 1 KPI (v1.1: `bright_fixed_solid_frac` only). (The verdict's Gate 1 now
  checks pixel size and detector set only; how each spot was imaged is graded in preprocessing, step 5.)
- **Not material**: imaging and measurement columns (`porosity_void_threshold`, `flake_tilt_deg`,
  `bright_contrast_ratio`, `histogram_anomaly_z`, the `_ci95` and `_integral_range_um2` columns). They are never
  fed to any classifier.

## 2. What the batches show

**Established** (what the data clearly say):
- **Batch_1 contains one anomalous session; it is not a lot-wide shift.** The two 2316 spots differ from
  everything else in the data:
  - Si phase in the solid: 0.162 and 0.204, against 0.066 ± 0.011 (+8.7 and +12.5 SD).
  - Si-particle cores are darker: 1.65 and 1.67, against 2.13.
  - Si shapes are ragged (solidity −29 and −12 SD) and the agglomerates are large (+9.4 and +10.1 SD).
  - They have the longest solid chords in the data (+3.6 and +5.2 SD).
  - They are the only images with FIB curtains: curtain index 1.68 and 1.64, against 1.045 ± 0.068.

  The other five B1 spots match the baseline on the Si phase (0.067). Session 2316 holds only B1, so a material
  change and a session effect cannot be told apart there.
- **What 2316 means for the cell depends on what the material is, so it is neither good nor bad until EDS.**
  - `si_grade`'s best fit is a different Si product, a porous or agglomerated Si–C composite, at 2.5–3× the
    baseline Si area.
  - Area cannot be read as Si mass for such a product.
  - The candidate materials move ICE in opposite directions: an O-richer SiOx lowers it, a pre-lithiated grade
    raises it, and for a porous Si–C composite it depends on the design [4, 5, 11, 12].
  - If it were simply more of the same SiOx, it would be a trade-off for the material and bad in a fixed cell
    design: lower ICE, more swelling, faster fade [1–3].
- **The Batch_1 certificate reads INVESTIGATE.** Every Si-phase driver is carried by the same two spots:
  - Tier 1 `bright_solid_frac`: Δ +0.034, P(beyond margin) 0.79, INCONCL.
  - Tier 2 `bright_agglom_d50_um` fails (5/7 spots inside, P 0.75).
  - The lot spread of `bright_solid_frac` is 5.4× the baseline's (q 0.024).
  - The other Tier 1 KPI, `porosity_open_frac`, is also INCONCL: "shifted within tolerance", P 0.24 (not a 2316
    effect; see Leads).

  REJECT stays closed because the 90 % CI [−0.011, +0.078] spans 0 (INCONCL). Two more checks would block it too:
  the fixed-threshold identity check reads "not confirmed", and the only session-matched contrast (2080) has the
  opposite sign. Action: EDS on at least 3 bright particles, the supplier's Si-phase CoA, and re-imaging next to a
  retained baseline reference.
- **The Batch_2 certificate reads INVESTIGATE, most likely equivalent.**
  - Porosity is EQUIV (P 0.06). All three Tier 2 KPIs pass 7/7. There is no heterogeneity or novelty flag.
  - Only `bright_solid_frac` blocks CONDITIONAL ACCEPT. It reads −1.05 SD (−17 %), and P = 0.24 is above the 0.2
    bar.
  - That shift is not confirmed within sessions (−1.50 SD, p 0.24). The two lowest B2 spots come from 2048, a
    session that holds only B2.
  - If the shift were real: a small capacity shortfall with slightly better ICE. That is a trade-off in the
    out-of-spec direction, but inside the margin.
  - Both certificates were built while B1 and B2 were already in view, so they test the plumbing, not the accuracy.

**Leads** (not established; none survives correction over the 59–68 columns tested):
- **B1 porosity is lower by 18 %** (0.089 against 0.108, −1.04 SD). Within sessions it is −1.64 SD, p 0.17. Only
  one B1–B3 spot pair shares a session, and the test has ≈ 30 % power at this size. The two 2316 spots do not cause
  it. If real, it is a denser electrode: a **trade-off** between rate (mildly also fast charge) and volumetric
  energy density [17, 18]. The certificate says "shifted within tolerance" and its action is monitoring.
- **Both lots may have a slightly coarser solid skeleton, with fewer pores per line and less pore wall.**
  - `solid_chord_x_um`, within: +2.5 / +1.7 SD, p 0.026 (BH q 0.45).
  - `solid_lt_d50_um`, within: +1.20 / +1.52 SD, p 0.068.
  - `interface_density_per_um`, within: −2.11 / −1.42 SD, p 0.057. About half of this follows the lower porosity.
  - Pore widths and flake alignment are unchanged.
  - If real: **neither**, a sign that the supplier's graphite, binder or calendering changed. It becomes the
    rate-vs-SEI trade-off only if coarser graphite is confirmed.
- **There are hints on Si dispersion and shape.**
  - Si is spread more evenly than the baseline in both lots (`bright_excess_het_ratio` within −1.54 / −1.19 SD,
    p 0.031). Without one B2 spot, p is 0.19.
  - B2's Si shards are more elongated (`bright_aspect_aw` +1.64 SD, p 0.036; a few large particles carry it) and
    lie flatter (`bright_orient_order` +1.73 SD, p 0.17).
  - Within sessions, B1's Si particles read finer (d50 −1.97 SD, p 0.021). This rests on one direct spot pair and
    the direction was found after looking.
  - All of these read **neither**.
- **No detectable change was seen** in pore width, pore patchiness, flake alignment, the Si grade outside 2316,
  carbon domains (no sign of a graphite blend). The acquisition check in preprocessing (step 5) grades 29 of 31 spots
  G-A and warns on the two curtained 2316 spots (G-C). Power is low: only large shifts are excluded.

## 3. Feature → cell

Numbers in brackets are references (§6). Each feature name links to its folder README, where the evidence sits.

### Si phase

| Feature | What it tells you about the cell | If higher | If lower | Best value | Our batches now | Confidence | Used in the verdict as |
|---|---|---|---|---|---|---|---|
| [`bright_solid_frac`](si_fraction/README.md) | Si dose: the share of the solid that is the Si-based phase. To first order this is the Si-phase wt % of the active material, if the material stays the same | More anode capacity per gram, but lower ICE (oxide → Li silicates and Li₂O), more swelling and damage, and faster early fade of the Si fraction [1–6]. **Trade-off** for the material. **Bad** in a fixed cell design: at a fixed cathode loading the extra capacity goes mostly unused, while the extra Li loss is real (design arithmetic, no citation) | Capacity shortfall against the design (the N/P margin shrinks), with slightly better ICE, swelling and life [2–5]. **Trade-off, out of spec** | Match B3: 0.066 ± 0.011 (margin ± 0.0166) | B1 0.100 (+3.0 SD), all from 2316 (0.162, 0.204); the other 5 B1 spots read 0.067. The within-session test cannot see 2316; on B1's spots in mixed sessions it gives −1.66 SD, p 0.24. B2 0.055 (−1.05 SD; −0.66 SD without the B2-only session 2048); within −1.50 SD, p 0.24. Neither shift is established | Strong for each direction if the phase is Si-based (EDS pending); moderate for the net cell effect | **Tier 1.** B1: INCONCL, P 0.79, CI [−0.011, +0.078]. B2: INCONCL, P 0.24 > 0.2, the one thing that keeps B2 from CONDITIONAL ACCEPT |
| [`bright_fixed_solid_frac`](si_fraction/README.md) | The same share measured with a fixed 1.45 × graphite threshold: a measurement and identity check | Moving with the primary: read it like `bright_solid_frac` up. Moving against it: **neither**, a sign of the session tone curve or of a Si material with a different grey level | Moving with the primary: read it like `bright_solid_frac` down. Moving against it: **neither** | B3 0.081 ± 0.018; it must move with the primary | B1 0.093 (+0.68 SD; 0.073 without 2316), B2 0.061 (−1.07 SD). Within p 0.59. Same direction as the primary. Perturbation ratio 1.83 (fails the 0.5 bar) | Moderate | **Gate**: identity companion of the Tier 1 KPI. B1 "not confirmed" (CI includes 0), B2 passes. Anything other than a pass blocks REJECT |
| [`bright_n_per_1000um2`](si_fraction/README.md) | Number of Si objects ≥ 1 µm per area. At a fixed fraction it reflects Si size and dispersion | More, smaller objects (finer or broken Si): more surface, more SEI, lower ICE, less stress per particle [1, 6]. **Neither** on its own | Coarser Si or agglomerates, with more stress per particle (hot-spots: mechanism only) [1, 6]. **Neither**; bad only if `si_particles` confirms coarsening | B3 8.3 ± 1.6 | B1 11.6: the 2316 spots read 20.5 and 20.8, and B1 is 7.9 without them. B2 6.7 (−0.93 SD). Within p 0.13: not confirmed | Low | Not used |
| [`bright_d90_um`, `bright_d50_um`](si_particles/README.md) | Si particle size (2D section). The coarse tail means fracture and contact loss; fines mean surface, SEI and ICE | More fracture and contact-loss risk, less SEI, slightly higher ICE [1, 7]. **Trade-off, leaning bad** for cycle life. At the micron scale there is an optimum: a narrow PSD cycled best [8] | Less cracking, but more SEI and lower ICE. **Trade-off** (life against ICE) [1, 8] | B3 d50 4.07 ± 0.76 µm, d90 6.72 ± 0.93 µm | B1 d90 7.10, only from 2316 (+5.4, +3.4 SD); 5.62 without. Within sessions B1 reads *finer* (d90 −1.80 SD, p 0.026): one direct spot pair, direction found after looking, so thin. B2 d90 5.91 (within −0.66 SD): no change | Low–moderate | **Tier 3** (d90; left Tier 2: split-half r_x −0.13): B1 +0.41 SD, B2 −0.87 SD (screen q 0.81 / 0.50). d50 not used |
| [`bright_agglom_d50_um`](si_particles/README.md) | Size of Si clusters (particles < 1 µm apart merged): possible local swelling hot-spots | Plausible local swelling and cracking hot-spots [2, 9]. **Bad**, but only if more Si does not explain it (inference; the column rises with the Si fraction, r 0.46) | Better-dispersed Si. **Good** (same inference) | B3 4.56 ± 0.65 µm; read with `bright_solid_frac` | B1 6.27, all from 2316 (+9.4, +10.1 SD). That is partly mechanical, from their 2.5–3× Si fraction, and their fraction-corrected clustering is normal. B1 is 4.43 without 2316. B2 4.60 | Low | **Tier 2**: B1 fails 5/7 (P 0.75), the Tier 2 flag behind B1's Si-phase reason; B2 passes 7/7. Caveat: its between-batch signal and its reliability come almost entirely from the two 2316 spots (η² without them ≈ 0); the panel stays frozen at v1.1 because the test set has been released, so any re-tiering is only a proposal for after the blind test is scored |
| [`bright_solidity_aw`](si_particles/README.md) | Compactness of the Si objects. Low means ragged, porous or clustered: a different Si product | **Neither** (the baseline, 0.90, is already near the ceiling) | Dense micrometric aggregates fade fast, but internal mesoporosity managed the stress and cycled stably [9]. **Neither from BSE alone**; bad only if EDS shows dense aggregates | B3 0.896 ± 0.016 | B1 0.798, all from 2316 (−29, −12 SD); 0.887 without. B2 0.896. Within p 0.33 | Low | Not used |
| [`bright_aspect_aw`, `bright_orient_order`](si_particles/README.md) | How elongated the Si shards are and how flat they lie: a signature of milling, classification or mixing | **Neither**: a sign the supplier's process changed. The idea that orientation changes how swelling splits between directions is a hypothesis only | **Neither** (same) | B3 aspect 1.64 ± 0.14, orientation 0.13 ± 0.10 | B2 aspect 1.87 (+1.64 SD within, p 0.036; the number-weighted aspect shows nothing). B2 orientation 0.276 (+1.73 SD within, p 0.17): a hint, not a finding. Graphite alignment shows no sign of harder calendering but cannot rule out a moderate one. B1 aspect 1.73 (+1.61 SD within) | Low | Not used |
| [`bright_contact_pore_frac`](si_particles/README.md) | Share of the Si outline that faces pore rather than carbon or binder: the electronic wiring of the Si | Weaker wiring, and Si can become isolated as it swells and shrinks [3, 10]. But the pore is also room to swell into. **Trade-off, leaning bad** (inference) | Si better embedded in the carbon-binder web. **Good, probably** (inference) | Lower leans better; compare only with a same-session reference (B3 0.066 ± 0.016) | B1 0.078 from 2316 (+4.7, +5.3 SD; not readable as material). B1 is 0.052 without 2316; B2 0.048. Within B1 −1.18, B2 −1.03 SD, p 0.073: the benign direction, not established. Session R² 0.93 | Low | Not used (session-dominated) |
| [`bright_contrast_ratio`](si_grade/README.md) | BSE level of the Si cores: the mean atomic number (Z), i.e. the grade, of the Si phase. Session explains 94 % of it | Si-richer grade (lower x in SiOx): more capacity and ICE, but more swelling and fade [1, 4, 5]. **Trade-off** if EDS confirms. It can also be a kV or detector change [13] | Four possible causes with opposite cell effects: an O-richer SiOx (lower capacity and ICE, less swelling) [4, 5]; a porous Si–C composite (built for low swelling) [11]; a pre-lithiated SiOx (ICE goes **up**) [12]; or a kV or detector change [13]. **Neither from BSE alone**: send for EDS | Match a B3 spot from the same session (2.13 ± 0.15) | B1 1.92 (−1.34 SD), all from the 2316 cores (1.65, 1.67; z −3.2, −3.0); the other 5 B1 spots read 2.03. B2 2.10. Within p 0.71: no batch difference | Low | **Tier 3**; on the `not_material` list (never fed to a classifier) |
| [`bright_internal_dark_frac`](si_grade/README.md) | Pores, carbon or a second phase inside the Si particles: a test for a porous Si–C composite | Fits a porous or agglomerated Si–C composite, a different product built to buffer swelling [11]. **Neither**: a sign the Si product changed. **Bad** if SE imaging shows real cracks: fresh surface grows SEI (shown for graphite [14], applied here by analogy) | Denser particles; the baseline is already near the dense floor. **Neither** | B3 0.011 ± 0.005 | B1 0.018; the mean shift comes from 2316 (+7.5, +4.1 SD). B2 0.011. Within p 0.42 | Low | **Tier 3** |
| [`bright_dim_frac`](si_grade/README.md) | Grey objects between graphite and Si: lower-Z Si, dense binder pockets or particle edges, which BSE cannot tell apart [13] | **Neither** (ambiguous) | **Neither** | B3 0.025 ± 0.021 | B1 0.013 (it does not flag 2316), B2 0.027. Within p 0.20 | Low | **Tier 3** |
| [`s2_bright_corrlen_x/y_um`, `s2_bright_integral_range_um2`](two_point_correlation/README.md) | Size and clustering scale of the Si phase, from the two-point correlation | Coarser or clustered Si: swelling concentrates, with cracking and contact loss [1]. **Bad, if real** | If the Si is finer: **trade-off** (more even swelling, more SEI). If the same particles are only better dispersed: **good**. `bright_d90_um` tells the two apart | B3 1.82 ± 0.30 / 1.63 ± 0.28 µm; 14.9 ± 4.3 µm² | B1 1.74 / 1.52 µm, lower in all 3 shared sessions (within p 0.052 / 0.13). Not a finding: 8 columns were tested and the per-spot values are noise. B2 1.93 / 1.52. Weak sign that 2316's extra Si is not coarser or clustered | Low | Not used (the integral range is on the `not_material` list) |

### Pores and transport

| Feature | What it tells you about the cell | If higher | If lower | Best value | Our batches now | Confidence | Used in the verdict as |
|---|---|---|---|---|---|---|---|
| [`porosity_open_frac`](open_porosity/README.md) (and its fixed-threshold twin `porosity_fixed060_frac`) | A relative 2D index of the electrolyte-filled volume. It sets ionic transport (D_eff/D₀ = ε/τ) and trades off against volumetric energy density | Easier ion transport, better rate [17]. Only a small fast-charge gain: porosity was an ineffective lever against plating, tortuosity an effective one [18]. Lower volumetric energy density. **Trade-off** | Denser electrode: more tortuous, poorer rate, mildly higher plating risk at fast charge [17, 18]. Higher energy density. Less room for the Si to swell (general knowledge). Wetting direction unknown [19]. **Trade-off** | Match B3: 0.108 ± 0.018 (margin ± 0.0275) | B1 0.089 (−1.04 SD, −18 %); within −1.64 SD, p 0.17 (one direct B1–B3 pair). Not a 2316 effect. B2 0.102 (−0.31 SD). The twin agrees (within p 0.34) | Moderate (strong mechanism, biased 2D proxy) | **Tier 1.** B1: INCONCL, "shifted within tolerance", P 0.24, CI [−0.039, +0.001], action monitoring. B2: EQUIV (P 0.06). The twin is not used |
| [`pore_lt_d50_um`, `pore_lt_d90_um`](local_thickness/README.md) | Pore width (2D local thickness): how fast the electrolyte fills and wets the electrode | At the same porosity, filling can be faster, but no rate gain is expected, and wider is not better without limit [19]. **Neither** (at most a small wetting gain; see note). d90 up on its own means coarse gaps, cracks or delamination: **neither**, inspect those spots | At the same porosity, slower filling: **bad** for wetting [19]. A rate or plating penalty arises only at bottlenecks and is not established [21]. Together with lower porosity: **trade-off** (energy density against rate and wetting) | B3 0.78 ± 0.12 / 1.96 ± 0.52 µm | No detectable change: B1 0.806, B2 0.789 µm; within p 0.56 (d90 0.55). Power is low: the within-session CI of −1.86 to +0.90 SD does not exclude a narrowing as large as the margin. B1's raw excess comes from 2316 | Moderate (d50), low (d90) | **Tier 2** (d50): both lots pass 7/7 (P 0.06 / 0.02). d90 not used |
| [`s2_void_corrlen_x/y_um`](two_point_correlation/README.md) (with the void x/y ratio) | Pore size scale in the plane and through the thickness, measured without splitting pores (ρ 0.89–0.92 with `pore_lt_d50_um`). The x/y ratio is pore flattening, a proxy for through-plane tortuosity | Faster capillary filling [20]: **good** for wetting at the same porosity according to that folder (see note); a **trade-off** if it comes from lighter calendering. Ratio up: **bad** for rate at the same porosity [17] | Slower wetting: **bad**; a **trade-off** if porosity also fell. Ratio down: **good** for transport | B3 0.833 ± 0.160 / 0.542 ± 0.082 µm; ratio 1.53 ± 0.12 | No detectable change. Within: B1 −0.79 / −0.86, B2 +0.01 / −0.48 SD (p 0.65 / 0.51); ratio p 0.56. B1's raw excess is all from 2316 | Moderate | Not used |
| [`pore_n_per_1000um2`](minkowski_functionals/README.md) | How finely the visible pore space is split. In 2D the Euler number is about the pore count, and it says nothing about 3D percolation | Finer pore network. **Neither**: a sign the process changed; no battery link is established | Coarser network. **Neither** | B3 96.5 ± 8.0 per 1000 µm² | B1 92.4, B2 89.6; within p 0.41: no change | Low | **Tier 3** (left Tier 2: split-half r_x 0.25): B1 −0.51 SD, B2 −0.86 SD (screen q 0.70 / 0.50) |

Note on wider pores: `two_point_correlation` calls them good for wetting (capillary filling [20]). `local_thickness`
calls them neither, because the most open, uncalendered film in [19] wetted more slowly than a lightly calendered one.
Read wider pores as at most a small wetting gain.

### Graphite structure

| Feature | What it tells you about the cell | If higher | If lower | Best value | Our batches now | Confidence | Used in the verdict as |
|---|---|---|---|---|---|---|---|
| [`solid_chord_y_um`](chord_length/README.md) | Through-plane solid distance between pores. It is the closest image stand-in for graphite flake thickness or particle size, but only an upper bound and never calibrated against PSD | (a) Coarser graphite: **trade-off**. Slower solid diffusion lowers rate and adds plating risk at fast charge, mainly above ≈ 10 µm [22]; in exchange there is less SEI and first-cycle loss [14]. (b) Fewer pores at the same porosity, or binder, Si agglomerates or calendering: **neither** | (a) Finer graphite: **trade-off** (rate against SEI) [14, 22]. (b) More, smaller pores: **neither** | B3 4.92 ± 0.46 µm (v1 margin ± 0.686) | B1 5.93, carried by 2316 (+3.6, +5.2 SD), the same event as the Si flag. Without 2316 the raw delta is +0.60 µm, inside the v1 margin. B2 5.29. Within: B1 +2.4, B2 +1.5 SD, p 0.12, so a shift is not shown. If real, it means fewer pores per line: **neither** | Low | **Tier 3** (left Tier 1: fails the Batch_3-only MSA gate, %GRR upper 82 %, ndc 0.97, and the invariance gate, 0.62). B1 Δ +1.01 µm (+2.2 SD, screen q 0.18); B2 +0.37 µm (+0.80 SD, q 0.70) |
| [`solid_chord_x_um`](chord_length/README.md) | In-plane solid distance between pores | As `solid_chord_y_um` | As `solid_chord_y_um` | B3 5.80 ± 0.63 µm | B1 6.93, B2 6.23. Within +2.5 / +1.7 SD, p 0.026, and all four B3 contrasts are positive. This is the strongest within-session signal, but BH q is 0.45 over 68 columns, so it is a lead. It comes from fewer pores per µm, not wider pores. **Neither**, if real | Low | Not used |
| [`solid_lt_d50_um`](local_thickness/README.md) | Median thickness of the solid ligaments between pores. Not a particle size (r 0.06 with `particle_size_d50_um`) | Coarser skeleton. **Neither**; a trade-off (slower diffusion against less SEI [14]) only if larger particles are confirmed. Size alone does not fix the rate direction [23] | Finer skeleton, more surface, so more SEI and lower ICE [14, 23]. **Neither**; a trade-off if finer particles are confirmed | B3 4.62 ± 0.35 µm | B1 4.88, B2 4.85. Within +1.20 / +1.52 SD, p 0.068. Perturbation ratio 0.63 (fails). A weak lead; it correlates with `solid_chord_y_um` (r 0.62), so it is not independent | Low | Not used |
| [`interface_density_per_um`, `interface_density_resid_z`](minkowski_functionals/README.md) | Pore/solid boundary per area: the macro (> 50 nm) surface where the SEI forms. The residual is the part not explained by porosity | At the same porosity, finer material: more SEI and lower ICE [14, 15], but shorter diffusion paths and better rate [16, direction only]. **Trade-off.** If porosity rises with it, read `porosity_open_frac` | At the same porosity, less SEI (higher ICE) and poorer rate. **Trade-off** | B3 0.532 ± 0.047 µm⁻¹; residual ≈ 0 (± 2 is still baseline-like) | B1 0.453 (−1.67 SD); within −2.11 SD, p 0.057 (one direct B1–B3 pair; the 2316 spots are the lowest of all 31; B1 is 0.475 without them). B2 0.497 (−0.73; within −1.42). About half of the shift is lower porosity (residual within −0.86 / −0.81 SD, p 0.18). Not established | Moderate (ICE), low (rate) | **Tier 2** (L_A): B1 6/7 (P 0.60, its 3rd-ranked driver), B2 7/7 (P 0.13). Residual not used |
| [`solid_chord_hv_ratio`](chord_length/README.md), [`flake_orient_order`](flake_orientation/README.md) | How flat the graphite flakes lie (calendering texture), which sets through-plane against in-plane tortuosity. H/V and order correlate at r 0.94, so they count as one piece of evidence | Flatter flakes make the through-plane path more tortuous [17]: lower rate [24], more plating at fast charge (image-based simulation [25]). **Bad** at the same porosity; a **trade-off** if harder calendering also densified the electrode | Better through-plane transport: graphite aligned vertically reached 80 % SOC at 1C in 50 instead of 138 min [26]. **Good** for rate at the same porosity; a **trade-off** if it comes from lighter calendering (less dense). Rule out curtains first | B3 H/V 1.18 ± 0.04; order S 0.295 ± 0.063 | Flat. H/V 1.176 / 1.180 against 1.177 (within p 0.24); S 0.307 / 0.301 against 0.295 (within p 0.66). Only large shifts are excluded (≈ 1.3 SD pooled, ≈ 2 SD with the session controlled) | Moderate (S), low (the H/V column itself) | **Tier 3** (H/V and S; left Tier 2: split-half r_x 0.26 and 0.10). B1 −0.02 / +0.20 SD, B2 +0.07 / +0.10 SD (screen q ≥ 0.81) |

### Spatial uniformity

| Feature | What it tells you about the cell | If higher | If lower | Best value | Our batches now | Confidence | Used in the verdict as |
|---|---|---|---|---|---|---|---|
| [`bright_excess_het_ratio`](heterogeneity/README.md) | Si clustering between 12.8 µm tiles beyond what a random dispersion of the same particles gives (a dispersion index) | Si-rich patches concentrate swelling [1]. In a model, SiO uniformity changes polarisation and capacity [27]; agglomerated slurries give more resistive anodes [28]. Counterpoint: the least-dispersed binder cycled best [29]. **Bad** (expected, not shown for this metric) | More even than the baseline. **Neither**: a sign that the mixing or the Si powder changed | B3 0.82 ± 0.14 (a random dispersion gives ≈ 0.77) | B1 0.645, B2 0.583; within −1.54 / −1.19 SD, p 0.031. Only a hint: p is 0.19 without one B2 spot, BH q ≈ 0.42, and p is 0.068 after adjusting for the Si aspect ratio. Not a 2316 effect. **Neither** | Low | Not used |
| [`porosity_tile_cv`, `bright_tile_cv`](heterogeneity/README.md) | Raw tile-to-tile spread. It mostly tracks phase coarseness (pores) and the Si fraction (Si), not patchiness | **Neither** by itself; it means patchiness only if the excess ratio rises too | **Neither** by itself | Inside the B3 mean ± 2.86 SD ranges 0.214–0.551 / 0.519–1.685 | Porosity CV: B1 0.458 (+1.3 SD), B2 0.413, against 0.382. Bright CV: B1 0.869, B2 1.174, against 1.102. Within p 0.27 / 0.40: not established. Half of B1's raw shift is 2316 | Low | **Tier 3** (left Tier 2: split-half r_x 0.08 / 0.33). Porosity CV B1 +1.28, B2 +0.51 SD; bright CV B1 −1.14, B2 +0.36 SD (screen q ≥ 0.18) |

### Carbon domains

| Feature | What it tells you about the cell | If higher | If lower | Best value | Our batches now | Confidence | Used in the verdict as |
|---|---|---|---|---|---|---|---|
| [`carbon_dark_domain_frac`](carbon_domains/README.md) | Share of the graphite in a second, darker BSE level. It could be a second graphite grade (a blend), or electron channelling or pore-back contrast | If it is a blend, there is more of the darker grade. ICE moves with surface area [14, 15]. Natural graphite brings cost and processability, synthetic graphite brings rate [32]. **Neither** until EDS, Raman or XRD identifies the grade; a **trade-off** if a natural/synthetic shift is confirmed. If it is channelling or pore-back [13, 37], nothing changes in the cell | Less of it, or a single grade. A full switch to another grade also reads 0. **Neither** | Match a baseline from the same session (baseline spots range 0–0.28) | B1 0.013 (weak domains in 4/7 spots), B2 0.082 (3/7, two of them in the B2-only session 2048), B3 0.028 (2/17). Within p 0.31. Both 2316 spots read 0. No evidence of a blend or grade change | Low | **Tier 3** (raw shift B1 −0.18 SD, B2 +0.67 SD) |

### Acquisition controls and measurement diagnostics

The `acq_` values are no longer columns of `processed/features.csv`. They are measured by `preprocessing/process_data.py`
(step 5) into `processed/acquisition.csv`, with a plain-language warning per problem; see
[`preprocessing/acquisition.md`](../preprocessing/acquisition.md). The rows below are kept so a reader knows what they mean.

None of these describes the electrode. "Bad" below means bad for the measurement only: the material KPIs of that
spot become biased.

| Feature | What it tells you about the cell | If higher | If lower | Best value | Our batches now | Confidence | Used in the verdict as |
|---|---|---|---|---|---|---|---|
| [`acq_bse_noise_sigma`, `acq_bse_black_level`, `acq_inlens_sat255_frac`](../preprocessing/acquisition.md) | Nothing about the cell. BSE noise, BSE black offset and Inlens saturation say whether a spot's material KPIs can be trusted | **Neither** for the cell. Bad for the measurement beyond the envelope: noise above 0.235 cannot be equalised; Inlens above 0.10 [35] | **Neither** (a black level of 0 means the detector clips) | Inside the known envelope: black 0–24.4, noise ≤ 0.214, Inlens ≤ 0.066 | All 14 incoming spots are inside. Pooled, noise reads "separates" (sep 0.61) and black level "acquisition?" (sep 0.59), both only through B3-only sessions; within p 0.69 / 0.78. That is the leakage trap [34]. Inlens: B1 lower in all 3 shared sessions (p 0.094), a chance-level hint | Strong (noise, black level), moderate (Inlens) | Preprocessing grade (step 5): G-A for all 14 incoming spots except the two 2316 spots (G-C, curtaining). Not part of the verdict's Gate 1 any more |
| [`acq_curtain_index`](../preprocessing/acquisition.md) | FIB ion-milling stripes. Nothing directly about the cell (hard phases and pores can seed them). On our data they bias gradient and orientation KPIs (report §7.10), and curtains need filtering before a Si/C–graphite anode is segmented [36] | **Neither** for the cell; bad for the measurement above 1.30 | Towards 1 means clean. **Neither** | ≈ 1 (envelope 0.888–1.165) | 2316 reads 1.68 / 1.64 (z +9.3 / +8.8): the only curtained images, sitting on the Si-phase lead. The other B1 spots read 1.01, B2 0.988, against B3 1.045. The within-session test cannot see 2316 | Strong for 2316-like curtains, low for small changes | Preprocessing warning only (r 0.83 with `bright_solid_frac`, all through 2316); rates 2316 G-C |
| [`acq_focus`, `acq_cnr`, `acq_bse_clip0_frac`, `acq_inlens_noise_sigma`, `acq_bse_graphite_level`](../preprocessing/acquisition.md) | Sharpness, contrast-to-noise, clipped pixels (these carry porosity), Inlens noise, graphite grey level. Diagnostics, not the cell | **Neither** | **Neither** (focus below 0.0107 is bad for the measurement) | Not a material property | The clip fraction "acquisition?" (sep 1.17, q 0.014) and CNR "separates" (0.66) come from B3-only sessions: within p 0.77 / 0.83. Focus: B2 is 2–6 % below its co-session spots (p 0.0625), a chance-level hint | Moderate–strong | Display-only or folder diagnostics |
| [`porosity_void_threshold`](open_porosity/README.md), [`flake_tilt_deg`](flake_orientation/README.md) | The per-image pore threshold (it follows the tone curve) and the flake tilt (mounting or scan angle) | **Neither**: the imaging or mounting changed. A tilt lowers flake order S by ≈ (1 − cos 2·tilt), ≈ 6 % at 10°; read the spread instead | **Neither** | Not a material property | The threshold "separates" (sep 0.89, q 0.03), but within p 0.86, so it is acquisition. Tilt: B1 +1.1°, B2 −1.0°, against +2.3 ± 5.1° | Strong | Not used; on the `not_material` list (never fed to a classifier) |
| [`bright_frac_ci95`](si_fraction/README.md), [`porosity_open_ci95_frac`](open_porosity/README.md), [`s2_void_integral_range_um2`](two_point_correlation/README.md) | Single-image sampling error bars (integral range, the ImageRep idea [33]). Not material properties | **Neither**: one spot is less representative, so more sites are needed | **Neither** | Not a material property | No batch change (q ≥ 0.31; within p 0.09–0.88). The Si-phase median SE (0.012) is about the B3 SD (0.010), so site scatter is sampling noise. The porosity median SE (0.009) is half the B3 site SD (the session adds the rest), so never use it as a batch error bar | Strong (as statistics) | Not used (they size the error bars); on the `not_material` list |

## 4. Fine now, worse later

These changes would not show at incoming QC or formation, or would show only a small part of their cost. The rest
appears after cycling or under fast charge.
- **Si dose and Si grade** (`bright_solid_frac`, `bright_contrast_ratio`, `bright_internal_dark_frac`).
  - Formation shows only part of the cost: the first-cycle Li loss.
  - Swelling, damage and the faster fade of the Si fraction build up over cycling [1–3, 6].
  - A Si product of a different grade or structure changes capacity, ICE and swelling together [4, 5, 11, 12].
  - This is the open question for B1's 2316 spots (2.5–3× the Si area, a darker and more textured phase): settle it
    with EDS before release.
- **Si size and clustering** (`bright_d90_um`, `bright_agglom_d50_um`, `bright_excess_het_ratio`, `s2_bright_*`).
  - A coarse Si tail cracks, pulverises and loses contact over repeated swelling [1, 7].
  - Dense aggregates fade fast [9].
  - Clusters as local swelling hot-spots is an inference [2, 9].
  - Outside 2316, neither lot shows coarsening or clustering beyond the baseline.
- **Si wiring** (`bright_contact_pore_frac`). Si that starts with less carbon contact can become isolated as it
  swells and shrinks. Loss of active Si is a main fade mode in graphite–Si electrodes [3, 10]; applying that to this
  column is an inference.
- **Surface and cracks** (`interface_density_per_um` up, `solid_lt_d50_um` down, `bright_n_per_1000um2` up;
  `bright_internal_dark_frac` if SE imaging shows cracks). More accessible surface means more first-cycle Li loss
  [14, 15]. Fresh crack surface grows SEI and costs Li (shown for graphite, applied to Si by analogy [14]).
- **Transport hot-spots** (`flake_orient_order` and `solid_chord_hv_ratio` up, `porosity_excess_het_ratio` up (no
  longer a column),
  `porosity_open_frac` down). Through-plane tortuosity and dense patches raise the risk of Li plating at fast charge
  [17, 18, 25, 31]. That risk appears under fast charge, not in a slow formation test. Both incoming lots are flat on
  alignment and pore patchiness. B1's porosity hint points the harmful way, mildly.

## 5. The team's original features

Their five folders (`porosity/`, `bright_phase/`, `pore_size/`, `particle_size/`, `histogram_anomaly/`) have been
moved to `features/_retired/<name>/`. Their code and READMEs are kept for reference, but their columns are no longer
computed. Status follows `notes/research_report.md` §3 ("Existing
features: keep or fix"). Numbers are from the final run (`processed/robustness.csv`, `processed/rankings.csv`).

| Column | What it means | Kept or superseded, and why | Replaced by |
|---|---|---|---|
| `porosity_frac` | Void fraction from a multi-Otsu split of the raw BSE image | **Kept as a concept, rebuilt and renamed**: noise is matched before thresholding, and the value is presented as a relative index. The old column reads the same way (B1 0.086, B2 0.098, B3 0.107) but is more acquisition-sensitive: perturbation ratio 0.62 (fails the 0.5 bar), session R² 0.69, within p 0.18 | [`porosity_open_frac`](open_porosity/README.md) (Tier 1; perturbation ratio 0.43) |
| `bright_phase_frac` | The top multi-Otsu class as a fraction of the image | **Superseded.** It picks different grey populations in different sessions: session R² 0.95, ICC 0.73, perturbation ratio 0.81. It reads 0.187 / 0.202 at 2316 | [`bright_solid_frac`](si_fraction/README.md) (fraction of solid, perturbation ratio 0.14), with [`bright_fixed_solid_frac`](si_fraction/README.md) as its identity check |
| `pore_size_median_um2`, `pore_size_p90_um2` | Area of connected pore objects | **Superseded.** They are noise-driven (r −0.71 with noise σ, report §3), session R² 0.92 / 0.87, perturbation ratio 2.95 / 1.19. The screen calls the median "separates" (sep 0.85, q 0.039), but within p is 0.51: that is acquisition | [`pore_lt_d50_um`, `pore_lt_d90_um`](local_thickness/README.md) (no pore splitting; perturbation ratio 0.27 / 0.21) |
| `pore_size_count_per_1000um2` | Number of connected pore components per area | **Dropped as a material KPI.** It counts pieces of a 3D-connected network plus speckle. Session R² 0.81, within p 0.46, perturbation ratio 1.58 | Nearest successor: [`pore_n_per_1000um2`](minkowski_functionals/README.md) (objects ≥ 64 px on the harmonised mask; a Tier 3 diagnostic, still a "neither" descriptor) |
| `particle_size_d10_um`, `_d50_um`, `_d90_um` | Watershed equivalent-circle diameter of the solid | **Retired as a PSD analogue**: the watershed cuts 10–40 µm flakes into ≈ 1 µm pieces. d50 was kept under investigation for its early within-session signal (p 0.026). On the final run that signal is p 0.13 (B1 +2.06 SD), and the perturbation ratios are 1.12–1.48, all failing the bar | [`solid_chord_y_um`](chord_length/README.md) (graphite-size stand-in, a Tier 3 diagnostic) and [`solid_lt_d50_um`](local_thickness/README.md). They measure something different (r 0.06 between `solid_lt_d50_um` and `particle_size_d50_um`) |
| `histogram_anomaly_z` | Mean \|z\| of a spot's BSE histogram against the baseline histograms | **Demoted** to an acquisition-novelty diagnostic. Session R² 0.94, perturbation ratio 6.08, within p 0.89. It reads 3.02 / 3.18 at 2316, but it mostly tracks how the image was taken. Not in the verdict | Imaging novelty: the [`acq_`](../preprocessing/acquisition.md) check in preprocessing. Material novelty: the verdict's kNN novelty check on the Tier 1 and Tier 2 KPIs (`analysis/verdict_config.yaml`) |

## 6. Links and references

- The research synthesis, the empirical feature screen and the per-batch certificates this document was written
  against are in the team's first repository and were not carried over. Their successors here are `ledger/`
  (feature ideas with papers and results), `literature/` (feature to battery-outcome evidence) and `qc/verdict.py`.
- Numbers: `processed/rankings.csv` (sep, q), `processed/robustness.csv` (within-session test, session R²,
  perturbation ratios), `processed/features.csv`. The detail behind every row is in the folder README it links to.

References. Every DOI comes from `ledger/entries/*.yaml`. The claims follow the folder READMEs, which say where a
claim was checked only against a title or against `notes/research_report.md`.

1. Obrovac & Chevrier 2014, Chem. Rev. (alloy negative electrodes). https://doi.org/10.1021/cr500207g
2. Moyassari et al. 2022, J. Electrochem. Soc. (Si content: capacity, cycle stability, expansion). https://doi.org/10.1149/1945-7111/ac4545
3. Kirkaldy et al. 2022, ACS Appl. Energy Mater. (rapid loss of active Si). https://doi.org/10.1021/acsaem.2c02047
4. Liu et al. 2019, Chem. Soc. Rev. (silicon oxides). https://doi.org/10.1039/c8cs00441b
5. Wu et al. 2024, Adv. Mater. (low ICE of SiOx). https://doi.org/10.1002/adma.202405751
6. Moon et al. 2021, Nat. Commun. (Si–graphite degradation, Si particle size). https://doi.org/10.1038/s41467-021-22662-7
7. Liu et al. 2012, ACS Nano (size-dependent fracture of Si). https://doi.org/10.1021/nn204476h
8. Wu et al. 2018, RSC Adv. (micro-SiOx/C PSD optimum). https://doi.org/10.1039/c8ra00539g
9. Schott et al. 2017, J. Phys. Chem. C (Si aggregates vs mesoporosity; nano-Si analogy). https://doi.org/10.1021/acs.jpcc.7b08457
10. Son et al. 2018, Adv. Sci. (cascading failure in graphite–Si). https://doi.org/10.1002/advs.201801007
11. Chae et al. 2021, Adv. Mater. (micrometre porous Si/C by pitch impregnation). https://doi.org/10.1002/adma.202103095
12. Yan et al. 2020, ACS Appl. Mater. Interfaces (pre-lithiated SiOx/C, high ICE). https://doi.org/10.1021/acsami.0c05153
13. Goldstein et al. 2018, Scanning Electron Microscopy and X-Ray Microanalysis (BSE contrast, channelling). https://doi.org/10.1007/978-1-4939-6676-9
14. Winter, Novák & Monnier 1998, J. Electrochem. Soc. (graphite surface and first-cycle loss). https://doi.org/10.1149/1.1838281
15. Joho et al. 2001, J. Power Sources (surface, pore structure and first-cycle charge loss). https://doi.org/10.1016/s0378-7753(01)00595-x
16. Liu et al. 2022, Materials (nano-graphite rate; direction only). https://doi.org/10.3390/ma15155148
17. Ebner et al. 2014, Adv. Energy Mater. (tortuosity anisotropy). https://doi.org/10.1002/aenm.201301278
18. Colclasure et al. 2019, J. Electrochem. Soc. (extreme fast charge without plating). https://doi.org/10.1149/2.0451908jes
19. Sheng et al. 2014, Front. Energy Res. (calendering and wettability). https://doi.org/10.3389/fenrg.2014.00056
20. Washburn 1921, Phys. Rev. (capillary flow). https://doi.org/10.1103/PhysRev.17.273
21. Holzer et al. 2013, J. Mater. Sci. (constrictivity). https://doi.org/10.1007/s10853-012-6968-z
22. Weng et al. 2023, Nano-Micro Lett. (kinetic limits of graphite for fast charge). https://doi.org/10.1007/s40820-023-01183-6
23. Choi et al. 2023, Materials (reassembled fine graphite). https://doi.org/10.3390/ma16216896
24. Billaud et al. 2016, Nat. Energy (magnetically aligned graphite). https://doi.org/10.1038/nenergy.2016.97
25. Parmananda et al. 2022, ACS Appl. Mater. Interfaces (multiscale heterogeneity of graphite, extreme fast charge). https://doi.org/10.1021/acsami.1c25214
26. Controlling the crystallographic orientation of graphite electrodes for fast-charging Li-ion batteries, 2021, ACS Appl. Mater. Interfaces. https://doi.org/10.1021/acsami.1c19735
27. Gao & Xu 2024, Small Sci. (impedance inhomogeneity in SiO/graphite). https://doi.org/10.1002/smsc.202300291
28. Kitamura, Tanaka & Mori 2022, J. Colloid Interface Sci. (mixing sequence, dispersion, resistance). https://doi.org/10.1016/j.jcis.2022.06.006
29. Armstrong et al. 2022, J. Power Sources (Si–graphite homogeneity; counterpoint). https://doi.org/10.1016/j.jpowsour.2021.230671
30. Kabra et al. 2020, ACS Appl. Mater. Interfaces (microstructure and Li plating). https://doi.org/10.1021/acsami.0c15144
31. Choi et al. 2026, Adv. Sci. (staging heterogeneity before Li plating). https://doi.org/10.1002/advs.77918
32. Zhao et al. 2022, Adv. Mater. (natural graphite in LIBs). https://doi.org/10.1002/adma.202106704
33. Dahari et al. 2025, Adv. Sci. (representativity from a single image). https://doi.org/10.1002/advs.202414149
34. Kapoor & Narayanan 2023, Patterns (leakage in ML-based science). https://doi.org/10.1016/j.patter.2023.100804
35. Roldan et al. 2024, J. Microsc. (FIB-SEM image-quality indices). https://doi.org/10.1111/jmi.13254
36. Kim et al. 2019, Microsc. Microanal. (curtain filtering on a Si/C–graphite anode). https://doi.org/10.1017/S1431927619014752
37. Prill et al. 2013, J. Microsc. (FIB-SEM segmentation of porous media, shine-through). https://doi.org/10.1111/jmi.12021
