# Versions (balanced accuracy, chance 0.33; 90 % session-bootstrap intervals; delta paired vs V1)

| id | change | losess [90 %] | p | mixed | joins | delta vs V1 [90 %] | P(delta>0) | gained / lost | leak p |
|---|---|---|---|---|---|---|---|---|---|
| V1 | the model the page used so far (seed 0) | 0.58 [0.40, 0.76] | 0.010 | 0.69 | 0.75 | | | | 0.77 |
| V1e | same run as V1, but the last checkpoint (epoch 30) instead of the one picked by validation mIoU (epoch 19): the checkpoint rule every later version uses | 0.56 [0.37, 0.76] | 0.020 | 0.62 | 0.75 | -0.02 [-0.07, +0.04] | 0.19 | 2 / 3 | 0.61 |
| V1.4a | the material-map decoder and its loss are removed; the encoder learns from the cross-detector contrastive task alone (Jude's idea) | 0.53 [0.39, 0.67] | 0.025 | 0.56 | 0.50 | -0.05 [-0.24, +0.13] | 0.32 | 4 / 5 | 0.54 |

One spot is worth 0.02 (Batch_3) to 0.05 (Batch_1/2) of balanced accuracy. A version beats V1 only if its delta clears the seed-noise row (V1s1) and its interval excludes 0; the best of K versions is an optimistic pick.
