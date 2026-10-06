# Acquisition check (preprocessing step 5)

How each spot was imaged. `python preprocessing/process_data.py` measures it for every spot, prints a WARNING for each
spot that was not imaged like the known spots (curtaining, blur, noise, Inlens burn-out, ...) and writes ten `acq_`
columns plus the grade to `processed/acquisition.csv`. They are deliberately kept out of `processed/features.csv`.
**These are not material KPIs.** Never use them as classifier inputs and never rank them as batch-separating features. Several of them identify Batch_3's imaging sessions, so a model that sees
them can learn "how the picture was taken" instead of the material.

| Column | Unit | Role | Meaning |
|---|---|---|---|
| `acq_bse_black_level` | raw grey (0–255) | **gate** | BSE black level: 0.5th percentile of the blurred crop. About 0 when the detector clips black, 23–24 in session 2060 |
| `acq_bse_graphite_level` | raw grey | diagnostic | Raw BSE grey level of graphite (the harmonisation anchor) |
| `acq_bse_noise_sigma` | graphite units | **gate** | Immerkær noise σ of the anchored BSE (0 = black, 1 = graphite), before the noise top-up |
| `acq_bse_noise_above_target` | 0/1 | diagnostic flag | 1 = noisier than the harmonisation target (0.235), so the noise could not be equalised |
| `acq_bse_clip0_frac` | fraction | diagnostic | Share of raw BSE pixels at 0. Depends on porosity, so it never gates |
| `acq_cnr` | ratio | diagnostic | (graphite − black) / noise σ, with σ measured on graphite interiors only |
| `acq_inlens_sat255_frac` | fraction | **gate** | Share of raw Inlens pixels at 255 |
| `acq_inlens_noise_sigma` | rank units (0–1) | diagnostic | Immerkær noise σ of the rank-normalised Inlens, before its top-up |
| `acq_curtain_index` | ratio | **gate** | Vertical-stripe (curtaining) power on the SE spectrum relative to its neighbourhood. 1 = no stripes |
| `acq_focus` | graphite units² | **gate** | Laplacian variance on graphite interiors, after 2×2 binning, minus the white-noise part. Higher = sharper |

`gate_status(values)` in `acquisition.py` turns a spot's checked columns into G-A / G-B / G-C, and `warnings_for(values)`
turns them into the plain-language warnings. The frozen limits are in `acquisition.yaml`.

## Battery impact at a glance

None of these columns says anything about the cell. They say whether the material KPIs from a spot can be trusted.

| If it goes … | What it means | Good, bad or neither? | Confidence |
|---|---|---|---|
| `acq_bse_black_level` up | The detector offset was lifted (like session 2060). Anchored KPIs are unaffected (Δ = 0 under black +25), but the value alone points at B3-only sessions: a leakage cue | neither (gate: watch) | strong |
| `acq_bse_noise_sigma` up | Shorter dwell time or less averaging. Small objects and edges get lost. Above 0.235 the noise top-up cannot equalise it | bad for measurement | strong |
| `acq_curtain_index` up | Ion-milling curtaining (vertical stripes). It biases orientation, crack and gradient KPIs | bad for measurement | strong for 2316-like curtains, low for small changes |
| `acq_focus` down | Defocus or a lower detector bandwidth. Sizes, edges and counts are biased | bad for measurement | moderate (graphite texture also enters) |
| `acq_inlens_sat255_frac` up | Inlens gain set too high, or charging. Carbon-binder ridges are lost in Inlens-based KPIs | bad for measurement | moderate |
| `acq_bse_clip0_frac` up | Mostly more porosity (the pores are what clips), or a lower offset | neither (diagnostic only) | strong |

**Best value:** inside the known-session envelope (Gate 1 = G-A). No direction is better.

**Our batches:**
- **Batch_1:** 5 of 7 spots G-A. The two 2316 spots are G-C on the curtain index: 1.64–1.68, against ≤ 1.16 everywhere
  else and a tested range that ends at 1.30. So the Si-phase lead sits in a curtained session that is not comparable on
  acquisition. Preprocessing prints a curtaining WARNING for both.
- **Batch_2:** all 7 spots G-A, with nothing unusual.
- **Batch_3:** all 17 spots G-A, but its own sessions are the quietest (2088), the sharpest (1904) and the only ones
  with a lifted black (2060, 1612, 2088). This is the leakage trap.
- For Batch_1 and Batch_2 these statuses are partly circular, because their own spots helped set the envelope (the
  upper noise bound is the B1 spot f1vzngrs, for example). For a new batch they are not.

## What it measures

Each column describes the microscope, not the electrode. All columns are measured on the same central crop that
`features/_common` uses: 1336 rows from the artefact-free band, minus 8 px on each side, about 5800 µm².

