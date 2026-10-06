# bright_phase (retired)

The share of the whole BSE frame that falls in the brightest of three grey classes, using a per-image multi-Otsu
threshold on the 1–99 % stretched image. This was the original "how much Si phase" number. It added one column to
`processed/features.csv`, and it is no longer computed.

| Column | Unit | Meaning |
|---|---|---|
| `bright_phase_frac` | area fraction of the whole frame (0–1) | Pixels of the 2 px-blurred, stretched BSE above the upper 3-class multi-Otsu threshold ÷ all pixels of the frame, pores included. If the bright phase is Si-based, this is the Si-phase share of the section. Superseded by `bright_solid_frac`; **not a KPI** |

## Status

**Retired on 2026-10-03.** Commit 84cb17c moved this folder unchanged from `features/bright_phase` to
`features/_retired/bright_phase`. The only edit was the import path at `feature.py:10`. `feature_dirs()` skips
folders whose names start with `_` (`features/__init__.py:40-42`), so the column is no longer in
`processed/features.csv`. The audit numbers below were computed on b0b5841, before the move, with the same code.

| Retired folder | Columns | Superseded by |
|---|---|---|
| `porosity/` | `porosity_frac` | `open_porosity` → `porosity_open_frac` |
| `bright_phase/` (this one) | `bright_phase_frac` | `si_fraction` → `bright_solid_frac` (Tier-1 Si-dose KPI); `bright_frac` is the same-denominator twin |
| `pore_size/` | `pore_size_median_um2`, `_p90_um2`, `_count_per_1000um2` | `local_thickness` → `pore_lt_d50_um`, `pore_lt_d90_um`; `minkowski_functionals` → `pore_n_per_1000um2` |
| `particle_size/` | `particle_size_d10/d50/d90_um` | **No full replacement yet.** Graphite flake-size features are being researched |
| `histogram_anomaly/` | `histogram_anomaly_z` | Acquisition-novelty diagnostic only |

**Audit verdict for this column: drop as a material feature** (explainability 1/5, categorisation 1/5). It has
session R² 0.95, B3 session ICC 0.73 and lifted-black z +4.70. Without the two session-2316 spots, η² falls to 0.013.
Leave-one-session-out AUC is 0.29 (B1) and 0.15 (B2), below chance. `bright_solid_frac` measures the same physical
quantity and fixes each of these problems. It runs on the harmonised crop with an anchored, noise-matched image, an
adaptive midpoint threshold, object cleanup, a solid denominator and a single-image error bar.

**Why it is kept** (as code, importable with `import features._retired.bright_phase.feature`):
- **Comparability.** Everything quoted before the harmonisation used this column: the research report (§6.1, ICC
  0.73; :192), the feature screen (`bright_phase_frac_old`), the ledger entry, and column 5 of the audited
  `processed/features.csv`.
- **It is the negative control for the harmonisation.** It asks the same question with the old recipe, which shows
  what the new recipe removed. Session R² without 2316 drops from 0.74 to 0.53 (`bright_frac`). Lifted-black z drops
  from +4.70 to +0.77, and B3 ICC from 0.73 to 0.00.

The docstring (`feature.py:6-7`) and the ledger entry call the bright phase "an additive (or a contaminant)". That is
wrong for this electrode. The bright phase is the Si-based active material: most likely SiOx, from morphology and
contrast (`notes/research_report.md` §7.14), not yet confirmed by EDS. A change in it is a change in the
active-material balance, not in a minor additive.

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| up | If the extra bright area is Si phase, the anode holds more Si. It stores more Li per gram [5, 6]. It loses more Li in the first cycle, because the oxide in SiOx turns into Li silicates and Li₂O (lower ICE) [6, 9]. It swells more and takes more mechanical damage [5, 7, 10], and it fades faster early on [7, 8, 10]. The denominator is the whole frame, so a denser, less porous electrode with the same recipe also reads higher. **On our data most "up" readings came from the imaging:** the lifted-black session 2060 reads +4.7 B3-SD | **Trade-off** at the material level (capacity against ICE, swelling and life). **Bad** for an incoming lot in a fixed cell design, but only once `bright_solid_frac` confirms it | Mechanism: strong, *if* the phase is Si-based. This column as evidence for it: **low** (session R² 0.95, perturbation ratio 0.81) |
| down | Less Si phase: the anode has less capacity than the cell's N/P design assumes [7, 11], with slightly better ICE, swelling and fade [6, 7, 8]. A more porous electrode also reads lower | **Trade-off, out of spec**, with the same proviso | Same as above |
| moves while `bright_solid_frac` does not | Not a cell property. Possible causes: frame rows that the harmonised crop excludes (the top-of-frame artefact, the Cu band of epqdaau9); a different noise level or sharpness; a tone curve that moves the multi-Otsu threshold along the particle-edge ramp | **Neither**: a measurement artefact | Moderate. Shown for session 2060 and for the gamma and blur perturbations (*Evidence*) |

