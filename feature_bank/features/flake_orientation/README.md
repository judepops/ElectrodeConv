# flake_orientation

How well the graphite flakes lie flat in the electrode plane (the calendering texture), measured on the BSE
graphite/void boundaries with the structure tensor. It is an **expected-stable check** (a diagnostic in the
verdict): on our 31 spots the alignment shows no detectable difference between the three batches, so a large shift
on a new batch would be news. It adds two columns to `processed/features.csv`; the spread is computed in
`feature.py` only:

| Column | Unit | Meaning |
|---|---|---|
| `flake_orient_order` | dimensionless (-1 to 1) | nematic order S = ⟨cos 2θ⟩ of the local layer direction θ relative to the image horizontal, coherence-weighted, on graphite/void boundary pixels. 1 = all flake faces horizontal, 0 = isotropic |
| `flake_orient_spread_deg` | deg | axial circular SD of θ about its own mean, √(−2 ln R)/2 (R = mean resultant length of 2θ). 0 = perfect alignment, ≈ 60+ = isotropic. Does not change when the sample is tilted. **Not a features.csv column** (team audit 2026-10-03): ρ −0.98 with `flake_orient_order` |
| `flake_tilt_deg` | deg | mean layer direction, ½·arg Σ w e^{2iθ}, positive = counter-clockwise as displayed. **Diagnostic for sample mounting / scan rotation**, not a material property |

## Battery impact at a glance

`flake_orient_order` and `flake_orient_spread_deg` are one signal read two ways (r = −0.99 across spots), so they
share rows. The spread is not a features.csv column (team audit 2026-10-03): ρ −0.98 with `flake_orient_order`.

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| order **up** / spread **down** | Flakes lie flatter. Platelet shape and fabrication-induced alignment make the ion path through the coating thickness more tortuous than along it, which lowers through-plane electrolyte transport (X-ray tomography) [1, 2]. In image-based simulations of 14 CT-scanned graphite electrodes, this platelet tortuosity anisotropy dominated fast-charge capacity, heat and lithium plating [3]. Causes: harder calendering or a flakier graphite [1] | **bad** for rate and fast charge (more plating risk) at the same porosity. If harder calendering caused it, it is a **trade-off**: the electrode is also denser, i.e. more energy per volume (general knowledge; check `porosity_open_frac`) | moderate: 3D mechanism from tomography [1] and simulation [3], converse measured in cells [5]; our number is a 2D trace with no calibration to tortuosity |
| order **down** / spread **up** | Flakes less aligned, so through-plane transport improves: graphite magnetically oriented with its basal planes vertical reached 80 % SOC at 1C (CC-CV) in 50 instead of 138 min [5]. In a supplier lot it can mean a rounder (spheroidised) graphite [1, 4] or lighter calendering. Our 2D number also drops for non-material reasons: vertical FIB curtains [7] or extra isotropic bright particles near the boundaries | **trade-off**: better rate and fast charge [3, 5]; if lighter calendering caused it, the electrode is less dense (lower energy per volume; check porosity). If a different graphite caused it, it is also **a sign the supplier's process changed**, with other properties (capacity, first-cycle efficiency) not predicted by this column. Rule out curtains and the Si phase first | low–moderate: the transport direction is well established [1, 3, 5]; the cause behind a drop is ambiguous |
| `flake_tilt_deg` **up or down** | The section was mounted or scanned at a different angle. Says nothing about the material | **neither**: acquisition geometry. Read the tilt-invariant spread when \|tilt\| is large | strong (geometry) |

**Best value:** match the baseline. Lower alignment helps through-plane transport and higher alignment hurts it,
but in a supplier lot either shift usually travels with a change in calendering density or graphite shape, so the
net effect on the cell depends on porosity too. A real shift (once curtains, tilt and scan blur are ruled out) is a
sign that the graphite shape or the calendering changed; read it together with `porosity_open_frac` and
`solid_chord_hv_ratio`.

**Our batches** (final integrated run; `rankings.csv`, `robustness.csv`, certificates in `analysis/verdicts/`):