- **BSE black and graphite levels.** These are the two grey levels that anchor the harmonised BSE.
  - In 27 of 31 images (all but session 2060), the detector offset clips some BSE pixels at 0. The measured black level
    is then a clip floor, not the physical black.
  - The measured level (0.5th percentile) is 0–2 in most sessions, ≈ 4.4 in 2088 and ≈ 6 in 1612 (where fewer than
    0.5 % of pixels clip), and 23–24 in the unclipped session 2060.
- **Noise and CNR.** Pixel-to-pixel noise, estimated without segmenting anything, is set by dwell time, frame
  averaging and beam current. CNR expresses the same noise as graphite-to-black contrast over noise σ.
- **Clipping and saturation.** `acq_bse_clip0_frac` is the share of BSE pixels lost at black (these are pore pixels).
  `acq_inlens_sat255_frac` is the share of Inlens pixels lost at white (bright carbon-binder ridges and edges).
- **Curtaining.** Ion-milling curtains are vertical stripes, ≈ 0.2–0.5 µm apart, milled into the polished face. The
  preparation method (FIB or broad ion beam) is not confirmed for this data. They are seen best on SE/ETD. In this data set they are strong only in session 2316 (both Batch_1 outlier spots), visible by
  eye.
- **Focus.** Fine (≈ 50–100 nm) texture on flat graphite after the noise contribution is subtracted. It measures
  focus and detector bandwidth, together with the graphite's own polishing texture.

## Why it matters for the battery

None of these columns has a direct battery meaning. What they do is protect every material KPI from mistaking a
microscope change for a material change.

- **Session confound.** Image height marks 13 imaging sessions. Session explains 69–95 % of the variance of the first
  features, and batch is confounded with session everywhere except in 5 mixed sessions (research report §1.2, §7.1).
- **Noise changes what segmentation finds.** It changes counts, edges and small-object sizes: processed σ drove pore
  median size (r = −0.71) and porosity (r = −0.60) before noise matching (§7.2). Noise is estimated here with the
  Immerkær Laplacian-difference estimator [1].
- **Curtains bias directional and porosity measures.** They bias gradient-based anisotropy: session 2316 has the
  strongest curtains and the lowest E_yy/E_xx (§7.10). FIB milling conditions change both the curtaining and the
  apparent pore-area fraction of porous electrode layers [5]. On a Si/C–graphite anode, which is close to this
  material, curtain artefacts needed a dedicated Fourier filter before segmentation [4].
- **Focus and noise are standard quality indices.** Noise, contrast, focus, curtaining and charging are the standard
  quality problems of FIB-SEM data, and quality indices exist for each [3]. The variance of the Laplacian is a
  standard focus measure [2].
- **Settings legitimately differ between sessions.** Multi-material battery samples (hard particles, soft binder) are
  often imaged with different set-ups [6], so differences between sessions are expected, not exceptional.
- **The leakage trap is real here.** `notes/polaron_chat.md` records it: 18 of 31 spots have an image height found in
  only one batch, the lifted black level appears only in Batch_3, and the SE detector name appears only in Batches 2
  and 3. A blind-test classifier can score "correctly" on these cues alone. This is the leakage failure described for
  ML-based science in general [7] and documented for site-specific signatures in histology [8].
- **The columns are negative controls.** Real material KPIs should not track them [9]. The batch must not be "removed"
  by regressing them out, because that inflates confidence [10].

## Industry / Polaron use

- **Academic practice, not a published vendor gate.** FIB-SEM image-quality indices exist [3], but no vendor publishes
  an acquisition gate for incoming electrode QC.
- **Closest industrial analogue: measurement-system analysis.** Under AIAG MSA, a retained reference sample is
  re-imaged in every session in which a lot is imaged. That turns the session confound into a calibration (research
  report §6.3, §6.8).
- **Polaron.** Polaron's "Trust in Microstructure Quantification" and its representativity tool ImageRep [11] address
  sampling error. This folder covers the acquisition side of the same trust question.
- **What would move these columns.** A different microscope, kV, detector gain or offset, dwell time or line
  averaging, working distance or focus, or FIB milling current and angle. Curtaining can be reduced by rocking the
  sample during milling (Amass literature, DOI 10.1017/S1431927617000241). A supplier or process change would not
  move them, except through clipping (`acq_bse_clip0_frac` follows porosity).

## How it is computed

All inputs come from `features._common.harmonise.harmonised(sample)` (`h`) and the raw TIFs cut to the same crop
(`h.acq["crop"]`). Tuning numbers live in `acquisition.yaml`.

