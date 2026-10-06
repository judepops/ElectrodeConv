# chord_length

Mean chord (intercept) length of the solid and the pore phase, along the electrode plane (x) and through the
thickness (y). Adds three columns to `processed/features.csv`; the two pore chords are computed in `feature.py` only.

| Column | Unit | Meaning |
|---|---|---|
| `solid_chord_x_um` | µm | Mean length of an unbroken solid run along an image row (in-plane): the typical in-plane solid distance between two pores |
| `solid_chord_y_um` | µm | The same along image columns (through-plane). The closest image stand-in for graphite flake thickness / particle size. **Diagnostic** (Tier 3) in the verdict (`verdict_config.yaml` v1.1); it left Tier 1 because it fails the Batch_3-only MSA gate (%GRR upper 82 %, ndc 0.97) and the invariance gate (0.62) |
| `solid_chord_hv_ratio` | – | `solid_chord_x_um / solid_chord_y_um`: in-plane elongation of the solid skeleton (1 = isotropic) |
| `pore_chord_x_um` | µm | Mean length of an unbroken pore run along a row: in-plane pore width. **Not a features.csv column** (team audit 2026-10-03): identity φ/N_L, fixed by porosity and the solid chord |
| `pore_chord_y_um` | µm | The same along columns: pore height through the thickness. **Not a features.csv column** (same reason) |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `solid_chord_x/y_um` up | Longer unbroken solid between two pores. The image cannot separate two causes: **(a)** coarser or thicker graphite flakes, so Li diffuses further inside each particle and there is less graphite surface; **(b)** the same porosity in fewer, larger pores, or CBD, Si-phase agglomerates or harder calendering closing small gaps | **(a) Trade-off**: slower solid-state transport, so lower rate and more Li-plating risk at fast charge, mainly for larger particles (solid diffusion is not the limiting step below about 10 µm; interface and electrode transport are) [10]; against less surface, so less SEI and first-cycle loss [6]. **(b) Neither: a sign the supplier's process changed**; read the transport effect from `porosity_open_frac` and `pore_lt_d50_um` | Moderate on (a); low on which cause applies (2D proxy, never calibrated against PSD) |
| `solid_chord_x/y_um` down | **(a)** Finer graphite: shorter diffusion paths, more surface; or **(b)** the same porosity in more, smaller pores | **(a) Trade-off**: better rate where solid diffusion limits [10]; more SEI and first-cycle loss [6]. **(b) Neither: a sign the supplier's process changed** | Moderate on (a); low on the cause |
| `solid_chord_hv_ratio` up | Flakes lie flatter (stronger in-plane alignment from calendering or more platelet-like graphite): ions take a longer path through the thickness | **Bad** for fast charge: higher through-plane tortuosity [4] and lower rate [5]; slow transport at fast charge leads to Li plating [10] | Strong mechanism [4]; low for this column (split-half r 0.27, B3 ICC 0.23) |
| `solid_chord_hv_ratio` down | Less in-plane alignment (rounder or spheroidised graphite, lighter calendering) | **Good** for rate: lower through-plane tortuosity [4, 5]. If it comes from lighter calendering, porosity is usually higher too (lower energy density): check porosity | Moderate; low for this column |
| `pore_chord_x/y_um` up (not a features.csv column, team audit 2026-10-03: identity φ/N_L, fixed by porosity and the solid chord) | Wider pores. At the same pore count this is higher porosity (identity below) | **Trade-off** (through porosity): easier electrolyte transport against lower energy density. Pore width alone has no established direction: wetting is set by the whole pore structure and changed non-monotonically with calendering in a graphite anode [11] | Low (2D; largely redundant with porosity and `pore_lt_d50_um`) |
| `pore_chord_x/y_um` down (not a features.csv column, as above) | Narrower pores, e.g. from heavier calendering | **Trade-off** if from calendering: denser electrode (energy) against slower wetting. Heavy calendering cut a graphite anode's wetting rate to about a third of its peak, light calendering raised it [11]. Otherwise **neither: a sign the supplier's process changed** | Low |

**Best value:** match the baseline. No cell maker or supplier publishes a chord spec, and each direction of the solid
chord is either a trade-off or only a sign of a process change, so the approved Batch_3 values are the target: solid
chord x 5.80 ± 0.63 µm and y 4.92 ± 0.46 µm (v1 Tier-1 margin ± 0.686 µm = 1.5 × B3 SD), H/V 1.18 ± 0.04 (lower is
better for rate, but any change flags a calendering or graphite-shape change), pore chord x 0.69 ± 0.08 µm and
y 0.59 ± 0.07 µm.