- **Batch_1:** S = 0.307 ± 0.058 vs 0.295 ± 0.063 in Batch_3 (+0.20 baseline SD); spread 43.7° vs 44.7°
  (−0.25 SD). Acquisition-controlled (inside the mixed sessions): +0.48 SD in S (95 % CI −1.4 to +2.4) and
  −0.63 SD in spread, exact within-session p = 0.66. The only direct B1–B3 comparison is one spot each in session
  2080; the rest comes indirectly through B2 in 2148 and 2156. Pooled: sep 0.10, q 0.97. No detectable difference.
- **2316 caveat (n_eff = 1 session):** the two Si-rich 2316 spots sit at z = −0.11 (4ih2ggld) and −1.38
  (5n1q8atc), both inside the baseline range (0.177–0.401); 5n1q8atc is the lowest B1 spot. 2316 also has the
  strongest FIB curtains (`acq_curtain_index` 1.64–1.68 vs a median of 1.04), and curtains lower S, so that dip
  cannot be assigned to the graphite. Without 2316, B1 is 0.331 (+0.58 SD; raw mean of 5 spots, not
  session-controlled), still inside the baseline scatter. 2316 holds no baseline spot, so it is not part of the
  within-session test. The column does not echo the Si-phase anomaly.
- **Batch_2:** S = 0.301 ± 0.069 (+0.10 SD); spread 44.2° (−0.13 SD). Acquisition-controlled: +0.56 SD in S
  (CI −0.9 to +2.0) and −0.55 SD in spread, p = 0.66; sep 0.10, q 0.97. B2 − B3 is positive in all three shared
  sessions (+0.03, +0.53, +1.73 SD), but the B2 term alone gives within-session p = 0.39 (same 192 relabellings),
  so this is not a shift. It is the same direction as the B2 SiOx-orientation lead (`bright_orient_order` +1.73 SD
  within sessions, p 0.17) but a third of its size: graphite alignment gives **no evidence** of stronger
  calendering in B2, yet cannot rule out a moderate one (CI up to +2.0 SD).
- **Verdict use:** `flake_orient_order` is a **diagnostic** (Tier 3) in v1.1: shown, never decisive. It left
  Tier 2 because its left/right split-half reliability r_x is 0.10 (bar 0.35). The certificates show B1 +0.20 SD
  and B2 +0.10 SD (screen q 0.81 / 0.96). It plays no part in either INVESTIGATE call. The spread (a duplicate, no
  longer a column) and the tilt (a mounting diagnostic, on the `not_material` list, so no classifier reads it) are
  not used by the verdict.
- **Reading:** no evidence of a calendering or graphite-shape change in either lot, but only large changes are
  excluded. Pooled over all spots, the 80 %-power detectable shift is ≈ 0.08 in S (≈ 1.3 SD, ≈ 27 % of the mean;
  `verdict.py` v1: 0.082 for B1, 0.084 for B2). With acquisition controlled, the intervals reach ≈ +2 SD.

## What it measures

The calendered anode is a stack of graphite flakes, typically 5–20 µm across, that lie roughly parallel to the
current collector. In the cross-section, the edges where a flake face meets a pore run mostly left–right. At
every pixel of the BSE image the structure tensor finds the dominant edge direction within about 0.4 µm [6]. The
layer direction θ is perpendicular to the brightness gradient. Each pixel is weighted by how clearly oriented
its neighbourhood is (coherence).

Only pixels on the boundary between graphite and open void are used. That is where flake faces meet the
electrolyte-filled pores, and these interfaces set the through-plane ion path. Pixels within 0.2 µm of the
Si-like bright phase are left out: those SiOx shards are angular and isotropic, and would read as "disorder"
even when the graphite is perfectly aligned. The order parameter S summarises the θ distribution against the
image horizontal. The spread is its width about its own mean. The tilt is that mean.

Assumption: image vertical is through the coating thickness. Flakes lie horizontally in every spot and the FIB
curtains run vertically, but no current collector is visible except possibly at the bottom of epqdaau9.

## Why it matters for the battery

- **Tortuosity anisotropy.** Synchrotron tomography showed that particle shape and fabrication-induced alignment
  make the pore network more tortuous through the thickness than in-plane [1]. That lowers the effective
  electrolyte diffusivity in the direction the current actually flows [1, 2].
