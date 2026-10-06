# Label-free structure of the feature spaces

Diagnostics only: nothing in this file may feed a model. Unit = crop, groups = the source images.

- Crops: 31 (Batch_1 7, Batch_2 7, Batch_3 17) from 13 source images; crop version P0.
- Spaces scored: 6 (2 of them pooled per family); 0 on fewer than 31 crops; skipped: 276.
- Clusters: k = 3; spectral (RBF, bandwidth = median distance) and agglomerative (ward).
- Nulls: 1000 relabellings, seed 0. `image` = the three folder names permuted at random inside each source image (respects the 13 groups). `crop` = folder labels shuffled over the crops (ignores the groups). `source` = source images shuffled over the crops.
- p_max = against the largest value over all spaces per relabelling; p_max_z = the same on z-scores.
- The fixed-point share is high for any labelling in a high-dimensional space: read it against its null mean.
- Max-statistic null, ari_folder under `image`: median 0.15, 95 % 0.32, 99 % 0.40.
- Max-statistic null, ari_folder under `crop`: median 0.06, 95 % 0.17, 99 % 0.26.
- Max-statistic null, fixed_point under `image`: median 0.81, 95 % 0.87, 99 % 0.94.
- Max-statistic null, fixed_point under `crop`: median 0.74, 95 % 0.84, 99 % 0.87.
- Max-statistic null, ari_source under `source`: median 0.03, 95 % 0.08, 99 % 0.10.
- Max-statistic null, ari_source_k13 under `source`: median 0.04, 95 % 0.13, 99 % 0.16.

## Spaces, by ARI against the folder label (top 4 of 4)

| space | crops | dims | tag | ARI folder (spectral / agglo) | p_max image | p_max crop | ARI source (spectral / agglo / k13) | p_max source | fixed point (null mean) | fixed point p_max_z image |
|---|---|---|---|---|---|---|---|---|---|---|
| legacy_dinov2s / BSE / harmonised / 25 / final | 31 | 768 | mixed | 0.23 / -0.01 | 0.198 / 0.999 | 0.016 / 0.963 | 0.21 / 0.08 / 0.41 | 0.001 / 0.044 | 0.81 (0.78) | 0.878 |
| legacy_dinov2s / Inlens / harmonised / 25 / final | 31 | 768 | mixed | 0.17 / 0.17 | 0.398 / 0.398 | 0.045 / 0.045 | 0.20 / 0.20 / 0.57 | 0.001 / 0.001 | 0.65 (0.70) | 0.999 |
| legacy_acq / Inlens / raw / 25 / - | 31 | 1 | imaging | 0.16 / 0.12 | 0.498 / 0.671 | 0.082 / 0.149 | 0.14 / 0.14 / 0.12 | 0.001 / 0.001 | 0.52 (0.44) | 0.678 |
| legacy_acq / BSE / raw / 25 / - | 31 | 4 | imaging | 0.01 / 0.01 | 0.997 / 0.997 | 0.911 / 0.911 | 0.14 / 0.14 / 0.76 | 0.001 / 0.001 | 0.77 (0.57) | 0.031 |

## One pooled space per family

| space | crops | dims | tag | ARI folder (spectral / agglo) | p_max image | p_max crop | ARI source (spectral / agglo / k13) | p_max source | fixed point (null mean) | fixed point p_max_z image |
|---|---|---|---|---|---|---|---|---|---|---|
| legacy_dinov2s / * / * / * / * | 31 | 1536 | mixed | 0.08 / 0.30 | 0.869 / 0.077 | 0.337 / 0.005 | 0.17 / 0.20 / 0.58 | 0.001 / 0.001 | 0.77 (0.78) | 0.961 |
| legacy_acq / * / * / * / * | 31 | 5 | imaging | 0.03 / 0.01 | 0.990 / 0.997 | 0.757 / 0.911 | 0.14 / 0.14 / 0.78 | 0.001 / 0.001 | 0.77 (0.60) | 0.066 |

## Mean over spaces, by family

| family | spaces | ARI folder spectral | ARI folder agglo | ARI source spectral | ARI source agglo | ARI source k13 | fixed point | fixed point minus null (image) |
|---|---|---|---|---|---|---|---|---|
| legacy_acq | 2 | 0.08 | 0.06 | 0.14 | 0.14 | 0.44 | 0.65 | 0.14 |
| legacy_dinov2s | 2 | 0.20 | 0.08 | 0.20 | 0.14 | 0.49 | 0.73 | -0.01 |

## Mean over spaces, by detector

| detector | spaces | ARI folder spectral | ARI folder agglo | ARI source spectral | ARI source agglo | ARI source k13 | fixed point | fixed point minus null (image) |
|---|---|---|---|---|---|---|---|---|
| BSE | 2 | 0.12 | -0.00 | 0.18 | 0.11 | 0.59 | 0.79 | 0.11 |
| Inlens | 2 | 0.16 | 0.15 | 0.17 | 0.17 | 0.34 | 0.58 | 0.01 |

## Mean over spaces, by view

| view | spaces | ARI folder spectral | ARI folder agglo | ARI source spectral | ARI source agglo | ARI source k13 | fixed point | fixed point minus null (image) |
|---|---|---|---|---|---|---|---|---|
| harmonised | 2 | 0.20 | 0.08 | 0.20 | 0.14 | 0.49 | 0.73 | -0.01 |
| raw | 2 | 0.08 | 0.06 | 0.14 | 0.14 | 0.44 | 0.65 | 0.14 |

## Mean over spaces, by scale_nm

| scale_nm | spaces | ARI folder spectral | ARI folder agglo | ARI source spectral | ARI source agglo | ARI source k13 | fixed point | fixed point minus null (image) |
|---|---|---|---|---|---|---|---|---|
| 25 | 4 | 0.14 | 0.07 | 0.17 | 0.14 | 0.47 | 0.69 | 0.06 |

## Mean over spaces, by layer

| layer | spaces | ARI folder spectral | ARI folder agglo | ARI source spectral | ARI source agglo | ARI source k13 | fixed point | fixed point minus null (image) |
|---|---|---|---|---|---|---|---|---|
| - | 2 | 0.08 | 0.06 | 0.14 | 0.14 | 0.44 | 0.65 | 0.14 |
| final | 2 | 0.20 | 0.08 | 0.20 | 0.14 | 0.49 | 0.73 | -0.01 |

## Mean over spaces, by tag

| tag | spaces | ARI folder spectral | ARI folder agglo | ARI source spectral | ARI source agglo | ARI source k13 | fixed point | fixed point minus null (image) |
|---|---|---|---|---|---|---|---|---|
| imaging | 2 | 0.08 | 0.06 | 0.14 | 0.14 | 0.44 | 0.65 | 0.14 |
| mixed | 2 | 0.20 | 0.08 | 0.20 | 0.14 | 0.49 | 0.73 | -0.01 |

## Skipped

- 274 space(s): 2 crops done and finite, 20 needed
- 2 space(s): nothing readable stored for it (saved token grids are not read)
