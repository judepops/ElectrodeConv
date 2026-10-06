# Harness results

31 crops (Batch_1 7, Batch_2 7, Batch_3 17), 13 source images. Chance balanced accuracy = 0.333. Intervals: 200 bootstrap resamples of source images (percentile 95 %). Null A: 100 per-image relabellings. Null B: 100 shuffles inside the mixed images. Both nulls refit the weights and the temperature.

| Row | Columns | LOSO-13 BA [95 % CI] | ΔBA vs acquisition [95 % CI] | Macro AUC | Log-loss | Null A p | Null B p | LOCO-nbr BA [95 % CI] |
|---|---|---|---|---|---|---|---|---|
| **Model A** (all non-leakrisk spaces) | 537177 | 0.608 [0.410, 0.778] | -0.143 [-0.280, 0.038] | 0.689 | 0.950 | 0.030 | 0.079 | 0.580 [0.407, 0.733] |
| **Model B** (no imaging, no leakrisk) | 536015 | 0.541 [0.347, 0.722] | -0.210 [-0.348, 0.012] | 0.723 | 0.912 | 0.079 | 0.277 | 0.532 [0.335, 0.735] |
| majority class | – | 0.333 [0.333, 0.333] | -0.417 [-0.589, -0.227] | 0.051 | 1.104 | – | – | 0.333 [0.333, 0.333] |
| acquisition only (imgqc) | 795 | 0.751 [0.560, 0.922] | – | 0.877 | 0.823 | 0.010 | 0.277 | 0.751 [0.560, 0.922] |
| best single family (inner-chosen) | – | 0.608 [0.437, 0.778] | -0.143 [-0.297, 0.011] | 0.779 | 0.862 | – | – | 0.560 [0.313, 0.796] |
| uniform kernel sum, A's kernels | 537177 | 0.549 [0.369, 0.710] | -0.202 [-0.377, -0.031] | 0.707 | 0.958 | – | – | 0.549 [0.311, 0.754] |
| uniform kernel sum, B's kernels | 536015 | 0.549 [0.326, 0.723] | -0.202 [-0.375, -0.047] | 0.691 | 1.009 | – | – | 0.597 [0.337, 0.811] |
| old DINOv2-S | 1536 | 0.375 [0.160, 0.608] | -0.375 [-0.568, -0.149] | 0.509 | 1.130 | – | – | 0.549 [0.349, 0.739] |
| provenance oracle (LOCO-nbr only) | – | – | – | – | – | – | – | 0.465 [0.222, 0.667] |
| single family: emb_convnextb | 187696 | 0.627 [0.422, 0.834] | -0.123 [-0.345, 0.111] | 0.832 | 0.828 | – | – | 0.655 [0.422, 0.905] |
| single family: emb_dinov2l | 82000 | 0.655 [0.456, 0.839] | -0.095 [-0.217, 0.027] | 0.851 | 0.796 | – | – | 0.608 [0.316, 0.878] |
| single family: emb_dinov3l | 82000 | 0.655 [0.456, 0.839] | -0.095 [-0.217, 0.027] | 0.854 | 0.792 | – | – | 0.608 [0.316, 0.878] |
| single family: emb_micronet | 177712 | 0.597 [0.386, 0.797] | -0.154 [-0.324, 0.017] | 0.714 | 0.962 | – | – | 0.588 [0.354, 0.831] |
| single family: fbank | 282 | 0.473 [0.294, 0.619] | -0.277 [-0.500, -0.001] | 0.609 | 1.097 | – | – | 0.616 [0.393, 0.801] |
| single family: glcm_lbp | 918 | 0.597 [0.393, 0.776] | -0.154 [-0.341, 0.076] | 0.681 | 1.019 | – | – | 0.597 [0.336, 0.840] |
| single family: imgqc | 795 | 0.445 [0.302, 0.564] | -0.305 [-0.448, -0.124] | 0.753 | 0.937 | – | – | 0.588 [0.352, 0.772] |
| single family: legacy_acq | 5 | 0.731 [0.556, 0.889] | -0.020 [-0.113, 0.110] | 0.806 | 0.780 | – | – | 0.711 [0.545, 0.874] |
| single family: legacy_dinov2s | 1536 | 0.454 [0.285, 0.622] | -0.297 [-0.486, -0.067] | 0.722 | 0.897 | – | – | 0.616 [0.416, 0.807] |
| single family: orient | 288 | 0.415 [0.194, 0.620] | -0.336 [-0.621, 0.000] | 0.506 | 1.089 | – | – | 0.510 [0.326, 0.681] |
| single family: phase | 694 | 0.356 [0.204, 0.520] | -0.395 [-0.653, -0.144] | 0.520 | 1.100 | – | – | 0.395 [0.206, 0.547] |
| single family: psd | 278 | 0.541 [0.340, 0.738] | -0.210 [-0.478, 0.140] | 0.664 | 1.039 | – | – | 0.636 [0.419, 0.833] |
| single family: registry | 53 | 0.426 [0.317, 0.559] | -0.325 [-0.556, -0.033] | 0.717 | 0.931 | – | – | 0.560 [0.384, 0.761] |
| single family: xdet | 4461 | 0.501 [0.300, 0.717] | -0.249 [-0.439, -0.005] | 0.678 | 1.013 | – | – | 0.501 [0.244, 0.736] |