- **Fast charge and plating.** In image-based electrochemical simulations of 14 CT-scanned graphite electrodes,
  the tortuosity anisotropy from platelet morphology dominated fast-charge performance. Platelet electrodes
  reached lower capacity, generated more heat and plated more severely; clustering of the active material alone
  had little effect [3]. Across 18 graphite electrodes, particle morphology and structural anisotropy set the
  directional tortuosity and its heterogeneity [4].
- **The converse has been shown in cells.** Graphite whose basal planes were turned vertical by a magnetic field
  during casting reached 80 % state of charge at 1C (CC-CV) in 50 min instead of 138 min [5].
- **Direction.** More alignment (higher S, lower spread) is worse for rate and plating at the same porosity; if
  it comes from harder calendering, the denser electrode is the trade-off. Less alignment helps transport but in a
  supplier lot usually comes with a different particle shape or a lower calendering density. So a real change in
  either direction is, first of all, a sign that the graphite or the calendering changed.

## Industry / Polaron use

- **CoA analogue.** The powder-level counterpart is the XRD orientation index I(004)/I(110) of graphite
  (GB/T 24533-2019, Annex F) [9]. Cell makers also use it on the electrode: Samsung SDI's US 10,629,892 B2 [10] claims
  an orientation-index window for the negative electrode. Both are averages over a whole sample, not an image.
- **Imaging tools.** Imaging-vendor software (Avizo, GeoDict, MATBOX) and Polaron's microstructure platform
  quantify transport anisotropy from 3D volumes. We found no public cross-section structure-tensor KPI used for
  incoming QC, so this column is academic-style.
- **What would move it.** Calendering pressure or line speed, the graphite's shape (flake vs spheroidised
  natural graphite, or synthetic needle/mosaic coke), its particle-size distribution, and a change in the
  natural/synthetic blend.

## How it is computed

Detector: BSE, through `features/_common/harmonise.py`. The image is the same central crop of every spot,
anchored so that black = 0 and graphite = 1, and topped up to one noise level. It uses the shared void and
bright masks. Everything below is in `config.yaml`.

1. **Downsample** `h.bse`, `h.void` and `h.bright` 2× by 2×2 area means (masks by majority), giving 50 nm/px
   (`downsample: 2`).
2. **Structure tensor.** Take derivative-of-Gaussian gradients Ix, Iy at σ = 1.5 px (75 nm;
   `gradient_sigma_px`). Average Ix², Iy² and IxIy with a Gaussian of σ = 8 px (0.4 µm;
   `integration_sigma_px`) to get Jxx, Jyy, Jxy. The layer direction is perpendicular to the dominant gradient:
   cos 2θ = (Jyy − Jxx)/d and sin 2θ = −2Jxy/d, with d = √((Jxx − Jyy)² + 4Jxy²). Coherence is
   w = (d / (Jxx + Jyy))².
3. **Boundary pixels.** Keep the band where a 3×3 dilation of the void mask differs from its 3×3 erosion
   (`boundary_width_px: 1`). Remove pixels within 4 px (0.2 µm) of the bright phase (`bright_exclusion_px`) and
   a 16 px frame (0.8 µm; `edge_margin_px`). A normal spot keeps ≈ 0.7–2·10⁵ pixels (5n1q8atc, with the most
   bright phase, ≈ 7·10⁴). Below 2000
   (`min_boundary_px`) the column is nan.
