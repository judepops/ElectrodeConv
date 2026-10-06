# particle_size (retired)

The number-weighted equivalent-circle diameters (d10 / d50 / d90) of the watershed cells into which the solid of
the old multi-Otsu BSE pore mask is cut, one cell per distance-map maximum. It was named a "particle size", but it
measures how far apart the pores are, not the graphite particles. It added three columns to
`processed/features.csv`, and it is no longer computed.

| Column | Unit | Meaning |
|---|---|---|
| `particle_size_d10_um` | µm | 10th percentile of the cell ECDs (number-weighted): the smallest pore-bounded solid cells, set by closely spaced pores and the 0.125 µm² size floor |
| `particle_size_d50_um` | µm | Median cell ECD. **Not a particle D50**: a solid with random pores and no particles at all gives the same 3.3–4.5 µm |
| `particle_size_d90_um` | µm | 90th percentile: the largest pore-free solid cells. Within sessions it tracks the solid local thickness (r 0.73 with `solid_lt_d50_um`) |

## Status

**Retired on 2026-10-03.** Commit 84cb17c moved this folder unchanged from `features/particle_size` to
`features/_retired/particle_size`. `feature_dirs()` skips folders whose names start with `_` (`features/__init__.py:40-42`),
so the three columns are no longer in `processed/features.csv`, the v1.1 decision rule or the dashboard. The audit
numbers below were computed on b0b5841, before the move, with the same code.

| Retired folder | Columns | Superseded by |
|---|---|---|
| `porosity/` | `porosity_frac` | `open_porosity` → `porosity_open_frac` |
| `bright_phase/` | `bright_phase_frac` | `si_fraction` → `bright_solid_frac` |
| `pore_size/` | `pore_size_median_um2`, `_p90_um2`, `_count_per_1000um2` | `local_thickness` → `pore_lt_d50_um`, `pore_lt_d90_um`; `minkowski_functionals` → `pore_n_per_1000um2` |
| `particle_size/` (this one) | `particle_size_d10/d50/d90_um` | **No full replacement yet.** Graphite flake-size features are being researched (ledger `flake_morphology`, status in_progress) |
| `histogram_anomaly/` | `histogram_anomaly_z` | Acquisition-novelty diagnostic only |

- **Why there is no replacement.** Graphite particles in a calendered electrode touch without a visible pore
  between them, so a pore mask alone cannot separate them. A first attempt to cut flakes on Inlens ridges and BSE
  valleys was not reliable either (split-half r 0.02–0.34, perturbation 0.6–1.5 SD; `notes/feature_screen.md:462`).
