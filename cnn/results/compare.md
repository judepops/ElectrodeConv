# V1 vs V2 vs V1+2 (same 5 folds by spot; balanced accuracy, chance 0.33; 90 % session-bootstrap intervals)

| model | balanced accuracy [90 %] | recall B1 / B2 / B3 | mixed sessions | delta vs V1 [90 %] |
|---|---|---|---|---|
| V1 (label-free) | 0.64 [0.48, 0.81] | 0.86 / 0.29 / 0.76 | 0.62 | reference |
| V2 (batch-supervised) | 0.54 [0.37, 0.69] | 0.43 / 0.43 / 0.76 | 0.62 | -0.10 [-0.37, +0.17] |
| V1+2 concatenated | 0.76 [0.63, 0.91] | 1.00 / 0.57 / 0.71 | 0.80 | +0.12 [-0.03, +0.31] |
| V1+2 fine-tuned (V1 encoder + batch supervision) | 0.53 [0.38, 0.68] | 0.43 / 0.29 / 0.88 | 0.44 | -0.10 [-0.35, +0.07] |

## Does the embedding know the material?

| embedding | mean out-of-fold feature R2 | porosity_frac | si_solid_frac | si_n_per_1000um2 | si_d50_um | si_d90_um | si_aspect_aw | si_agglom_d50_um | interface_density_per_um | pore_n_per_1000um2 | solid_chord_x_um | solid_chord_y_um | porosity_block_cv | si_block_cv |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V1 (label-free) | 0.25 | 0.29 | 0.35 | -0.01 | 0.32 | 0.35 | 0.00 | 0.30 | 0.33 | 0.12 | 0.43 | 0.47 | 0.34 | 0.00 |
| V2 (batch-supervised) | 0.05 | 0.10 | 0.04 | -0.05 | 0.07 | 0.06 | -0.00 | 0.04 | 0.07 | 0.02 | 0.12 | 0.12 | 0.12 | -0.03 |
| V1+2 fine-tuned (V1 encoder + batch supervision) | 0.15 | 0.09 | 0.10 | 0.03 | 0.10 | 0.11 | -0.03 | 0.10 | 0.28 | 0.17 | 0.37 | 0.36 | 0.30 | -0.01 |
| untrained encoder (control) | 0.55 | 0.83 | 0.77 | 0.29 | 0.72 | 0.77 | 0.08 | 0.66 | 0.63 | 0.27 | 0.74 | 0.74 | 0.50 | 0.09 |