4. **Summaries over those pixels.** C = Σw cos 2θ / Σw and S' = Σw sin 2θ / Σw.
   `flake_orient_order` = C. `flake_orient_spread_deg` = √(−2 ln R)/2 with R = √(C² + S'²), in degrees (computed,
   not a column).
   `flake_tilt_deg` = −½ atan2(S', C), in degrees; the minus sign converts array coordinates (y down) to the
   on-screen counter-clockwise convention. **This sign is opposite to the screen's `st_tilt_bnd_deg`.**

The recipe is the orientation screen's (`st_*_bnd`), restricted to graphite/void boundaries and moved onto the
shared harmonisation. Runtime is 0.54 ± 0.07 s per spot on top of the harmonised spot.

## Evidence on our data

**Final pipeline numbers** (integrated run: `analysis/rank_features.py` → `processed/rankings.csv` for sep and q;
`analysis/robustness.py` → `processed/robustness.csv` for the rest). sep is the between/within ratio (> 1 strong,
bar ≈ 0.65), q is BH-corrected (bar < 0.1), within-session p is the exact permutation inside the five mixed
sessions (192 relabellings), and the perturbation ratio is the largest shift under six synthetic acquisition
changes ÷ baseline SD (< 0.5 good).

| Column | B1 / B2 / B3 mean | sep | q | within-session p | within-session B1 / B2 (SD) | session R² (chance ≈ 0.40) | perturbation ratio |
|---|---|---|---|---|---|---|---|
| `flake_orient_order` | 0.307 / 0.301 / 0.295 | 0.10 | 0.97 | 0.66 | +0.48 / +0.56 | 0.52 | 0.074 (gamma 1.25) |
| `flake_tilt_deg` | +1.1 / −1.0 / +2.3° | 0.28 | 0.64 | 0.26 | −1.06 / −1.17 | 0.58 | 0.085 (gamma 0.8) |

Both are "no difference" in `rankings.csv`. The worst leave-one-out sep is 0.06 / 0.18. The leak
correlation with image height is 0.49 for order and spread, under the 0.6 bar but not negligible, and the
session-driven part is already covered by the within-session test. Baseline variance components
(`robustness.csv`) for S: ICC 0.16 and an upper-bound %GRR of 40 %. Most of the spot-to-spot scatter is within
a session, consistent with the field-of-view heterogeneity below. 40 % is above the AIAG 30 % line, but that
gate applies only to Tier-1 REJECT paths, and this column is a diagnostic. These numbers agree with the builder's
validation run that follows, with one exception: the perturbation ratios are 0.074 / 0.075, not 0.06, and the
table and text below now use the final values. Across spots, S correlates r = 0.94 with `solid_chord_hv_ratio`,
the other alignment diagnostic, so the two are one piece of evidence, not two.

**Builder's validation run.** The final code was run on all 31 spots (`preprocessing.iter_samples()`, shared
harmonisation) with stdout-only scripts, and every number below was reproduced by an independent review run.
Units of "SD" below are the Batch_3 between-spot SD (S: 0.063; spread: 4.0°; tilt: 5.1°).

| | `flake_orient_order` | `flake_orient_spread_deg` | `flake_tilt_deg` |
|---|---|---|---|
| Batch_1 (7) | 0.307 ± 0.058 | 43.7 ± 3.9 | +1.1 ± 6.9 |
| Batch_2 (7) | 0.301 ± 0.069 | 44.2 ± 4.0 | −1.0 ± 7.0 |
| Batch_3 (17) | 0.295 ± 0.063 | 44.7 ± 4.0 | +2.3 ± 5.1 |
| η²(batch) | 0.007 | 0.012 | 0.05 |
| session R² (chance ≈ 0.40) | 0.52 (perm. p 0.17) | 0.49 (p 0.24) | 0.58 (p 0.07) |
| within-session test, exact p (192 relabellings) | **0.66** | **0.66** | 0.26 |
| session-adjusted B1−B3 / B2−B3 (95 % CI), SD | +0.48 [−1.4, +2.4] / +0.56 [−0.9, +2.0] | −0.63 [−2.6, +1.3] / −0.55 [−2.0, +0.9] | −1.1 / −1.2 |
| perturbation ratio (max \|Δ\| / B3 SD; final `robustness.py`) | **0.074** (gamma 1.25) | **0.075** (gamma 1.25) | 0.085 (gamma 0.8) |
| split-half r (left vs right half) | 0.09 | 0.14 | 0.19 |
| minimum detectable shift, 7 vs 17 spots, 80 % power | 1.26 SD = 0.079 (27 % of the mean) | 1.26 SD = 5.0° | 6.4° |

