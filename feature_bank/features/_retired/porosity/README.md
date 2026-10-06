# porosity (retired)

The share of the whole BSE frame darker than a per-image multi-Otsu pore threshold, computed on the 1–99 % stretched
image. This was the original porosity KPI. The folder also holds the shared legacy segmentation (`segment_bse`,
`pore_mask`) that `bright_phase`, `pore_size` and `particle_size` reuse. It added one column to
`processed/features.csv`, and it is no longer computed.

| Column | Unit | Meaning |
|---|---|---|
| `porosity_frac` | area fraction (0–1) | Pixels below the lower 3-class Otsu threshold of the blurred, stretched BSE ÷ all pixels of the frame. A *relative* index (see *What it measures*). Superseded by `porosity_open_frac` |

## Status

**Retired on 2026-10-03.** Commit 84cb17c moved this folder unchanged from `features/porosity` to
`features/_retired/porosity`. `feature_dirs()` skips folders whose names start with `_` (`features/__init__.py:40-42`), so
the column is no longer in `processed/features.csv`. The audit numbers below were computed on b0b5841, before the
move, with the same code.

| Retired folder | Columns | Superseded by | Audit reason (run2 scorecard) |
|---|---|---|---|
| `porosity/` (this one) | `porosity_frac` | `open_porosity` → `porosity_open_frac` | Redundant: r = 0.94 with the new KPI, and r = 0.986 when this mask is measured on the same crop. It tells the same within-session story. It is noisier within a session (σ_site 0.0135 vs 0.0105), more gamma-sensitive (0.62 vs 0.43), includes the frame-artefact rows, and has no error bar |
| `bright_phase/` | `bright_phase_frac` | `si_fraction` → `bright_solid_frac` | Acquisition-dominated: session R² 0.95, within-session p 0.65, lifted-black z +4.7, gamma ratio 0.81 |
| `pore_size/` | `pore_size_median_um2`, `_p90_um2`, `_count_per_1000um2` | `local_thickness` → `pore_lt_d50_um`, `pore_lt_d90_um`; `minkowski_functionals` → `pore_n_per_1000um2` | Session R² 0.92 / 0.87 / 0.81, within-session p 0.51 / 0.31 / 0.46. The blur ratio of the median is 2.95, because the median is set by 20–40 px objects at the size cut-off |
| `particle_size/` | `particle_size_d10/d50/d90_um` | **No full replacement yet.** Graphite flake-size features are being researched | Unreliable: split-half r 0.12–0.36, gamma ratio 1.1–1.5. The watershed splits the solid between pores, so the result follows pore spacing at least as much as flake size (its own docstring says big flakes are cut into ≈ 1 µm pieces). d90's incoming-vs-B3 p = 0.042, the minimum attainable, is a lead for the flake-size work, not a result |
| `histogram_anomaly/` | `histogram_anomaly_z` | Acquisition-novelty diagnostic only | Session R² 0.94, within-session p 0.89, perturbation ratio 6.1 (gamma). It flags a new imaging condition, not a new material |

**Why it is kept** (as code, importable with `import features._retired.porosity.feature`):
- **Comparability.** Every porosity number quoted before the harmonisation used this column: the research report's
  provisional calls, the feature screen, the ledger and the first `rank_features.py` runs.
- **It is the reference** the harmonised KPI was validated against. The two give the same B1/B2 deltas (see
  *Evidence*).
- **The other four retired features import it.** `segment_bse` / `pore_mask` are what `bright_phase`, `pore_size`
  and `particle_size` use.

Do not use it for decisions, and do not feed it to a classifier next to `porosity_open_frac`: Spearman 0.935 makes
it a duplicate.

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| up | More open pore area in the section. Electrolyte transport gets easier: ionic resistance and tortuosity fall as porosity rises [4, 5], so there is less electrolyte polarisation at high rate. The cost is less active material per cm³, so lower volumetric energy density (mass balance). If the electrode is under-calendered, particle contact may also weaken (general knowledge, no verified citation) | **Trade-off:** better rate, worse volumetric energy density | Transport: strong [3–5]. Size of any effect: low, because this is a 2D relative index with a frame-window bias |
| down | Denser electrode: harder calendering, higher coat density, or a graphite that packs tighter. Ionic resistance and tortuosity rise [4, 5], and the reaction concentrates near the separator [6]. Rate capability drops [5]. Fast-charge Li plating is limited by electrolyte transport in the anode. Lowering tortuosity is the effective lever there, and simply raising porosity is not [7], so a small porosity loss raises plating risk only modestly. Volumetric energy density goes up | **Trade-off:** bad for rate (and mildly for fast charge), good for energy density | Transport: strong [4–6]. Plating: moderate [7]. Same low confidence for the size |

