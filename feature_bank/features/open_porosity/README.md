# open_porosity

The share of the cross-section that is open void (black in BSE), with a single-image 95 % error bar, a fixed-threshold
sensitivity value and the threshold that was used. Adds four columns to `processed/features.csv`.

| Column | Unit | Meaning |
|---|---|---|
| `porosity_open_frac` | area fraction (0–1) | Void area ÷ crop area from the shared harmonised void mask `h.void`. **Tier-1 decision KPI.** A *relative* index (see below) |
| `porosity_open_ci95_frac` | area fraction | Half-width of the 95 % sampling interval of `porosity_open_frac` for this one image: 1.96 × the two-point-correlation standard error |
| `porosity_fixed060_frac` | area fraction | Sensitivity recipe: anchored, blurred BSE < 0.6 graphite units, same speck/hole cleanup as `h.void` |
| `porosity_void_threshold` | graphite units | The per-image Otsu pore/graphite threshold behind `h.void` (diagnostic, never a KPI) |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `porosity_open_frac` up (its fixed-threshold twin `porosity_fixed060_frac` reads the same way) | More electrolyte-filled volume and a less tortuous path, so ions move more easily (D_eff/D₀ = ε/τ ≈ ε^α; α ≈ 1.5 for spheres, higher through the plane of aligned graphite flakes [R1–R3]): less electrolyte polarisation at high rate. The fast-charge gain is small: in a validated cell model, raising porosity at fixed loading was an *ineffective* lever against Li plating, while lowering tortuosity was effective [R4]. The cost is less active material per cm³, so lower volumetric energy density (mass balance). If the electrode is under-calendered, particle-to-particle and particle-to-foil contact also gets weaker | **Trade-off:** better rate (and a little more fast-charge margin), but lower volumetric energy density and possibly poorer electronic contact | Transport: strong [R1–R3]. Fast-charge gain: moderate, and small [R4]. Energy density: mass balance. Contact: general knowledge, no verified citation here. All read through a biased 2D relative index |
| `porosity_open_frac` down (same for `porosity_fixed060_frac`) | Denser electrode: harder calendering, higher coat density, or a graphite that packs tighter. Tortuosity rises as porosity falls [R3], so ion paths get longer and narrower: more electrolyte polarisation and lower capacity at high rate [R1–R3]. Fast-charge plating at the separator side is limited by electrolyte transport [R4] and depends on microstructure [R5], so its risk goes up, but probably only modestly for a small shift at fixed loading [R4]. Wetting is non-monotonic: light calendering speeds it up, heavy calendering slows it [R10], and where our calendered baseline sits on that curve is unknown. Volumetric energy density goes up (mass balance). With the ≈ 6 % Si-based phase (most likely SiOx), less pore space also leaves less room for it to swell (general knowledge, no verified citation here) | **Trade-off:** bad for rate and (mildly) fast charge, good for volumetric energy density | Transport: strong [R1–R3]. Plating: moderate [R4, R5]. Wetting: direction unknown for a small shift [R10]. SiOx swelling buffer: low. Moderate overall as a 2D relative index (pore-back bias, see *What it measures*) |
| `porosity_open_ci95_frac` up / down | The sampling error bar of one image gets wider or narrower. It grows with the porosity level and with coarser or more clustered pores, which have a larger integral range [R6, R11] | **Neither:** a precision diagnostic, not a material property | Strong (as a statistic) |
| `porosity_void_threshold` up / down | The per-image Otsu pore/graphite split has moved. It tracks the detector tone curve and the session, not the batch (session R² 0.79, within-session p = 0.86, perturbation ratio 1.66) | **Neither:** a sign that the imaging changed, not the material | Strong (it is meant to adapt) |

**Best value:** match the approved baseline. Porosity is a designed compromise between rate / fast charge and
energy density, so neither direction is better in itself. The index is also relative (biased low by pore-back), so
there is no absolute target. A shift in either direction, once a within-session comparison shows it is not the
session, points at calendering, coat weight, slurry or graphite PSD.

