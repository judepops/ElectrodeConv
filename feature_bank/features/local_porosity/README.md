# local_porosity

How much of the electrode sits in dense, pore-starved patches. The measurement is taken on the harmonised BSE void mask, window by window, rather than as one mean. It adds two columns to `processed/features.csv`.

| Column | Unit | Meaning |
|---|---|---|
| `local_porosity_q25_frac` | fraction | 25th percentile of the porosity of 5 µm × 5 µm tiles: the porosity of the densest quarter of the cross-section |
| `local_porosity_dense_window_frac` | fraction of windows | Share of 2.5 µm × 2.5 µm windows whose porosity is below 25 % of the spot's own porosity. It is relative to the spot, so a uniformly denser electrode does not count as patchy |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| `q25` down / `dense_window` up | More of the active material sits in patches with little or no pore space. Ions reach it only through long, tortuous paths, so its local ionic resistance is higher [1, 2, 4]. It lithiates last at high rate. Its pore-side neighbours carry more of the current, which raises the risk of Li plating during fast charge [4] | bad for rate and fast charge; neutral at slow rates | moderate (mechanism); low for the size of the effect in a 2D section |
| `q25` up / `dense_window` down | Pores are spread more evenly. Every region of the coating has electrolyte nearby | good, up to the point where the electrode is simply under-compacted. Check `porosity_open_frac` for that | moderate |

**Best value:** as close to the approved baseline as possible. The baseline is Batch_3, with `q25` 0.037 ± 0.010 and `dense_window` 0.419 ± 0.024. A shift towards more dense patches means calendering or mixing made the coating less uniform [3, 5].

**Our batches** (31 spots; see Evidence for the caveats):
- **Batch_1:** `q25` 0.023 ± 0.009 and `dense_window` 0.471 ± 0.042. That is more pore-starved patches than the baseline, by −1.4 and +1.8 baseline SD within sessions.
- **Batch_2:** `q25` 0.028 ± 0.009 and `dense_window` 0.444 ± 0.026. The direction is the same, by −1.6 and +1.9 SD within sessions.

Both shifts are leads, not established differences. Several of the mixed-session pairs are neighbouring tiles of one strip.

## What it measures

The void mask comes from `features/_common` (`h.void`). It is the black, electrolyte-accessible pore phase in the anchored, noise-matched BSE image, on the same 1336 × 6980 px crop (33 × 175 µm) of every spot. Instead of averaging it over the whole crop, this feature looks at the porosity of small windows:
- 5 µm tiles. There are about 200 per spot, and the 25th percentile is reported.
- 2.5 µm windows, about one flake thickness. The share that is nearly pore-free is reported.

A materials expert can picture it as follows. Take a grid of squares about the size of a graphite flake's thickness over the cross-section, and count how many squares are solid wall-to-wall.

Mean porosity can stay the same while the pores bunch up. A few large voids then sit next to long dense stretches. These two columns measure the dense side of that distribution directly. They complement the mean (`open_porosity`) and the spread (`heterogeneity.porosity_tile_cv`).

## Why it matters for the battery

- **Transport is local.** Image-based models of real electrodes show that porosity and tortuosity vary from sub-volume to sub-volume, and that this heterogeneity changes local current and performance compared with a homogeneous-electrode model [1]. In a composite electrode, tortuosity is locally inhomogeneous. Kehrwald et al. argue that such inhomogeneities, not the average, may set where degradation and failure start [2].
- **Fast charge and plating.** Microstructure-resolved 3D models show that heterogeneity becomes important at high rate. It causes a heterogeneous current distribution and non-uniform lithiation between particles and through the thickness [4]. Pore-starved regions are where this non-uniformity starts.
- **Process origin.** Calendering is the step that sets the final pore structure. Calendering defects and non-uniform compaction are classified as a distinct failure source [3, 5]. Agglomerates left by mixing also give dense and porous pockets. Either would move these columns before the mean porosity moves much.

## Industry / Polaron use