**Best value:** match the approved baseline (Batch_3: 0.107 ± 0.019 on this index). Porosity is a designed compromise,
so neither direction is better in itself. Use `porosity_open_frac` for any decision.

**Our batches** (run2 audit scorecard; same numbers as `processed/robustness.csv`):
- **Batch_1: lower-porosity hint, not established.** 0.0863 ± 0.0153 vs 0.1066 ± 0.0194, a gap of −0.020 (−1.04
  B3-SD, −19 %).
  - Within sessions: −1.05 B3-SD, exact p = 0.18; incoming-vs-B3 p = 0.33.
  - Without the high, B3-only session 2088, the gap shrinks to −0.014.
  - The harmonised KPI gives the same −0.019, and the decision layer calls B1 INCONCL on it.
- **Batch_2: equivalent on this index.** 0.0980 ± 0.0138, a gap of −0.009 (−0.44 SD, −8 %). Within sessions −0.37
  SD; without session 2088 the gap is −0.002.

## What it measures

The BSE detector shows open pores as black, graphite as mid-grey and the Si-based phase as bright. `porosity_frac` is
the share of pixels darker than the per-image pore/graphite cut. Unlike every harmonised feature, it is taken over
the **whole frame**:
- The frame is 6960–7000 × 1612–2316 px, i.e. ≈ 174 × 40–58 µm and 7 000–10 100 µm² at 25 nm/px. Its height is the
  session (`Sample.session`, `preprocessing/process_data.py:161-164`).
- It includes the top 250 rows, which carry a top-of-frame artefact.
- It includes the bottom 25 rows, which also hold the Cu current-collector band of Batch_2/epqdaau9
  (`_common/config.yaml: crop`).

It is a **relative index, not the electrode porosity.** The values run from 0.064 (B1 f1vzngrs) to 0.152 (B3
hzumfsms), against a calendered graphite anode that is plausibly 25–35 % porous (general knowledge, not verified
here). Two things make it read low:
- **Pore-back.** The material behind an open pore reads grey and is counted as solid. Separating pores from the
  carbon-binder domain needs dedicated imaging such as Kintsugi Pt infiltration [8], and pore segmentation in SEM of
  porous media is a known hard problem [9].
- **Sub-resolution pores.** The pores inside the carbon-binder web are too small to resolve and read as grey.

Spot-to-spot and batch-to-batch comparisons are meaningful; the absolute level is not.

## Why it matters for the battery

- **Ionic transport and rate.** Electrolyte-filled pores carry the Li⁺ current. Effective conductivity scales as
  ε/τ, usually written in Bruggeman form ε^α; the origin and limits of that form are reviewed in [11].
  - High-rate performance is largely set by the ionic resistivity of the electrolyte-filled electrode [4].
  - On calendered graphite anodes, ionic resistance and tortuosity rise as porosity falls. Calendering amplified
    the performance loss at high current [5].
  - Lower-porosity composite electrodes have lower ionic conductivity, and this concentrates the reaction near the
    separator side [6].
  - Aligned graphite flakes make the through-plane path more tortuous than the in-plane one [3], so a porosity
    change matters most through the thickness.
- **Fast charge.** In high-energy cells, electrolyte transport in the anode limits fast charge and triggers Li
  plating. Reducing tortuosity was an effective remedy; increasing porosity was not [7]. A small porosity loss
  therefore moves plating risk in the harmful direction, but probably only modestly.
- **Energy density.** Less porosity means more active material per volume (mass balance).
- **Details.** `features/open_porosity/README.md` covers wetting, SiOx swelling and a worked resistance example.
  They apply here unchanged, read through a noisier window.

## Industry / Polaron use

- **Cell makers** set porosity by calendering and compute it from coat weight, thickness and true density (general
  knowledge). Compaction density is a graphite CoA / GB/T 24533 item, and LG Energy Solution's US 12,196,651 B2
  specifies region-wise pore fractions on cross-sections (both cited from `notes/research_report.md` §2; no DOI).
- **Per-image (multi-)Otsu** on an SEM cross-section is the generic default of image tools. scikit-image's
  `threshold_multiotsu` implements Liao et al. [2] and cites an ImageJ plugin by Y. Tosa. It is what a quick
  in-house porosity script does, which is why this was the first feature.
