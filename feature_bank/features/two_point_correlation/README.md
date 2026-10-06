# two_point_correlation

Two-point correlation S2(r) of the void, solid and Si-like bright phase, summarised by a correlation length along x
(in-plane) and y (through-plane), plus integral ranges that size the single-image error of a phase fraction. Adds
six columns to `processed/features.csv`; the two solid lengths are computed in `feature.py` only.

| Column | Unit | Meaning |
|---|---|---|
| `s2_void_corrlen_x_um` | µm | Lag along x at which the normalised void S2 falls to 1/e: in-plane pore size scale |
| `s2_void_corrlen_y_um` | µm | The same along y: through-plane pore size scale |
| `s2_solid_corrlen_x_um` | µm | The same for solid (= not void). **Repeats the void value**: see "What it measures". **Not a features.csv column** (team audit 2026-10-03): duplicate of `s2_void` (two-phase identity, r 0.997 / 0.970) |
| `s2_solid_corrlen_y_um` | µm | As above, along y. **Not a features.csv column** (same reason) |
| `s2_bright_corrlen_x_um` | µm | Correlation length of the Si-like bright phase along x: particle / cluster size scale |
| `s2_bright_corrlen_y_um` | µm | The same along y |
| `s2_void_integral_range_um2` | µm² | Integral range of the void indicator: the area over which porosity is correlated; sets the porosity standard error of one image |
| `s2_bright_integral_range_um2` | µm² | The same for the bright phase |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| Void lengths `s2_void_corrlen_x/y_um` **down** | Narrower pores (Spearman ρ = 0.89–0.92 with `pore_lt_d50_um` over the 31 spots). Capillary filling is slower in narrower pores [13], so electrolyte wetting takes longer, and narrow throats can limit local ion transport. Typical causes: heavier calendering or finer graphite | **Bad** for wetting, possibly for rate. If porosity also fell (heavier calendering), it is a **trade-off**: more energy density, slower wetting and rate | Moderate for the mechanism [13]; on a graphite anode, heavy calendering (53 → 41 µm) cut the wetting rate about 3×, although light calendering (59 → 53 µm) raised it [12]. Low–moderate for a 2D 1/e length as a pore-size proxy |
| Void lengths **up** | Wider pores: faster capillary filling [13]. Wetting depends on pore size distribution, not only on porosity [12] | **Good** for wetting at the same porosity. **Trade-off** if it comes from lighter calendering: more porosity means less energy density and weaker particle contact | As above |
| Void x/y ratio (x length ÷ y length, derived) **up** | Pores flatter between aligned flakes: a longer through-plane ionic path, i.e. higher through-plane tortuosity [6] | **Bad** for rate and fast charge at the same porosity. If it comes from heavier calendering, the density gain makes it a **trade-off** | Moderate for the mechanism [6]; low as a 2D pore proxy (y as through-plane is inferred) |
| Void x/y ratio **down** | Rounder, less flattened pores: lighter calendering or rounder (spheroidised) graphite. Lower through-plane tortuosity [6] | **Good** for through-plane transport. **Trade-off** if it comes from lighter calendering (lower density) | Moderate for the mechanism, low as a 2D proxy |
| Void integral range `s2_void_integral_range_um2` **up** | Porosity is correlated over larger areas. On our data this is mostly bigger pores (ρ = 0.78–0.83 with the void lengths) and partly patchier porosity (ρ = 0.67 with `porosity_tile_cv`). One image pins down porosity less precisely [3, 4] | **Neither**: a sign that the pore structure's scale changed. Read the void lengths for the battery direction. For QC, more sites are needed for the same precision | Low |
| Void integral range **down** | Finer, more evenly spread porosity; a tighter single-image error bar [3, 4] | **Neither**: a sign that the pore structure changed (QC precision improves) | Low |
| Bright lengths `s2_bright_corrlen_x/y_um` and `s2_bright_integral_range_um2` **up** | Coarser or more clustered Si-like phase (rank correlation ρ = 0.56–0.71 with `bright_agglom_d50_um`; linear r only 0.11–0.45). Swelling is concentrated in fewer places, which means local cracking and loss of electronic contact [7] | **Bad**, if real | Low. The mechanism is plausible but there is no quantitative link, and the site values are noise (split-half r ≈ 0) |
| Bright lengths and bright integral range **down** | Finer particles: more even swelling, but more Si surface, so more SEI and lower first-cycle efficiency [7]. Or the same particles better dispersed: fewer swelling hot-spots with no extra surface | **Trade-off** if the particles are finer; **good** if only the dispersion improved. `bright_d90_um` tells the two apart | Low |
| `s2_solid_corrlen_*`, either way (not a features.csv column, team audit 2026-10-03: duplicate of `s2_void`, r 0.997 / 0.970) | The void length again, by construction (two-phase identity, r = 0.97–0.997; only crop-edge terms differ). It is **not** graphite thickness: r = −0.07 (Spearman −0.32) with `solid_chord_y_um` | Read it as the void rows. The research report's §8 row "thicker graphite flakes" does not apply to this column | Strong (a mathematical identity) |