**Our batches** (final integrated run: `analysis/rank_features.py` and `analysis/robustness.py`; detail in Evidence):
- **Raw means are longer in both lots, but a session-controlled shift is not established.** Solid chord x / y:
  Batch_1 6.93 / 5.93 µm, Batch_2 6.23 / 5.29 µm, baseline 5.80 / 4.92 µm (sep 0.91, q 0.027 / 0.029). That test
  ignores sessions, and session explains 70–76 % of the variance (chance ≈ 40 %). **Within the five mixed sessions**
  (acquisition-controlled, joint test of both lots): x B1 +2.5, B2 +1.7 B3-SD, exact p = 0.026; y B1 +2.4, B2 +1.5,
  p = 0.12. After correction over the 68 columns tested (BH q 0.45 / 0.49), x is a lead and y is not shown. B1 has
  only one direct B1–B3 pair (session 2080: +3.2 / +3.0 SD).
- **Batch_1 and session 2316 (n_eff = 1).** The certificate's delta (+1.01 µm on y) is carried by the two spots of one B1-only
  session, 2316 (4ih2ggld, 5n1q8atc). They are outside the within-session test, have the longest solid chords in the
  data (y +3.6 / +5.2 SD) and are the only B1 sites outside the baseline range (mean ± 2.86 SD). The same two spots
  carry the Si-phase anomaly (bright phase 16–20 % of the solid against 6.6 % in the baseline, ≈ 11 µm agglomerates,
  all counted as solid here), the strongest FIB curtains and a low H/V (1.12 / 1.07). So this is the same
  one-session event as the Si-phase flag, not independent evidence. Without them the raw B1 delta is +0.60 µm,
  inside the 0.686 µm v1 margin (raw, not session-controlled).
- **Batch_2:** delta +0.37 µm (+0.80 SD), diagnostic screen q 0.70.
- **Reading.** Pore chords and H/V sit at baseline (sep ≤ 0.18, q ≥ 0.91, within-session p ≥ 0.24). If the solid-chord
  shift is real, it is fewer pores per line, not wider pores or a different alignment. **Neither: a sign the
  supplier's process changed** (CBD, calendering or graphite grade; at 2316 also the Si phase; the image cannot say
  which). It becomes the rate-vs-SEI trade-off above only if it is coarser graphite, which this column cannot show.
- **What the verdict does.** `solid_chord_y_um` is a **diagnostic** (Tier 3) in v1.1: shown, never decisive. It left
  Tier 1 because, on Batch_3 alone, it fails the MSA gate (%GRR upper 82 %, ndc 0.97) and the invariance gate (gamma
  ratio 0.62 > 0.5). Batch_1: delta +1.01 µm (+2.2 SD), screen q 0.18. It is no longer among the reasons behind B1's
  INVESTIGATE, and the identity check is gone (Evidence, point 7). `solid_chord_hv_ratio` is also a **diagnostic**:
  it left Tier 2 because its left/right split-half reliability r_x is 0.26 (bar 0.35). `solid_chord_x_um`, which
  carries the strongest within-session signal, and the pore chords (no longer columns) are not used by the verdict.

## What it measures

Lay a straight line across the cross-section. It cuts the microstructure into alternating runs ("chords" or
"intercepts") of solid and pore. The **mean chord length** of a phase is the average length of its runs. These
columns give it for both phases, separately for lines along x (image rows, in the electrode plane) and y (image
columns). The mean is number-weighted: every run counts once, whatever its length.

- Image: BSE, through the shared harmonised void mask (`features/_common`). Solid = everything that is not open pore:
  graphite, the Si-like bright phase and the carbon-binder domain (CBD) together.
- Scale: 25 nm pixels on a 1336 × ~6980 px crop (33 µm × 175 µm, ~5800 µm²). Typical values in the baseline: solid
  chord 5.8 µm (x) and 4.9 µm (y); pore chord 0.69 µm (x) and 0.59 µm (y).
- Orientation: image y is very likely the through-thickness direction. Flakes lie horizontally, curtains run
  vertically, and the anisotropy is the same in every batch (research report §7.10).

**What a solid chord is and is not.** A solid chord ends only where it meets a pore. Two graphite flakes that touch
without a pore between them form one chord. So the solid chord is the **solid distance between pores**, an upper bound
on flake thickness, not a particle size. The through-plane value is the closest thing to graphite particle size that
needs no particle splitting. It moves the same way as flake thickness and PSD, but nobody has calibrated it against
them.

Stereological identities (exact with the default estimator, checked on our data):
- `solid_chord = (1 − φ) / N_L` and `pore_chord = φ / N_L`, where φ is porosity and N_L is the number of pores a line
  crosses per µm. Hence `solid_chord / pore_chord = (1 − φ)/φ` (measured ratio / prediction = 1.0000 on every one of
  the 31 spots, both axes, because both phases share one N_L = P_L/2).
  Porosity, pore chord and solid chord carry only **two** independent numbers per direction.