- **Polaron / Imperial** go further: Kintsugi separates pores from the carbon-binder domain [8], and ImageRep attaches
  a representativity error bar to a single image [12]. This legacy column has neither; `porosity_open_frac` adds the
  error bar.
- **What would move it:** calendering line load or gap, coat weight, slurry solids and binder content, graphite PSD
  and shape, and the Si-phase dose.

## How it is computed

**Detector:** BSE only, with no `features/_common` harmonisation (this recipe predates it).

1. **Load** (`preprocessing/process_data.py`).
   - `load_grey` takes channel 0 of the RGB-saved TIF (`:74-77`).
   - `trim_border` drops edge rows and columns where ≥ 95 % of pixels are ≥ 245 or ≤ 10 (`:80-97`). An audit probe
     showed it removed 0 rows and 0 columns on all 31 spots.
   - `normalise_brightness` maps the 1st and 99th percentiles of the whole image linearly to 0 and 255, clips, and
     casts to uint8 (`:100-107`). The result is cached as `processed/full/<batch>/<id>_BSE.png` (`load_image`,
     `:203`).
   - On our data the 1st percentile sits at the black level (−0.04 to +0.03 graphite units) and the 99th inside the
     bright phase (2.0–2.6 graphite units).
   - Graphite therefore lands at stretched grey 97–127, set by the session (session R² 0.90). After the stretch,
     1.0–3.8 % of pixels sit at 0 (B1 / B2 / B3 means 0.025 / 0.023 / 0.013) and 1.0–1.3 % at 255.
2. **Blur:** `ndi.gaussian_filter(sample.bse, blur_sigma_px=2)` (`feature.py:24`). scipy keeps the uint8 dtype, so the
   blurred values are truncated to integers (checked: 0.59 → 0, 6.99 → 6). This is harmless, because the thresholds
   are found on the same truncated image.
3. **Thresholds:** `threshold_multiotsu(blurred[::4, ::4], classes=3)` (`feature.py:25-26`).
   - It works on every 4th row and column (`subsample: 4`, 1/16 of the pixels) with scikit-image's default 256-bin
     histogram.
   - It returns the two cuts that maximise Otsu's between-class variance [1], extended to three classes [2]. They
     are cast to int (`:27`).
   - There is no clamp, no fallback, and no check that the three classes really are pore / graphite / bright.
   - On our data the pore cut `low` is 63–85 stretched grey. Mapped back through the stretch onto the harmonised
     anchors, that is 0.60–0.73 graphite units (mean 0.670); the harmonised Otsu void threshold is 0.62–0.71
     (r = 0.90). The bright cut `high` is 148–174, or 1.28–1.62 graphite units.
4. **Pore mask:** `pore_mask = blurred < low` at full resolution (`feature.py:31-34`). There is no speck removal and no
   hole filling.
5. **`porosity_frac = pore_mask.mean()`** over the whole frame (`feature.py:37-39`).
6. **Cache:** `segment_bse` caches `(blurred, low, high)` keyed on the identity of `sample.bse` (`feature.py:18, 21-28`),
   so the dependent features reuse one segmentation per spot. For example, `bright_phase` uses `blurred > high`
   (`_retired/bright_phase/feature.py:13-16`).

Tuning (`config.yaml`): `blur_sigma_px: 2` (50 nm), `subsample: 4`, `classes: 3`.

**Why the stretch hardly matters.** Otsu's criterion depends only on how the histogram splits, so a linear grey
map carries the thresholds along with the image. The stretch acts only through its tail clipping and the
requantisation to 256 levels (`notes/research_report.md:247` makes the same point).
- Black +25 changes `porosity_frac` by exactly 0.
- Contrast × 0.85 changes it by 0.12 B3-SD, which is quantisation.
- A non-linear tone change does move it: gamma 0.8 / 1.25 gives 0.52 / 0.62 B3-SD.

## Evidence on our data

All 31 spots, recipe exactly as in the code. B3-SD = the between-spot SD within Batch_3 (0.0194). Session R² is
≈ 0.40 by chance (13 height groups, 31 spots). Within-session p is the exact permutation p over 192 relabellings
inside the 5 mixed sessions (minimum ≈ 0.005); incoming p tests B1 + B2 against B3 (24 arrangements, minimum
0.042).