**Best value:** match the baseline for every S2 column. No column has a one-sided "higher is better" direction:
longer void lengths help wetting but usually mean lighter calendering, and a finer Si phase trades swelling for surface.
Baseline (Batch_3, 17 spots): void 0.833 ± 0.160 µm (x) and 0.542 ± 0.082 µm (y), x/y 1.53 ± 0.12, void integral
range 5.2 ± 2.6 µm²; bright 1.82 ± 0.30 µm (x) and 1.63 ± 0.28 µm (y), bright integral range 14.9 ± 4.3 µm².

**Our batches** (final run of `rank_features.py` and `robustness.py`; effects in baseline-SD units; within-session p
is the joint test of both lots inside the five mixed sessions). No S2 column separates either lot (sep ≤ 0.35, below
the ≈ 0.65 that acquisition alone reaches; q ≥ 0.62). "No detectable change" is not proven equivalence: only 3 of
B1's and 5 of B2's 7 sites sit in mixed sessions, so only large shifts could have shown (B1's −1.5 SD on
bright y still gives p = 0.13).
- **Batch_1: no detectable change in pore scale, pore flattening or Si clustering.** Void lengths 0.881 / 0.573 µm
  (x / y) sit +0.3 / +0.4 SD above the baseline raw. All of that excess is session 2316 (4ih2ggld z = +2.5 / +3.2);
  without it B1 sits at −0.1 / −0.3 SD. 2316 holds only B1, so it is one session (n_eff = 1) that the within-session
  test cannot see. Within the shared sessions B1 sits at −0.8 / −0.9 SD (p = 0.65 / 0.51). Bright lengths are
  1.74 / 1.52 µm, lower than the other lot in all three shared sessions (−0.9 / −1.5 SD, p = 0.052 / 0.13). That
  does not survive eight tested columns and the site values are noise. If it were real, it would mean finer Si, not
  clustered Si. At 2316 the bright S2 does not suggest coarser or clustered Si either (bright length z = −1.4 at
  4ih2ggld, +0.1 / +0.5 at 5n1q8atc), but that is weak evidence.
- **Batch_2: no detectable change on any S2 column.** Void lengths 0.892 / 0.545 µm (+0.0 / −0.5 SD within
  sessions), x/y ratio 1.63 against 1.53 (+0.8 SD, p = 0.56), bright lengths 1.93 / 1.52 µm (+0.4 / −0.6 SD),
  integral ranges 5.7 µm² (void) and 15.1 µm² (bright).
- **What the verdict does with it.** No S2 column is Tier 1, Tier 2 or a diagnostic in `analysis/verdict_config.yaml`
  v1.1, and the integral ranges are on its `not_material` list (never fed to a classifier). Under v1,
  `s2_solid_corrlen_y_um` was the identity companion of the then Tier-1 KPI `solid_chord_y_um`, and it read "not
  confirmed" for both lots (it does not follow B1's +1.0 µm solid-chord excess). Because the column is the pore
  scale, not graphite thickness, that check was uninformative ("not checked" in effect). It could even "confirm"
  for the wrong reason: at the two 2316 sites it is high (z = +2.3 / +0.8) because their pores are larger. v1.1
  drops the check: `solid_chord_y_um` is now a diagnostic (it fails the Batch_3-only MSA gate, %GRR upper 82 %, and
  the invariance gate, 0.62). If it ever returns to Tier 1, its companion should be a real second estimator of
  graphite thickness, for example `solid_lt_d50_um` (ρ = 0.63 with it).

## What it measures

**The two-point correlation function** S2(r) of a phase is the probability that two points a vector r apart both fall
in that phase [1, 2]. At r = 0 it equals the area fraction φ. Far away the two points are independent, and S2 → φ².
How fast it gets there is a size scale of the phase; the shape of the decay carries spacing, clustering and
anisotropy. S2 is the basic "microstructure descriptor" in Torquato's framework [1, 2]. It is measured on segmented
masks without splitting particles.

The columns compress S2 to the **correlation length**: the lag r at which the normalised function
f(r) = (S2(r) − φ²) / (φ − φ²) first drops below 1/e. f runs from 1 at r = 0 to 0. It is computed separately along x
(image rows, in the electrode plane) and y (image columns, very likely through the thickness). Baseline values: void
0.83 µm (x) and 0.54 µm (y); bright 1.8 µm (x) and 1.6 µm (y).