1. **`acq_bse_black_level`, `acq_bse_graphite_level`, `acq_bse_noise_sigma`, `acq_bse_noise_above_target`.** Copied
   from `h.acq`. The black level is the 0.5th percentile of the σ = 2 px blurred crop. The graphite level is the
   smoothed, parabola-refined histogram mode between the 15th and 92nd pixel percentiles. Noise is the Immerkær
   σ [1] of the anchored image before the noise top-up. The flag is set when that σ exceeds
   `_common` `noise.bse_target_sigma` = 0.235.
2. **`acq_bse_clip0_frac`.** Share of raw BSE crop pixels equal to `saturation.bse_black_code` (0).
   **`acq_inlens_sat255_frac`.** Share of raw Inlens crop pixels equal to `saturation.inlens_white_code` (255).
   **`acq_inlens_noise_sigma`.** Copied from `h.acq["inlens_noise_sigma"]`: Immerkær σ after rank normalisation.
3. **Graphite interiors** (used for `acq_cnr` and `acq_focus`). Pixels with `h.bse_blur` inside
   `graphite_interior.range` = [0.85, 1.15], then eroded with a 9 × 9 square (`erode_px` = 4) so no particle edge is
   included. This is about 45 % of the crop.
4. **`acq_cnr`** = 1 / σ, where σ is the Immerkær response averaged over graphite interiors only. The image is the
   anchored BSE before the top-up. Because the image is in graphite units, 1/σ equals (graphite − black) / σ_raw.
5. **`acq_focus`.**
   - Bin the anchored BSE (before top-up) 2 × 2 (`focus.bin_px`).
   - Take the variance of the 4-neighbour Laplacian over binned pixels whose four source pixels are all graphite
     interior.
   - Subtract `laplacian_noise_gain` · σ² / bin² = 20 σ² / 4. That is the Laplacian variance white noise of σ would
     give after binning, using the interior σ from step 4. This is the screen's `bse_focus_lap2_excess` recipe [2],
     with the noise measured on the same pixels as the Laplacian.
6. **`acq_curtain_index`.**
   - Take the SE crop as the rank-normalised `h.se`, so black level, gain and gamma cannot move it.
   - Cut Hann-windowed 256 × 256 tiles (`curtain.tile_px`): 5 tile rows × 27 tile columns. The window stops the image
     border from painting its own line on the frequency axes.
   - Average the tiles' power spectra (Welch).
   - Vertical stripes put their power on the ky = 0 line. Within `kx_range` = 0.05–0.15 cycles/px (periods 7–20 px,
     where the 2316 curtains sit), the index is the mean power at |ky| ≤ `band_ky_bins` (2 bins) divided by the mean
     power at the same kx with |ky| between `flank_ky_bins` = 4 and 10 bins.
   - White noise gives ≈ 1. A steep isotropic spectrum reads a little above 1, because at low kx the flank lies at a
     larger |k| than the line (blurred white noise, σ = 2 px: 1.17; see "Uncertainty and pitfalls").
   - The flank is kept close to the line on purpose: for the raw-SE variant, a 4–16 bin flank let blur σ = 1 move the
     index by 1.1 B3-SD, against 0.64 with 4–10.

**Gate 1: how a new batch is compared to the known-session envelope** (`gate_status`, limits in `acquisition.yaml → gate`).

- Five columns gate: black level, BSE noise σ, Inlens saturation, curtain index and focus. These are the four
  descriptors named in research report §6.5, plus focus.
- Each gate column has two intervals, frozen 2026-10-03 and rounded outward:
  - the **envelope**: [min, max] over the 31 known spots (13 sessions; the curtain index leaves out 2316, see below);
  - the **tested range**: [min, max] over the known spots plus their 24 perturbed copies (black +25, gamma 0.8 and
    1.25, contrast × 0.85, noise σ 4, blur σ 1, on 4 baseline spots). These are the acquisition changes the KPI
    robustness tests covered.
- Exceptions:
  - Black level and saturation start at 0.
  - The noise tested range goes up to the top-up target 0.235. Anything below the target is topped up to the same
    noise, so the KPIs see identical noise.
  - **Curtain envelope without session 2316:** [0.888, 1.165], the 29 other spots. 2316 is the one session with
    curtains visible by eye (z ≈ +9 against B3). Inside the envelope, it would let 2316-like curtaining pass as G-A.
  - **Upper tested bound of curtain index and Inlens saturation:**
    - No perturbed copy exceeded the known maximum of these two columns. The [min, max] rule therefore left no G-B
      room above the envelope, and a clean spot just above the known maximum would have been G-C.
    - These two bounds are instead the envelope maximum, plus the largest upward perturbation shift, plus 2
      full-crop sampling SDs from the split halves.
    - Curtain index: 1.164 + 0.023 + 2 × 0.056 ≈ **1.30**. Inlens saturation: 0.0655 + 0.025 + 2 × 0.004 ≈ **0.10**.
  - Both exceptions were added in review (2026-10-03). They are the reason the 2316 spots are G-C.
