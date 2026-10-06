# Harness results

31 crops (Batch_1 7, Batch_2 7, Batch_3 17), 13 source images. Chance balanced accuracy = 0.333. Intervals: 200 bootstrap resamples of source images (percentile 95 %). Null A: 100 per-image relabellings. Null B: 100 shuffles inside the mixed images. Both nulls refit the weights and the temperature.

| Row | Columns | LOSO-13 BA [95 % CI] | ΔBA vs acquisition [95 % CI] | Macro AUC | Log-loss | Null A p | Null B p | LOCO-nbr BA [95 % CI] |
|---|---|---|---|---|---|---|---|---|
| **Model A** (all non-leakrisk spaces) | 1541 | 0.521 [0.347, 0.701] | -0.190 [-0.319, -0.037] | 0.697 | 1.003 | 0.099 | 0.842 | 0.569 [0.370, 0.759] |
| **Model B** (no imaging, no leakrisk) | 1536 | 0.375 [0.160, 0.608] | -0.336 [-0.539, -0.148] | 0.509 | 1.130 | 0.376 | 0.871 | 0.549 [0.349, 0.739] |
| majority class | – | 0.333 [0.333, 0.333] | -0.378 [-0.530, -0.191] | 0.051 | 1.104 | – | – | 0.333 [0.333, 0.333] |
| acquisition only (legacy_acq) | 5 | 0.711 [0.524, 0.863] | – | 0.845 | 0.819 | 0.030 | 0.713 | 0.711 [0.524, 0.863] |
| best single family (inner-chosen) | – | 0.731 [0.556, 0.889] | 0.020 [-0.045, 0.083] | 0.802 | 0.780 | – | – | 0.711 [0.545, 0.874] |
| uniform kernel sum, A's kernels | 1541 | 0.683 [0.500, 0.855] | -0.028 [-0.141, 0.074] | 0.801 | 0.806 | – | – | 0.683 [0.500, 0.855] |
| uniform kernel sum, B's kernels | 1536 | 0.434 [0.250, 0.621] | -0.277 [-0.426, -0.130] | 0.703 | 0.961 | – | – | 0.569 [0.354, 0.753] |
| old DINOv2-S | 1536 | 0.375 [0.160, 0.608] | -0.336 [-0.539, -0.148] | 0.509 | 1.130 | – | – | 0.549 [0.349, 0.739] |
| provenance oracle (LOCO-nbr only) | – | – | – | – | – | – | – | 0.465 [0.222, 0.667] |
| single family: legacy_acq | 5 | 0.731 [0.556, 0.889] | 0.020 [-0.045, 0.083] | 0.802 | 0.780 | – | – | 0.711 [0.545, 0.874] |
| single family: legacy_dinov2s | 1536 | 0.454 [0.285, 0.622] | -0.258 [-0.466, -0.050] | 0.722 | 0.897 | – | – | 0.616 [0.416, 0.807] |

Kernel rows use the kernel nearest-class-mean classifier; single-family rows use L2 logistic regression on the in-fold PCA.
ΔBA is paired: the same image resamples are used for the row and for the acquisition-only baseline.

## Blind-test model

Rule (config/primary.yaml), read on loso13: **A**. higher balanced accuracy (6 crops apart). A: 18 crops correct (BA 0.521); B: 12 (BA 0.375).

## A: nulls and confusion (LOSO-13)

- Balanced accuracy 0.521; 18 of 31 crops correct.
- Null A: mean 0.324, SD 0.154, 95th percentile 0.638, p = 0.099.
- Null B: mean 0.603, 95th percentile 0.731, p = 0.842; accuracy on the mixed-image crops 0.308 against a null mean of 0.353, p = 0.762.

| true \ predicted | Batch_1 | Batch_2 | Batch_3 |
|---|---|---|---|
| Batch_1 | 3 | 4 | 0 |
| Batch_2 | 3 | 3 | 1 |
| Batch_3 | 1 | 4 | 12 |

## B: nulls and confusion (LOSO-13)

- Balanced accuracy 0.375; 12 of 31 crops correct.
- Null A: mean 0.325, SD 0.159, 95th percentile 0.619, p = 0.376.
- Null B: mean 0.530, 95th percentile 0.712, p = 0.871; accuracy on the mixed-image crops 0.231 against a null mean of 0.348, p = 0.812.

| true \ predicted | Batch_1 | Batch_2 | Batch_3 |
|---|---|---|---|
| Batch_1 | 2 | 5 | 0 |
| Batch_2 | 3 | 3 | 1 |
| Batch_3 | 2 | 8 | 7 |

## acquisition: nulls and confusion (LOSO-13)

- Balanced accuracy 0.711; 22 of 31 crops correct.
- Null A: mean 0.345, SD 0.154, 95th percentile 0.601, p = 0.030.
- Null B: mean 0.691, 95th percentile 0.779, p = 0.713; accuracy on the mixed-image crops 0.308 against a null mean of 0.340, p = 0.832.