**Best value:** as close to the approved baseline as possible. Batch_3 reads 0.070 ± 0.016 of the frame. No direction
is better for an incoming lot. Do not decide on this column; use `bright_solid_frac` (B3 0.066 ± 0.011 of the solid).

**Our batches** (31 spots; B3-SD = 0.0158):
- **Batch_1:** 0.104 ± 0.063 (+2.1 B3-SD). All of the excess comes from the two session-2316 spots: 0.187 and 0.202
  (+7.4 and +8.3 SD). The other five spots read 0.068 ± 0.013 (−0.16 SD). Within sessions the B1 coefficient is
  −0.61 SD (joint exact p = 0.65). This is the same single-session (n_eff = 1) anomaly that `si_fraction` and
  `si_grade` report, and it carries the same grade ambiguity (see *Evidence*, item 1).
- **Batch_2:** 0.067 ± 0.015 (−0.24 SD). Within sessions −0.17 SD (p = 0.65). No difference.

## What it measures

In BSE the signal rises with mean atomic number [4]. The Si-based particles (Si Z = 14, O Z = 8) therefore look
brighter than graphite (C, Z = 6). `bright_phase_frac` is the share of the **entire image** that multi-Otsu puts in
the brightest of three grey classes. The image is all 1612–2316 rows × ≈ 7000 columns, so the measured area itself
changes with the session (≈ 7 050–10 130 µm²). Nothing anchors the grey scale physically. The 1–99 % stretch maps
each image's own percentiles to 0 and 255, so the threshold is set relative to that image's histogram, and that
histogram depends on how much bright phase the image holds (`Sample.raw` docstring, `preprocessing/process_data.py`).

**Where the threshold lands.** This README's own probe ran on Modal (31 spots, production code). It mapped each
threshold back to the harmonised graphite units (graphite = 1):
- The upper threshold is 148–174 stretched grey (median 160), which is **1.28–1.62 × graphite**.
- It correlates r = 0.93 with that image's bright-phase mode, so in practice it is an *adaptive* threshold.
- It sits 34–47 % of the way from graphite to the bright mode (B3 0.43 ± 0.03). The harmonised midpoint sits at 50 %.
- It therefore catches 98–100 % of the harmonised bright mask `h.bright`, plus a rim of edge and grey pixels. In the
  median spot 7 % of its bright pixels lie outside `h.bright`; in the lifted-black spot tuy3zymq, 47 %.

By the Delesse principle the area fraction of a random section estimates the volume fraction [12]. Because the
denominator includes pores, this is the Si-phase share of the *electrode*, not of the solid.

## Why it matters for the battery

The mechanism is the one in `features/si_fraction/README.md`, which has the full argument:

- **Capacity.** Si alloys up to Li₁₅Si₄ and stores several times more Li per gram than graphite. SiOx sits in
  between [5, 6]. The Si-phase fraction therefore sets the anode's specific capacity and the N/P balance the cell was
  designed for [7, 11].
- **First-cycle efficiency.** The oxide part of SiOx reacts irreversibly to Li silicates and Li₂O. More SiOx means
  more Li lost in formation [6, 9].
- **Swelling and damage.** Si expands by up to ≈ 280 % on lithiation. SiOx expands less, but still far more than
  graphite [5]. Electrode thickness change rises with Si content [7], and so does mechanical degradation [10].
- **Fade.** In Si–graphite the Si fraction loses capacity first [8, 10], and capacity loss rises with Si content [7].

**Harmful directions.** Higher gives more capacity but lower ICE, more swelling and faster fade. Lower gives a
capacity shortfall against the design. Both are out-of-spec supplier changes. **This column cannot tell either from
an imaging change** (*Evidence*). It also reads a porosity change as a Si change, because pores are in the
denominator.

## Industry / Polaron use

- **The algorithm.** Multi-Otsu is a common generic first pass in image analysis: scikit-image's
  `threshold_multiotsu` implements Liao et al. [2], extending Otsu [1]. We found no industry QC specification that
  uses a stretched-frame multi-Otsu fraction as a release criterion; we checked only the sources in
  `notes/research_report.md` §2.