- Image: BSE, through the shared harmonised masks (`features/_common`): `h.void` (open pore), `h.solid` (= not void)
  and `h.bright` (Si-like phase, adaptive-midpoint decision recipe). Crop 1336 × ~6980 px at 25 nm (33 × 175 µm).
- **Why direction-resolved.** Calendering presses flakes and pores flat. A single isotropic S2 would average that away.
  The void correlation length is ≈ 1.56× longer in-plane than through-plane (pooled over 31 spots; B1 1.54, B2
  1.63, B3 1.53, within-session p = 0.56): pores are flattened between horizontal flakes. The screen found ≈ 1.55
  with a different recipe.
- **Solid repeats void.** In a two-phase split the solid indicator is 1 − void. Its autocovariance is identical, so
  (S2_solid − φ_s²)/(φ_s − φ_s²) equals the void's normalised S2 at every lag. Only the finite-crop edge terms differ.
  On our data the r between the void and solid columns is 0.997 (x) and 0.970 (y), with a maximum difference of
  0.04 µm (x) and 0.05 µm (y). They are no longer computed as columns (team audit 2026-10-03). **Do not count them as
  independent evidence.** Solid-phase size information is in the chords (`chord_length`), not in the 1/e point of S2. We also
  tried the carbon matrix (solid minus bright) as an alternative. It mixes the void and bright scales (r = 0.35 / 0.57
  with them) and has worse precision (split-half 0.27), so we did not use it.
- **Integral range** A₂ = ∫ C(r) dr / (φ(1 − φ)), where C is the indicator autocovariance. It is the area of one
  "independent cell" for that phase [3]. The single-image standard error of the area fraction is
  sqrt(A₂ φ(1 − φ) / A_image). That is the ImageRep idea of Polaron/Imperial [4]. Computed by the shared
  `fraction_se()`.

**Relation to interface density and chords.** The slope of S2 at the origin measures the boundary:
- Along a direction, S2′(0) = −P_L / 2, where P_L is the phase boundaries crossed per unit length.
- For an isotropic 2D section this becomes S2′(0) = −L_A / π, with L_A the interface length per area [1]. In 3D the
  analogue is S2′(0) = −S_V/4 (Debye et al. [5]).
- The number-weighted mean chord of the phase is −φ / S2′(0) along that axis, so S2 at small r and the mean chords
  are the same information.

Checked on cfe5vt7s: the S2 slope at 0 (first-lag difference) along x is −0.1665 µm⁻¹ against −P_L/2 = −0.1665 and
−φ/pore_chord = −0.1664; along y −0.1924 / −0.1935 / −0.1933. The 0.6 % gap along y is a crop-edge term: S2 at lag
1 px averages over all rows but the last, and the last row of this crop holds 8.1 % void against 11.7 % overall. The slope is therefore not a separate column: use `chord_length`. The 1/e
correlation length adds the decay *beyond* the boundary, which is related to pore size and shape.

## Why it matters for the battery

- **Pore size scale and anisotropy** (`s2_void_*`). The size and flattening of pores govern how fast electrolyte
  wets the electrode and how tortuous the ionic path is through the thickness. Flattened pores between aligned flakes
  raise through-plane tortuosity [6]. Shorter void correlation lengths mean narrower pores. Capillary filling is
  slower in narrower pores [13], and wetting depends on pore size distribution as well as porosity [12]; narrow
  throats may also limit local ion transport (not shown on our data). A lower x/y ratio means less flattening
  (lighter calendering or rounder particles).
- **Si-phase clustering** (`s2_bright_*`). The bright correlation length grows with particle size and with
  clustering (agglomerates correlate over their whole extent). Clustered Si-based particles concentrate swelling and
  can lose electronic contact. Si-based phases expand far more than graphite on lithiation [7]. A **longer** bright
  correlation length at the same bright fraction points at coarser or more agglomerated Si.
- **Error bars** (`*_integral_range_um2`). Larger integral range means fewer independent cells per image and a less
  precise phase fraction. A batch whose porosity or Si phase is correlated over larger areas is also more
  heterogeneous. Both feed the decision layer's per-image sampling term (research report §6.2).

## Industry / Polaron use

- **Polaron / Imperial.** ImageRep (Dahari et al. 2025) predicts how representative one image is from its two-point
  statistics. That is the integral range used here [4]. Polaron's quality pages ask for "objective acceptance
  criteria" and "drift detection" (research report §2). Polaron's SliceGAN validates generated 3D microstructures
  against 2D statistics, including the two-point correlation [8].