| true \ predicted | Batch_1 | Batch_2 | Batch_3 |
|---|---|---|---|
| Batch_1 | 7 | 0 | 0 |
| Batch_2 | 3 | 3 | 1 |
| Batch_3 | 2 | 3 | 12 |

## A: ALIGNF weights over the LOSO-13 folds

| Family | Weight, mean ± SD |
|---|---|
| legacy_dinov2s | 0.762 ± 0.115 |
| legacy_acq | 0.238 ± 0.115 |

| Kernel (top 12) | Weight, mean ± SD |
|---|---|
| `legacy_dinov2s\|BSE\|harmonised\|mixed::rbf` | 0.599 ± 0.113 |
| `legacy_acq\|BSE\|raw\|imaging::linear` | 0.148 ± 0.070 |
| `legacy_dinov2s\|Inlens\|harmonised\|mixed::linear` | 0.075 ± 0.087 |
| `legacy_acq\|Inlens\|raw\|imaging::linear` | 0.050 ± 0.042 |
| `legacy_acq\|Inlens\|raw\|imaging::rbf` | 0.040 ± 0.039 |
| `legacy_dinov2s\|Inlens\|harmonised\|mixed::rbf` | 0.036 ± 0.049 |
| `legacy_dinov2s\|BSE\|harmonised\|mixed::linear` | 0.032 ± 0.074 |
| `legacy_dinov2s\|BSE\|harmonised\|mixed::mmd` | 0.021 ± 0.041 |

## B: ALIGNF weights over the LOSO-13 folds

| Family | Weight, mean ± SD |
|---|---|
| legacy_dinov2s | 1.000 ± 0.000 |

| Kernel (top 12) | Weight, mean ± SD |
|---|---|
| `legacy_dinov2s\|BSE\|harmonised\|mixed::rbf` | 0.647 ± 0.108 |
| `legacy_dinov2s\|Inlens\|harmonised\|mixed::rbf` | 0.132 ± 0.077 |
| `legacy_dinov2s\|Inlens\|harmonised\|mixed::linear` | 0.127 ± 0.132 |
| `legacy_dinov2s\|BSE\|harmonised\|mixed::linear` | 0.073 ± 0.097 |
| `legacy_dinov2s\|BSE\|harmonised\|mixed::mmd` | 0.021 ± 0.040 |

## Folds that cannot be learned

- loso13: 0 of 13 folds.
- loco_nbr: 0 of 31 folds.

## What was scored

4 spaces, 10 kernels.

| Space | Tag | Columns | Tile arrays (width) |
|---|---|---|---|
| `legacy_acq\|BSE\|raw\|imaging` | imaging | 4 | – |
| `legacy_acq\|Inlens\|raw\|imaging` | imaging | 1 | – |
| `legacy_dinov2s\|BSE\|harmonised\|mixed` | mixed | 768 (tile means) | 768 |
| `legacy_dinov2s\|Inlens\|harmonised\|mixed` | mixed | 768 (tile means) | 768 |

## Bank on disk

| Family | Crops done | In the harness |
|---|---|---|
| emb_convnextb | 2/31 | no (incomplete) |
| emb_dinov2l | 2/31 | no (incomplete) |
| emb_dinov3l | 2/31 | no (incomplete) |
| emb_micronet | 2/31 | no (incomplete) |
| fbank | 2/31 | no (incomplete) |
| glcm_lbp | 2/31 | no (incomplete) |
| imgqc | 2/31 | no (incomplete) |
| legacy_acq | 31/31 | yes |
| legacy_dinov2s | 31/31 | yes |
| orient | 2/31 | no (incomplete) |
| phase | 2/31 | no (incomplete) |
| psd | 2/31 | no (incomplete) |
| registry | 2/31 | no (incomplete) |
| scat | 2/31 | no (incomplete) |
| xdet | 2/31 | no (incomplete) |

Gaps:

- emb_convnextb: not done (29)
- emb_dinov2l: not done (29)
- emb_dinov3l: not done (29)
- emb_dinov3l: tile array emb_dinov3l/BSE/anchored/50/b11_tokens_28x28x1024 is 802816 wide (> 4096): left on disk, not used for kernels (1)
- emb_dinov3l: tile array emb_dinov3l/Inlens/anchored/50/b11_tokens_28x28x1024 is 802816 wide (> 4096): left on disk, not used for kernels (1)
- emb_micronet: not done (29)
- fbank: not done (29)
- glcm_lbp: not done (29)
- imgqc: not done (29)
- orient: not done (29)
- phase: not done (29)
- psd: not done (29)
- registry: not done (29)
- scat: not done (29)
- xdet: not done (29)
