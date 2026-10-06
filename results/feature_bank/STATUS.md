# Feature bank status

Written 2026-10-04 07:14 by `python -m bank.qa`. Expected per column: 31 crops (injection columns: 6).

| family | P0 | black25 | gamma0.8 | gamma1.25 | contrast0.85 | noise4 | blur1 | pore_r2 | pore_r4 | pore_r8 | bright_rm50 | bright_rm100 | scalars | blocks | s/crop |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (views) | 31 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | | | |
| emb_convnextb | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 48 | 60 | 4 |
| emb_dinov2l | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 80 | 84 | 18 |
| emb_dinov3l | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 80 | 86 | 16 |
| emb_micronet | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 48 | 56 | 1 |
| fbank | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 282 | 2 | |
| glcm_lbp | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 594 | 24 | |
| imgqc | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 277 | 15 | |
| orient | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 72 | 6 | |
| phase | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 104 | 16 | |
| psd | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 154 | 12 | |
| registry | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 53 | 0 | |
| scat | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |  |  | |
| xdet | 31 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 107 | 22 | |

Passed review: imgqc, registry, xdet