- **Nearest harmonised size descriptors.** None of them is a PSD; each measures something defined and reproducible:
  - `solid_chord_x_um` / `solid_chord_y_um` (`chord_length`, the research report's graphite-size stand-in);
  - `solid_lt_d50_um` (`local_thickness`);
  - `s2_solid_corrlen_x_um` / `_y_um` (`two_point_correlation`).

  Within sessions d50 correlates with `solid_chord_x_um` (r 0.46) and d90 with `solid_lt_d50_um` (r 0.73).
- **Why it is kept** (as code: `import features._retired.particle_size.feature` before `features.compute_all(sample)`;
  this also imports and registers the retired `porosity_frac`):
  - **Comparability.** Every "watershed d50" number in `notes/research_report.md` (§1 line 32, §3 rank 14 and the
    keep-or-fix table, §6.1 variance components, §7), `notes/feature_screen.md` and the first `rank_features.py`
    runs came from this code.
  - **A record of a negative result.** The report's "only acquisition-controlled signal" (d50, p = 0.026) does not
    reproduce (see *Evidence*). This README is where that is written down.

  Do not use it for decisions, and do not quote it as a particle size.

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `particle_size_d50_um` up (`d10` reads the same way) | **What it actually tracks:** larger pore-bounded solid cells, i.e. pores further apart. On our data that comes with lower porosity (within-session r −0.60 with `porosity_frac`; r −0.86 between the d50 and porosity shifts of 32 perturbed runs) or with a tone-curve change (gamma). **If it were a real graphite size increase** (it is not; see *What it measures*): longer solid-state diffusion paths, so lower rate and, from coarse particles, more Li plating at fast charge [9, 10]; less surface, so less SEI and lower first-cycle loss [7, 8] | **Neither**: not readable as particle size | Low |
| `particle_size_d50_um` down (`d10` the same) | **Tracks:** pores closer together (more or finer pores, higher porosity), or the opposite tone-curve change. **A real graphite size decrease** would mean more surface, so more SEI and first-cycle loss [7, 8], better rate down to a limit [9, 10], and fewer SEI-breakage and exfoliation losses at fast charge [11] | **Neither** | Low |
| `particle_size_d90_um` up / down | **Tracks:** the largest pore-free stretches of solid. Pore-free bands in a phantom raise d90 from 5.8–6.8 to 8.1–9.9 µm at the same d50, and within sessions d90 follows `solid_lt_d50_um` (r 0.73). Read `solid_lt_d50_um` instead; it measures this directly | **Neither** | Low |

**Best value:** none. The columns are not a material property with a target. For a real graphite PSD the target
would be the baseline lot or the supplier specification, because any shift means a different powder lot, milling
or classification step.

**Our batches** (independent audit, run2 scorecard; B3-SD = between-site SD within Batch_3):
- **Batch_1: no established difference.** d50 3.738 ± 0.145 vs B3 3.605 ± 0.109 µm (+1.2 B3-SD marginal). Within
  sessions +2.06 SD, exact p = 0.13. The coefficient rests on one spot (ffwubibz): without it +0.58 SD, p = 0.22.
  d90 is +0.74 SD marginal and +1.36 SD within sessions (p = 0.057).
- **Batch_2: no established difference.** d50 3.592 ± 0.085 µm (−0.12 SD; within sessions −0.28 SD). d90
  7.166 ± 0.280 vs 7.003 ± 0.267 µm (+0.61 SD; within sessions +1.41 SD).
- For both batches, the single-image bootstrap SE of d50 (0.108–0.122 µm) is as large as the whole B3 between-site
  SD (0.109 µm), so no single spot can be read.

## What it measures

The solid is everything the old BSE pore mask does not call pore: graphite, the bright Si-based phase, the
carbon-binder web and the pore-back surfaces seen through open pores. For each solid pixel the code computes the
distance to the nearest pore pixel. A "centre" is placed at every local maximum of that distance map that lies at
least 125 nm from any pore and at least 1 µm from the next centre. Regions are then grown from the centres out to
the pore edges (watershed), and the code reports the equivalent-circle diameter (ECD) of each region. d10/d50/d90
are percentiles of the *list of regions*, so every region counts once, whatever its size.

The watershed boundaries fall where pores are; where there is no pore, they fall on the saddles of the distance map
between neighbouring pores. A graphite particle is therefore found as one region only if its contacts with its
neighbours show up as pore pixels. In a calendered electrode they mostly do not. The audit tested this on synthetic
masks with the production parameters (G3, `ps_phantom.py`):

| Synthetic solid | Truth | What the code returns |
|---|---|---|
| Isolated disk | ECD 10.0 µm | 1 region, 10.0 µm (exact) |
| Isolated ellipse flake, 20 × 4 µm | ECD 8.9 µm | 4 regions (6.0, 5.8, 2.2, 2.2 µm) |
| Isolated rectangular flake, 20 × 4 µm | ECD 10.1 µm | 17 regions, the largest 3.6 µm (a flat distance ridge has many maxima) |
| Voronoi particles, median ECD 13.3 µm, contacts visible as 0.2 µm gaps | 13.3 µm | 72 regions, d50 12.2 µm |
| The same particles, contacts not visible | 13.3 µm | 1 region of 105.6 µm |
| Solid with random pores and **no particles at all**, porosity 0.047 / 0.068 / 0.091 | no particles | d50 4.47 / 4.20 / 3.72 µm |

So the code sizes particles only where their contacts appear in the pore mask. Elsewhere it returns the size of the
solid cells between pores, which gets smaller as porosity rises. The real data sit at d50 3.43–3.97 µm, which is
exactly the particle-free range. A typical supplier graphite D50 is 17–21 µm (laser diffraction, volume-weighted;
`notes/research_report.md` §2). Even the area-weighted median of these regions is only 5.6–6.8 µm.

## Why it matters for the battery

The mechanisms below are why a real graphite particle-size distribution (PSD) would matter. **This column cannot
deliver any of them.** They are listed so a reader knows what the name promised and what a working replacement
(`flake_morphology`) must capture.

- **Rate and lithium plating.** Li⁺ must diffuse into each particle. Weng et al. find that the rate-determining step
  depends on particle size: below about 10 µm, interfacial Li⁺ transfer and electrode transport dominate rather than
  diffusion inside the particle, and slow intercalation leads to Li plating [10]. Bläubaum et al. find that a narrow
  distribution of smaller spherical graphite performs better than broad, coarse ones, that extremely small particles
  hurt again, and that coarse particles promote Li plating whatever the PSD shape [9]. Röder et al. model how a wide
  PSD makes surface overpotentials and reaction rates uneven between particles [13].
- **Surface area, SEI and first-cycle loss.** Winter et al. correlate the first-cycle charge loss of graphites with
  their BET surface [7]. Zaghib et al. study how graphite particle size changes the irreversible capacity loss [8].
  Smaller particles mean more surface, so more SEI and a lower ICE (the direction is general knowledge; refs 7 and 8
  are checked by title only).
- **Fast-charge ageing.** Zhang et al. find that SEI breakage, graphite exfoliation and electrolyte decomposition
  drive fade in fast charge, and that smaller graphite suppresses them. Rate did not improve in their cells, because
  the NMC811 cathode limited it [11].
- **Graphite–Si blends** (our material is graphite + a SiOx-like phase). Jeschull et al. show that the choice of
  graphite, including its particle size, changes the electrode morphology (void space, Si distribution) and the
  capacity retention of graphite–Si electrodes. Blending in smaller graphite improved Coulombic efficiency without
  hurting cycling, while extra calendering generally made retention worse [12].
- **Flake shape and alignment.** Electrode tortuosity is anisotropic [14]: in graphite anodes, platelets aligned
  by coating and calendering make the through-plane path longer than the in-plane one (mechanism as summarised in
  `notes/research_report.md` §8; ref 14 checked by title only). A flake-size feature should therefore report
  thickness and aspect, not one ECD.

## Industry / Polaron use

- **Suppliers and cell makers** quote PSD as volume-weighted D10/D50/D90 from laser diffraction of the powder (ISO
  13320), a standard CoA item (GB/T 24533; example TDS: Targray PGPT350, D50 17–21 µm; `notes/research_report.md`
  §2, line 102). A 2D number-weighted ECD from a calendered cross-section is not comparable with it. Sections cut
  particles off-centre (the Wicksell problem [4]; [5]), and different geometric definitions of "size" give different
  numbers for the same structure [6].
- **Image-based particle sizing** (watershed splitting on 3D tomography in Avizo, GeoDict or MATBOX) is used in
  academia and by imaging vendors. We have no evidence that Polaron or a cell maker uses a 2D watershed ECD on
  cross-sections as a QC metric.
- **What would move a real graphite PSD:** the graphite source or grade, the supplier's milling, spheroidisation or
  classification, and slurry mixing: longer milling in slurry making breaks large graphite particles [11].
  Calendering can also crack particles (general knowledge).
- **What moves this column:** porosity and pore spacing (calendering, coat weight, slurry), the multi-Otsu pore
  threshold (tone curve, bright-phase content), and the frame size (see *Uncertainty*).

## How it is computed

Detector: BSE only, on the **processed** image `sample.bse` (not the raw TIF and not the harmonisation in
`features/_common`). The whole trimmed frame is used (≈ 7000 × 1612–2316 px, ≈ 7 000–10 000 µm²), not the
harmonised central crop.

1. **Clean image** (`preprocessing/process_data.py`):
   - read the first channel of the TIF (`load_grey`, :74-77);
   - drop edge rows/columns in which ≥ 95 % of pixels are ≥ 245 or ≤ 10 (`trim_border`, :80-97);
   - stretch the 1st–99th percentile to 0–255, clipping 1 % at each end (`normalise_brightness`, :100-107).
2. **Pore mask** (`features/_retired/porosity/feature.py:21-34`, `porosity/config.yaml`):
   - Gaussian blur σ = 2 px (`blur_sigma_px`, 50 nm). The blurred image stays 8-bit: scipy keeps the input dtype and
     truncates.
   - Three-class multi-Otsu (`classes: 3`) on every 4th pixel in each direction (`subsample: 4`) gives two
     thresholds, cast to `int`.
   - pore = blurred < lower threshold. The thresholds are recomputed for every image and cached per sample.
3. **Subsample** (`feature.py:31-32`): solid = NOT pore, taking every 2nd pixel (`scale: 2`, 50 nm/px, striding
   without averaging). The config comment's "diameters within ~2 %" was not re-checked by the audit.
4. **Distance map** (`:33`): Euclidean distance from each solid pixel to the nearest pore pixel. The frame edge does
   not count as pore.
5. **Centres** (`:34-35`): `peak_local_max` with `min_distance_px: 20` (1 µm between centres),
   `min_centre_depth_px: 2.5` (≥ 125 nm from any pore) and `exclude_border=False`.
6. **Watershed** (`:36-38`): centres labelled 1…N, watershed on −distance inside the solid. Solid slivers with no
   centre (thinner than ≈ 0.25 µm) stay unlabelled and are ignored.
7. **Sizes** (`:42-51`):
   - pixel count per region; regions < 50 px at scale (`min_particle_px`, 0.125 µm², ECD 0.40 µm) are dropped;
   - area = px × 0.05² µm² and ECD = 2√(area/π);
   - `np.percentile` (linear interpolation) gives d10/d50/d90 over the region list, so they are number-weighted;
   - there is no edge correction: regions cut by the frame are kept as they are;
   - all three columns are NaN if no region survives.

A typical image gives 370–475 regions (47–57 per 1000 µm² over the 31 spots). The noise top-up used by the
harmonised features is not applied, so the result is deterministic.

## Evidence on our data

All 31 spots, run on Modal from the raw TIFs with the production code at b0b5841 (independent audit,
`run2/out/scorecard.csv`; follow-ups in `wf/graphite`, `wf/graphite_verify`). B3-SD = between-site SD within Batch_3.
Session R² by chance ≈ 0.40 (13 height groups, 31 spots). Within-session p: exact permutation of batch labels inside
the 5 mixed sessions, OLS y ~ C(session) + C(batch), 192 relabellings, minimum ≈ 0.005. Incoming p: the same test
with one df (B1 + B2 vs B3), 24 arrangements, minimum 0.042.

### Scorecard

| | `particle_size_d10_um` | `particle_size_d50_um` | `particle_size_d90_um` |
|---|---|---|---|
| B1 / B2 / B3 mean ± SD (µm) | 1.962 ± 0.083 / 1.901 ± 0.095 / 1.961 ± 0.090 | 3.738 ± 0.145 / 3.592 ± 0.085 / 3.605 ± 0.109 | 7.201 ± 0.208 / 7.166 ± 0.280 / 7.003 ± 0.267 |
| η²(batch); without the two 2316 spots | 0.08; 0.08 | 0.22; 0.15 | 0.12; 0.08 |
| session R² (chance 0.40) | 0.39 | 0.32 | 0.38 |
| within-session p (b1, b2 in B3-SD) | 0.40 (+0.58, −0.41) | 0.13 (+2.06, −0.28) | 0.057 (+1.36, +1.41) |
| incoming p (B1+B2 vs B3, b in B3-SD) | 0.71 (−0.24) | 0.96 (+0.12) | **0.042** (+1.40), the floor |
| B3 variance components σ_site / σ_session (µm); ICC | 0.085 / 0.029; 0.10 | 0.103 / 0.038; 0.12 | 0.281 / 0.000; 0.00 |
| split-half r, left/right; top/bottom | 0.36; 0.17 | 0.23; 0.33 | 0.12; 0.12 |
| mean \|half − half\| (B3-SD), x; y | 1.13; 1.51 | 1.46; 1.34 | 1.12; 1.47 |
| seed spread / B3-SD | 0 (deterministic) | 0 | 0 |
| perturbation ratio (worst kind) | 1.12 (gamma 1.25) | 1.44 (gamma 1.25) | 1.48 (gamma 1.25) |
| lifted-black session 2060, z | +0.84 | +0.57 | −0.23 |
| LOSO AUC, B1 vs B3; B2 vs B3 | 0.19; 0.61 | 0.74; 0.23 | 0.76; 0.76 |
| phantom error | none: no particle truth exists (see below) | | |
| scorecard heuristic → reviewed verdict | unreliable → **drop** | unreliable → **drop** | unreliable → **unreliable** |

The `rank_features.py` screen (permutes across all spots, no session control; ledger entry) gave sep 0.39 / 0.71 /
0.41, q 0.34 / 0.10 / 0.21 and sep_loo 0.26 / 0.56 / 0.35, i.e. "no difference" for all three.

### What the numbers say

- **Low session R² is not robustness.** The columns sit at the 0.40 chance level only because they are mostly
  site-level noise. The ICC is 0.00–0.12, split-half r is 0.12–0.36, and the two halves of one image differ on average
  by 1.1–1.5 B3-SD.
- **Sampling error equals the whole baseline spread** (G4). The i.i.d. bootstrap over regions at three B3 sites
  (372–474 regions each) gives these SEs:

  | Site (session) | SE of d10 / d50 / d90 (µm) |
  |---|---|
  | cfe5vt7s (2080) | 0.075 / 0.108 / 0.175 |
  | xgj4xftb (1612) | 0.113 / 0.122 / 0.259 |
  | x7u69zsw (2060) | 0.062 / 0.120 / 0.219 |

  The B3 between-site SD is 0.090 / 0.109 / 0.267 µm, so the SE of d50 is 1.0–1.1× it. The bootstrap ignores
  spatial correlation, so it understates the SE.
- **The research report's d50 signal does not reproduce** (G5). The report quoted within-session p = 0.026 (B1 > B2
  in 3 of 3 pairs). The exact permutation test gives p = 0.13. A parametric F-test for the batch term gives 0.037,
  which is probably where 0.026 came from. Both fail once the single spot ffwubibz (B1, session 2080) is removed:
  - ffwubibz has the largest d50 of all 31 spots (3.971 µm) and supplies the +3.30 SD B1–B3 contrast in 2080;
  - without it, B1 falls from +2.06 to +0.58 SD (+0.063 µm), with exact p = 0.22 (64 relabellings) and parametric
    p = 0.35;
  - `notes/feature_screen.md:102` had already reported p = 0.27, "driven by the single 2080 site".