- `gate_status` does not check pixel size or the detector set, the identity part of §6.5. `analysis/verdict.py`'s
  Gate 1 does.
- For each new spot:

  | Status | Condition | Action |
  |---|---|---|
  | **G-A** | Every gate column inside its envelope | Proceed |
  | **G-B** | Some gate column outside the envelope but inside the tested range | Proceed, with a WARNING ("treat with care") |
  | **G-C** | Some gate column outside the tested range, or missing | NOT COMPARABLE: KPIs shown, no material verdict, re-image beside a retained reference |

- `gate_status` returns the per-column detail too.
- The verdict does not read these grades (its Gate 1 checks only pixel size and detector set). Read the preprocessing
  warnings before trusting a verdict.
- Recommended use:
  - Drop G-C spots from the material verdict but list their KPIs. If fewer than 3 spots remain, Gate 0
    (INSUFFICIENT DATA) applies.
  - The lot status is the worst status among the spots that are used.
  - Where the only G-C column is Inlens saturation or the curtain index, the spot's BSE grey-level KPIs can still be
    shown as a sensitivity check:
    - Inlens saturation biases Inlens-derived KPIs.
    - Curtains (topographic, seen on SE) mainly bias gradient, orientation and crack KPIs.
- The diagnostics (graphite level, clip fraction, CNR, Inlens noise and the above-target flag) are printed on the
  certificate and never gate. Gating on them would turn real material changes, such as more porosity giving more
  clipped pixels, into "re-image".

## Evidence on our data

Computed on all 31 spots with the code in this folder; scratch scripts printed to stdout only. Chance session R² ≈ 0.40.
The within-session p is the exact permutation over all 192 within-mixed-session batch relabellings of
y ~ C(session) + C(batch), with the RSS drop as statistic (minimum attainable p ≈ 0.005). b1 and b2 are the
session-adjusted B1 − B3 and B2 − B3 effects in B3 between-spot SD units (sd3).

| Column | B1 mean ± sd | B2 mean ± sd | B3 mean ± sd | η²(batch) | session R² | within-session p | b1, b2 (sd3) |
|---|---|---|---|---|---|---|---|
| `acq_bse_black_level` | 0.12 ± 0.14 | 0.33 ± 0.43 | 7.5 ± 9.4 | 0.22 | 1.00 | 0.78 | −0.02, −0.01 |
| `acq_bse_graphite_level` | 56.4 ± 3.8 | 54.6 ± 4.8 | 57.4 ± 3.5 | 0.08 | 0.92 | 0.66 | −0.46, −0.10 |
| `acq_bse_noise_sigma` | 0.187 ± 0.017 | 0.187 ± 0.016 | 0.166 ± 0.022 | 0.24 | 0.97 | 0.69 | +0.26, +0.09 |
| `acq_bse_noise_above_target` | 0 | 0 | 0 | – | – | – | (never fires on known data) |
| `acq_bse_clip0_frac` | 0.027 ± 0.009 | 0.025 ± 0.009 | 0.008 ± 0.009 | 0.53 | 0.93 | 0.77 | −0.39, −0.16 |
| `acq_cnr` | 5.35 ± 0.40 | 5.28 ± 0.44 | 6.10 ± 0.83 | 0.27 | 0.99 | 0.83 | −0.09, −0.02 |
| `acq_inlens_sat255_frac` | 0.016 ± 0.010 | 0.022 ± 0.009 | 0.025 ± 0.020 | 0.06 | 0.80 | **0.094** | −0.74, −0.20 |
| `acq_inlens_noise_sigma` | 0.070 ± 0.003 | 0.066 ± 0.019 | 0.062 ± 0.017 | 0.06 | 0.89 | 0.51 | +0.49, +0.21 |
| `acq_curtain_index` | 1.20 ± 0.32 | 0.99 ± 0.07 | 1.05 ± 0.07 | 0.19 | 0.94 (0.64 without 2316) | 0.56 | +0.37, −0.16 |
| `acq_focus` | 0.027 ± 0.008 | 0.025 ± 0.003 | 0.036 ± 0.022 | 0.09 | 1.00 | **0.062** | −0.00, −0.04 |