**Raw within-session contrasts** (SD units) for S: 2068 B2−B3 +0.03; 2080 B1−B2 −1.18, B1−B3 +0.55,
B2−B3 +1.73; 2148 B1−B2 +0.98; 2156 B1−B2 −0.46; 2272 B2−B3 +0.53. B1−B2 signs are mixed. B2−B3 is positive
in all three shared sessions, but two of the three are ≤ 0.53 SD and the B2 term alone has within-session
p = 0.39, so there is no consistent batch shift. The spread mirrors S (r = −0.99 across spots).

**Perturbations** were applied to the raw uint8 BSE/Inlens/SE of B3 spots 71vgq3fw, cfe5vt7s, hzumfsms and
0grcilhi, and the whole harmonisation was rerun. Largest shift in S, per perturbation (final `robustness.py`):
black level +25 0.000, gamma 0.8 0.040, gamma 1.25 0.074 (on 0grcilhi; the build run had 0.064), contrast ×0.85
0.012, noise σ 4 0.048, blur σ 1 px 0.047 SD. Against these six it is more than twice as robust as the screen's
all-boundary version (0.17), because the gamma-sensitive Si-phase edges are gone. The lifted-black session 2060 sits
at z = +0.05 against the rest of B3. **But a 1 px blur along one axis only** (added to `robustness.py` later; it mimics
a stigmation or scan-direction change) shifts S by 0.49 SD (x) and 0.52 SD (y), on 71vgq3fw. The order parameter
reads the gradient direction, so an anisotropic blur moves it directly. This is the main reason it is a v1.1
diagnostic and not a decision column.

**Reading.**
1. **No batch signal.** Every S and spread batch mean is within ≈ 0.25 SD of the baseline (largest: B1 spread
   −0.25 SD; final run). Within the mixed sessions, p = 0.66. Session R² is at chance (p 0.17), so the pooled
   comparison is not session-dominated. That is what an expected-stable check needs: B1 and B2 show no
   large calendering or graphite-shape change, while shifts below ≈ 1.3 SD (pooled) or ≈ 2 SD
   (session-controlled) cannot be excluded. The screen reached the same conclusion with its own recipe (all
   within-session p ≥ 0.11; `orientation.json`), and the result was independently reproduced
   (`verifications.json`).
2. **Precision is limited by the field of view, not by acquisition.** Split-half r is only 0.09–0.19: the two
   87 × 33 µm halves of one spot differ about as much as two spots do. A spot holds a few hundred flakes, and
   alignment varies on that scale. A single spot therefore says little; a batch mean over ≥ 7 spots is the unit.
   Detecting a 10–15 % change in S would need roughly 3–7× more imaged area per batch (the detectable shift falls
   as 1/√area [8]).
3. **The 5n1q8atc "disorder" was mostly the Si phase, not the graphite.** The screen's all-boundary version flagged
   Batch_1/5n1q8atc at z = +4.9 (spread 64°). Restricted to graphite/void boundaries, this spot sits at z = −1.4
   (S) and +1.4 (spread), inside the baseline range; the remainder may be 2316's strong curtains. Its apparent
   disorder came mainly from its extra, isotropic bright particles, which
   `si_fraction` / `si_particles` already measure. Keeping composition out of this column is the reason for the
   bright exclusion. For comparison, our all-boundary variant gives B1 0.242 ± 0.084, B2 0.268 ± 0.069 and
   B3 0.254 ± 0.057 (within-session p 0.66), with 5n1q8atc at z = −2.8.
4. **Agreement with the screen.** Our S correlates r = 0.97 with the screen's pore–graphite `st_S_bnd_poregraphite`
   and r = 0.88 with its all-boundary `st_S_bnd`. Alignment is real but modest: S ≈ 0.30 and a spread of ≈ 45°,
   against ≈ 60°+ for isotropic.
5. **Tilt is a mounting diagnostic.** It reaches +10 to +14° (f1vzngrs +13.9°, epqdaau9 +11.1°, 9luzk4jm +10.2°)
   and −8.2° (3806gxp0), and its halves disagree by 7.8° on average, so prefer the tilt-invariant spread
   whenever the tilt is large.

## Uncertainty and pitfalls

- **Sampling.** The spot-to-spot SD (0.063 in S) is mostly within-image heterogeneity: split-half r ≈ 0.1. Use
  batch means over ≥ 7 spots from ≥ 2 sessions, and read a single spot only for gross anomalies (|z| > 3).