- **d90's p = 0.042 is not a finding.** All four B1/B2-vs-B3 contrasts are positive (2068 +2.77, 2080 +0.10 and
  +0.51, 2272 +0.81 SD), which is the minimum attainable p. But 5 of 58 material columns reach that floor, against
  2.4 expected by chance. d90 also has split-half r 0.12, a gamma ratio of 1.48 and a bootstrap SE of 66 % of the
  B3 SD. Within sessions it is largely `solid_lt_d50_um` (r 0.73), which has its own README and a defined meaning.
- **It follows porosity** (G3):
  - session-demeaned r(d50, `porosity_frac`) = −0.60;
  - across the 32 perturbed runs, the d50 shift tracks the porosity shift (r = −0.86, p = 3 × 10⁻¹⁰);
  - gamma 1.25 raises porosity by 0.002–0.012 and moves d50 by −0.011 to −0.157 µm; gamma 0.8 lowers porosity and
    raises d50 by 0.074–0.123 µm.
- **Particle-free phantoms give the real-data values.** The audit's 18 rendered phantoms have a uniform graphite
  matrix, random pore ellipses or disks, Si ellipses and *no graphite particle boundaries*. Run through the full
  image pipeline they give:
  - d50 3.34–4.10 µm (mean 3.68 ± 0.19), against 3.43–3.97 µm on the 31 real spots;
  - d90 5.8–6.8 µm with uniform pores and 8.1–9.9 µm when the pores are confined to bands (`patchy`).

  The `:ideal` variants are identical, because this feature does not read the harmonised masks that the ideal
  variant replaces. That is why the scorecard has no phantom error for these columns.