- **The quantity.** Si content and grade are powder CoA items (GB/T 38823-2020, research report §2). Commercial
  graphite–SiOx negative electrodes are standard, e.g. the LG M50 cell [13]. Polaron/Imperial report phase
  fractions with a single-image representativity error bar (ImageRep [14]). This column has none.
- **What would move it:** Si-phase dosing, Si grade, blend-ratio errors and segregation. Electrode porosity also
  moves it (denominator), and on these data so does the imaging session.

## How it is computed

Detector: BSE only. Every line is in the retired code; line numbers are for the current tree.

1. **Clean image** (`preprocessing/process_data.py`, `clean()`, which `load_image` caches as
   `processed/full/<batch>/<id>_BSE.png`):
   - `load_grey` takes the first of the identical RGB channels.
   - `trim_border` drops edge rows and columns where ≥ 95 % of pixels are ≥ 245 or ≤ 10. On our 31 spots no row is
     trimmed.
   - `normalise_brightness(low=1, high=99)` maps the 1st and 99th percentile of the **whole frame** linearly to
     0–255 and clips the darkest and brightest 1 %, giving uint8.
2. **Segmentation** (`features/_retired/porosity/feature.py:21-28`, `segment_bse`, shared with `porosity_frac`,
   `pore_size` and `particle_size`):
   - Gaussian blur, `blur_sigma_px` 2 (`porosity/config.yaml`). The input is uint8, so `scipy.ndimage` returns uint8
     and the blurred image is re-quantised to integers.
   - `threshold_multiotsu` with `classes` = 3 runs on every `subsample` = 4th row and column (1/16 of the pixels;
     256-bin histogram). The two thresholds are cast to `int`.
   - The result is cached by array identity, so each spot is segmented once.
3. **Mask and fraction** (`feature.py:13-21`): `bright = blurred > high`, and `bright_phase_frac = bright.mean()`
   over the full frame. There is no crop, no minimum object size, no core or hole cleanup, no solid denominator and
   no error bar.
4. **Tuning.** This folder's `config.yaml` has no keys. The numbers are `blur_sigma_px: 2`, `subsample: 4` and
   `classes: 3` in `porosity/config.yaml`, plus the function defaults of `trim_border` (245 / 10 / 0.95) and
   `normalise_brightness` (1 / 99).

**What the recipe is, and is not, invariant to.**
- A per-image percentile stretch followed by per-image Otsu is affine-invariant, so black level and gain cancel
  (`notes/research_report.md:247`). Black +25 moves it 0.00 B3-SD, contrast × 0.85 moves it 0.03.
- It is not invariant to the tone curve (gamma), to noise and sharpness (there is no noise matching) or to what else
  is in the frame (there is no crop).
- **Why the threshold sits below the midpoint, and why it drifts.** At its optimum, Otsu's threshold is the average of
  the two class means it separates [3]. For the 3-class case each threshold satisfies the same condition with its
  neighbouring classes; that is our own derivation from the between-class variance, not checked in a source.
  - The bright class includes the particles' edge-ramp pixels, so its mean sits below the bright mode. That puts the
    threshold at ≈ 43 % of the ramp instead of 50 %.
  - Our reading: any grey population just above the threshold, such as the textured, brighter-rendering regions of
    session 2060, lowers the bright-class mean, which pulls the threshold down further and admits more of that
    population.

## Evidence on our data

**Sources.** The independent audit of 2026-10-03 ran the production code (b0b5841) on Modal from the raw TIFs
(scorecard and per-variant rows; audit scratch, not in the repo). This README's own probe added the threshold
position, the crop-restricted fraction and the overlap with `h.bright` on the same 31 spots, the 4 perturbation
spots and the phantoms. B3-SD is the between-spot SD within Batch_3. Session R² is read against a chance level of
≈ 0.40 (13 sessions, 31 spots; ≈ 0.39 without 2316). The within-session p is the exact permutation of batch labels
inside the 5 mixed sessions (192 relabellings, minimum ≈ 0.005). "Incoming p" tests B1+B2 against B3 in the same
design (24 arrangements, minimum 0.042).