Kernel rows use the kernel nearest-class-mean classifier; single-family rows use L2 logistic regression on the in-fold PCA.
ΔBA is paired: the same image resamples are used for the row and for the acquisition-only baseline.

## Blind-test model

Rule (config/primary.yaml), read on loso13: **B**. A and B differ by 2 correctly classified crop(s), within the margin of 2. A: 21 crops correct (BA 0.608); B: 19 (BA 0.541).

## A: nulls and confusion (LOSO-13)

- Balanced accuracy 0.608; 21 of 31 crops correct.
- Null A: mean 0.309, SD 0.147, 95th percentile 0.560, p = 0.030.
- Null B: mean 0.485, 95th percentile 0.655, p = 0.079; accuracy on the mixed-image crops 0.462 against a null mean of 0.429, p = 0.485.

| true \ predicted | Batch_1 | Batch_2 | Batch_3 |
|---|---|---|---|
| Batch_1 | 5 | 2 | 0 |
| Batch_2 | 2 | 2 | 3 |
| Batch_3 | 1 | 2 | 14 |

## B: nulls and confusion (LOSO-13)

- Balanced accuracy 0.541; 19 of 31 crops correct.
- Null A: mean 0.318, SD 0.136, 95th percentile 0.560, p = 0.079.
- Null B: mean 0.473, 95th percentile 0.597, p = 0.277; accuracy on the mixed-image crops 0.462 against a null mean of 0.390, p = 0.347.

| true \ predicted | Batch_1 | Batch_2 | Batch_3 |
|---|---|---|---|
| Batch_1 | 3 | 4 | 0 |
| Batch_2 | 1 | 3 | 3 |
| Batch_3 | 1 | 3 | 13 |

## acquisition: nulls and confusion (LOSO-13)

- Balanced accuracy 0.751; 24 of 31 crops correct.
- Null A: mean 0.335, SD 0.134, 95th percentile 0.558, p = 0.010.
- Null B: mean 0.690, 95th percentile 0.759, p = 0.277; accuracy on the mixed-image crops 0.462 against a null mean of 0.480, p = 0.832.

| true \ predicted | Batch_1 | Batch_2 | Batch_3 |
|---|---|---|---|
| Batch_1 | 7 | 0 | 0 |
| Batch_2 | 3 | 3 | 1 |
| Batch_3 | 2 | 1 | 14 |

## A: ALIGNF weights over the LOSO-13 folds

| Family | Weight, mean ± SD |
|---|---|
| psd | 0.403 ± 0.080 |
| emb_convnextb | 0.130 ± 0.057 |
| xdet | 0.126 ± 0.044 |
| emb_dinov2l | 0.109 ± 0.045 |
| imgqc | 0.077 ± 0.048 |
| registry | 0.069 ± 0.041 |
| phase | 0.042 ± 0.036 |
| emb_dinov3l | 0.037 ± 0.053 |
| orient | 0.005 ± 0.011 |
| glcm_lbp | 0.001 ± 0.003 |
| emb_micronet | 0.000 ± 0.000 |
| fbank | 0.000 ± 0.000 |