- **The harmonised void does not rescue it.** The same watershed on `h.void` (`rv_ps_hv_*`, `wf/graphite`) gives d50
  B1 3.825 / B2 3.663 / B3 3.662 µm, with session R² 0.55. The definition, not the mask, is the problem.
- **Acquisition.** black +25 changes nothing (ratio 0 for all three), because the 1–99 % stretch removes an offset.
  The lifted-black session 2060 is unremarkable (z −0.23 to +0.84). Gamma is the dominant sensitivity (0.73–1.48).
  Blur and noise also fail the 0.5 bar of the R2 invariance gate (`analysis/verdict_config.yaml:53`): d10 blur 0.85
  and noise σ = 4 0.77, d50 y-blur 0.84 and blur 0.75, d90 y-blur 0.74. The cells respond to how thin pores render.

**Verdict:** d10 and d50 drop; d90 unreliable. Not usable for explanation or categorisation. The phenomenon it
picks up (pore spacing, thick solid ligaments) is measured better by `solid_chord_x_um` / `solid_chord_y_um`
(perturbation 0.53 / 0.62, split-half r 0.58–0.76) and `solid_lt_d50_um`.

## Uncertainty and pitfalls

- **Definition.** Touching particles merge (13.3 µm Voronoi particles → one 105.6 µm region). Flat flakes split
  into 4–17 regions. A particle-free solid gives the same d50 as the data. The bias therefore depends on porosity
  and on the stretch-dependent multi-Otsu threshold, so it differs between sites. The docstring's "Same bias for
  every batch, so batch differences are still meaningful" (`feature.py:11-12`) and "d10 / d50 / d90 are what a
  powder supplier quotes" (`feature.py:6-7`) are both wrong.