| | `bright_phase_frac` (this column) | `bright_frac` (successor, same denominator) | `bright_solid_frac` (Tier-1 KPI) |
|---|---|---|---|
| B1 / B2 / B3 mean ± SD | 0.104 ± 0.063 / 0.067 ± 0.015 / 0.070 ± 0.016 | 0.091 ± 0.056 / 0.049 ± 0.013 / 0.059 ± 0.010 | 0.100 ± 0.060 / 0.055 ± 0.013 / 0.066 ± 0.011 |
| η²(batch) (without 2316) | 0.19 (**0.013**) | 0.25 (0.14) | 0.25 (0.15) |
| Session R² (without 2316) | **0.95 (0.74)** | 0.90 (0.53) | 0.90 (0.50) |
| Within-session p; B1, B2 coefficient (B3-SD) | 0.65; −0.61, −0.17 | 0.29; −1.44, −1.37 | 0.24; −1.66, −1.50 |
| Incoming p (B1+B2 vs B3) | 0.58 | 0.083 | 0.083 |
| Lifted-black session 2060, z | **+4.70** | +0.77 | +0.60 |
| B3 session ICC (σ_site, σ_session) | **0.73** (0.0085, 0.0141) | 0.00 (0.0110, 0) | 0.00 (0.0122, 0) |
| Split-half r x / y, all (without 2316) | 0.78 / 0.86 (0.23 / 0.44) | 0.66 / 0.77 (−0.16 / 0.07) | 0.64 / 0.75 (−0.19 / 0.03) |
| Worst perturbation ratio (kind) | **0.81** (gamma 0.8) | 0.17 (gamma 1.25) | 0.14 (gamma 1.25) |
| Noise-seed spread ÷ B3-SD | 0 (no random noise top-up) | 0.010 | 0.011 |
| LOSO AUC B1 / B2 vs B3 | **0.29 / 0.15** | 0.64 / 0.71 | 0.61 / 0.71 |
| Phantom error, crop-matched (see item 7) | −0.4 to −2.0 % | ≤ 2.0 % | ≤ 1.6 % |

Earlier screens: `rank_features.py` gave sep 0.64, q 0.12, sep_loo 0.44, "no difference"
(`ledger/entries/bright_phase.yaml`). The feature screen put the perturbation ratio at 0.28, from a numpy replica on
other spots; the production code gives 0.81. The strongest acquisition correlate is `acq_curtain_index`
(|ρ| = 0.39, below the 0.6 leak bar). Spearman with `bright_solid_frac` is 0.69 (0.62 without 2316); within B3 the
Pearson r is only 0.33.

**What the numbers say**

1. **The batch signal is session 2316, and it is ambiguous.**
   - The two B1 spots there read 0.187 and 0.202 (z +7.4 and +8.3). Without them η² falls from 0.19 to 0.013.
   - The multi-Otsu threshold in those spots drops to 1.28 and 1.30 g (B3 1.50 ± 0.08, z −2.5 and −2.7). It follows
     their darker bright mode (1.665 g, against 1.88–2.32 in B3). This is the same grade ambiguity the verified audit
     found for the adaptive recipe (SF-2, SF-3). A particle-only darkening can inflate the area. A common threshold
     instead shrinks the excess to 1.5–2× (a lower bound). `si_fraction` reports 2316 as a bracket of 0.12–0.20 of
     the solid.
   - 2316 holds only B1 (n_eff = 1), so no test on these images can separate a material change from a session
     effect.
2. **Outside 2316 there is no batch effect.**
   - Within-session p = 0.65 and incoming p = 0.58. Without 2316 the batch deltas are −0.16 SD (B1) and −0.24 SD
     (B2).
   - Within-session contrasts in B3-SD: 2068 B2−B3 −0.13; 2080 B1−B3 −1.47 and B2−B3 −0.94; 2148 B1−B2 +1.02;
     2156 B1−B2 −1.29; 2272 B2−B3 +0.87. The signs disagree.
   - Leave-one-session-out AUC is 0.29 / 0.15. The direction learned from the other sessions points the wrong way in
     the held-out one, which is the signature of a session-driven column.
3. **The session component is the lifted-black session 2060 plus the frame.**
   - B3 ICC is 0.73 (σ_session 0.014 > σ_site 0.0085), and all of it comes from 2060. Its four spots read 0.078,
     0.096, 0.102 and 0.102; the other 13 B3 spots read 0.052–0.073. Without 2060, B3 is 0.063 ± 0.007 with ICC 0.00.
   - **About 40 % of the 2060 excess is the frame.** Measured on the harmonised crop, the same mask gives z +2.72
     instead of +4.70. In three of the four 2060 spots, the 250 top rows read 0.149–0.157 bright against 0.084–0.092
     in the crop.
   - **The rest is the threshold.** In tuy3zymq and kbdh4tri it sits at only 34 % and 38 % of the ramp (B3
     0.43 ± 0.03). As a result, 47 % and 28 % of their bright pixels lie outside `h.bright`, and 40 % and 22 % are
     darker than the adaptive threshold. The feature screen traced these pixels to textured, CBD-like regions that
     render brighter in that session.