**Our batches** (final integrated run: `analysis/rank_features.py`, `analysis/robustness.py` and the certificates in
`analysis/verdicts/`):
- **Batch_1: shifted within tolerance; a lower-porosity hint that is not established.** 0.0887 ± 0.0156 vs Batch_3
  0.1077 ± 0.0183: −0.019 absolute, −1.04 B3-SD, −18 % relative.
  - Over all spots: sep = 0.55, below the ≈ 0.65 acquisition bar, and q = 0.17, which misses the 0.1 bar. This raw
    gap mixes batch and session: leaving out the one high, B3-only session 2088 shrinks it to −0.013 (−0.73 B3-SD).
  - Within the mixed sessions: coefficient −1.64 B3-SD, joint exact p = 0.17 (B1 and B2 terms tested together, 192
    relabellings). Only one B1 spot shares a session with a baseline spot (2080: −1.81 B3-SD, one site each); the
    other B1 contrasts are against B2 (2148 −0.91, 2156 +0.55), so the B1 coefficient is chained through B2. The test
    is also weak for a B1-only shift: at the observed size a real shift reaches p ≤ 0.05 in only ≈ 30 % of simulated
    draws. So p = 0.17 neither establishes nor rules out the deficit.
  - Not a 2316 effect. The two 2316 spots (one B1-only session, n_eff = 1) read 0.098 and 0.070; the within-session
    test cannot use them, and without them B1 is still 0.091 (−0.017).
  - Verdict: Tier 1, zone INCONCL, reason "shifted within tolerance". Δ = −0.019, 90 % CI [−0.039, +0.001]: the
    estimate is inside the ±0.0275 margin, the CI reaches past it. P(|Δ| > margin) = 0.24; porosity's action is
    release to monitoring. Porosity is not what makes B1 INVESTIGATE: that is the Si-phase (`bright_solid_frac`) and
    solid-chord excess carried by the two 2316 spots, i.e. one session (n_eff = 1).
  - If it is real, it is in the harmful direction for rate (mildly for fast charge) and the favourable one for
    energy density. Its functional size cannot be pinned down from 2D images (see *Why it matters*).
- **Batch_2: equivalent.** 0.1020 ± 0.0175, which is −0.006 or −0.31 B3-SD (0.000 if session 2088 is left out of the
  baseline). Within sessions −0.85 B3-SD (lower than B3 in 2 of 3 contrasts; same joint p = 0.17). Verdict: Tier 1
  EQUIV, 90 % CI [−0.026, +0.014] inside ±0.0275, P = 0.06. Porosity passes; B2 is held at INVESTIGATE by
  `bright_solid_frac` (P = 0.24, above the 0.2 CONDITIONAL ACCEPT bar), not by porosity.
- `porosity_void_threshold` is the only porosity column that `rank_features.py` calls "separates" (sep 0.89, q = 0.03;
  B1/B2 0.659 vs B3 0.688). The difference disappears within sessions (p = 0.86), so it reflects acquisition, not
  the material. It is not in the verdict.

## What it measures

The BSE detector images the polished cross-section. Open pores, the spaces between graphite flakes and Si-phase
particles that the electrolyte fills, return almost no backscattered electrons and appear black. Graphite is mid-grey and
the Si-like phase is bright. `porosity_open_frac` is the share of the image that is black, measured on the same
central window of every spot: 1336 × 6984 px, ≈ 33 × 175 µm, ≈ 5 830 µm², at 25 nm/px.

It is a **relative index, not the electrode porosity**. A calendered graphite anode is plausibly 25–35 % porous
(general knowledge; Hille et al. report 19–34 % for calendered graphite anodes, and that range is only partly verified
[R9]). The 2D section shows 7–15 % here, for two reasons:
- **Pore-back.** Where a pore is open, the beam sees the material behind it. That surface reads mid-grey, smooth and
  defocused, and is counted as solid. In FIB-SEM this is the "shine-through" problem that Prill et al.'s
  segmentation method addresses [R7].