- **Number- vs volume-weighting, 2D vs 3D.**
  - The columns are number-weighted percentiles of 2D section areas. A supplier PSD is volume-weighted and 3D.
  - Random sections cut particles off-centre, so section diameters underestimate particle diameters and broaden
    the distribution (Wicksell [4]; [5]).
  - Even the area-weighted region median (5.6–6.8 µm) is a third of a typical supplier D50.
  - No stereological correction is valid here, because the regions are not particles.
- **Sampling.** One image holds ≈ 370–475 regions. The d50 SE (0.11–0.12 µm) equals the B3 between-site SD. A
  cell-size statistic, if one were ever kept, would need site-bootstrap CIs pooled per session or batch, not
  single-spot values.
- **Frame edge and frame size** (G9):
  - 16–26 % of the regions touch the frame edge and are truncated. That share is a session property (session
    R² 0.76; Spearman ρ −0.67 with frame height, p = 3 × 10⁻⁵).
  - Dropping edge regions raises the B3 mean d50 from 3.605 to 3.721 µm (+1.06 B3-SD) and leaves the batch pattern
    unchanged (B1 3.856, B2 3.708).
  - Halving the frame height lowers the mean d50 by 0.11–0.18 µm (top/bottom halves 3.449 / 3.518 vs full 3.632);
    halving the width lowers it by 0.01–0.08 µm.
  - d50 itself is not significantly related to frame height over 1612–2316 px (ρ 0.20, p = 0.28). It is still a
    session-linked bias that grows with smaller frames.
