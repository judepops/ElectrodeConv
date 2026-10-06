# cnn/results: what has been tried, what it scored, what it means

Read this before changing the CNN. Every number here was written by code (`cnn/supcon.py score`, `cnn/compare.py`,
`cnn/baselines.py`); the JSON files next to this README are the source.

## The question and how it is scored

Given only the three SEM images of a spot (BSE, Inlens, SE), which batch is it? 31 labelled spots: Batch_1 7,
Batch_2 7, Batch_3 17 (the baseline). The score is **balanced accuracy** (mean of the three per-batch hit rates;
chance 0.33) on spots the model never saw. With 31 spots one Batch_1 or Batch_2 spot is worth 0.05, so intervals
are wide: every score comes with a 90 % interval from resampling the 13 imaging sessions (`cnn/uncertainty.py`).

## Models

| name | what it is | how it learns |
|---|---|---|
| **V1** (`cnn/processed/v_k7_con02`) | label-free encoder: one network per detector, material-map decoder, detectors matched to each other | never sees a batch label; a logistic regression on the spot embedding makes the call |
| **V2** (`supcon/v2`) | early fusion: the 3 images go in as one 3-channel image (`FusionNet` in `cnn/supcon.py`) | supervised contrastive on the batch label (same batch together, other batches apart; positives must come from a different spot) + a batch classifier head + a light material map |
| v2_spot | V2, but the contrast acts on spot means (average of the spot's tiles in the mini-batch) | |
| v2_con | V2 without the classifier head, temperature 0.05 | its contrastive loss never left chance |
| **V1+2 / r2a** | V2 recipe started from V1's trained encoder (encoder learning rate x0.1), spot-level contrast and classifier | the "knowledge of V1, specialisation of V2" combination |
| r2b | r2a + a session-adversarial head (gradient reversal) so the embedding cannot carry the imaging session | |
| r3a | r2a + embeddings centred in every mini-batch, temperature 0.05, cosine classifier with margin 0.2 | stronger gradients on subtle differences |
| r3b | r3a + Batch_1 vs Batch_2 negatives weighted x3 in the contrastive loss | more push on the pair nothing has separated |

Supervised models (everything except V1) see the labels, so they are retrained 5 times, each time without one fifth
of the spots, and scored only on the spots they never saw (`supcon.py run` / `score`). The batches are treated as
one imaging sitting (Polaron built them by splitting one cell with their own model), so the folds are by spot.

## Round one: supervised encoders alone (balanced accuracy on unseen spots, chance 0.33)

| model | score [90 %] | recall B1 / B2 / B3 | file |
|---|---|---|---|
| V1, leave one spot out / one session out | 0.64 / 0.58 (p 0.01) | | `../README.md` history |
| V2 | 0.54 [0.37, 0.69] | 0.43 / 0.43 / 0.76 | `v2_score.json` |
| v2_spot | 0.47 [0.31, 0.61] | 0.43 / 0.14 / 0.82 | `v2_spot_score.json` |
| v2_con | 0.55 [0.38, 0.69] | 0.43 / 0.57 / 0.65 | `v2_con_score.json` (loss at chance: effectively an untrained encoder) |
| v2_noseg (V2 without the material map, Jude's idea) | 0.52 [0.36, 0.67] | 0.43 / 0.43 / 0.71 | `v2_noseg_score.json`; V1 + v2_noseg side by side 0.66 |

Baselines on the same test (`baselines.json`): hand-crafted features 0.45 (seg3 masks 0.49), imaging cues alone
0.66, pixel statistics 0.38, untrained encoder 0.49, shuffled labels 0.34 (95th percentile 0.54).

## What we have learned

1. **Batch_3 is recognisable, Batch_1 vs Batch_2 is not.** Every model so far, supervised or not, recalls Batch_3
   at 0.65 to 0.82 and Batch_1 / Batch_2 near chance. Even on its own training spots V2 merges Batch_1 and Batch_2
   into one block (cosine similarity matrix on the team page).
2. **Supervision alone did not beat the label-free model.** With 24 training spots per fold the supervised network
   memorises spot and session identity: V2's embedding puts a spot's nearest neighbour in the same imaging session
   26 % of the time (chance 6 %, p 0.008); V1's did not.
3. **V2's batch direction is not made of named features.** The Batch_1 minus Batch_3 difference in V2's embedding
   has no component along the 13 feature read-outs (`v2_difference.json`; a random direction gives 0.03), so it is
   hard to interpret. V1's calls decompose largely into named features.
4. **The contrastive term on its own does not learn here**; the classifier head carries the signal.
5. **Dropping the material map did not help** in either framework (old model: -0.05; V2: 0.52 vs 0.54), so the
   "no classification before the CNN" idea is not supported by these runs.

## Round two: combining V1 and V2 (`compare.json`, `compare_extra.json`, `cnn/compare.py`)

All rows on the SAME 5 folds by spot with the same classifier (standardised blocks, logistic regression), so they
compare directly. "delta" is paired against V1 on the same resampled sessions.

| model | score [90 %] | recall B1 / B2 / B3 | delta vs V1 [90 %], P(better) |
|---|---|---|---|
| V1 | 0.64 [0.48, 0.81] | 0.86 / 0.29 / 0.76 | reference |
| V2 | 0.54 [0.37, 0.69] | 0.43 / 0.43 / 0.76 | -0.10 [-0.37, +0.17], 0.26 |
| **V1 + V2 side by side** | **0.76 [0.63, 0.91]** | 1.00 / 0.57 / 0.71 | +0.12 [-0.03, +0.31], 0.87 |
| V1 encoder fine-tuned with batch supervision (r2a) | 0.53 (0.58 with evalkit's classifier) | 0.43 / 0.29 / 0.88 | -0.10 |
| r2a + session-adversarial head (r2b) | 0.47 (evalkit) | 0.43 / 0.14 / 0.82 | |
| V1 + r2a side by side | 0.68 | | +0.04 |
| V1 + v2_spot side by side | 0.64 | | 0.00 |
| V1 + v2_con side by side | 0.51 | | -0.13 |
| V1 + r2a + v2_con + v2_spot | 0.58 | | -0.06 |

Reading: **V1 + V2 is the best so far, but it is the best of five concatenations**, the others give 0.51 to 0.68, so
part of the 0.76 is selection luck. The test running now: V2 retrained with seeds 1 and 2 (`v2s1`, `v2s2`), each
concatenated with V1. If both land near 0.75 the gain is real (V2's supervised view adds information V1 lacks); if
they fall back to about 0.64 it was noise. Fine-tuning V1's encoder with labels (r2a) did not help, and the
session-adversarial head made things worse.

## Is it learning the material? (`compare.json`, "material")

| embedding | mean out-of-fold R2 of the 13 tile features | share of the Batch_1 - Batch_3 direction along named features (random direction) | session leak (chance 0.06) |
|---|---|---|---|
| untrained encoder (control) | **0.55** | | |
| V1 | 0.25 (shuffled null -0.15) | 0.18 (0.008) | 0.06, p 0.78 |
| V2 | 0.05 | 0.17 (0.025) | 0.26, p 0.002 |
| r2a | 0.15 | 0.04 (0.025) | 0.16, p 0.16 |

Two lessons. (1) **"The embedding predicts porosity" is not evidence of learning:** an untrained network predicts the
13 features better than any trained one, because they are low-level image statistics that random filters already
capture, and training throws away what its objective does not need. (2) The informative check is whether the
direction that separates the batches runs along named features: in V1, 18 % of the Batch_1 - Batch_3 difference lies
in the span of the 13 feature read-outs, 22 times a random direction, with no session leak. That is the evidence that
V1's batch signal is material structure. V2 also aligns (7x random) but leaks session; r2a barely aligns.

## Round three: stronger gradients for subtle differences

The V2 similarity matrix showed every tile at cosine 0.83 to 1.00, so at temperature 0.1 "same batch" (0.98) vs
"other batch" (0.92) is a logit gap of only 0.6 and the loss barely pushes. r3a = r2a (V1 encoder, spot-level) plus:
z centred in every mini-batch (removes the shared direction), temperature 0.05 (doubles the gap), and a cosine
classifier with margin 0.2 (keeps pulling after the easy cases are solved).

| model | score [90 %] | recall B1 / B2 / B3 | note |
|---|---|---|---|
| r2a (before) | 0.58 [0.42, 0.72] | 0.57 / 0.29 / 0.88 | evalkit classifier |
| **r3a** | **0.63 [0.48, 0.77]** | 0.57 / 0.43 / 0.88 | best supervised single model so far |
| V1 + r3a side by side | 0.58 | | no gain over V1 (0.64) |
| r3b (r3a + Batch_1/Batch_2 negatives x3) | 0.63 [0.53, 0.72] | 0.43 / 0.57 / 0.88 | same total; recall shifts from Batch_1 to Batch_2 |
| V1 + r3b side by side | 0.61 | | |
| r3c (r3a + vertical flips and 90-degree rotations) | 0.48 [0.32, 0.66] | 0.43 / 0.43 / 0.59 | **rotations hurt** (-0.15); calls all 3 test spots Batch_2 |

The loss changes help the supervised model (+0.05 over r2a, +0.09 over V2) and bring it level with V1, but its
view now overlaps V1's (it starts from V1's encoder), so joining them adds nothing. Up-weighting the Batch_1/Batch_2
negatives (r3b) moves errors between those two batches without reducing them. **Do not rotate or vertically flip
these images:** the electrode has a direction (through the coating thickness, flakes lying horizontally) and
rotation destroys real information (r3c 0.48 vs 0.63). Running next: r3c (+ rotations), v2c
(V2 from scratch + the r3a loss changes, to pair with V1) with seeds 1 and 2, V2 seeds 1 and 2 (is V1 + V2 = 0.76 reproducible?).

## Is V1 + V2 = 0.76 real? Seed check

V2 retrained with another random seed (`v2s1`), everything else identical, same folds and classifier:

| model | score [90 %] | recall B1 / B2 / B3 | delta vs V1 | known test set (one-per-batch) |
|---|---|---|---|---|
| V1 + V2 seed 0 | 0.76 [0.63, 0.91] | 1.00 / 0.57 / 0.71 | +0.12 | 2/3 (3/3) |
| V1 + V2 seed 1 | 0.66 [0.49, 0.84] | 0.71 / 0.57 / 0.71 | +0.03 | 2/3 (3/3), same calls, more confident |
| **V1 + V2, seeds 0 and 1 averaged** | **0.71 [0.58, 0.88]** | 0.86 / 0.57 / 0.71 | +0.08, P(better) 0.83 | |
| V2 seed 1 alone | 0.45 [0.29, 0.61] | 0.43 / 0.14 / 0.76 | | |

Reading: the gain from adding V2 to V1 is real but smaller than the first run suggested, about +0.03 to +0.12 with
the two-seed average at +0.08. Averaging seeds is the stable version of the best model; six more V2 seeds (3 to 8)
are training on a second GPU box to make that average reliable.

## v2c: the r3a loss changes on V2 from scratch

| model | score [90 %] | recall B1 / B2 / B3 | known test set |
|---|---|---|---|
| v2c (V2 from scratch + centring, temperature 0.05, cosine margin 0.2) | 0.39 [0.25, 0.53] | 0.43 / 0.14 / 0.59 | |
| V1 + v2c side by side | 0.57 [0.40, 0.75] | 0.71 / 0.29 / 0.71 | 1 / 3 (one-per-batch 0 / 3) |

The changes that lifted r3a (which starts from V1's encoder) push a from-scratch encoder to near chance: with 24
training spots, the sharper loss is too hard to learn from nothing. V2 as first trained stays the partner for V1.

## Test-spot calls so far (`test_calls.json`)

Each model refitted on all 31 training spots; probability of the call in brackets; "stable" = same call in that share
of 31 refits with one training spot left out.

| test spot | V1 | V2 | V1 + V2 |
|---|---|---|---|
| 3e122cbj | Batch_3 (0.60, stable 77 %) | Batch_1 (0.65, 100 %) | Batch_2 (0.57, 90 %) |
| fn0mhxef | Batch_2 (0.59, 90 %) | Batch_1 (0.49, 77 %) | Batch_1 (0.62, 94 %) |
| xrv9xvzb | Batch_3 (0.54, 77 %) | Batch_3 (0.72, 100 %) | Batch_2 (0.61, 90 %) |

The models disagree. Polaron said the test set holds one spot per batch, and neither V1 nor V1 + V2 gives that,
so each has at least one wrong. xrv9xvzb is the most consistent (Batch_3). The image-adjacency clue in
`evalkit.SEAM_GUESS` (each test image continues a training image) says 3e122cbj Batch_1, fn0mhxef Batch_2,
xrv9xvzb Batch_3; that is about where the crop was cut, not a material reading. Treat every call here as weak until
the V2 seed check shows whether V1 + V2 is reliable.

## Eval set (6 spots, `classify_Hackathon-Polaron-eval.json`; images are not in the repo)

`python cnn/classify.py --dir <eval folder> --per-batch 2 --add-labelled 3e122cbj=Batch_2,fn0mhxef=Batch_1,xrv9xvzb=Batch_3`
(V1 + V2, classifier fitted on the 31 training spots + the 3 earlier test spots, whose labels are now known).

| spot | height | V1 alone | V2 alone | V1 + V2 | confidence |
|---|---|---|---|---|---|
| 0eryguqq | 1612 | B3 (0.95) | B3 (1.00) | **B3** | strong: both agree |
| 4hq27w4c | 2148 | B1 (0.96) | B1 (0.81) | **B1** | strong |
| fspqbkxl | 2148 | B2 (0.97) | B2 (0.83) | **B2** | strong |
| fhwrjtet | 1612 | B2 (0.51) | B3 (1.00) | **B3** | contested |
| soo2ax3r | 2156 | B3 (0.64) | B1 (0.78) | **B1** | contested |
| y59rxmxl | 1880 | B3 (0.48) | B1 (0.55) | **B1** (0.63; B2 0.30) | weak |

If the set holds exactly two spots per batch, the best joint assignment moves y59rxmxl to Batch_2.

How to read it: the eval images are new pieces of electrode (pixel correlation with every training image ~0.01) and
sit as close to the training spots as training spots sit to each other (4hq27w4c a little further in V1). The 1.00
probabilities of V1 + V2 are overconfident (34 spots in 2048 dimensions separate too easily); agreement between V1,
which never saw a label and shows no session leak, and V2 is the better confidence signal. The contested calls match
the training batch of their imaging session in V2, the model known to leak session; on the earlier test set,
session membership was wrong for 2 of 3 spots.

## FINAL eval calls (safe version): V1 + V2, two V2 seeds averaged

`python cnn/classify.py --dir <eval folder> --v2 v2,v2s1 --per-batch 2 --add-labelled 3e122cbj=Batch_2,fn0mhxef=Batch_1,xrv9xvzb=Batch_3`

| spot | call | P(B1, B2, B3) | V1 and V2 agree? |
|---|---|---|---|
| 0eryguqq | **Batch_3** | 0.00 / 0.00 / 1.00 | yes |
| 4hq27w4c | **Batch_1** | 0.99 / 0.00 / 0.00 | yes |
| fhwrjtet | **Batch_3** | 0.00 / 0.00 / 1.00 | no (V1 alone: Batch_2) |
| fspqbkxl | **Batch_2** | 0.00 / 0.99 / 0.01 | yes |
| soo2ax3r | **Batch_1** | 0.84 / 0.13 / 0.03 | no (V1 alone: Batch_3) |
| y59rxmxl | **Batch_1** (Batch_2 if the set is exactly two per batch) | 0.77 / 0.19 / 0.04 | no (V1 alone: Batch_3) |

Same calls with one V2 seed or two. Held-out score of this model 0.71 [0.58, 0.88]; 3/3 on the earlier test set with
the one-per-batch rule. The probabilities are overconfident; the three "yes" rows are the reliable ones.
The V1 V2 combined model (one network, both losses summed, `cnn/joint.py`) is training; it replaces this answer only
if it scores higher on the same folds and agrees on the known test set.

## FINAL eval calls: V1 + V2, three V2 seeds averaged (supersedes the two-seed table above)

`python cnn/classify.py --dir <eval folder> --v2 v2,v2s1,v2s2 --per-batch 2 --add-labelled 3e122cbj=Batch_2,fn0mhxef=Batch_1,xrv9xvzb=Batch_3`

Held-out score 0.68 [0.58, 0.82] (seed 0 alone 0.76, seeds 0+1 0.71: the estimate settles as seeds are added; V1 alone
0.64). Known test set with the one-per-batch rule: 3/3 at 79 % confidence (runner-up assignment 8 %).

| spot | call | P(B1, B2, B3) |
|---|---|---|
| 0eryguqq | **Batch_3** | 0.00 / 0.00 / 1.00 |
| 4hq27w4c | **Batch_1** | 0.99 / 0.00 / 0.00 |
| fhwrjtet | **Batch_3** | 0.00 / 0.10 / 0.90 |
| fspqbkxl | **Batch_2** | 0.00 / 0.99 / 0.01 |
| soo2ax3r | **Batch_1** | 0.71 / 0.27 / 0.02 |
| y59rxmxl | **Batch_1** | 0.71 / 0.26 / 0.03 |

If the eval set is exactly two per batch, one of soo2ax3r / y59rxmxl is Batch_2; the model splits that almost evenly
(0.27 vs 0.26) and the joint assignment picks soo2ax3r. That one slot is a coin flip.

## FINAL eval prediction: V1 + four V2 members averaged (supersedes the tables above)

Members: V2 seeds 0, 1, 2 and v2_noseg (the same recipe without the light material-map term). Held-out score
0.71 [0.58, 0.88] (three members 0.68; V1 alone 0.64). Known test set: 3/3 with the one-per-batch rule at 79 %.

| spot | final call | P(B1, B2, B3) |
|---|---|---|
| 0eryguqq | **Batch_3** | 0.00 / 0.00 / 1.00 |
| 4hq27w4c | **Batch_1** | 0.99 / 0.00 / 0.00 |
| fhwrjtet | **Batch_3** | 0.00 / 0.07 / 0.92 |
| fspqbkxl | **Batch_2** | 0.00 / 0.99 / 0.01 |
| soo2ax3r | **Batch_1** | 0.73 / 0.24 / 0.02 |
| y59rxmxl | **Batch_1**, or **Batch_2** if the set is exactly two per batch | 0.71 / 0.25 / 0.04 |

`python cnn/classify.py --dir <eval folder> --per-batch 2 --add-labelled 3e122cbj=Batch_2,fn0mhxef=Batch_1,xrv9xvzb=Batch_3`
(the default `--v2` is now these four members, all in `models/`).

## V1 V2 combined (one network, both losses summed): final check

| version | held-out score [90 %] | recall B1 / B2 / B3 | known test set (rule) |
|---|---|---|---|
| combined, from scratch, 12 epochs (`j_comb12`) | 0.63 [0.48, 0.76] | 0.43 / 0.57 / 0.88 | 2/3 (1/3): B2 / B2 / B3; V2 half stayed at chance (0.29 alone) |
| combined, started from trained V1 + V2, 12 epochs (`j_init`) | 0.66 [0.46, 0.83] | 0.86 / 0.29 / 0.82 | 1/3 (1/3): B1 / B2 / B3 |
| **V1 + four V2 members side by side (final)** | **0.71 [0.58, 0.88]** | 0.86 / 0.57 / 0.71 | 2/3 (3/3) |

Warm-starting fixed the dead V2 half (its batch loss starts well below chance) and lifted the combined model from
0.63 to 0.66, but it still trails the side-by-side ensemble and gets only 1 of the 3 known test spots. Its eval calls
match the final ones on five spots (y59rxmxl is Batch_1 at 0.47). Training the two together pulls their views
towards each other; keeping them separate and joining them at the classifier keeps what makes each useful.