- **Sub-resolution pores.** The pores inside the carbon-binder web are smaller than a few pixels and read as grey.

Comparisons between spots, batches and sessions are meaningful. The absolute level is not.

`porosity_open_ci95_frac` says how far the fraction could move by chance if the same material were imaged at
another place of the same size. `porosity_fixed060_frac` repeats the measurement with one fixed threshold instead of
a per-image one. If the two disagree about a batch difference, the difference sits in how the threshold adapts, not
in the material.

## Why it matters for the battery

- **Ionic transport and rate.** Effective electrolyte diffusivity and conductivity scale as D_eff/D₀ = ε/τ, usually
  written ε^α. The Bruggeman exponent α is 1.5 for spheres and higher through the plane of electrodes made of aligned
  graphite flakes, because particle shape and fabrication-induced alignment make tortuosity anisotropic [R1]; the
  Bruggeman form itself has limits [R2], and measured electrode tortuosity rises as porosity falls [R3]. (α = 1.5–3
  below is an illustrative range.) Lower porosity therefore means longer, narrower ion paths, more electrolyte
  polarisation and lower capacity at high rate.
- **Fast-charge lithium plating.** When the electrolyte cannot resupply Li⁺ fast enough, salt depletes inside the
  anode and Li plates at the graphite/separator interface; Colclasure et al. show this is the main fast-charge limit
  of high-energy cells [R4]. In their validated model, lowering electrode tortuosity was an effective remedy, but
  raising porosity (or the N/P ratio) was *not* [R4]. A likely reason (our reading, not stated in the abstract) is that
  at fixed loading more porosity also makes the electrode thicker. Microstructure at several length scales sets the
  plating propensity [R5]. **Lower porosity is still the harmful direction for fast charge, but a small shift at
  constant coat weight probably changes the plating risk only modestly.**
- **Wetting and formation.** The effect is non-monotonic. On a graphite anode, Sheng et al. found that light
  calendering *speeds up* electrolyte wetting: the wetting rate rose from 0.375 to 0.589 mm/s^0.5 as thickness went
  from 59 to 53 µm. Heavier calendering slows it again, to 0.206 mm/s^0.5 at 41 µm [R10]. Where our calendered
  baseline sits on that curve is unknown, so the wetting direction of a small shift is unknown.
- **Si-phase swelling (graphite–SiOx).** Pores also give the Si-based phase room to expand on lithiation, so a
  denser electrode may swell more and lose more particle contact. General knowledge, no verified citation here; low
  confidence.
- **Too high is also bad:** lower volumetric energy density (mass balance) and, if under-calendered, poorer
  particle-to-particle and particle-to-foil contact (general knowledge, no verified citation here).
- **Illustration, if the B1 gap were real and the 2D index scaled to 3D** (upper bound; the gap is not established,
  and pore-back and the 2D→3D bias are ignored): Batch_1's index is 17.6 % (relative) below Batch_3. At fixed
  thickness and α = 1.5–3 that is +34 % to +79 % electrolyte resistance if the *relative* change carried over to the
  true porosity, or +10 % to +22 % if only the *absolute* change (−0.019) carried over onto a true ≈ 30 % porosity.
  At a fixed coat weight the electrode also gets 3–7 % thinner, which offsets part of this (+24 % to +66 %, or
  +7 % to +18 %). The functional size of a change cannot be pinned down from these images.

## Industry / Polaron use

- **Cell makers** control electrode porosity mainly through calendering, computing it from coat weight, thickness and
  true density. Compaction density is a graphite CoA / GB/T 24533 item. LG Energy Solution's US 12,196,651 B2
  specifies region-wise pore fractions measured on cross-sections (research report §2).