- **Tone curve.** The pore threshold is a multi-Otsu cut on the 1–99 % stretched image. The stretch depends on
  how much bright phase and black the frame holds (`process_data.py:166-170`). Gamma ±25 % moves the columns by
  0.7–1.5 B3-SD.
- **Whole frame, artefact rows included.** Unlike the harmonised features, it runs on the full trimmed frame.
  Dropping the top 250 and bottom 25 rows changes the B3 mean d50 by only −0.006 µm, so this is minor.
- **Phase-blind.** Graphite, the Si-based phase, the carbon-binder web and pore-back all count as solid. A Si
  particle inside graphite is not separated unless a pore surrounds it.
- **3D validity.** None as a particle size. As a "pore-spacing" index it is a 2D relative measure with no
  established 3D link.

## References

All DOIs were checked against the Crossref API on 2026-10-03 (title, authors, year, journal). Refs 8–13 were found
in the offline index `literature.load_papers`. Their battery claims are taken from the Crossref abstracts,
except ref 8, which has no abstract on Crossref and is cited for its title only. Refs 7 and 14 have no Crossref
abstract either: they are cited for their titles, and the ICE direction for ref 7 is general knowledge. The methods
references (1–6) are cited for the algorithm or concept named in their titles. `skimage.filters.threshold_multiotsu`
implements the multilevel extension of ref 1 (Liao et al. 2001; general knowledge, DOI not checked).

1. Otsu, N. (1979) A threshold selection method from gray-level histograms. *IEEE Trans. Syst. Man Cybern.* 9:62–66.
   https://doi.org/10.1109/tsmc.1979.4310076
2. Vincent, L. & Soille, P. (1991) Watersheds in digital spaces: an efficient algorithm based on immersion
   simulations. *IEEE Trans. Pattern Anal. Mach. Intell.* 13:583–598. https://doi.org/10.1109/34.87344 (also
   verified in the ledger entry)