- **Session.** Session R² is at chance here (p 0.17–0.24), but the within-session test has wide intervals
  (≈ ±2 SD). The honest statement is "no difference larger than ≈ 1.3 SD if session effects are negligible, and
  none larger than ≈ 2 SD with acquisition controlled".
- **Curtaining and scan anisotropy.** Vertical FIB curtains are oriented edges too [7]. They add vertical structure
  (lower S) where they cross graphite/void boundaries; session 2316 has the strongest curtains
  (`acq_curtain_index` 1.64–1.68 vs a median of 1.04). The verification
  pass also found a session-specific fast-scan low-pass (high-frequency power ratio Px/Py 0.75–0.88). It is
  uncorrelated with S today, but a 1 px x-only or y-only blur moves boundary orientation features by
  0.4–0.8 SD. A new batch from a different scan setup should be checked for both.
- **Tilt.** S is measured against the image horizontal, so a tilted mount lowers it by ≈ (1 − cos 2·tilt)·S
  (≈ 6 % at 10°). The spread is tilt-invariant.
- **Segmentation.** The void mask is the shared Otsu recipe. Pore-back (sub-surface material seen through pores)
  reads as solid, so some "boundary" pixels are edges of pore-back regions. Variants of threshold, scale and
  weighting in the screen correlated r ≥ 0.97 with each other.
- **2D vs 3D.** A section shows the in-plane trace of a 3D orientation distribution. S and the spread are valid
  for comparing sections cut the same way (vertical sections through the coating), not as a 3D order parameter
  or a substitute for the XRD orientation index. Through-plane tortuosity needs a 3D volume.

## References

1. Ebner, Chung, García et al. (2014; online 2013). Tortuosity anisotropy in lithium-ion battery
   electrodes. *Adv. Energy Mater.* 4, 1301278. https://doi.org/10.1002/aenm.201301278
2. Tjaden, Brett, Shearing (2016). Tortuosity in electrochemical devices: a review of
   calculation approaches. *Int. Mater. Rev.* https://doi.org/10.1080/09506608.2016.1249995
3. Probing the role of multi-scale heterogeneity in graphite electrodes for extreme fast charging (2022).
   *ACS Appl. Mater. Interfaces.* https://doi.org/10.1021/acsami.1c25214
4. Probing the influence of multiscale heterogeneity on effective properties of graphite electrodes (2022).
   *ACS Appl. Mater. Interfaces.* https://doi.org/10.1021/acsami.1c19694
5. Controlling the crystallographic orientation of graphite electrodes for fast-charging Li-ion batteries (2021).
   *ACS Appl. Mater. Interfaces.* https://doi.org/10.1021/acsami.1c19735
6. Reconstructing the orientation distribution of actin filaments in the lamellipodium of migrating keratocytes
   from electron microscopy tomography data (2012). *Cytometry A* (structure-tensor orientation distributions
   from EM images). https://doi.org/10.1002/cyto.a.22050
7. Mitigating curtaining artifacts during Ga FIB TEM lamella preparation of a 14 nm FinFET device (2017).
   *Microsc. Microanal.* (origin of FIB curtaining). https://doi.org/10.1017/S1431927617000241
8. Dahari, Docherty, Kench et al. (2025). Prediction of microstructural representativity
   from a single image. *Adv. Sci.* https://doi.org/10.1002/advs.202414149
9. GB/T 24533-2019, Graphite negative electrode materials for lithium-ion batteries (Annex F, orientation index).
   https://www.codeofchina.com/standard/GBT24533-2019.html (standard, no DOI)
10. Samsung SDI, US 10,629,892 B2 (negative-electrode orientation index). https://patents.google.com/patent/US10629892B2/en
    (patent, no DOI)

DOIs 1, 2 and 8 are tool-verified ledger entries. DOIs 3–7 come from `literature.load_papers`; their author lists
were not retrieved, so they are cited by title. OpenAlex search was rate-limited (HTTP 429) during this build.
Billaud et al. (2016, *Nat. Energy*, magnetically aligned graphite) is cited in `notes/research_report.md` but
not here, because its DOI could not be re-verified with a tool.