| Quantity | `porosity_frac` | `porosity_open_frac` (successor) |
|---|---|---|
| B1 / B2 / B3 mean ± SD | 0.0863 ± 0.0153 / 0.0980 ± 0.0138 / 0.1066 ± 0.0194 | 0.0887 ± 0.0156 / 0.1020 ± 0.0175 / 0.1077 ± 0.0183 |
| η²(batch) | 0.19 (0.16 without the two 2316 spots) | 0.17 |
| session R² (chance 0.40) | 0.69 | 0.67 |
| within-session p (b1, b2 in B3-SD) | 0.18 (−1.05, −0.37) | 0.17 (−1.64, −0.85) |
| incoming-vs-B3 p (b) | 0.33 (−0.48) | 0.21 (−0.99) |
| B3 σ_site / σ_session, ICC | 0.0135 / 0.0149, 0.55 | 0.0105 / 0.0160, 0.70 |
| %GRR upper, ndc | 74 %, 1.28 (fails the 30 % / ndc ≥ 5 gate) | 83 %, 0.93 |
| split-half r, x / y | 0.86 / 0.77 | 0.80 / 0.83 |
| seed spread ÷ B3-SD | 0 (deterministic, no noise top-up) | 0.005 |
| perturbation ratio, worst | 0.62 (gamma 1.25); gamma 0.8 0.52, contrast 0.12, blur 0.09, others ≤ 0.05, black +25 0.00 | 0.43 (gamma 0.8) |
| lifted-black session 2060, z | −1.12 | −1.25 |
| LOSO AUC vs B3, B1 / B2 | 0.77 / 0.48 | 0.73 / 0.40 |
| phantom error, mean / max | +0.8 % / 3.9 % (area-matched, see below) | +2.2 % / 6.1 % |

- **`rank_features.py`** (`processed/rankings.csv`): sep 0.58, p = 0.049, q = 0.13, sep_loo 0.48, verdict "no
  difference". That p permutes across all spots and ignores the session, which is why it looks better than the
  within-session p of 0.18.
- **Within-session contrasts** (B3-SD):
  - 2068: B2−B3 −0.60
  - 2080: B1−B3 −0.82, B2−B3 +0.83
  - 2148: B1−B2 −0.78
  - 2156: B1−B2 −0.09
  - 2272: B2−B3 −0.96

  B1 is lower in all three of its contrasts, but only one is against the baseline (2080, one spot each). B2 is below
  B3 in 2 of 3. This is the same weak "B1 ≈ 2 % (absolute) less porous" hint the harmonised KPI shows, and it is not
  established.
- **Same segmentation, different window.** Restricted to the harmonised crop, the old mask correlates
  r = 0.986 with `porosity_open_frac`, and its within-session B1 coefficient moves from −1.05 to −1.76 B3-SD
  (successor −1.64; session R² 0.63). The legacy pore cut, mapped to graphite units, tracks the harmonised one
  (r = 0.90). Most of the r = 0.94 disagreement between the two columns is therefore the **measurement window**,
  not the threshold:
  - Rows 0–249 read 0.018 lower than the central band in 28 of 31 spots; session 1612 is the exception at +0.031.
  - The bottom 25 rows read 0.044 higher.
  - These rows make up 10.8–15.5 % of the frame depending on the image height, i.e. on the session. They bias each
    spot by −0.0065 to +0.0077 (−0.34 to +0.40 B3-SD) against its own central band. Batch means move only by
    −0.0009 / −0.0014 / −0.0019.
- **The threshold shift is acquisition.** B1/B2 sessions have lower pore cuts than B3 (0.650 / 0.652 vs 0.686
  graphite units), but within sessions the difference is gone (p = 0.65, session R² 0.77). This is the same pattern
  as the harmonised `porosity_void_threshold`.
- **Pore-floor clipping does not explain the B1 gap.** B1/B2 sessions clip more pore pixels at raw 0 (2.7 % / 2.5 %
  vs 0.8 % in B3). The four unclipped session-2060 spots were darkened by 30 grey levels, which brings them to
  2.5–3.2 % clipped, the B1/B2 range.
  - `porosity_frac` moves +0.0022 to +0.0035 (mean +0.0031, 0.16 B3-SD).
  - The adaptive harmonised KPI moves +0.0026 and the fixed-0.6 recipe +0.0102.
  - At 24 levels (0.9–1.3 % clipped) the shift is 0.0000.

  If anything, clipping makes the B1/B2 deficit look ≈ 0.003 smaller.