- `N_L = P_L / 2`, where P_L is the boundary crossings per µm. In S2 terms `N_L = −S2′(0)` along that axis, so the
  chords carry the same information as the slope of the two-point correlation at the origin (`two_point_correlation`).
  The interface length per area is L_A ≈ (π/4)(P_Lx + P_Ly) (isotropic-in-plane approximation). On our data this
  gives L_A ≈ 0.53 µm⁻¹ for B3.

## Why it matters for the battery

- **Graphite particle size / flake thickness** (`solid_chord_y_um`). Particle size sets the solid-state diffusion
  length of Li in graphite and the surface area per volume. Larger particles mean longer diffusion paths and lower rate
  capability, but which step limits fast charge depends on particle size: below about 10 µm, interfacial Li⁺
  transfer and transport through the electrode limit, not diffusion inside the particle [10]. Finer particles mean
  more surface, so more SEI growth and more first-cycle loss: first-cycle charge loss scales with the graphite BET
  surface area [6]. D50 is the first item on an anode powder certificate of analysis (research report §2), and
  powders are certified, not electrodes. A **longer** solid chord can also mean **fewer pores**: same
  porosity in fewer, larger pores, or CBD filling small gaps. On our data that is the more likely reading, if the
  shift is real (see Evidence).
- **Flake alignment** (`solid_chord_hv_ratio`). Calendering lays graphite flakes flat. That makes the pore network
  more tortuous through the thickness than along it. Ebner et al. found the through-plane tortuosity of
  graphite-flake anodes clearly higher than the in-plane value, driven by particle shape and alignment [4]. Billaud
  et al. improved rate by aligning flakes vertically [5]. **Higher** H/V means stronger in-plane alignment: higher
  through-plane ionic resistance and worse fast charge; slow intercalation at fast charge leads to Li plating [10].
- **Pore width** (`pore_chord_*`). The pore chord is a directional pore size. Electrolyte wetting is controlled
  largely by the pore structure (porosity, pore-size distribution, pore geometry). In a graphite anode, light
  calendering raised the wetting rate and heavier calendering lowered it to about a third of its peak [11]. So
  narrower pores from heavy calendering are a warning, but pore width alone has no fixed good direction. The pore
  chord is largely redundant with local-thickness pore size and with porosity plus solid chord (identity above).

Harmful directions are not fixed: they depend on the supplier specification. For QC the question is a change from the
approved baseline.

## Industry / Polaron use

- **Powder CoA analogue.** PSD D10/D50/D90 (laser diffraction) is CoA item #1 for graphite (GB/T 24533, supplier
  TDS). The orientation index from XRD (I004/I110) is on the CoA and in a Samsung SDI patent (research report §2).
  Neither is measured on the electrode. The through-plane solid chord and the H/V ratio are their closest image
  proxies, as relative indices only.
- **Stereology.** The mean intercept length, L̄ = V_V / N_L, is classical quantitative metallography: the intercept
  method for grain and phase size, with minus-sampling for border-cut intercepts [1]. Torquato & Lu formalised the
  chord-length distribution for two-phase random media [2]. The lineal-path function, a related descriptor, was not
  built [3]. Taiwo et al. compared stereological 2D estimates with 3D analysis for Li-ion electrodes [7].
- **Software.** Chord-length distributions are in PoreSpy [8] and in the electrode toolboxes listed in the research
  report (MATBOX, GeoDict, Avizo). We know of no cell maker or supplier that publishes a chord-based incoming spec, so
  as a QC KPI this is **academic only**.
- **What would move it.** A different graphite grade, milling or classification (flake size). Spheroidisation (H/V
  toward 1). Calendering pressure (pore spacing and alignment). Binder/CBD amount or mixing: CBD fills small gaps, so
  there are fewer pores per line and solid chords get longer.

## How it is computed

1. `h = harmonised(sample)` (`features/_common`). The masks are the frozen shared recipe: crop the central 1336
   artefact-free rows minus 8 px each side; anchor BSE on black and graphite; add noise up to one fixed level; void =
   Otsu between pore and graphite on the σ = 2 px blurred image; drop pore specks < 16 px; fill solid pin-holes
   < 16 px. Solid = `h.solid` (= not void).
2. For every row (x) and every column (y), find the runs of the phase (`complete_chords`): pad the line with the other
   phase, take differences, pair the starts with the ends.