- **Polaron/Imperial:** single-image representativity and "track microstructure distributions" drift detection [6]. They report phase fractions with an integral-range error bar and watch the distribution, not only the mean. This feature applies that idea to the local porosity distribution.
- **Cell makers:** calendering-defect classification [3] and inline density checks target the same uniformity question at a coarser scale.
- No public incoming-QC specification quotes a dense-patch share. Treat it as a research-grade KPI.

## How it is computed

1. `h = harmonised(sample)`, `void = h.void`. Shared harmonisation applies: crop, black/graphite anchoring, noise top-up, Otsu void threshold (see `features/_common`).
2. **Tiles.** Non-overlapping `tile_px` = 200 px (5 µm) tiles via an integral image. Porosity of each tile. `local_porosity_q25_frac` = the `quantile` = 0.25 quantile.
3. **Windows.** `window_px` = 100 px (2.5 µm) windows on a `window_stride_px` = 50 px grid. `local_porosity_dense_window_frac` = share of windows with porosity < `dense_rel` (0.25) × the spot's own porosity.
4. NaN if there are fewer than 20 tiles or windows, or no void.

Runtime: about 3 s per spot on Modal, almost all of it the shared harmonisation (cached for the other features).

## Evidence on our data

The full audit protocol was run on Modal from the raw TIFs, with the production code: all 31 spots, left/right and top/bottom halves each re-harmonised independently, 3 noise top-up seeds, and 8 raw perturbations on 4 Batch_3 spots (black +25, gamma 0.8/1.25, contrast ×0.85, noise σ 4, blur σ 1 px, x-only and y-only blur). Statistics are at site level.

| | `q25_frac` | `dense_window_frac` |
|---|---|---|
| Batch means ± SD (B1 / B2 / B3) | 0.023 ± 0.009 / 0.028 ± 0.009 / 0.037 ± 0.010 | 0.471 ± 0.042 / 0.444 ± 0.026 / 0.419 ± 0.024 |
| η² batch / session R² (chance ≈ 0.40) | 0.30 / 0.78 | 0.37 / 0.78 |
| Within-session batch test (exact, 192 relabellings) | p = 0.031 | p = 0.078 |
| Incoming (B1+B2) vs B3 within sessions (exact, 24) | p = 0.042, the smallest attainable | p = 0.042, the smallest attainable |
| Within-session shift B1 / B2 (baseline SD) | −1.36 / −1.58 | +1.77 / +1.86 |
| Mixed-session contrasts (baseline SD) | 2068 B2−B3 −1.2; 2080 B1−B3 −2.1, B2−B3 −1.7; 2272 B2−B3 −1.5; 2148 B1−B2 +0.3; 2156 B1−B2 +1.1 | 2068 +2.0; 2080 +2.9, +1.7; 2272 +1.1; 2148 −1.8; 2156 +0.1 |
| Without the two session-2316 B1 spots (B1 / B2 vs B3) | −0.9 / −0.9 SD | +1.2 / +1.0 SD |
| Split-half r, x / y (independent halves) | 0.47 / 0.61 | 0.51 / 0.64 |
| Noise-seed spread / baseline SD | 0.02 | 0.03 |
| Worst perturbation / baseline SD | 0.37 (gamma 0.8); blur 0.11, x/y blur ≤ 0.07 | 0.70 (gamma 0.8); blur 0.24, x/y blur ≤ 0.12 |
| Lifted session 2060 (z vs other B3) | −0.4 | −0.3 |
| Leave-one-session-out AUC, B1 / B2 vs B3 | 0.80 / 0.67 | 0.84 / 0.67 |
| Measurement-system bracket on B3 (%GRR upper, ndc) | 0.90, 0.7 | 0.82, 1.0 |

**How to read this.**

What holds up:
- Both columns are robust to acquisition. Seed spread is ≤ 0.03 SD, the worst perturbation is ≤ 0.7 SD, and the lifted session does not stand out.
- Both are moderately reliable within one image (r 0.5–0.6).
- The direction is the same in every B1/B2-vs-B3 contrast within a session.