- **Phantoms.** The synthetic BSE has three phases at grey 4 / 60 / 125, PSF σ 1 px and noise σ 9, at 1700 × 4200 px
  (the audit runner's `make_phantom`, outside the repo; 6 geometries × 3). Against the true pore fraction of the *whole* phantom:
  - mean error +0.8 %, max |error| 3.9 %
  - thin slits: horizontal +2.6 %, tilted +3.4 %
  - Si-rich: −1.2 %
  - isotropic, disks and patchy: within ±0.3 %

  The scorecard's +0.4 % / 6.5 % compares the whole-frame value with the truth on the harmonised crop, so it mixes
  in an area mismatch. Phantoms have no pore-back and no frame artefact, so this tests the threshold only.
- **Noise association.** r = −0.78 with the raw BSE noise σ over all spots, −0.78 within B3 and −0.54 within B3
  without 2088. The noise σ = 4 perturbation moves the value by only 0.04 B3-SD, so the association does not come
  from the arithmetic. Its source (acquisition or material) is unresolved, as for the successor.
- **Categorisation.** The B1 LOSO AUC of 0.77 is not session-free evidence. Session R² is 0.69, B1 owns three
  single-batch sessions (1780, 1880, 2316), and the within-session test is p = 0.18. As one of the 18 "promising +
  weak" material columns, it sits in a set whose 3-class leave-one-session-out balanced accuracy is 0.445
  (p = 0.14).

**What the evidence supports.** As a measurement, the legacy segmentation is close to the harmonised void mask; it
is accurate on phantoms, robust to offset, contrast, noise and realistic clipping, and reproducible across halves
(r 0.77–0.86). Its own weaknesses are:
- the session-dependent window
- worse within-session precision (σ_site 0.0135 vs 0.0105)
- larger gamma sensitivity
- no error bar
- no threshold sanity check

As a batch signal it carries only the unproven B1 deficit of ≈ −0.02 (within-session p = 0.18). It cannot separate
B2 from B3. Verdict: **redundant**, kept for comparability only.

## Uncertainty and pitfalls

- **No error bar.** The single-image sampling SE of the successor is ≈ 0.009 (`open_porosity` README). Here it is
  similar or slightly smaller, because the frame is larger. Spot-to-spot SD in B3 is 0.019, and the session
  component (0.0149) is as large as the within-session one (0.0135). With %GRR at 74 % and ndc 1.28 it fails a
  measurement-system gate, so it could never support a REJECT on its own.
- **Window artefact.** The top 250 and bottom 25 rows, and a frame area that varies 1.44× with the session, put a
  session-dependent bias of up to ±0.4 B3-SD on each spot.
- **Gamma / tone curve.** A ±25 % gamma change moves it by up to 0.62 B3-SD (≈ 0.012). That is the largest
  synthetic acquisition sensitivity.
- **Multi-Otsu has no clamp.** In a stress test far beyond our data, already-clipped spots were darkened by 24–30
  grey levels, which leaves 6–14 % of pixels at 0 and also compresses graphite contrast. Our maximum is 4.2 %.
  - The 3-class split jumped into the graphite peak on 7 of 27 spots at −30, giving porosity 0.23–0.77, and on one
    spot (f1vzngrs, 6.1 % clipped) already at −24.
  - The harmonised recipe clamps its cut to [0.5, 0.75] graphite units.
  - A badly underexposed new session would break this column silently.
- **Coupling to the bright class.** The pore cut is optimised jointly with the bright class, so it can depend on how
  much bright phase an image holds. For porosity on our data it does not (r = −0.02 between the pore cut in graphite
  units and `bright_phase_frac`). The feature screen found the coupling does matter for the connected-component pore
  counts on the bright-rich 2316 spots.
- **Biased low (pore-back, sub-resolution pores)** [8, 9]. If a supplier change alters pore depth or the CBD texture,
  the bias changes too, and the index would move without a real porosity change.
- **Sessions 2088 (high: z +2.6, +3.8, +1.4 against the other B3 spots) and 2060 (low: z −1.12)** read the same way
  in every recipe tried. There, material and acquisition cannot be separated.
- **2D → 3D.** Area fraction estimates volume fraction for a uniform random section (Delesse; general stereology,
  no verified citation here). 2D sections are ambiguous for tortuosity and pore connectivity [10], so this column
  cannot stand in for the transport properties that make porosity matter.

## References

DOIs resolved through the Crossref API on 2026-10-03, except [2]. Battery claims were checked against the abstracts
(offline `literature.load_papers` index, Semantic Scholar, or the web abstract for [5]).

1. Otsu (1979) A threshold selection method from gray-level histograms. *IEEE Trans. Syst. Man Cybern.* 9:62–66.
   https://doi.org/10.1109/tsmc.1979.4310076 (the thresholding criterion)
2. Liao, Chen, Chung (2001) A fast algorithm for multilevel thresholding. *J. Inf. Sci. Eng.* 17:713–727.
   DOI 10.6688/JISE.2001.17.5.1, as printed by scikit-image 0.26's `threshold_multiotsu` docstring. **Not in
   Crossref:** doi.org resolves it to the Airiti Library record of JISE 17(5):713–727, so the DOI is registered
   elsewhere. Treat it as partly verified.
3. Ebner, Chung, García et al. (2014; online 2013) Tortuosity anisotropy in lithium-ion battery electrodes.
   *Adv. Energy Mater.* 4:1301278. https://doi.org/10.1002/aenm.201301278 (particle shape and fabrication-induced
   alignment make tortuosity anisotropic)