- **Academic.** S2 is the standard descriptor for reconstructing and classifying random media [1, 2]. A given S2 does
  not determine the microstructure: different structures share the same S2 [9]. PoreSpy provides
  `metrics.two_point_correlation` [10].
- **Not a CoA item.** No supplier certificate lists S2. For QC it is a relative descriptor (proposed for Tier 2 in
  the research report §6.4, but not in `verdict_config.yaml` v1.1): calendering and pore structure for the void, and
  Si dispersion for the bright phase.
- **What would move it.** Calendering pressure (void lengths, x/y ratio). Graphite particle shape (x/y). Si-phase
  milling, grade or mixing intensity (bright correlation length and integral range).

## How it is computed

1. `h = harmonised(sample)` (`features/_common`, frozen shared recipe: crop, black/graphite anchoring, noise matching,
   void by Otsu, bright by the adaptive midpoint between graphite and the image's own bright mode). Masks used:
   `h.void`, `h.solid`, `h.bright`.
2. **Directional S2** (`s2_profile`). For axis x: FFT every row, zero-padded to ≥ n + max lag so the circular
   correlation never wraps onto real pixels. Take |F|², inverse FFT, sum over rows. Divide each lag r by the number of
   overlapping pixel pairs, rows × (n − r). This is the unbiased "normalised by overlap counts" estimator, with no
   wrap-around. The normalisation uses the whole-crop φ (the standard S2 definition), while lag r only sees n − r
   pixels per line. Normalising by the means of the two overlapping windows instead changes the lengths by 0.1–1.8 %
   (void) and 1–4 % (bright, worst along y), at most ≈ 0.2 B3-SD (checked on cfe5vt7s, 4ih2ggld, 71vgq3fw). The
   same along columns for y. The axis profiles are exact (no 2×2 block averaging needed).
3. **Correlation length** (`correlation_length_um`). f(r) = (S2 − φ²)/(φ − φ²) with φ the mask's area fraction.
   Take the first lag where f < 1/e and interpolate linearly between that lag and the one before. Pixels × 0.025 µm.
4. **Integral range**: `fraction_se(mask)[1]` from `features/_common`. It averages the mask in 4 × 4 px blocks, runs a
   2D FFT autocovariance normalised by overlap counts, and sums it over |dy| ≤ 4 µm, |dx| ≤ 12 µm. That number is set
   in `features/_common/config.yaml → representativity`.
5. Tuning numbers (`config.yaml`): `max_lag_um: 20` (no crossing within 20 µm gives `nan`; never happened);
   `min_phase_frac: 0.002` (a phase below 0.2 % or above 99.8 % of the crop gives `nan`).

Runtime: 1.8 s per spot for all eight columns (six FFT profiles and two integral ranges), on top of the shared
harmonisation.

## Evidence on our data

**Final pipeline numbers.** These come from the integrated run: `analysis/rank_features.py` → `processed/rankings.csv`
(sep, q; it permutes across all spots, so it does not control for session) and `analysis/robustness.py --perturb` →
`processed/robustness.csv` (within-session p, session R², perturbation ratio). Where they differ from the builder's
tables further down, these numbers win.

| Column | B1 / B2 / B3 mean | sep | q | within-session p | session R² | perturbation ratio (worst) |
|---|---|---|---|---|---|---|
| `s2_void_corrlen_x_um` | 0.881 / 0.892 / 0.833 µm | 0.19 | 0.82 | 0.65 | 0.52 | 0.23 (gamma 0.8) |
| `s2_void_corrlen_y_um` | 0.573 / 0.545 / 0.542 µm | 0.19 | 0.87 | 0.51 | 0.59 | 0.18 (gamma 1.25) |
| `s2_bright_corrlen_x_um` | 1.74 / 1.93 / 1.82 µm | 0.35 | 0.62 | 0.052 | 0.39 | 0.14 (gamma 1.25) |
| `s2_bright_corrlen_y_um` | 1.52 / 1.52 / 1.63 µm | 0.25 | 0.64 | 0.13 | 0.38 | 0.08 (gamma 1.25) |
| `s2_void_integral_range_um2` | 6.41 / 5.66 / 5.20 µm² | 0.24 | 0.72 | 0.88 | 0.43 | 0.22 (gamma 1.25) |
| `s2_bright_integral_range_um2` | 14.4 / 15.1 / 14.9 µm² | 0.08 | 0.99 | 0.37 | 0.44 | 0.08 (gamma 1.25) |

- **Verdicts.** `rank_features.py` gives "no difference" for all eight columns of that run. Worst leave-one-out sep is ≤ 0.26.
  Leakage ρ is 0.52–0.55 for the void and solid columns (with black level), under the 0.6 bar but the closest to it,
  and 0.20–0.29 for the bright columns (with contrast).
- **Gauge R&R.** Upper bracket 0.48–0.53 for the void lengths, above the 0.30 AIAG bar. As a stand-alone KPI they
  could not support a measurement-based REJECT. The bright columns have session ICC = 0.
- **Void x/y ratio.** This is derived, so it is not in the CSVs. The same `robustness.py` functions run on
  `features.csv` (stdout only) give 1.54 / 1.63 / 1.53, within-session p = 0.56 (B1 −0.35 / B2 +0.82 SD) and
  session R² 0.45.
- **Bright x/y ratio.** Also derived: 1.15 / 1.28 / 1.13, within-session p = 0.094 (B1 +1.6, B2 +2.3 SD). This was a
  post-hoc look at one of two derived ratios, and its split-half was not measured. The screen found the same B2
  elevation in `s2_siox_aniso` and could not trust it (split-half 0.01). **It is not a finding.**
- **Correction to the builder's tables below.** The bright-phase perturbation ratios dropped:
  - bright x 0.81 → 0.14, bright y 0.75 → 0.08 and bright integral range 0.14 → 0.08, all at gamma 1.25.
  - The unperturbed values are unchanged (`recompute_vs_csv` ≤ 2e-15, same means). The most likely reason is the
    revision of the shared bright-mode search in `features/_common/harmonise.py`, which postdates this validation.
    The `bright_mode_clamp` comment in `features/_common/config.yaml` now notes that gamma 1.25 moves the bright mode
    to ≈ 2.6.
  - The bright columns now pass the 0.5 invariance bar. They stay unusable per site because their split-half
    r ≈ 0, which is a sampling problem, not an acquisition one.
  - The void numbers are unchanged.

**Builder's validation** (before integration) on all 31 spots (`preprocessing.iter_samples()`). The script was our
own and printed to stdout. `analysis/rank_features.py` was not run at that point, because it writes shared outputs.
Within-session test: OLS y ~ C(session) + C(batch), RSS drop from adding batch, exact permutation over the 192
within-mixed-session relabellings (minimum p ≈ 0.005). Perturbations: raw uint8 images of B3 71vgq3fw, cfe5vt7s,
hzumfsms and 0grcilhi; ratio = max |Δ| / B3 between-spot SD. Split-half: the same code on the left and right half of
the masks.

Independent re-check (review): a second implementation (1-D labelled runs for the chords, direct
shift-and-multiply S2 without FFT) matched these columns to machine precision on 9 spots. The spots cover every
mixed session, 2060 (71vgq3fw) and 2316 (4ih2ggld). The statistics and the perturbation pass were recomputed
from scratch and match the tables here.

| Column | B1 | B2 | B3 | η²(batch) | session R² | within-session coef. (B3-SD) B1 / B2, p | split-half r | perturbation ratio (worst) |
|---|---|---|---|---|---|---|---|---|
| `s2_void_corrlen_x_um` | 0.881 ± 0.19 | 0.892 ± 0.16 | 0.833 ± 0.16 | 0.028 | 0.52 | −0.79 / +0.01, p = 0.65 | 0.47 | 0.23 (gamma 0.8) |
| `s2_void_corrlen_y_um` | 0.573 ± 0.13 | 0.545 ± 0.049 | 0.542 ± 0.082 | 0.022 | 0.59 | −0.86 / −0.48, p = 0.51 | 0.47 | 0.18 (gamma) |
| `s2_solid_corrlen_x_um` | 0.883 ± 0.18 | 0.886 ± 0.15 | 0.830 ± 0.16 | 0.031 | 0.53 | −0.77 / −0.11, p = 0.64 | 0.49 | 0.23 (gamma 0.8) |
| `s2_solid_corrlen_y_um` | 0.552 ± 0.11 | 0.548 ± 0.050 | 0.544 ± 0.089 | 0.002 | 0.56 | −0.92 / −0.30, p = 0.41 | 0.46 | 0.19 (gamma) |
| `s2_bright_corrlen_x_um` | 1.74 ± 0.28 | 1.93 ± 0.16 | 1.82 ± 0.30 | 0.058 | 0.39 | −0.86 / +0.44, p = 0.052 | −0.09 | 0.14 (gamma 1.25; builder 0.81) |
| `s2_bright_corrlen_y_um` | 1.52 ± 0.26 | 1.52 ± 0.19 | 1.63 ± 0.28 | 0.050 | 0.38 | −1.53 / −0.64, p = 0.13 | −0.03 | 0.08 (gamma 1.25; builder 0.75) |
| `s2_void_integral_range_um2` | 6.4 ± 2.7 | 5.7 ± 2.3 | 5.2 ± 2.6 | 0.040 | 0.43 | −0.51 / −0.11, p = 0.88 | 0.57 | 0.22 (gamma 1.25) |
| `s2_bright_integral_range_um2` | 14.4 ± 3.4 | 15.1 ± 4.1 | 14.9 ± 4.3 | 0.003 | 0.44 | −0.88 / +0.06, p = 0.37 | −0.01 | 0.08 (gamma 1.25; builder 0.14) |

Session R² chance level is ≈ 0.40. The perturbation ratios of the bright rows are the final `robustness.py` values;
the builder's own pass is shown in brackets (see the correction above).

Raw within-session contrasts (first batch minus second, B3-SD):

| Column | 2068 B2−B3 | 2080 B1−B2 | 2080 B1−B3 | 2080 B2−B3 | 2148 B1−B2 | 2156 B1−B2 | 2272 B2−B3 |
|---|---|---|---|---|---|---|---|
| `s2_void_corrlen_x_um` | −0.72 | −1.99 | +0.17 | +2.16 | −1.29 | −0.14 | −0.98 |
| `s2_void_corrlen_y_um` | −0.89 | −0.96 | −0.40 | +0.56 | −1.72 | +1.02 | −0.86 |
| `s2_bright_corrlen_x_um` | +0.28 | −1.51 | −1.11 | +0.40 | −0.94 | −1.37 | +0.88 |
| `s2_bright_corrlen_y_um` | −0.34 | −0.13 | −1.49 | −1.36 | −1.28 | −1.03 | −0.64 |
| `s2_void_integral_range_um2` | −1.21 | −1.74 | +0.69 | +2.43 | −1.33 | +0.62 | −0.93 |
| `s2_bright_integral_range_um2` | +0.80 | −0.60 | −1.29 | −0.69 | −1.83 | +0.01 | −0.28 |

Perturbation detail, max over the 4 spots in B3-SD (black +25 / gamma 0.8 / gamma 1.25 / contrast ×0.85 / noise σ 4 /
blur σ 1), final `robustness.py` run:
- void x: 0.00 / 0.23 / 0.22 / 0.01 / 0.02 / 0.08
- void y: 0.00 / 0.18 / 0.18 / 0.01 / 0.02 / 0.07
- bright x: 0.00 / 0.10 / 0.14 / 0.00 / 0.01 / 0.03 (builder's gamma 1.25: 0.81)
- bright y: 0.00 / 0.07 / 0.08 / 0.01 / 0.01 / 0.02 (builder's gamma 1.25: 0.75)
- IR void: 0.00 / 0.21 / 0.22 / 0.01 / 0.02 / 0.05
- IR bright: 0.00 / 0.04 / 0.08 / 0.00 / 0.00 / 0.02 (builder's gamma 1.25: 0.14)

What this says:
1. **No batch signal** in any S2 column within sessions. The only p near 0.05 is bright x (0.052): B1 is below the
   other lot in all three shared sessions (B1 −0.9, B2 +0.4 SD). It does not survive eight tested columns, the site
   value has split-half r ≈ 0, and the screen's pooled-particle PSD shows no B1 difference (`notes/feature_screen.md`),
   so it reads as noise. If it were real it would mean finer Si in B1, not clustering. Raw η² is ≤ 0.06 everywhere.
2. **The void correlation lengths are among the most acquisition-robust pore-size descriptors** (≤ 0.23 under every
   perturbation, against 0.27 for `pore_lt_d50_um` and 0.29 for `pore_chord_y_um`; blur only 0.07–0.08), with
   moderate precision (split-half 0.47, gauge R&R upper bracket 0.48–0.53). They are an **expected-stable
   "calendering and pore structure unchanged" check**, but they track the Tier-2 KPI `pore_lt_d50_um` at
   ρ = 0.89–0.92. In v2 they fit best as its identity companion (a second estimator of the same pore scale that
   splits no pores), not as an extra Tier-2 vote, which would count the pore scale twice. As a Tier-2 quality range
   (baseline ± 2.86 SD) both lots would pass: 7/7 sites inside on x, and on y 7/7 for B2 and 6/7 for B1 (4ih2ggld
   outside). None of this is in `verdict_config.yaml` v1.1. They agree with the texture screen (`s2_pore_x_le`
   0.77 µm, `s2_pore_y_le` 0.50 µm, perturbation 0.22, split-half 0.53, also no batch signal). The pore x/y
   anisotropy is 1.54 / 1.63 / 1.53 (B1 / B2 / B3) with no detectable within-session batch effect (p = 0.56).
3. **Bright-phase S2 is not usable per site.** Split-half r is about 0 for both lengths and for the bright integral
   range. A half image holds only a few dozen 2–10 µm particles, so the site value is particle-sampling noise. That
   matches the screen (`s2_siox_aniso`, split-half 0.01). The builder's pass found that gamma 1.25 moved the bright
   lengths by 0.75–0.81 B3-SD, through the adaptive bright threshold. In the final `robustness.py` run that is down to
   0.08–0.14, so acquisition is no longer the problem; sampling is. Batch-pooled means might still be informative; a
   site-level KPI is not.
4. **Session structure is weak.** Within B3 the void correlation length has ICC 0.23–0.28, against 0.68–0.83 for the
   solid chords. The bright columns have ICC 0. Session R² is 0.52–0.59 (void) and at chance for bright.
5. **Integral range → per-image error bars.** The B3 void integral range is 5.2 ± 2.6 µm², about 1100 independent
   cells per image. That gives a single-image porosity SE ≈ 0.009 (1σ), close to the research report's ±0.007. The
   bright integral range is 14.9 ± 4.3 µm², about 390 cells. That gives a single-image bright-fraction SE ≈ 0.012,
   about 20 % of the baseline bright fraction of 0.059. **One image cannot pin down the Si-phase fraction to better
   than ±20 % (1σ) from sampling alone.**
6. **Special sessions.** The lifted-black session 2060 reads −1.3 to −1.5 B3-SD on void lengths and void integral
   range: shorter, less correlated pores. The final `robustness.py` lifted_z values are −1.46 (x), −1.26 (y) and
   −1.28 (integral range). That is the same pattern every pore-size feature shows there, and it is confounded with
   acquisition. The 2316 B1 site 4ih2ggld has the longest void length in y of all 31 sites (z +3.2, above every
   baseline site) and the second longest in x (z +2.5; baseline site 0grcilhi is longer). Together with 5n1q8atc
   it carries all of B1's raw excess on the void columns (one session, n_eff = 1).

## Uncertainty and pitfalls

- **Sampling.** Split-half |L − R| ≈ 1 B3-SD for the void lengths: one image gives a noisy site value. The integral
  range is itself the sampling-error model for phase fractions. It covers within-image sampling only, not
  segmentation or site-to-site variation [4]. The `fraction_se` window (|dy| ≤ 4 µm, |dx| ≤ 12 µm) truncates the
  covariance for the bright phase, whose particles reach 10 µm. The bright integral range may therefore be biased low.
- **Segmentation and resolution.** Correlation lengths shrink when blur closes thin gaps or when small objects are
  removed. Ledesma-Alonso et al. showed how S2-based descriptors depend on resolution [11]. Here σ = 1 px blur moves the
  void lengths by only ≤ 0.08 B3-SD, but compare only values made with the frozen recipe.
- **Gamma** is the main acquisition sensitivity (void ≤ 0.23). The bright columns reach ≤ 0.14 in the final
  `robustness.py` run; the builder's pass, before the shared bright-mode revision, found 0.75–0.81. Gamma acts through
  the shared void and bright thresholds and can only be fixed in `features/_common`.
- **Degeneracy.** One S2 fits many microstructures [9], and a single 1/e point fits even more. Two batches with equal
  correlation lengths are not "the same microstructure". The column only reports that this one scale did not move.
- **Two-phase redundancy.** `s2_solid_*` equals `s2_void_*` by construction (see above). Counting both in a
  multivariate score double-weights the pore scale, which is why the solid lengths are no longer columns.
- **Interface relation needs isotropy.** S2′(0) = −L_A/π assumes an isotropic 2D section. Our sections are not
  isotropic (x/y ≈ 1.56 for void), so we use the directional form S2′_θ(0) = −P_L(θ)/2, which holds without
  assumptions along each measured direction.
- **3D validity.**
  - S2 along a vector lying in the section plane is a genuine 3D S2 value for that direction. A pair of points in
    the plane is a pair of points in the material. So `corrlen_x` and `corrlen_y` are valid 3D descriptors for those
    two directions, assuming the polished surface is an ideal section. Pore-back and curtaining break that
    assumption.
  - The out-of-plane direction is not sampled. If the electrode is transversely isotropic (in-plane directions
    equivalent, likely for a calendered coating, not verified), then x stands for all in-plane directions.
  - The integral range here is 2D (µm²). It sets the error of an area fraction on this section, not of a 3D volume
    fraction. The 3D integral range has units of µm³.
  - 2D-to-3D reconstructions that assume isotropy (e.g. the original SliceGAN setting [8]) contradict the measured
    anisotropy.
- **Orientation** of image y as through-thickness is inferred from flake layering, not measured. Only epqdaau9 may
  show the current collector.

## References

1. Torquato, S. (2002) *Random Heterogeneous Materials: Microstructure and Macroscopic Properties*. Springer
   (two-point correlation, interface relation S2′(0) = −L_A/π in 2D). https://doi.org/10.1007/978-1-4757-6355-3
2. Torquato, S. (2002) Statistical description of microstructures. *Annu. Rev. Mater. Res.* 32.
   https://doi.org/10.1146/annurev.matsci.32.110101.155324
3. Lantuéjoul, C. (1991) Ergodicity and integral range. *J. Microsc.* 161, 387.
   https://doi.org/10.1111/j.1365-2818.1991.tb03099.x
4. Dahari, A., Docherty, R., Kench, S. et al. (2025) Prediction of microstructural representativity from a single
   image. *Adv. Sci.* https://doi.org/10.1002/advs.202414149
5. Debye, P., Anderson, H. R. & Brumberger, H. (1957) Scattering by an inhomogeneous solid. II. The correlation
   function and its application. *J. Appl. Phys.* https://doi.org/10.1063/1.1722830
6. Ebner, M., Chung, D.-W., García, R. E. & Wood, V. (2014) Tortuosity anisotropy in lithium-ion battery electrodes.
   *Adv. Energy Mater.* 4, 1301278. https://doi.org/10.1002/aenm.201301278
7. Obrovac, M. N. & Chevrier, V. L. (2014) Alloy negative electrodes for Li-ion batteries. *Chem. Rev.* 114, 11444.
   https://doi.org/10.1021/cr500207g
8. Kench, S. & Cooper, S. J. (2021) Generating three-dimensional structures from a two-dimensional slice with
   generative adversarial network-based dimensionality expansion. *Nat. Mach. Intell.* 3, 299.
   https://doi.org/10.1038/s42256-021-00322-1
9. Gommes, C. J., Jiao, Y. & Torquato, S. (2012) Microstructural degeneracy associated with a two-point correlation
   function and its information content. *Phys. Rev. E* 85, 051140. https://doi.org/10.1103/PhysRevE.85.051140
10. Gostick, J. T., Khan, Z. A., Tranter, T. G. et al. (2019) PoreSpy: a Python toolkit for quantitative analysis of
    porous media images. *J. Open Source Softw.* https://doi.org/10.21105/joss.01296
11. Ledesma-Alonso, R., Barbosa, R. & Ortegón, J. (2018) Effect of the image resolution on the statistical descriptors
    of heterogeneous media. *Phys. Rev. E* 97, 023304. https://doi.org/10.1103/PhysRevE.97.023304
12. Sheng, Y., Fell, C. R., Son, Y. K. et al. (2014) Effect of calendering on electrode wettability in lithium-ion
    batteries. *Front. Energy Res.* 2, 56. https://doi.org/10.3389/fenrg.2014.00056 (graphite anode; wetting rate
    rises with light calendering and falls about 3× with heavy calendering; wetting is set by porosity, pore size
    distribution, geometry and topology)
13. Washburn, E. W. (1921) The dynamics of capillary flow. *Phys. Rev.* 17, 273 (capillary penetration length² ∝
    pore radius × time). https://doi.org/10.1103/PhysRev.17.273

All DOIs were confirmed through Crossref with the ledger's lookup code (OpenAlex search was rate-limited, HTTP 429).
Refs 9 and 11 came from the local Amass corpus (`literature.load_papers`). Refs 5 and 13 came from Crossref
bibliographic searches (ref 13 on 2026-10-03). Ref 2 was already verified in the ledger. Ref 12 was already in the
ledger (`local_thickness`, `open_porosity`); it was re-confirmed with the ledger's `lookup_doi` (OpenAlex) on
2026-10-03, and its abstract was read through OpenAlex to check the wetting claims above. The research report marked
ref 1 "[DOI from memory, unverified]"; it is now confirmed by Crossref (Torquato, *Random Heterogeneous Materials*,
2002). The exact equation numbers in [1] for the 2D slope relation were not re-checked; the relation itself was
confirmed numerically on our data. "SliceGAN validates against two-point statistics" and "the original SliceGAN
setting assumes isotropy" are from the research report and general knowledge, not re-checked in [8]. The claims
drawn from [7] (fracture and contact loss of coarse or clustered alloy particles; more SEI on finer ones) follow the
research report §8 and were not re-checked against the full review.