3. Mean chord length per axis (`mean_chord_um`). `estimator` in `config.yaml` picks how chords cut by the crop
   border are handled:
   - **`vv_nl` (default)**: phase pixels on all lines ÷ half the number of phase boundaries crossed inside the lines
     (chord starts plus chord ends, N_L = P_L/2). This is the stereological L̄ = V_V / N_L [1]: an unbiased estimator
     of the number-weighted mean chord. It uses the visible part of the border-cut chords and does not need to know
     their full length. Counting both ends rather than starts only gives solid and pore the same N_L and cancels
     which phase each line happens to begin and end in. A starts-only count shifted single spots by up to 2.5 %
     through the thickness. The symmetric count is as precise or slightly more so: split-half 0.69 / 0.70 / 0.27
     against 0.68 / 0.70 / 0.24 for solid x / y / H/V.
   - **`minus_sampling`**: discard every chord that touches either end of its line (minus-sampling). Weight each
     remaining chord of L px by 1/(n − L − 1), the inverse of the number of positions at which it fits inside a line
     of n px (Miles–Lantuéjoul correction; standard stereology [1]). Without the weight, long chords would be
     under-counted.
4. `solid_chord_hv_ratio = solid_chord_x_um / solid_chord_y_um`.
5. Guard: fewer than `min_chords` (200) complete chords along an axis gives `nan`. A typical spot has ~34,000.

**Why V_V/N_L is the default and not plain minus-sampling** (chosen on precision, never on batch signal). The crop is
only 33 µm tall, so **27 % of through-plane solid chords touch the border** (7 % in x). Both estimators are unbiased:
B3 means 5.80 vs 5.77 µm (x) and 4.92 vs 4.93 µm (y). Minus-sampling throws away the long chords that hold most of the
solid length, and that costs precision through the thickness. Split-half r for `solid_chord_y` is 0.70 with V_V/N_L
and 0.52 with minus-sampling; for the H/V ratio it is 0.27 vs 0.07. Ignoring the border altogether is biased. Counting
every run as if complete (as the screens did) reads y chords 13 % short and inflates H/V from 1.18 to 1.31 (B3
means). Unweighted minus-sampling reads y chords 15 % short.

Tuning numbers (`config.yaml`): `estimator: vv_nl`, `min_chords: 200`. Every segmentation number lives in
`features/_common/config.yaml`. Runtime: 0.05 s per spot for all five columns, on top of the shared harmonisation.

## Evidence on our data

### Final pipeline numbers

Source: `analysis/rank_features.py` (`processed/rankings.csv`: sep, q) and `analysis/robustness.py`
(`processed/robustness.csv`: within-session p, session R², perturbation ratio) on the integrated run, 31 spots. Means
in µm (H/V has no unit). rank_features permutes across all spots, so its sep and q do **not** control for session; the
within-session p does (exact permutation inside the five mixed sessions, minimum ≈ 0.005).

| Column | B1 / B2 / B3 mean | sep | q | within-session p | session R² | perturbation ratio |
|---|---|---|---|---|---|---|
| `solid_chord_x_um` | 6.93 / 6.23 / 5.80 | 0.91 | 0.027 | **0.026** | 0.70 | 0.53 (gamma 0.8) |
| `solid_chord_y_um` (diagnostic) | 5.93 / 5.29 / 4.92 | 0.91 | 0.029 | 0.12 | 0.76 | 0.62 (gamma 0.8) |
| `solid_chord_hv_ratio` (diagnostic) | 1.176 / 1.180 / 1.177 | 0.04 | 0.99 | 0.24 | 0.64 | 0.17 (gamma 0.8) |

For the solid chords sep_loo is 0.81 / 0.79: dropping any one spot keeps them above the ≈ 0.65 acquisition bar.
Dropping the two session-2316 spots together (one session) gives sep 0.71 / 0.65, so through the thickness the
all-spot separation falls to the acquisition bar without that session. leak_rho is 0.26 / 0.25 (black level), well
under 0.6. For H/V and the pore chords leak_rho is 0.46–0.57, close to that
limit, but they show no batch difference anyway. Corrected over all 68 columns in `robustness.csv` (BH), the
within-session p of 0.026 / 0.12 becomes q = 0.45 / 0.49. No column in the pipeline survives that correction, so the
within-session signal is a lead, not a finding. The builder's numbers below (means ± SD, η², session R², within-session
coefficients and contrasts, ICC, perturbation detail) agree with the final run to the printed precision. The
multiple-testing note (point 1) and the session-2060 offsets (point 4) were updated to the final run. The final
review re-computed every number here from `processed/features.csv`. It added the y contrasts (point 1), the
porosity-adjusted y test (point 2) and the overlap of session 2316 with the Si-phase anomaly (point 4).

### Builder's validation and review