| Kernel (top 12) | Weight, mean ± SD |
|---|---|
| `psd\|Inlens\|harmonised\|imaging::rbf` | 0.190 ± 0.058 |
| `psd\|BSE\|harmonised\|material::rbf` | 0.181 ± 0.069 |
| `emb_convnextb\|BSE\|anchored\|mixed::mmd` | 0.121 ± 0.040 |
| `emb_dinov2l\|BSE\|anchored\|mixed::mmd` | 0.108 ± 0.044 |
| `xdet\|BSExInlens\|harmonised\|mixed::mmd` | 0.084 ± 0.037 |
| `imgqc\|BSE\|anchored\|imaging::linear` | 0.052 ± 0.028 |
| `phase\|BSE\|phase\|material::mmd` | 0.042 ± 0.036 |
| `registry\|BSE\|anchored\|imaging::rbf` | 0.039 ± 0.028 |
| `emb_dinov3l\|BSExInlens\|anchored\|mixed::rbf` | 0.037 ± 0.053 |
| `psd\|Inlens\|harmonised\|imaging::linear` | 0.020 ± 0.032 |
| `xdet\|BSE\|phase\|material::linear` | 0.020 ± 0.020 |
| `imgqc\|Inlens\|anchored\|imaging::linear` | 0.018 ± 0.018 |

## B: ALIGNF weights over the LOSO-13 folds

| Family | Weight, mean ± SD |
|---|---|
| psd | 0.225 ± 0.078 |
| xdet | 0.203 ± 0.059 |
| emb_convnextb | 0.183 ± 0.070 |
| emb_dinov2l | 0.179 ± 0.060 |
| registry | 0.077 ± 0.039 |
| emb_dinov3l | 0.068 ± 0.066 |
| orient | 0.034 ± 0.062 |
| phase | 0.030 ± 0.033 |
| glcm_lbp | 0.000 ± 0.001 |
| emb_micronet | 0.000 ± 0.000 |
| fbank | 0.000 ± 0.000 |

| Kernel (top 12) | Weight, mean ± SD |
|---|---|
| `psd\|BSE\|harmonised\|material::rbf` | 0.216 ± 0.079 |
| `emb_dinov2l\|BSE\|anchored\|mixed::mmd` | 0.179 ± 0.060 |
| `emb_convnextb\|BSE\|anchored\|mixed::mmd` | 0.143 ± 0.042 |
| `xdet\|BSExInlens\|harmonised\|mixed::mmd` | 0.130 ± 0.050 |
| `emb_dinov3l\|BSExInlens\|anchored\|mixed::rbf` | 0.068 ± 0.066 |
| `registry\|BSE\|harmonised\|mixed::rbf` | 0.040 ± 0.033 |
| `xdet\|BSExInlens\|anchored\|mixed::mmd` | 0.040 ± 0.071 |
| `orient\|Inlens\|harmonised\|mixed::rbf` | 0.031 ± 0.060 |
| `phase\|BSE\|phase\|material::mmd` | 0.030 ± 0.033 |
| `registry\|BSE\|phase\|material::linear` | 0.021 ± 0.032 |
| `xdet\|BSE\|phase\|material::linear` | 0.021 ± 0.022 |
| `emb_convnextb\|BSExInlens\|anchored\|mixed::linear` | 0.020 ± 0.038 |

## Folds that cannot be learned

- loso13: 0 of 13 folds.
- loco_nbr: 0 of 31 folds.

## What was scored

55 spaces, 134 kernels.