**Per session** (range over the session's spots). Every column is locked to the session:

| Session | Spots | black | graphite | noise σ | clip0 | CNR | Inlens sat | Inlens σ | curtain | focus |
|---|---|---|---|---|---|---|---|---|---|---|
| 1612 | B3×2 | 5.8–6.0 | 56.1–56.4 | 0.184 | 0.002 | 5.50–5.51 | 0.021–0.065 | 0.068–0.098 | 1.10–1.16 | 0.037–0.038 |
| 1780 | B1×1 | 0.0 | 58.9 | 0.174 | 0.036 | 5.56 | 0.006 | 0.066 | 1.00 | 0.022 |
| 1880 | B1×1 | 0.1 | 58.0 | 0.180 | 0.024 | 5.53 | 0.036 | 0.072 | 1.04 | 0.022 |
| 1904 | B3×3 | 0.4–1.8 | 54.7–55.2 | 0.147–0.153 | 0.008–0.015 | 6.52–6.69 | 0.037–0.051 | 0.044–0.054 | 0.91–1.07 | **0.078–0.081** |
| 2048 | B2×2 | 0.0–0.1 | 52.0–52.2 | 0.192 | 0.030–0.037 | 4.98–4.99 | 0.011–0.014 | 0.057–0.058 | 0.96–1.01 | 0.027–0.028 |
| 2060 | B3×4 | **22.9–24.4** | 61.2–61.7 | 0.175–0.181 | **0.000** | 5.59–5.75 | **0.000–0.001** | 0.070–0.075 | 0.98–1.12 | 0.030–0.032 |
| 2068 | B2×1, B3×3 | 0.8–1.7 | 51.6–58.0 | 0.166–0.186 | 0.010–0.014 | 5.41–5.89 | 0.033–0.040 | 0.040–0.048 | 1.04–1.10 | 0.026–0.027 |
| 2080 | B1, B2, B3 | 0.1–0.4 | 57.5–61.2 | 0.160–0.175 | 0.019–0.028 | 5.63–5.91 | 0.008–0.021 | 0.054–0.070 | 0.93–1.01 | 0.021–0.022 |
| 2088 | B3×3 | 4.3–4.4 | 59.6–59.9 | **0.128–0.130** | 0.003 | **7.55–7.59** | 0.010–0.021 | 0.050–0.057 | 1.01–1.13 | 0.016 |
| 2148 | B1, B2 | 0.0–0.1 | 49.9–50.5 | 0.209–0.214 | 0.024–0.030 | 4.74–4.77 | 0.013–0.026 | 0.067–0.074 | 0.89–0.91 | 0.028–0.029 |
| 2156 | B1, B2 | 0.4–0.9 | 61.4–61.7 | 0.168–0.172 | 0.015–0.020 | 5.80–5.86 | 0.022–0.032 | 0.074–0.082 | 1.08–1.09 | 0.021 |
| 2272 | B2, B3 | 0.0–0.2 | 52.4–52.9 | 0.194–0.197 | 0.023–0.034 | 5.01–5.04 | 0.016–0.031 | 0.092–0.100 | 0.94–1.04 | 0.026 |
| 2316 | B1×2 | 0.0 | 54.3–54.5 | 0.195–0.202 | 0.026–0.042 | 5.06–5.07 | 0.012–0.014 | 0.065–0.070 | **1.64–1.68** | 0.037–0.039 |

**What the numbers say**

1. **Everything is session-locked; batch shows up only through sessions.**
   - Session R² is 0.80–1.00 for every column. The pooled within-session SD is a small fraction of the total, for
     example noise 0.0051 vs 0.022 and focus 0.0008 vs 0.017.
   - The large batch η² values come from sessions that hold only B3: clip0 0.53, CNR 0.27, noise 0.24, black 0.22.
     Inside the mixed sessions, no column shows a batch effect: exact p = 0.51–0.83 for 7 of the 9 testable columns.
   - The B3-only sessions really were imaged differently: quieter (2088: σ 0.128), lifted black level (2060, 1612,
     2088) and sharper (1904: focus 3× every other session).
2. **Two thin within-session hints.**
   - **Inlens saturation**, p = 0.094. B1 saturates less than its co-session spots in all 3 sessions where it meets
     another batch: 2080, 2148 and 2156, b1 = −0.74 sd3. B2 is also below B3 in 2068 and 2272. The screen found the
     same, p = 0.036. This could be a carbon-binder or charging difference visible in Inlens, which would make it
     partly material. It rests on 3 B1 spots.
   - **Focus**, p = 0.062. B2 is 2–6 % below its co-session spots in 4 of the 5 mixed sessions (equal in 2156),
     about 1 pooled within-session SD. That is 0.02–0.05 sd3, because session 1904 dominates sd3, and far below the
     ×5 range between sessions. Focus is taken on graphite interiors, so graphite polishing texture is a possible
     material component.
   - About 10 columns were tested here (≈ 50 in the screen), so one or two p < 0.1 are expected by chance. Neither is
     evidence of a batch effect.
3. **Material dependence: which columns must not gate.**
   - **Clip fraction follows porosity.** After removing session means, `acq_bse_clip0_frac` correlates with
     harmonised porosity at r = +0.63 (p < 0.001) and with bright fraction at r = −0.51. Within B3, Spearman ρ = +0.60,
     against ρ = 0.56 in the research report. This confirms it as a diagnostic.
   - **Whole-crop noise σ also follows porosity** (r = −0.62 after removing session means), because clipped pore pixels
     carry no noise. The effect is small: −0.0023 σ per +0.01 porosity, so a +0.03 porosity shift moves σ by 0.007,
     against an envelope width of 0.086.
   - **Interior-based noise follows porosity less.** Its σ (= 1/`acq_cnr`) gives r = −0.42, and the interior and
     whole-crop σ agree at r = 0.987. `acq_cnr` is therefore the cleaner noise readout, while `acq_bse_noise_sigma` is
     the value the top-up actually uses.
   - **Inlens rank noise depends on the material too** (r = −0.50 with porosity), so it stays a diagnostic.
   - **Curtain index, focus and black level show no within-session material link:** r = −0.02, −0.13 and −0.29, all
     n.s.
4. **Curtain index: session 2316 is the only strongly curtained session.**
   - It reads 1.64–1.68 against 0.89–1.16 for every other spot (B3 1.045 ± 0.068, z = +8.8 and +9.3). This matches
     what is visible by eye in the SE images.
   - The stripes are site-wide: 70–72 % of 256-px tiles exceed 1.3, against 19–37 % in the two B3 spots checked (cfe5vt7s, ptg8lmto). Tiles with more
     bright phase show slightly *less* stripe signal (ρ = −0.25 and −0.27), so the Si particles do not seed the
     curtains.
   - The 2316 Si-phase lead therefore sits in the most curtained session, and its gradient-based anisotropy values are
     suspect (research report §7.10).
   - Without 2316, session R² falls to 0.64, and the split-half reliability within B3 is poor (r = 0.16; mean |L−R| =
     1.0 sd3). The index detects strong, 2316-like curtaining, not fine differences inside the baseline range.
5. **Split-half reliability** (left vs right half of the crop, all 31 spots):

   | Column | r | mean \|L−R\| |
   |---|---|---|
   | Focus | 1.00 | 0.04 sd3 |
   | BSE noise | 0.99 | 0.11 sd3 |
   | Clip fraction | 0.93 | 0.30 sd3 |
   | Inlens saturation | 0.88 | 0.29 sd3 |
   | Curtain index | 0.83 | 1.04 sd3 |

6. **Perturbation response.** On the raw uint8 images of B3 spots 71vgq3fw, cfe5vt7s, hzumfsms and 0grcilhi, the
   table gives max |Δ| / B3 between-spot SD. For gate descriptors a large response to *their own* perturbation is the
   point; what matters is that they ignore the others.

   | Column | black +25 | gamma 0.8 | gamma 1.25 | contrast ×0.85 | noise σ 4 | blur σ 1 |
   |---|---|---|---|---|---|---|
   | `acq_bse_black_level` | 2.66 (Δ = +25.0 exactly) | 1.51 | 1.09 | 0.95 | 0.16 | 0.01 |
   | `acq_bse_graphite_level` | 7.23 (+25) | 5.82 | 5.29 | 0.13 | 0.01 | 0.07 |
   | `acq_bse_noise_sigma` | **0.00** | 1.46 | 1.94 | **0.06** | 1.37 | 7.69 |
   | `acq_bse_clip0_frac` | 2.26 | 0.00 | 0.44 | 2.26 | 0.63 | 1.26 |
   | `acq_cnr` | 0.00 | 1.91 | 1.58 | 0.09 | 1.20 | 188 (blur removes pixel noise) |
   | `acq_inlens_sat255_frac` | 1.27 | 0.00 | 0.00 | 1.89 | 0.79 | 1.34 |
   | `acq_inlens_noise_sigma` | 0.01 | 0.00 | 0.01 | 0.00 | 1.04 | 3.60 |
   | `acq_curtain_index` | **0.00** | **0.00** | **0.01** | **0.01** | 0.22 | 0.67 |
   | `acq_focus` | **0.00** | 1.23 | 1.88 | **0.07** | **0.12** | 2.66 |

   - **Black level** responds exactly (+25.0). Gamma and contrast move it because they move the grey of the floor.
   - **Noise σ and focus** (graphite units) ignore offset and gain. They scale with gamma, as γ and γ², because gamma
     changes the local gain at graphite.
   - **Focus ignores added noise** (0.12), so the white-noise subtraction works.
   - **Curtain index** is exactly blind to black level, gamma and contrast because of the rank normalisation. It moves
     0.22 sd3 with noise and 0.67 sd3 with blur.
     - Blur changes the spectral slope, and the sign of the shift depends on the spot: +0.023 on cfe5vt7s, −0.046 on
       0grcilhi.
     - On the curtained 2316 spot 4ih2ggld, blur raises the index (1.68 → 1.84).
   - Gate result:
     - 29 of 31 known spots are G-A. The two 2316 spots are G-C on the curtain index alone.
     - Of the 24 perturbed copies, 16 come out G-B (black +25 and blur σ 1 always do) and none G-C, because the tested
       range is built from them.
7. **Acquisition-only classifier** (the leakage ceiling; chance balanced accuracy 0.33, SE ≈ 0.09 at n = 31).
   - **These 9 columns** (image height not included):
     - logistic regression: 0.58 leave-one-site-out (label-permutation p = 0.03) and 0.49 leave-one-session-out
       (p = 0.04);
     - random forest: 0.59 and 0.49;
     - the 5 gate columns alone: 0.49–0.58 and 0.49–0.53.
   - **Harmonised material fractions** (porosity + bright) score 0.43–0.54 and 0.30–0.36.
   - **The screen** (`acquisition_null.json`, logistic regression, leave-one-site-out / leave-one-session-out) found:
     - 14 raw descriptors including height: 0.70 / 0.51;
     - image-content raw descriptors: 0.68 / 0.63;
     - post-harmonisation descriptors: 0.66–0.70 / 0.63–0.70;
     - pore-floor brightness alone: 0.61 / 0.61;
     - anchored material features: at chance (0.30–0.33 / 0.20–0.29).
   - So acquisition alone identifies batch above chance even across sessions. Any material model must clearly beat
     ≈ 0.6–0.7 under both schemes before it shows material signal (research report §6.9).
8. **Runtime.** 0.37–0.58 s per spot for all five functions, with raw TIFs preloaded and the shared harmonisation
   excluded. Of that, `acq_cnr`'s erosion and convolution take ≈ 0.2 s. Loading the three raw TIFs adds ≈ 1 s when the
   harmonisation came from the disk cache. The review re-run on 9 spots measured 0.4–1.2 s on the busy shared machine.
9. **Review re-check** (2026-10-03).
   - Nine spots were re-run: every mixed session, plus 2060, 2316, 1904 and 2088. They reproduce `all.jsonl` exactly.
   - An independent re-implementation agrees to within 1e-5 (relative). It used a 9 × 9 binary erosion, `convolve2d`
     and a full `fft2`.
   - The exact 192-relabelling permutation test, η², session R², b1/b2, the correlations and the gate counts were all
     recomputed and match the tables above.
   - Fresh harmonisation of a 2316 spot agrees with the cached one to within 5e-6.

## Uncertainty and pitfalls

- **Envelope from 13 sessions.** The known-session envelope is [min, max] over 31 spots from 13 sessions (12 for the
  curtain index).
  - A new session can fall just outside it by chance: the hzumfsms contrast-×0.85 copy is G-B on a 0.0003 noise
    difference. G-B costs only a flag and a bias term, so this is deliberate.
  - For Batch_1 and Batch_2 the frozen envelope is partly circular, because their own spots helped set it.
- **Inlens noise matching misses one spot.** i9jiqjwl (2272) has an Inlens σ of 0.1003, above the `_common` Inlens
  target 0.10, so its Inlens is not noise-equalised (`h.acq["inlens_noise_above_target"]` = True). The target comment
  in `_common/config.yaml` says the noisiest known Inlens is ≈ 0.096.
  - The effect is negligible: the spot keeps σ 0.1003, against 0.100 for every topped-up spot.
  - The target has no margin, though. A slightly noisier new batch would not be equalised.
- **Thin tested range.** The tested range rests on 4 baseline spots and 6 perturbations. It says nothing about kV,
  detector-segment or scan-direction changes. A 1-px blur along one axis only, a fast-scan low-pass, moved boundary
  orientation features by 0.4–0.8 SD in the orientation verification. A Px/Py high-frequency power ratio would be a
  useful extra gate column; it is not built.
- **The black level is a clip floor.** In 27 of 31 images it is not the physical black. With black clipped, the
  graphite-units scale is (graphite − 0) and the CNR is understated by an unknown amount. Compare CNR within a
  session, not across.
- **Material leaks in.** Through clipping, noise σ follows porosity (−0.0023 per +0.01 porosity). Inlens saturation
  may follow carbon-binder edges (the B1 hint above). Focus includes graphite polishing texture. That is why gate
  limits are the wide tested ranges, not tight z-scores, and why clip fraction, CNR and Inlens noise only appear on
  the certificate.
- **Curtain index only detects strong curtaining.** It is reliable only for strong (2316-like) curtaining: B3
  split-half r = 0.16. Its full-crop sampling SD is about 0.056 (from the split halves), most of the B3 SD of 0.068.
  - Steep near-vertical graphite basal striations also put power near ky = 0 and can read as weak curtains.
  - Spectral-slope bias: a steep (blurred) isotropic spectrum reads above 1, because at low kx the flank lies at a
    larger |k| than the line.
    - Synthetic white noise reads 1.02; the same noise blurred at σ = 1 and σ = 2 px reads 1.05 and 1.17.
    - A radially whitened variant removes this bias (≈ 1.01 for both). On our data, though, it neither separated 2316
      better (z +10.0 vs +9.3) nor resisted blur better (0.69 vs 0.67 sd3), so it was not adopted (review check).
  - The axis is right. The same index on the transposed SE (horizontal stripes) reads 1.15–1.33 on every spot checked,
    2316 included: horizontal flake layering, not curtains. A synthetic vertical-stripe image reads ≫ 1, a horizontal
    one ≈ 1.
- **2316 is confounded.** Session 2316 is both the most curtained session and the Si-phase lead (n_eff = 1). The two
  cannot be separated without re-imaging those spots, or a retained reference, in a shared session.
- **The disk cache stores `h.se` as float16.** The curtain index then differs from a fresh computation by at most
  6 × 10⁻⁵, which is negligible.
- **2D/3D.** Not applicable: these columns describe images, not microstructure.
- **Leakage guard.** `acq_bse_black_level` alone reproduces the "lifted black level ⇒ Batch_3" cue, and the session
  table above lets anyone map values back to sessions. Any ranking (`analysis/rank_features.py`) or classifier must
  drop columns starting with `acq_`.

## References

1. Immerkær (1996) Fast Noise Variance Estimation. *Computer Vision and Image Understanding* 64:300.
   https://doi.org/10.1006/cviu.1996.0060 (DOI checked against Crossref)
2. Pech-Pacheco, Cristóbal, Chamorro-Martínez, Fernández-Valdivia (2000) Diatom autofocusing in brightfield
   microscopy: a comparative study. *Proc. ICPR 2000*. https://doi.org/10.1109/icpr.2000.903548 (ledger, verified)
3. Roldán, Redenbach, Schladitz et al. (2024) Image quality evaluation for FIB-SEM images. *J. Microsc.*
   https://doi.org/10.1111/jmi.13254 (Amass literature; Crossref)
4. Kim, Lee, Hong et al. (2019) Image Segmentation for FIB-SEM Serial Sectioning of a Si/C–Graphite Composite Anode
   Microstructure Based on Preprocessing and Global Thresholding. *Microsc. Microanal.*
   https://doi.org/10.1017/S1431927619014752 (Amass literature; Crossref)
5. Kwon, Jo, An (2026) Imaging optimization of FIB cross sections for reliable porosity analysis of PEMFC cathode
   catalyst layers. *Appl. Microsc.* https://doi.org/10.1186/s42649-026-00142-w (Amass literature; Crossref)
6. Mitchell, Khan, Wheatcroft et al. (2026) Recommended conditions for low kV 'sweet spot' imaging of battery
   materials. *J. Microsc.* https://doi.org/10.1111/jmi.70181 (Amass literature; Crossref)
7. Kapoor, Narayanan (2023) Leakage and the reproducibility crisis in machine-learning-based science. *Patterns*
   4:100804. https://doi.org/10.1016/j.patter.2023.100804 (Crossref)
8. Howard, Dolezal, Kochanny et al. (2021) The impact of site-specific digital histology signatures on deep learning
   model accuracy and bias. *Nat. Commun.* 12:4423. https://doi.org/10.1038/s41467-021-24698-1 (Crossref)
9. Lipsitch, Tchetgen Tchetgen, Cohen (2010) Negative controls: a tool for detecting confounding and bias in
   observational studies. *Epidemiology* 21:383. https://doi.org/10.1097/ede.0b013e3181d61eeb (Crossref search)
10. Nygaard, Rødland, Hovig (2016) Methods that remove batch effects while retaining group differences may lead to
    exaggerated confidence in downstream analyses. *Biostatistics* 17:29. https://doi.org/10.1093/biostatistics/kxv027
    (Crossref; online 2015)
11. Dahari, Docherty, Kench, Cooper (2025) Prediction of Microstructural Representativity From A Single Image
    (ImageRep). *Adv. Sci.* https://doi.org/10.1002/advs.202414149 (Crossref)

Also used: `notes/research_report.md` §3 (gate vs diagnostic table), §6.3–6.9 (MSA, Gate 1, blind-test protocol) and
§7. `notes/polaron_chat.md` (leakage trap). The screen results in `acquisition_null.json` and `verifications.json`.
Polaron, *Trust in Microstructure Quantification* (2026), https://www.polaron.ai/newsroom/trust-in-microstructure-quantification
(web page, no DOI). OpenAlex was rate-limited (HTTP 429) during this work, so the DOIs were checked against Crossref
through `ledger/ledger.py`'s own HTTP helper. `ledger.py normalize` has not been run.