Validated on all 31 spots (`preprocessing.iter_samples()`) with our own script, printed to stdout, before the
integrated run (`analysis/rank_features.py` was not run at that stage; its sep and q are in the table above). B3-SD =
between-spot SD of the 17 baseline spots. Within-session test: OLS y ~ C(session) + C(batch), statistic = drop in RSS
from adding batch, exact permutation over the 192 distinct batch relabellings within the five mixed sessions (minimum
p ≈ 0.005). Perturbations applied to the raw uint8 images of B3 spots 71vgq3fw, cfe5vt7s, hzumfsms and 0grcilhi;
ratio = max |Δ| / B3-SD. Split-half = the same code on the left and right half of the masks.

Independent re-check (review): a second implementation (1-D labelled runs for the chords, direct
shift-and-multiply S2 without FFT) matched these columns to machine precision on 9 spots. The spots cover every
mixed session, 2060 (71vgq3fw) and 2316 (4ih2ggld). The statistics and the perturbation pass were recomputed
from scratch and match the tables here.

| Column | B1 | B2 | B3 | η²(batch) | session R² | within-session coef. (B3-SD) B1 / B2, p | split-half r | perturbation ratio (worst) |
|---|---|---|---|---|---|---|---|---|
| `solid_chord_x_um` | 6.93 ± 0.62 | 6.23 ± 0.61 | 5.80 ± 0.63 | 0.37 | 0.70 | +2.54 / +1.65, **p = 0.026** | 0.69 | 0.53 (gamma 0.8) |
| `solid_chord_y_um` | 5.93 ± 0.80 | 5.29 ± 0.53 | 4.92 ± 0.46 | 0.36 | 0.76 | +2.41 / +1.51, p = 0.12 | 0.70 | 0.62 (gamma 0.8) |
| `solid_chord_hv_ratio` | 1.176 ± 0.066 | 1.180 ± 0.049 | 1.177 ± 0.044 | 0.001 | 0.64 | +1.25 / +1.05, p = 0.24 | 0.27 | 0.17 (gamma 0.8) |
| `pore_chord_x_um` | 0.670 ± 0.100 | 0.700 ± 0.081 | 0.691 ± 0.080 | 0.016 | 0.55 | −0.71 / −0.02, p = 0.65 | 0.55 | 0.36 (gamma 0.8) |
| `pore_chord_y_um` | 0.570 ± 0.085 | 0.593 ± 0.058 | 0.588 ± 0.069 | 0.014 | 0.56 | −1.08 / −0.37, p = 0.38 | 0.49 | 0.29 (gamma 0.8) |

Session R² chance level is ≈ 0.40 (13 groups, 31 spots).

Raw within-session contrasts (first batch minus second, B3-SD):

| Column | 2068 B2−B3 | 2080 B1−B2 | 2080 B1−B3 | 2080 B2−B3 | 2148 B1−B2 | 2156 B1−B2 | 2272 B2−B3 |
|---|---|---|---|---|---|---|---|
| `solid_chord_x_um` | +2.02 | +2.56 | +3.17 | +0.61 | +0.38 | −0.15 | +1.37 |
| `solid_chord_y_um` | +2.14 | +3.07 | +2.95 | −0.12 | +0.13 | −0.16 | +1.31 |
| `solid_chord_hv_ratio` | +0.50 | −0.54 | +1.69 | +2.23 | +0.63 | −0.03 | +0.78 |
| `pore_chord_x_um` | −0.57 | −2.17 | −0.42 | +1.75 | −1.45 | +0.86 | −0.58 |
| `pore_chord_y_um` | −0.71 | −1.82 | −0.92 | +0.91 | −1.61 | +0.83 | −0.82 |

Perturbation detail, max over the 4 spots in B3-SD (black +25 / gamma 0.8 / gamma 1.25 / contrast ×0.85 / noise σ 4 /
blur σ 1):
- solid x: 0.00 / 0.53 / 0.43 / 0.07 / 0.06 / 0.40
- solid y: 0.00 / 0.62 / 0.56 / 0.07 / 0.08 / 0.47
- H/V: 0.00 / 0.17 / 0.13 / 0.03 / 0.04 / 0.05
- pore x: 0.00 / 0.36 / 0.30 / 0.00 / 0.05 / 0.26
- pore y: 0.00 / 0.29 / 0.28 / 0.02 / 0.05 / 0.25

A 1 px blur along one axis only (added to `robustness.py` later; it mimics a stigmation or scan-direction change)
moves H/V by 0.59 SD (x blur) and 0.64 SD (y blur) on cfe5vt7s, and solid y by 0.09 / 0.34. The isotropic blur
above leaves H/V almost unchanged (0.05); a one-axis blur does not.