4. **Split-half reliability measures the session, not the material.**
   - Left/right and top/bottom halves agree at r = 0.78 / 0.86 on all spots and 0.23 / 0.44 without 2316. That is
     higher than `bright_solid_frac` (−0.19 / 0.03), because the 2060 and frame components repeat in both halves.
   - Within B3 without 2060 the agreement is r = −0.55 / 0.10.
   - The RMS left−right difference is 0.024, or 1.5 B3-SD. Top halves read +0.0055 higher on average, because they
     contain the rows 0–249 frame artefact.
5. **Perturbations** (raw images of 4 B3 spots, |Δ| ÷ B3-SD):

   | Perturbation | Ratio |
   |---|---|
   | black +25 | 0.00 |
   | contrast × 0.85 | 0.03 |
   | noise σ 4 | 0.13 |
   | x-blur 1 / y-blur 1 | 0.17 / 0.17 |
   | blur σ 1 | 0.32 |
   | gamma 1.25 | 0.49 |
   | gamma 0.8 | **0.81** |

   - The worst case is gamma 0.8 on 0grcilhi: +0.0127, with the threshold's ramp position falling from 0.40 to 0.37.
     This fails the 0.5 invariance gate.
   - Noise and blur matter here (0.13–0.32) but not for the harmonised columns (≤ 0.03), which match noise first.
   - The zero seed spread is not a robustness credit. This pipeline simply has no random step.
6. **Frame content.**
   - The full-frame value minus the crop value ranges from −0.007 (1880) to +0.019 (2272) by session.
   - The last 40 rows read 0.19–0.35 bright in six spots. In epqdaau9 that is the Cu current-collector band, which
     adds +0.25 B3-SD (verified audit, SF-9).
   - The frame area also grows with session height.
7. **Phantoms** (synthetic two-level images with known Si fraction, 18 renders):
   - The audit scorecard lists errors of −17.8 % to +1.2 % (mean −6.6 %). Those errors compare this full-frame value
     with a truth computed on the standard crop. The phantoms draw particle centres only inside the frame, so the frame
     margins are depleted. Most of that error is the window, not the segmentation.
   - Measured on the same crop as the truth, the multi-Otsu mask reads 0.4–2.0 % low.
   - The `:ideal` rows equal the pipeline rows, because this column does not read the harmonised masks.
   - Multi-Otsu finds the boundary on clean two-level images. Its failures on real data come from the grey
     populations, tone curves and frame content that the phantoms do not have.

**Verdict.** Do not use it for decisions or as a classifier input. It agrees with `bright_solid_frac` on the one large
signal (2316). Everywhere else it adds a session term (2060, frame rows, tone curve) and no material information.

## Uncertainty and pitfalls

- **No error bar.** By back-of-envelope, a ≈ 0.06 bright fraction over this area has a single-image sampling error
  of ≈ 0.010–0.012. That is the two-point estimate from `si_fraction`, scaled to the larger frame. The 13 B3 spots
  outside 2060 scatter by 0.0067, so there is no room for a site-level material signal.
- **The threshold moves with the image content.** The stretch percentiles and the Otsu class means both depend on how
  much bright and grey material is in view: 1.28 g in 2316, 1.62 g in 2068.
  - A darker Si grade lowers the threshold with it, as with the adaptive recipe.
  - A grey CBD-like population pulls the threshold into itself (2060).
- **Whole frame, not the crop.** The frame includes the rows 0–249 top-of-frame artefact, the bottom rows (Cu band in
  epqdaau9) and an area that changes with session height.
- **Porosity in the denominator.** A calendering change moves the column with no change in Si dose. Use a fraction of
  the solid.
- **No object cleanup.** Noise specks and thin bright edges count. Blur and noise perturbations move the column 0.13–0.32
  B3-SD.
- **Tone curve.** Gamma 0.8 moves it 0.81 B3-SD. A session with a different detector curve can fake a shift.
- **Identity.** BSE brightness alone does not prove Si [4]. Confirm with EDS before reading area as Si wt%.
- **2D → 3D.** The area fraction is an unbiased estimate of the volume fraction for a random section [12]. That holds
  only for what the mask calls bright, and the mask itself is session-dependent.