| Space | Tag | Columns | Tile arrays (width) |
|---|---|---|---|
| `emb_convnextb\|BSE\|anchored\|mixed` | mixed | 93844 | 1536 |
| `emb_convnextb\|BSExInlens\|anchored\|mixed` | mixed | 8 | – |
| `emb_convnextb\|Inlens\|anchored\|mixed` | mixed | 93844 | 1536 |
| `emb_dinov2l\|BSE\|anchored\|mixed` | mixed | 40996 | 2048 |
| `emb_dinov2l\|BSExInlens\|anchored\|mixed` | mixed | 8 | – |
| `emb_dinov2l\|Inlens\|anchored\|mixed` | mixed | 40996 | 2048 |
| `emb_dinov3l\|BSE\|anchored\|mixed` | mixed | 40996 | 2048 |
| `emb_dinov3l\|BSExInlens\|anchored\|mixed` | mixed | 8 | – |
| `emb_dinov3l\|Inlens\|anchored\|mixed` | mixed | 40996 | 2048 |
| `emb_micronet\|BSE\|anchored\|mixed` | mixed | 88852 | 3072 |
| `emb_micronet\|BSExInlens\|anchored\|mixed` | mixed | 8 | – |
| `emb_micronet\|Inlens\|anchored\|mixed` | mixed | 88852 | 3072 |
| `fbank\|BSE\|harmonised\|imaging` | imaging | 21 | – |
| `fbank\|BSE\|harmonised\|mixed` | mixed | 108 | 48 |
| `fbank\|Inlens\|harmonised\|imaging` | imaging | 27 | – |
| `fbank\|Inlens\|harmonised\|mixed` | mixed | 126 | 48 |
| `glcm_lbp\|BSE\|harmonised\|imaging` | imaging | 126 | 54 |
| `glcm_lbp\|BSE\|harmonised\|mixed` | mixed | 333 | 108 |
| `glcm_lbp\|Inlens\|harmonised\|imaging` | imaging | 126 | 54 |
| `glcm_lbp\|Inlens\|harmonised\|mixed` | mixed | 333 | 108 |
| `imgqc\|BSE\|anchored\|imaging` | imaging | 8 | – |
| `imgqc\|BSE\|raw\|imaging` | imaging | 393 | – |
| `imgqc\|Inlens\|anchored\|imaging` | imaging | 1 | – |
| `imgqc\|Inlens\|raw\|imaging` | imaging | 393 | – |
| `imgqc\|SE\|anchored\|leakrisk` | leakrisk | 1 | – |
| `imgqc\|SE\|raw\|leakrisk` | leakrisk | 393 | – |
| `legacy_acq\|BSE\|raw\|imaging` | imaging | 4 | – |
| `legacy_acq\|Inlens\|raw\|imaging` | imaging | 1 | – |
| `legacy_dinov2s\|BSE\|harmonised\|mixed` | mixed | 768 (tile means) | 768 |
| `legacy_dinov2s\|Inlens\|harmonised\|mixed` | mixed | 768 (tile means) | 768 |
| `orient\|BSE\|phase\|material` | material | 12 | – |
| `orient\|BSE\|phase\|mixed` | mixed | 84 | – |
| `orient\|BSE\|smoothed\|mixed` | mixed | 96 | – |
| `orient\|Inlens\|harmonised\|mixed` | mixed | 96 | – |
| `phase\|BSE\|phase\|material` | material | 366 | 6 |
| `phase\|BSE\|phase\|mixed` | mixed | 2 | – |
| `phase\|BSE\|smoothed\|mixed` | mixed | 326 | – |
| `psd\|BSE\|harmonised\|imaging` | imaging | 31 | – |
| `psd\|BSE\|harmonised\|material` | material | 26 | – |
| `psd\|BSE\|harmonised\|mixed` | mixed | 82 | 20 |
| `psd\|Inlens\|harmonised\|imaging` | imaging | 31 | – |
| `psd\|Inlens\|harmonised\|mixed` | mixed | 108 | 20 |
| `registry\|BSE\|anchored\|imaging` | imaging | 1 | – |
| `registry\|BSE\|harmonised\|imaging` | imaging | 2 | – |
| `registry\|BSE\|harmonised\|material` | material | 1 | – |
| `registry\|BSE\|harmonised\|mixed` | mixed | 3 | – |
| `registry\|BSE\|phase\|material` | material | 42 | – |
| `registry\|BSE\|phase\|mixed` | mixed | 4 | – |
| `xdet\|BSE\|harmonised\|mixed` | mixed | 3 | 1 |
| `xdet\|BSE\|phase\|material` | material | 1 | – |
| `xdet\|BSExInlens\|anchored\|imaging` | imaging | 2 | – |
| `xdet\|BSExInlens\|anchored\|mixed` | mixed | 199 | 4 |
| `xdet\|BSExInlens\|harmonised\|mixed` | mixed | 4136 | 4 |
| `xdet\|Inlens\|anchored\|mixed` | mixed | 60 | 2 |
| `xdet\|Inlens\|harmonised\|mixed` | mixed | 60 | 2 |

## Bank on disk

| Family | Crops done | In the harness |
|---|---|---|
| emb_convnextb | 31/31 | yes |
| emb_dinov2l | 31/31 | yes |
| emb_dinov3l | 31/31 | yes |
| emb_micronet | 31/31 | yes |
| fbank | 31/31 | yes |
| glcm_lbp | 31/31 | yes |
| imgqc | 31/31 | yes |
| legacy_acq | 31/31 | yes |
| legacy_dinov2s | 31/31 | yes |
| orient | 31/31 | yes |
| phase | 31/31 | yes |
| psd | 31/31 | yes |
| registry | 31/31 | yes |
| xdet | 31/31 | yes |

Gaps:

- emb_dinov3l: tile array emb_dinov3l/BSE/anchored/50/b11_tokens_28x28x1024 is 802816 wide (> 4096): left on disk, not used for kernels (1)
- emb_dinov3l: tile array emb_dinov3l/Inlens/anchored/50/b11_tokens_28x28x1024 is 802816 wide (> 4096): left on disk, not used for kernels (1)
- scat: no output on disk (1)