Black +25 gives exactly 0: the harmonisation anchors on the black level and the graphite mode, so a pure offset
leaves the masks unchanged.

What this says:
1. **The solid chord is the one column here with a within-session batch signal**, and it is thin. Incoming batches
   have longer solid chords than B3 in all four session-matched contrasts that include B3 (x: +2.0, +3.2, +0.6, +1.4
   B3-SD; y: three of four, +2.1, +3.0, −0.1, +1.3). B1 > B2 in two of the three B1–B2 pairs (x: 2080 +2.6, 2148
   +0.4, 2156 −0.2). The p values test both lots jointly. The exact p = 0.026 (x) is not corrected for multiple
   testing: over the 68 columns of the final robustness run, BH gives q = 0.45 (final pipeline numbers above).
   Through the thickness it is p = 0.12. The B1 evidence rests on one direct B1–B3 pair (session 2080). With the
   minus-sampling estimator the x signal is stronger (p = 0.005, the minimum attainable). We did not
   pick the estimator on that basis.
2. **It is not just porosity.** Solid chords correlate with porosity (`porosity_open_frac`, the same mask; r = −0.83),
   and porosity alone gives a within-session p of 0.167 (B1 −1.6, B2 −0.9 SD). After regressing on porosity (B3-only
   fit), solid chord x still shows B1 +2.1 / B2 +1.7 SD of the B3 residuals (0.35 µm), p = 0.042; y gives p = 0.12.
   The pore chord does not change, so the shift is in **N_L, the number of pores a line crosses**: x 0.132 / 0.145 /
   0.156 µm⁻¹ for B1/B2/B3 (within-session p = 0.052). If the shift is real, incoming batches have fewer, not
   smaller, pores per unit length at similar porosity. This agrees with the pore-morphology screen,
   where resolvable pore number density was about 1.6 B3-SD lower in all four B3 contrasts (`euler_A64`, p = 0.042).
   Physical candidates: CBD filling small gaps, coarser graphite, or a different calendering. We cannot tell them
   apart here.
3. **Session dominates.** In B3 the solid chord has ICC 0.83 (x) and 0.68 (y): σ_sess 0.61 / 0.39 µm against σ_w
   0.27 / 0.27 µm within a session. Use a session-aware SE (research report §6.4). For the v1 Tier-1 margin δ = 1.5·σ_R,
   σ_R (B3 total SD) is 0.46 µm for `solid_chord_y_um`, giving δ ≈ 0.69 µm.
4. **Special sessions.** The two B1 sites from session 2316 (4ih2ggld, 5n1q8atc; the Si-phase lead) are the longest
   in the data set: solid y z = +3.6 and +5.2 against B3. B1 without them is 6.67 ± 0.49 (x) and 5.52 ± 0.40 µm (y),
   raw means that do not control for session. Session 2316 holds only B1 spots, so it does not enter the
   within-session test at all. It also has the strongest FIB curtains in the data set (`acq_curtain_index` 1.68 /
   1.64 against at most 1.16 in B3) and a low H/V (1.12 / 1.07, z = −1.4 / −2.3): the through-plane chord rises more
   than the in-plane one there. Curtains run
   vertically and could bridge thin horizontal gaps, which would lengthen y chords. The same two spots carry the
   Si-phase anomaly (`bright_solid_frac` 0.16 / 0.20 against 0.066 in B3; `bright_agglom_d50_um` 10.6 / 11.1 µm),
   and the bright phase counts as solid here. Over all 31 spots solid chord y correlates r = 0.64 with
   `bright_solid_frac`, but r = 0.02 without session 2316, so the link is that one session. 4ih2ggld also has wide
   pores (pore chord y +1.8 SD), so the "fewer pores, same width" reading does not hold there. Without the two
   spots the raw B1 delta on y is +0.60 µm, inside the 0.686 µm v1 Tier-1 margin. With one session we cannot tell a
   curtain artefact, a Si-phase change and a graphite or CBD change apart (n_eff = 1). The B1 solid-chord excess on the
   certificate (now a diagnostic line) is therefore the same event as the Si-phase flag, not a second, independent finding. The
   lifted-black-level B3 session 2060 reads +0.70 / +0.85 SD (solid x / y) and −1.33 SD (both pore chords) against
   the other B3 spots (final run, `robustness.py` `lifted_z`; the builder's run, with the B3 total SD, gave +0.8 to
   +0.9 and −1.2). The screens saw the same −1 to −1.3 for
   pore-size features in that session in every recipe.
5. **H/V ratio is flat** across batches (1.18 in all three; within-session p = 0.24) and robust to the isotropic perturbations (0.17; 0.64
   under a one-axis blur, see above), but its
   precision is poor (split-half 0.27; B3 ICC 0.23). As the research report expected, it is an **expected-stable**
   check: only a gross alignment change would show. The orientation screen found the same for
   `chord_ratio_solid_xy` (split-half 0.26).