## References

DOIs resolved through the Crossref API on 2026-10-03, except [2] (see note). The battery-mechanism abstracts of
[6]–[10] and [13] were checked in the verified audit (SF-11). DOIs come from Crossref lookups, the research report or
the `si_fraction` README, never from memory.

1. Otsu (1979) A Threshold Selection Method from Gray-Level Histograms. *IEEE Trans. Syst. Man Cybern.* 9:62–66.
   https://doi.org/10.1109/tsmc.1979.4310076
2. Liao, Chen, Chung (2001) A fast algorithm for multilevel thresholding. *J. Inf. Sci. Eng.* 17(5):713–727.
   DOI 10.6688/JISE.2001.17.5.1. This is the multi-Otsu algorithm behind `skimage.filters.threshold_multiotsu`; the
   DOI is cited in its docstring and resolves at doi.org to the Airiti record. **Not in Crossref.**
3. Xu, Xu, Jin, Song (2011) Characteristic analysis of Otsu threshold and its applications. *Pattern Recognit. Lett.*
   32:956–961. https://doi.org/10.1016/j.patrec.2011.01.021. The claim that Otsu's threshold is the average of the two
   class means, and that it biases toward the class with larger variance, comes from the abstract as summarised by a
   web search. The full text was not read.
4. Goldstein, Newbury, Michael et al. (2018) *Scanning Electron Microscopy and X-Ray Microanalysis*, 4th ed.
   Springer. https://doi.org/10.1007/978-1-4939-6676-9. Cited for BSE contrast rising with mean atomic number, a
   standard textbook point; the page was not checked.
5. Obrovac; Chevrier (2014) Alloy Negative Electrodes for Li-Ion Batteries. *Chem. Rev.* 114:11444–11502.
   https://doi.org/10.1021/cr500207g
6. Liu et al. (2019) Silicon oxides: a promising family of anode materials for lithium-ion batteries.
   *Chem. Soc. Rev.* 48:285–309. https://doi.org/10.1039/c8cs00441b
7. Moyassari et al. (2022) The Role of Silicon in Silicon-Graphite Composite Electrodes Regarding Specific Capacity,
   Cycle Stability, and Expansion. *J. Electrochem. Soc.* 169:010504. https://doi.org/10.1149/1945-7111/ac4545
   (porous Si–graphite, 0–20 wt% Si)
8. Kirkaldy et al. (2022) Lithium-Ion Battery Degradation: Measuring Rapid Loss of Active Silicon in
   Silicon–Graphite Composite Electrodes. *ACS Appl. Energy Mater.* 5:13367–13376.
   https://doi.org/10.1021/acsaem.2c02047
9. Wu et al. (2024) Fundamental Understanding of the Low Initial Coulombic Efficiency in SiOx Anode for Lithium-Ion
   Batteries: Mechanisms and Solutions. *Adv. Mater.* 36. https://doi.org/10.1002/adma.202405751
10. Moon et al. (2021) Interplay between electrochemical reactions and mechanical responses in silicon–graphite
    anodes and its impact on degradation. *Nat. Commun.* 12. https://doi.org/10.1038/s41467-021-22662-7
11. Kirner et al. (2020) Optimization of Graphite–SiO blend electrodes for lithium-ion batteries.
    *J. Power Sources* 450:227711. https://doi.org/10.1016/j.jpowsour.2020.227711
12. Russ; DeHoff (2000) *Practical Stereology*, 2nd ed. Springer. https://doi.org/10.1007/978-1-4615-1233-2
    (Delesse: A_A = V_V)
13. Chen et al. (2020) Development of Experimental Techniques for Parameterization of Multi-scale Lithium-ion
    Battery Models. *J. Electrochem. Soc.* 167:080534. https://doi.org/10.1149/1945-7111/ab9050 (LG M50,
    graphite–SiOx negative electrode)
14. Dahari, Docherty, Kench et al. (2025) Prediction of Microstructural Representativity From A Single Image.
    *Adv. Sci.* 12. https://doi.org/10.1002/advs.202414149 (ImageRep)
15. Project sources (no DOI): `notes/research_report.md` §2, §6.1, :70, :192, :247; `notes/feature_screen.md`
    (phase-fraction screen, 2060 table); `features/si_fraction/README.md`; `ledger/entries/bright_phase.yaml`;
    GB/T 38823-2020 as cited in the research report.