- **Polaron / Imperial** report phase fractions with representativity error bars (ImageRep [R6]). They separate pores
  from the carbon-binder domain with Pt-infiltration "Kintsugi" imaging [R8], which is exactly the pore-back problem
  here. Image vendors (Avizo, GeoDict, MATBOX) report the same quantity.
- **What would move it:** calendering line load or gap, coat weight, slurry solids and binder content, graphite PSD
  and shape (a supplier change), and the Si-phase dose (it displaces graphite and packs differently).

## How it is computed

Detector: BSE only. Everything goes through the shared harmonisation `features/_common/harmonise.py`
(`h = harmonised(sample)`), so every feature sees the same void.

1. **Crop:** the same central 1336 rows of the artefact-free band, minus 8 px each side. Every spot is measured on the
   same area (`_common/config.yaml: crop`).
2. **Anchor:** raw BSE in graphite units, black level = 0 (0.5th percentile), graphite = 1 (mode of a blurred
   histogram).
3. **Noise match:** Gaussian noise is added up to σ = 0.235 graphite units (`noise.bse_target_sigma`), then the image
   is blurred at σ = 2 px.
4. **Void threshold:** Otsu between the pore and graphite populations of the blurred image, restricted to
   [0, 1.2) and clamped to [0.5, 0.75] (`segmentation.void_otsu_range`, `void_threshold_clamp`). On our data the
   threshold is 0.62–0.71 and never hits the clamp. This is `porosity_void_threshold`.
5. **Cleanup:** void specks < 16 px (0.01 µm²) are dropped and solid islands < 16 px are filled
   (`segmentation.min_void_px`). This is `h.void`.