3. Meyer, F. & Beucher, S. (1990) Morphological segmentation. *J. Vis. Commun. Image Represent.* 1:21–46.
   https://doi.org/10.1016/1047-3203(90)90014-m (marker-controlled watershed, the distance-map splitting used here)
4. Wicksell, S. D. (1925) The corpuscle problem: a mathematical study of a biometric problem. *Biometrika*
   17:84–99. https://doi.org/10.1093/biomet/17.1-2.84 (sizes of 3D particles from 2D sections)
5. Russ, J. C. & DeHoff, R. T. (2000) *Practical Stereology*, 2nd ed., Springer.
   https://doi.org/10.1007/978-1-4615-1233-2
6. Münch, B. & Holzer, L. (2008) Contradicting geometrical concepts in pore size analysis attained with electron
   microscopy and mercury intrusion. *J. Am. Ceram. Soc.* 91:4059–4067.
   https://doi.org/10.1111/j.1551-2916.2008.02736.x
7. Winter, M., Novák, P. & Monnier, A. (1998) Graphites for lithium-ion cells: the correlation of the first-cycle
   charge loss with the Brunauer-Emmett-Teller surface area. *J. Electrochem. Soc.* 145:428–436.
   https://doi.org/10.1149/1.1838281 (title only)
8. Zaghib, K., Nadeau, G. & Kinoshita, K. (2000) Effect of graphite particle size on irreversible capacity loss.
   *J. Electrochem. Soc.* 147:2110. https://doi.org/10.1149/1.1393493 (title only)
9. Bläubaum, L., Röder, F., Nowak, C., Chan, H. S., Kwade, A. & Krewer, U. (2020) Impact of particle size
   distribution on performance of lithium-ion batteries. *ChemElectroChem* 7:4755–4766.
   https://doi.org/10.1002/celc.202001249 (narrow, finer spherical-graphite PSD performs better; very small
   particles hurt; coarse particles promote Li plating)
10. Weng, S., Yang, G., Zhang, S., Liu, X. et al. (2023) Kinetic limits of graphite anode for fast-charging
    lithium-ion batteries. *Nano-Micro Lett.* 15:215. https://doi.org/10.1007/s40820-023-01183-6 (the rate-determining
    step depends on particle size; below about 10 µm, interfacial transfer and electrode transport dominate)
11. Zhang, S. S., Ma, L., Allen, J. L. & Read, J. A. (2021) Stabilizing capacity retention of Li-ion battery in
    fast-charge by reducing particle size of graphite. *J. Electrochem. Soc.* 168:040519.
    https://doi.org/10.1149/1945-7111/abf40c (smaller graphite suppresses SEI breakage and exfoliation; longer
    milling in slurry making reduces large graphite particles)
12. Jeschull, F., Surace, Y., Zürcher, S., Lari, G., Spahr, M. E., Novák, P. et al. (2020) Graphite particle-size
    induced morphological and performance changes of graphite–silicon electrodes. *J. Electrochem. Soc.*
    167:100535. https://doi.org/10.1149/1945-7111/ab9b9a
13. Röder, F., Sonntag, S., Schröder, D. & Krewer, U. (2016) Simulating the impact of particle size distribution on
    the performance of graphite electrodes in lithium-ion batteries. *Energy Technol.* 4:1588–1597.
    https://doi.org/10.1002/ente.201600232
14. Ebner, M., Chung, D.-W., García, R. E. & Wood, V. (2014; online 2013) Tortuosity anisotropy in lithium-ion
    battery electrodes. *Adv. Energy Mater.* 4:1301278. https://doi.org/10.1002/aenm.201301278 (title only here;
    also verified in the ledger)
15. Project sources:
    - `notes/research_report.md` §2 (CoA/PSD table, line 102; ISO 13320, GB/T 24533 and the Targray TDS are cited
      from there, no DOI), §1 line 32 and §3 line 196 (the superseded p = 0.026 claim and "keep d50 under
      investigation" call), §3 rank 14, §6.1 variance components;
    - `notes/feature_screen.md:102` and `:462`;
    - the ledger entries `particle_size.yaml` and `flake_morphology.yaml`;
    - the audit outputs `run2/out/scorecard.csv`, `rows.csv` and `phantoms_v2.csv`, and the verification notes
      G3, G4, G5 and G9 (`wf/graphite/ps_phantom.py`, `local_ps.py`, `diag_rows.csv`).