6. **Pore chords**: no batch signal, moderate precision, robust (≤ 0.36). They are largely redundant with porosity and
   solid chord (identity) and with local-thickness pore size (r = 0.94 between the screen's `pore_chord_x_um` and
   `pore_lt_d50_um`).
7. **The v1 identity companion could not confirm the chord, so v1.1 drops the check** (integration review, from
   `processed/features.csv`). `verdict_config.yaml` v1 paired `solid_chord_y_um` with `s2_solid_corrlen_y_um`, which is
   flat across batches (0.552 / 0.548 / 0.544 µm, sep 0.05, q 0.99, within-session p 0.41). That is expected, not a
   contradiction: at a solid fraction near 0.9 the 1/e correlation length of the solid follows the short phase. On
   our 31 spots it tracks φ × solid chord y = (1 − φ) × pore chord y (ratio 1.04 ± 0.07, r = 0.93), and it correlates
   r = 0.92 with `pore_chord_y_um` but r = −0.07 with `solid_chord_y_um`. So "identity not confirmed" on the v1
   certificates said nothing about the solid chord. Companions that do move the same way: the solid local thickness
   `solid_lt_d50_um` (an independent estimator; within-session B1 +1.2, B2 +1.5 SD, p = 0.068, r = 0.62 with solid
   chord y) and `interface_density_per_um` (B1 −2.1, B2 −1.4 SD, p = 0.057; not independent: it measures the same pore
   boundary, and (π/4)(P_Lx + P_Ly) reproduces its B3 value of 0.53 µm⁻¹).

Earlier screen (`scratchpad/screen/pore_morphology.json`, fixed 0.5 g void threshold, all chords counted, central
1600 rows): solid chord x B1 8.95 / B2 7.86 / B3 7.94 µm, within-session p = 0.15, split-half 0.77, gamma
perturbation 1.04. Values there are larger because that threshold gives 7.3 % porosity against ≈ 10.8 % here. The
signal is stronger and the gamma sensitivity smaller with the shared Otsu-based mask.

## Uncertainty and pitfalls

- **Single-image sampling error.** From split-half: mean |left − right| is 0.85 (x) and 1.05 (y) B3-SD per half image.
  That implies a whole-image sampling SE of roughly 0.5–0.7 B3-SD (≈ 0.3 µm). One image per site is a noisy site
  estimate. More area per site is the cheapest gain.
- **Session / sample cluster.** ICC 0.68–0.83 in B3. Never use the naive SD of site means as the error bar for a lot
  imaged in one session.
- **Acquisition.** Black level, contrast and added noise do nothing (≤ 0.08 B3-SD): the shared harmonisation absorbs
  them. **Gamma** (0.53–0.62) and **blur** (0.40–0.47) are the sensitivities, slightly above the 0.5 target. Both
  act through the shared void threshold: gamma moves the grey level of thin gaps relative to the Otsu threshold, and
  blur closes 1–2 px gaps. Fewer pores per line means longer solid chords. Gamma can only be fixed in
  `features/_common` (a third grey-level anchor; the screen found the Si phase unusable for that). A new batch with
  visibly softer focus should go to the acquisition gate before these numbers are read. Because the worst ratio
  (0.62, y) is above 0.5, `solid_chord_y_um` fails the verdict's invariance gate. With the MSA failure, that is why
  v1.1 moved it from Tier 1 to the diagnostics.