6. `porosity_open_frac = h.void.mean()`.
7. `porosity_open_ci95_frac = ci_z × se`, with `ci_z = 1.96` (this folder's `config.yaml`). The standard error comes
   from `fraction_se(h.void)`: the mask is block-averaged 4 × 4, its FFT autocovariance is summed over
   |dy| ≤ 4 µm, |dx| ≤ 12 µm, and var = ∑C·ΔA / A_image (Lantuéjoul's integral range [R11], the ImageRep idea [R6]).
8. `porosity_fixed060_frac`: `h.bse_blur < fixed_threshold` (0.6, this folder's `config.yaml`), then the same cleanup
   as step 5. The cleanup size is read from `_common`, so the two recipes differ only in the threshold.

Runtime of this folder's code: median 0.42 s per spot (max 1.2 s on a loaded machine), mostly the FFT in
`fraction_se`. The shared harmonisation adds about 6–8 s.

## Evidence on our data

All 31 spots, recipe exactly as in the code. B3-SD = between-spot SD within Batch_3. Session R² by chance ≈ 0.40
(13 height groups, 31 spots).

### Final pipeline numbers

Source: `analysis/rank_features.py` (sep, q) and `analysis/robustness.py` (within-session p, session R²,
perturbation ratio) on the integrated run (`processed/rankings.csv`, `processed/robustness.csv`).

| Column | B1 / B2 / B3 mean | sep | q | within-session p (b1, b2 in B3-SD) | session R² | perturbation ratio |
|---|---|---|---|---|---|---|
| `porosity_open_frac` | 0.0887 / 0.1020 / 0.1077 | 0.55 | 0.17 | 0.17 (−1.64, −0.85) | 0.67 | 0.43 (gamma 0.8) |
| `porosity_fixed060_frac` | 0.0803 / 0.0920 / 0.0910 | 0.38 | 0.50 | 0.34 (−1.65, −0.83) | 0.61 | 0.79 (gamma 1.25) |
| `porosity_open_ci95_frac` | 0.0182 / 0.0183 / 0.0178 | 0.05 | 0.99 | 0.67 (−0.83, −0.34) | 0.43 | 0.25 (gamma 0.8) |
| `porosity_void_threshold` | 0.659 / 0.659 / 0.688 | 0.89 | 0.03 | 0.86 (+0.67, +0.30) | 0.79 | 1.66 (gamma 0.8) |
| old `porosity_frac` (reference) | 0.0863 / 0.0980 / 0.1066 | 0.58 | 0.13 | 0.18 (−1.05, −0.37) | 0.69 | 0.62 (gamma 1.25) |

- `rank_features.py` permutes across all spots, so its p and q do not control for session. The within-session p is
  the acquisition-controlled test; its minimum is ≈ 0.005.
- For `porosity_open_frac`: sep_loo = 0.45, leak_rho = 0.45 (with black level, under the 0.6 bar), and the
  rank_features verdict is "no difference".
- B3 variance components: σ_site = 0.0105, σ_session = 0.0160, ICC 0.70, %GRR upper bound 83 %. That fails the AIAG
  30 % rule, so porosity cannot drive the R1 REJECT path. R2, the large-effect path, stays open because the
  perturbation ratio is ≤ 0.5.
- The validation table below was computed by the builder before the integrated run. The final run reproduces it
  to the stated precision, with two corrections now made in place: the old `porosity_frac` perturbation ratio is
  0.62, not the screen's 0.48, and the threshold's within-session p is 0.86, not 0.87.

### Builder's validation

| Column | B1 | B2 | B3 | η²(batch) | session R² | within-session (B3-SD; exact p, 192 relabellings) | perturbation ratio |
|---|---|---|---|---|---|---|---|
| `porosity_open_frac` | 0.0887 ± 0.0156 | 0.1020 ± 0.0175 | 0.1077 ± 0.0183 | 0.17 | 0.67 | b1 −1.64, b2 −0.85; p = 0.17 | **0.43** (gamma only; all others ≤ 0.053) |
| `porosity_open_ci95_frac` | 0.0182 ± 0.0045 | 0.0183 ± 0.0048 | 0.0178 ± 0.0053 | 0.00 | 0.43 | b1 −0.83, b2 −0.34; p = 0.67 | 0.25 |
| `porosity_fixed060_frac` | 0.0803 ± 0.0160 | 0.0920 ± 0.0197 | 0.0910 ± 0.0162 | 0.08 | 0.61 | b1 −1.65, b2 −0.83; p = 0.34 | 0.79 (gamma) |
| `porosity_void_threshold` | 0.659 ± 0.019 | 0.659 ± 0.028 | 0.688 ± 0.014 | 0.39 | 0.79 | b1 +0.67, b2 +0.30; p = 0.86 | 1.66 (by design: it adapts) |
| old `porosity_frac` (multi-Otsu, `processed/features.csv`) | 0.0863 ± 0.0153 | 0.0980 ± 0.0138 | 0.1066 ± 0.0194 | 0.19 | 0.69 | b1 −1.05, b2 −0.37; p = 0.18 | 0.62 (gamma 1.25, `robustness.py`; the screen had 0.48) |

- **Raw within-session contrasts** for `porosity_open_frac`, in B3-SD:
  - 2068: B2−B3 −1.32
  - 2080: B1−B2 −2.46, B1−B3 −1.81, B2−B3 +0.65
  - 2148: B1−B2 −0.91
  - 2156: B1−B2 +0.55
  - 2272: B2−B3 −1.05

  B1 is lower in 3 of its 4 contrasts, but only one of them is against the baseline (2080, one site each), and the
  two 2080 contrasts share the same B1 spot. B2 is below B3 in 2 of 3. This is the same "B1 ≈ 2 % (absolute) less
  porous" hint the research report and the screen found. **It is not established (p = 0.17).**
  - The joint test is weak for a B1-only shift. Only 3 B1 spots sit in mixed sessions, and 16 of the 192
    relabellings only reshuffle B2/B3 labels and keep the B1 contrasts intact. For a large B1-only shift the
    observed arrangement ranks at random among those 16, so p lands anywhere between 1/192 and 16/192 ≈ 0.08.
  - Simulation on this design (B1-only shift, Gaussian site and session noise in the B3 σ_site : σ_session ratio):
    at about the observed size (3 within-session SD; observed −0.030 ÷ 0.0105 = −2.9) the test gives p ≤ 0.05 in
    ≈ 30 % of 300 draws, median p ≈ 0.08. Even a 100-SD shift gives p ≤ 0.05 only about half the time
    (p = 0.005–0.08). p = 0.17 is therefore weak evidence either way, not evidence of equal porosity.
- **Plausibility.** Values run from 0.068 (B1 f1vzngrs) to 0.148 (B3 hzumfsms). Session 2088 (B3) is high: z = +2.6,
  +3.4 and +1.1 against the other B3 spots, with the excess in the grey 0.3–0.6 band (pore-back or shallow pores;
  screen finding). Without 2088 the B3 mean is 0.102, the marginal B1 gap shrinks to −0.013 and B2's vanishes
  (0.000), so part of the raw gaps is this one B3-only session. The lifted-black session 2060 reads low
  (z = −1.25), as with every other recipe. The black+25 perturbation changes nothing, so this is not the black
  level.
- **Variance components within B3** (method of moments, 7 sessions): σ_site-within-session = 0.0105,
  σ_session = 0.0160, ICC = 0.70. The old multi-Otsu recipe gives 0.0135 / 0.0149 / 0.55. Spots within a session now
  agree better, and almost all of the remaining B3 spread is between sessions.
- **Against the old `porosity_frac`:** r = 0.94, mean offset +0.002. The batch deltas against B3 are almost the same:
  B1 −0.019 (old −0.020) and B2 −0.006 (old −0.009). The within-session coefficients are larger in B3-SD units
  (−1.64 vs −1.05), because the new recipe has less within-session scatter. Gamma robustness is a little better:
  the worst perturbation ratio is 0.43 vs 0.62 for the old recipe in the integrated `robustness.py` run (the screen
  had put the old one at 0.48). Otherwise the gain is in definition, not separation: one void mask shared by every
  feature, a stated crop and noise level, and an error bar.
- **Against the screen's porosity variants** (computed independently on the central 1600 rows):
  - `porosity_otsu` (same idea): r = 0.97, offset +0.002. The screen recommended this variant (perturbation 0.42,
    split-half 0.83); it is reproduced here.
  - `porosity_I060`: r = 0.95.
  - `porosity_anchored_v2`: r = 0.95.
- **Fixed vs adaptive threshold.** The fixed 0.6 threshold sits below the Otsu one (mean 0.675), so it reads 0.013
  lower. It is about twice as gamma-sensitive (0.79 vs 0.43), the same result as the screen. It also shows a
  smaller *marginal* B1−B3 gap (−0.011 vs −0.019), because B1/B2 sessions have lower Otsu thresholds (0.659 vs 0.688).
  The threshold difference is between sessions (within-session p = 0.86), and within sessions the two recipes give
  the same batch coefficients (−1.65 vs −1.64 B3-SD).
- **Error bar check.** The median single-image se is 0.0090 (A_IR median 5.3 µm², IQR 4.2–6.4), so the CI half-width
  is 0.018.
  - Split-half check, left vs right half of each crop: observed RMS(L−R) = 0.0141, predicted 2·se = 0.0190. The se is
    conservative by about 1.35×, matching the screen's 1.4×.
  - Split-half r of the porosity itself: 0.77 over all spots, 0.90 within B3.
  - B3 between-site variance ÷ mean se² = 3.7. Sites really differ about 2× more than one image's sampling error
    (excess SD 0.016), and most of that is the session component above.
- **Perturbations** (B3 71vgq3fw, cfe5vt7s, hzumfsms, 0grcilhi; max |Δ| ÷ B3-SD):

  | Perturbation | Ratio |
  |---|---|
  | black +25 | 0.00 |
  | gamma 0.8 | 0.43 (|Δ| ≤ 0.008) |
  | gamma 1.25 | 0.40 |
  | contrast ×0.85 | 0.04 |
  | noise σ = 4 | 0.05 |
  | blur σ = 1 | 0.05 |

  Gamma is the only real sensitivity: a threshold between two anchors cannot be made gamma-invariant.

**Verdict:** reliable, acquisition-robust except under gamma, and it reproduces the old KPI. Batch signal: an
unproven B1 deficit of about −0.02. That is the marginal difference (−0.013 without session 2088); the
session-adjusted coefficient of −1.64 B3-SD is −0.030, resting on one direct B1–B3 pair plus contrasts chained
through B2. Fit for Tier 1 as long as the decision layer uses the session-aware SE (§6.4 of the research report),
not this single-image CI. The integrated verdict does this: SE 0.0106 (df 6.6), margin ±0.0275. B1 is INCONCL
(P(|Δ| > margin) = 0.24) and B2 is EQUIV (P = 0.06). With %GRR at 83 %, porosity can reach REJECT only through the
large-effect route R2.

## Uncertainty and pitfalls

- **The CI is sampling error only.** It is the right error bar for "how well does this image know its own
  porosity" and the wrong one for "how well does this lot know its porosity". The spot-to-spot SD in B3 (0.018) is
  2× the median se, and the session component (0.016) dominates. Never use `porosity_open_ci95_frac` as a batch
  error bar.
- **Biased low, and the bias may vary.** Pore-back and sub-resolution CBD pores both read as solid. If a supplier
  change alters pore depth or CBD texture, the bias changes too. **v2 plan:** a pore-back bracket. Its upper bound is
  `porosity_nonsolid_frac` from the multi-detector pixel classifier (BSE + SE relief + Inlens ridges; research
  report §3 rank 10). The screen's hysteresis variant (seeds < 0.35 grown into < 0.75: B1 0.098 / B2 0.109 /
  B3 0.114) can serve as a cheap interim upper bound.
- **Gamma / tone curve.** A ±25 % gamma change moves porosity by up to 0.008 (0.43 B3-SD). A session with a
  different detector tone curve can fake a shift of that size.
- **Correlation with raw noise.** `porosity_open_frac` correlates with the raw BSE noise level `acq.bse_noise_sigma`:
  - r = −0.72 over all spots and −0.62 within sessions.
  - `acq.bse_noise_sigma` is measured on the whole image, so it also picks up pore edges. Restricting the noise
    estimate to graphite interiors gives a cleaner measure: r = −0.66 over all spots and −0.42 within sessions.
  - The noise σ = 4 and blur σ = 1 perturbations move porosity by ≤ 0.001, so after noise matching the pipeline does
    not respond to noise as such.
  - The correlation therefore comes from acquisition or the sample, not from the arithmetic. Candidates: a dwell or
    line-averaging difference that changes the noise spectrum and edge sharpness in a way the synthetic battery does
    not reproduce, or a material/session confound (the quiet 2088 session is the most porous).
  - Unresolved. Re-imaging one spot twice in different sessions would settle it.
- **Session 2088 is high and 2060 low** for every recipe tried. Material and acquisition cannot be separated there.
- **Threshold quantisation.** The Otsu threshold moves in steps of ≈ 0.005 graphite units (histogram bins), which is
  part of its perturbation ratio. That is harmless for the fraction.
- **3D validity.** Area fraction = volume fraction (Delesse) holds for an isotropic, uniform random section. The
  number is valid in 3D *for what the 2D mask calls void*; the pore-back bias is a separate, one-sided error.

## References

DOIs resolved through the Crossref API on 2026-10-03, because the OpenAlex search quota behind `ledger.py search`
was exhausted that day. "Amass" marks papers also found with `literature.load_papers`. DOIs came from the research
report (§10) or the Amass literature, never from memory. The abstracts of R1–R5 and R10 were re-read on 2026-10-03
(Semantic Scholar / OpenAlex records of the same DOIs, or the Amass copy) to check each battery claim.

1. [R1] Ebner, Chung, García et al. (2014; online 2013) Tortuosity anisotropy in lithium-ion battery
   electrodes. *Adv. Energy Mater.* 4:1301278. https://doi.org/10.1002/aenm.201301278 (also verified in the ledger)
2. [R2] Tjaden, Cooper, Brett et al. (2016) On the origin and application of the Bruggeman
   correlation for analysing transport phenomena in electrochemical systems. *Curr. Opin. Chem. Eng.* 12:44–51.
   https://doi.org/10.1016/j.coche.2016.02.006
3. [R3] Landesfeind, Hattendorff, Ehrl et al. (2016) Tortuosity determination of battery electrodes and
   separators by impedance spectroscopy. *J. Electrochem. Soc.* 163:A1373. https://doi.org/10.1149/2.1141607jes
4. [R4] Colclasure, Dunlop, Trask et al. (2019) Requirements for enabling extreme fast charging of
   high energy density Li-ion cells while avoiding lithium plating. *J. Electrochem. Soc.* 166:A1412.
   https://doi.org/10.1149/2.0451908jes (abstract: electrolyte transport, salt depletion and Li plating at the
   graphite/separator interface limit fast charge; reducing tortuosity helps, increasing porosity does not)
5. [R5] Kabra, Parmananda, Fear et al. (2020) Mechanistic analysis of microstructural attributes to lithium
   plating in fast charging. *ACS Appl. Mater. Interfaces* 12:55795. https://doi.org/10.1021/acsami.0c15144 (Amass)
6. [R6] Dahari, Docherty, Kench et al. (2025) Prediction of microstructural representativity from a single
   image (ImageRep). *Adv. Sci.* 12. https://doi.org/10.1002/advs.202414149 (Amass)
7. [R7] Prill, Schladitz, Jeulin et al. (2013) Morphological segmentation of FIB-SEM data of highly porous
   media. *J. Microsc.* 250:77. https://doi.org/10.1111/jmi.12021 (Amass)
8. [R8] Cooper, Roberts, Liu et al. (2022) Methods—Kintsugi imaging of battery electrodes:
   distinguishing pores from the carbon binder domain using Pt deposition. *J. Electrochem. Soc.* 169:070512.
   https://doi.org/10.1149/1945-7111/ac7a68
9. [R9] Hille, Toepper, Schriever et al. (2022) Influence of laser structuring and calendering of graphite anodes on electrode
   properties and cell performance. *J. Electrochem. Soc.* https://doi.org/10.1149/1945-7111/ac725c (the 19–34 %
   porosity range is **[partly verified]** per the research report)
10. [R10] Sheng, Fell, Son et al. (2014) Effect of calendering on electrode wettability in lithium-ion
    batteries. *Front. Energy Res.* 2:56. https://doi.org/10.3389/fenrg.2014.00056 (graphite anode, 59 → 41 µm)
11. [R11] Lantuéjoul (1991) Ergodicity and integral range. *J. Microsc.* 161:387.
    https://doi.org/10.1111/j.1365-2818.1991.tb03099.x
12. Salzer, Prill, Spettl et al. (2015) Quantitative comparison of segmentation algorithms for FIB-SEM images
    of porous media. *J. Microsc.* 257:23. https://doi.org/10.1111/jmi.12182 (background for the v2 pore-back bracket)
13. Project sources: `notes/research_report.md` §2 (KPI table), §3 rank 4, §4, §6.2–6.4, §7.8, §8; screen results
    `phase_fractions.json` (`porosity_otsu`, `porosity_I060`, `porosity_frac_old`) and `acquisition_null.json`
    (`porosity_anchored_v1/v2`). LGES US 12,196,651 B2 and GB/T 24533-2019 are cited from the research report
    (URLs there; no DOI).