What weakens it:
- **Correlation with existing columns.** Neither is redundant above 0.9, but both follow the same axis as `solid_chord_x_um` and `interface_density_per_um` (|ρ| ≈ 0.85–0.89). Read them as an expert-friendly statement of that axis ("more of the electrode in pore-starved patches"), not as independent evidence.
- **One strip, three batch folders.** `notes/seam_examples` shows that sessions 2080, 2068 and 2148 are single strips split across batch folders. Along the 2080 strip (B3 `cfe5vt7s` | B2 `r17byphk` | B1 `ffwubibz`), `q25` goes 0.047 → 0.030 → 0.025. Within-session contrasts there compare neighbouring tiles of one sample, so the shift may be position along the electrode rather than a different lot.
- **Multiple testing.** Many columns were screened, so treat p ≈ 0.03–0.04 as a lead.
- **Measurement-system gate.** Like porosity, the columns fail the %GRR/ndc gate. The baseline variance is dominated by between-session (sample-region) differences, so a lot imaged in one session cannot be accepted or rejected on these columns alone.

## Uncertainty and pitfalls

- **2D vs 3D.** A window that looks pore-free can be fed by pores just above or below the section. The columns are relative indices of compaction uniformity, not transport numbers.
- **Void segmentation.** These columns inherit everything that biases the void mask:
  - pore-back reads as solid;
  - carbon-binder-filled pores read as solid;
  - the Otsu threshold follows the session pore floor (see the `open_porosity` audit).

  A recipe change in `features/_common` moves both columns.
- **Window size.** Results depend on the 2.5 µm / 5 µm choice. Smaller windows hold 0–2 pores and become counting noise. Larger ones leave too few windows per spot.
- **The 2316 spots.** Batch_1 `4ih2ggld` and `5n1q8atc` are the most pore-starved (`q25` 0.010–0.013). Their bright phase is unusual, so the shared void threshold behaves differently there.
- **Not for a classifier alone.** Leave-one-session-out AUCs are modest. Combine this feature with the composition KPIs, and never with acquisition columns.

## References

1. Cooper S. J., Eastwood D. S., Gelb J. et al. (2014). Image based modelling of microstructural heterogeneity in LiFePO4 electrodes for Li-ion batteries. *Journal of Power Sources* 247, 1033–1039. doi:10.1016/j.jpowsour.2013.04.156 (verified, Crossref)
2. Kehrwald D., Shearing P. R., Brandon N. P., Sinha P. K., Harris S. J. (2011). Local Tortuosity Inhomogeneities in a Lithium Battery Composite Electrode. *Journal of The Electrochemical Society* 158, A1393. doi:10.1149/2.079112jes (verified, Crossref)
3. Günther T., Schreiner D., Metkar A. et al. (2019). Classification of Calendering-Induced Electrode Defects and Their Influence on Subsequent Processes of Lithium-Ion Battery Production. *Energy Technology* 8, 1900026. doi:10.1002/ente.201900026 (verified, Crossref)
4. Lu X., Bertei A., Finegan D. P. et al. (2020). 3D microstructure design of lithium-ion battery electrodes assisted by X-ray nano-computed tomography and modelling. *Nature Communications* 11, 2079. doi:10.1038/s41467-020-15811-x (verified, Crossref)
5. Haselrieder W., Ivanov S., Christen D. K. et al. (2013). Impact of the Calendering Process on the Interfacial Structure and the Related Electrochemical Performance of Secondary Lithium-Ion Batteries. *ECS Transactions* 50(26), 59–70. doi:10.1149/05026.0059ecst (verified, Crossref)
6. Dahari A., Docherty R., Kench S., Cooper S. J. (2025). Prediction of Microstructural Representativity From A Single Image. *Advanced Science* 12(34), e14149. doi:10.1002/advs.202414149 (verified, Crossref)