- **Segmentation dependence.** The solid chord is "distance between resolved pores". Pores below 16 px (0.01 µm²)
  are dropped and thin gaps below about 2 px vanish in the σ = 2 px blur. Absolute values therefore depend on the
  recipe (the screen's 0.5 g threshold gave +37 %). Compare only numbers made with the same frozen recipe.
- **Pore-back.** Sub-surface pores seen through open pores read mid-grey and are counted as solid. That biases
  porosity low and solid chords high. The bias is one-sided and could differ between batches if pore filling differs.
- **Not a particle size.** Touching flakes merge into one chord, and CBD counts as solid. The solid chord is not
  calibrated against PSD and must not be read as D50. For a convex particle the mean chord is smaller than the
  diameter (2D/3 for spheres). Wicksell-type section effects apply to particle sizes, not to chords.
- **3D validity.** A line inside the section plane is also a line in 3D. So `pore_chord_x/y` and `solid_chord_x/y`
  are genuine 3D mean intercepts **for those two directions** (L̄ = V_V / N_L holds along any test-line direction
  [1]). The out-of-plane direction is not sampled. The in-plane x value stands for all in-plane directions only if the
  electrode is transversely isotropic (likely for a calendered coating, not verified). Turning the directional
  intercepts into a 3D surface density S_V needs an isotropy or vertical-section assumption [9]. The image is a
  polished 2D surface; FIB curtaining and pore-back break the "ideal section" assumption [7].
- **Orientation.** We assume image y = through-thickness. No spot except possibly epqdaau9 shows the current
  collector, so the direction is inferred from flake layering, not measured.

## References

1. Russ, J. C. & DeHoff, R. T. (2000) *Practical Stereology*, 2nd ed., Springer (mean intercept length L̄ = V_V/N_L,
   minus-sampling and edge corrections). https://doi.org/10.1007/978-1-4615-1233-2
2. Torquato, S. & Lu, B. (1993) Chord-length distribution function for two-phase random media. *Phys. Rev. E* 47,
   2950. https://doi.org/10.1103/physreve.47.2950
3. Lu, B. & Torquato, S. (1992) Lineal-path function for random heterogeneous materials. *Phys. Rev. A* 45, 922.
   https://doi.org/10.1103/physreva.45.922
4. Ebner, M., Chung, D.-W., García, R. E. & Wood, V. (2014) Tortuosity anisotropy in lithium-ion battery electrodes.
   *Adv. Energy Mater.* 4, 1301278. https://doi.org/10.1002/aenm.201301278
5. Billaud, J., Bouville, F., Magrini, T., Villevieille, C. & Studart, A. R. (2016) Magnetically aligned graphite
   electrodes for high-rate performance Li-ion batteries. *Nat. Energy* 1, 16097.
   https://doi.org/10.1038/nenergy.2016.97
6. Winter, M., Novák, P. & Monnier, A. (1998) Graphites for lithium-ion cells: the correlation of the first-cycle
   charge loss with the BET specific surface. *J. Electrochem. Soc.* 145, 428. https://doi.org/10.1149/1.1838281
7. Taiwo, O. O., Finegan, D. P., Eastwood, D. S. et al. (2016) Comparison of three-dimensional analysis and
   stereological techniques for quantifying lithium-ion battery electrode microstructures. *J. Microsc.*
   https://doi.org/10.1111/jmi.12389
8. Gostick, J. T., Khan, Z. A., Tranter, T. G. et al. (2019) PoreSpy: a Python toolkit for quantitative analysis of
   porous media images. *J. Open Source Softw.* https://doi.org/10.21105/joss.01296 (that PoreSpy ships a
   chord-length tool is from general knowledge, not checked in the paper)
9. Baddeley, A. J., Gundersen, H. J. G. & Cruz-Orive, L. M. (1986) Estimation of surface area from vertical
   sections. *J. Microsc.* 142, 259. https://doi.org/10.1111/j.1365-2818.1986.tb04282.x
10. Weng, S., Yang, G., Zhang, S. et al. (2023) Kinetic limits of graphite anode for fast-charging lithium-ion
    batteries. *Nano-Micro Lett.* 15, 215. https://doi.org/10.1007/s40820-023-01183-6 (the rate-determining step
    depends on particle size: below about 10 µm, interfacial Li⁺ transfer and electrode transport limit rather than
    diffusion inside the particle; slow intercalation leads to Li plating)
11. Sheng, Y., Fell, C. R., Son, Y. K. et al. (2014) Effect of calendering on electrode wettability in lithium-ion
    batteries. *Front. Energy Res.* 2, 56. https://doi.org/10.3389/fenrg.2014.00056 (graphite anode calendered from
    59 to 41 µm: the wetting rate rose from 0.375 to 0.589 mm/s^0.5 at 53 µm, then fell to 0.206 mm/s^0.5 at 41 µm;
    wetting is controlled by porosity, pore-size distribution and pore geometry)

DOIs 1–9 were confirmed through Crossref with the ledger's lookup code (OpenAlex search was rate-limited, HTTP 429,
during this work). DOIs 10 and 11 were confirmed through Crossref on 2026-10-03 (10 found with
`literature.load_papers(topic="particle_size")`, its claim taken from the Crossref abstract; 11 is already verified in
other ledger entries, and its claim is taken from the abstract as served by the Semantic Scholar API because Crossref
has none). The claims for refs 4, 5 and 6 rest on their titles and on `notes/research_report.md` §8 and §10. Crossref,
OpenAlex and Semantic Scholar serve no abstract for them, so we have not checked them against the papers' text. Refs 2
and 3 were already verified in the ledger. Industry statements (GB/T 24533, supplier TDS,
Samsung SDI orientation-index patent, MATBOX/GeoDict/Avizo) are taken from `notes/research_report.md` §2 and §10.