4. Landesfeind, Hattendorff, Ehrl et al. (2016) Tortuosity determination of battery electrodes and separators by
   impedance spectroscopy. *J. Electrochem. Soc.* 163:A1373–A1387. https://doi.org/10.1149/2.1141607jes
   (high-rate performance is largely set by the ionic resistivity of the electrolyte-filled electrode)
5. Hille, Toepper, Schriever et al. (2022) Influence of laser structuring and calendering of graphite anodes on
   electrode properties and cell performance. *J. Electrochem. Soc.* 169:060518.
   https://doi.org/10.1149/1945-7111/ac725c (ionic resistance and tortuosity rise as porosity falls; calendering
   amplifies the high-current losses)
6. Orikasa, Gogyo, Yamashige et al. (2016) Ionic conduction in lithium ion battery composite electrode governs
   cross-sectional reaction distribution. *Sci. Rep.* 6:26382. https://doi.org/10.1038/srep26382 (lower porosity →
   lower ionic conductivity → reaction distribution through the depth; offline index)
7. Colclasure, Dunlop, Trask et al. (2019) Requirements for enabling extreme fast charging of high energy density
   Li-ion cells while avoiding lithium plating. *J. Electrochem. Soc.* 166:A1412–A1424.
   https://doi.org/10.1149/2.0451908jes (electrolyte transport limits fast charge; reducing tortuosity helps,
   raising porosity does not)
8. Cooper, Roberts, Liu et al. (2022) Methods—Kintsugi imaging of battery electrodes: distinguishing pores from the
   carbon binder domain using Pt deposition. *J. Electrochem. Soc.* 169:070512.
   https://doi.org/10.1149/1945-7111/ac7a68
9. Prill, Schladitz, Jeulin et al. (2013) Morphological segmentation of FIB-SEM data of highly porous media.
   *J. Microsc.* 250:77–87. https://doi.org/10.1111/jmi.12021 (the abstract calls FIB-SEM pore segmentation a
   generally unsolved problem; reading it as the pore-back issue is our interpretation)
10. Taiwo, Finegan, Eastwood et al. (2016) Comparison of three-dimensional analysis and stereological techniques for
    quantifying lithium-ion battery electrode microstructures. *J. Microsc.* 263:280–292.
    https://doi.org/10.1111/jmi.12389 (2D estimates are ambiguous; tortuosity and pore connectivity need 3D;
    offline index)
11. Tjaden, Cooper, Brett et al. (2016) On the origin and application of the Bruggeman correlation for analysing
    transport phenomena in electrochemical systems. *Curr. Opin. Chem. Eng.* 12:44–51.
    https://doi.org/10.1016/j.coche.2016.02.006
12. Dahari, Docherty, Kench et al. (2025) Prediction of microstructural representativity from a single image
    (ImageRep). *Adv. Sci.* 12. https://doi.org/10.1002/advs.202414149
13. Project sources:
    - `notes/research_report.md` §2 (KPI table, GB/T 24533, LGES US 12,196,651 B2; no DOI) and line 247 (affine
      invariance)
    - `notes/feature_screen.md` (`porosity_frac_old`, the 2316 count coupling)
    - the run2 audit scorecard, plus scratch probes for the thresholds, crop, clipping and phantoms
