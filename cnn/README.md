# cnn

A small encoder trained on the fair tiles of `preprocessing/` to tell the three batches apart, and the tools that
say how well it does, which batch each test spot is, and why.

## The model (`supcon.py`, `model.py`, `data.py`)

**FusionNet** takes the three detector images of a tile (BSE, Inlens, SE) as one 3-channel image ("early fusion")
through a from-scratch encoder (`model.ARCHS`, default `k7`: 7x7 kernels, 5 stages). The embedding is the pooled
bottleneck, spatial mean + SD of the projected feature map: 512 numbers for `k7`, averaged per spot.

The loss is **supervised contrastive on the batch label** (Khosla et al. 2020): tiles of the same batch are pulled
together, tiles of other batches pushed apart. Positives are tiles of the same batch from a *different* spot, so the
network cannot get away with learning spot identity. Every mini-batch holds several spots of every batch so positives
exist. A plain cross-entropy head on the batch label (`--w-ce`) is added because the contrastive term alone sat at
chance for the first epochs of every fold. A light material-map term (`--w-seg 0.2`, a U-Net decoder painting pore /
graphite / Si from the preprocessing masks) keeps the encoder on the structure; `--w-seg 0` drops the decoder.

Why supervised: the earlier label-free encoder (below) could be scored once on its embedding, but it carried little
batch signal beyond what the imaging cues already give. Using the labels buys signal and costs honesty, which the
nested score pays back.

## Scoring honestly: nested leave-one-session-out

The encoder sees the batch labels, so any number computed from one encoder on its own training spots is in-sample,
however the downstream classifier is cross-validated. The fair protocol trains the encoder **13 times, each with one
whole imaging session hidden**, fits a logistic regression on that fold's training-spot embeddings, and calls only the
hidden session's spots. `supcon.py score` assembles those 31 out-of-fold calls into `score.json`: balanced accuracy
(chance 0.33), a 90 % session-bootstrap interval, per-class recall, the confusion matrix, Batch_3 vs the rest, and
the test calls from the full model. There is no permutation p (it would need 13 x 200 retrainings). **`score.json` is
the only fair headline.** `predict.py`, `probe_features.py`, `explain.py` and `attribute.py` run on the full model
(all 31 spots) and describe it; their out-of-fold numbers are optimistic and `predictions.json` says so
(`encoder_saw_labels`, `honest_score`).

Run folders: `processed/supcon/<name>/fold00..fold12/` (one held-out session each) and `processed/supcon/<name>/full/`
(all 31 spots, plus the test-tile embeddings). Each holds `last.pt`, `config.json`, `train_log.csv`, `embeddings.npz`.

## Commands

```bash
python cnn/supcon.py train --name v2 --fold 0           # one fold (session 0 of 13 held out)
python cnn/supcon.py train --name v2 --fold -1          # the full model on all 31 spots
python cnn/supcon.py train --name v2 --fold -1 --smoke --epochs 1 --crop 128 --device cpu   # laptop check, 6 spots
python cnn/supcon.py run --name v2 --gpu 0              # all 13 folds + full, 3 at a time on one GPU
python cnn/supcon.py score --name v2                    # -> processed/supcon/v2/score.json (the honest number)
python cnn/predict.py --run supcon/v2/full              # test-spot calls, leak check -> predictions.json, test_embeddings.npz
python cnn/novelty.py --run supcon/v2/full              # does each test spot look like ANY training batch?
python cnn/explain.py --run supcon/v2/full --subset     # why: named features, tile heat grid, neighbours, ablations
python cnn/attribute.py --run supcon/v2/full            # where in the image the score comes from (exact per-cell attribution)
python cnn/tile_features.py                             # 13 material numbers per tile from the masks -> processed/tile_features.csv
python cnn/probe_features.py --name supcon/v2/full      # does the embedding carry the known features, and anything beyond?
python cnn/baselines.py                                 # the simple things scored the same way -> dashboard/data/baselines.json
```

Or `python pipeline.py --name v2 --gpu 0` from the repo root (`--quick` for a laptop smoke).

Progress: one line per epoch on stdout and `processed/supcon/<name>/<fold>/progress.txt`; `run` keeps
`processed/supcon/<name>/progress.txt` up to date. Memory: the fused encoder passes each tile once (the old one
passed it three times); 30 epochs at crop 320 fit easily on an A100, and `--device cpu` works for smokes.

## What the tools say

`predict.py` embeds the three test spots with the same checkpoint and code path as the training tiles (checked
against the stored embeddings), calls them with a logistic regression fitted on all 31 spots, and reports chance,
the evalkit scorecard and a session-leak check (does the embedding group spots by imaging session?). Image height
is never an input.

`novelty.py` adds a "none of these batches" check: a spot's distance to its 3 nearest training spots, against the
distribution of training spots scored with their own session left out. Above the 95th percentile = "unlike training".

`explain.py`, for each spot along the batch direction of that classifier: the share of the call that the 13 named
tile features explain and each feature's signed push; a heat grid of the tiles with the strongest tiles and the
network's own material map (the preprocessing masks when the run has no decoder); the nearest training spots; and,
for the subset, material ablations (Si blanked, pores blanked, control) and imaging perturbations (BSE offset, gain,
noise) re-embedded.

`attribute.py` splits every tile's score exactly over the bottleneck grid (16 px cells for `k7`), draws it over the
BSE image, and reports where the positive attribution lands (pore / graphite / Si) against the area share.

`probe_features.py` asks, at tile level with folds by spot or session, whether the embedding carries the 13 tile
features (out-of-fold R2), and whether the part the features do not explain ("complement") still separates the
batches. For a supervised encoder both are in-sample descriptions, not scores.

Everything is scored with `evalkit.py`, copied unchanged from the old repo so numbers stay comparable;
`uncertainty.py` gives the session-bootstrap intervals and Wilson recall intervals.

## History: the label-free MaterialNet

The first model (V1) ran a shared 1-channel encoder over each detector separately and trained without batch labels:
a material-map decoder plus a cross-detector NT-Xent loss (BSE, Inlens and SE of one tile pulled together). Its
embedding, scored once with leave-one-session-out logistic regression, reached balanced accuracy **0.58 (permutation
p 0.01), mixed sessions 0.69**, against an imaging-cues-only bar of 0.66 on losess; a sweep of eight encoder setups
and a ladder of one-change versions (full-window training, flips and rotations, no decoder, seg3 masks) did not move
it clearly. The team removed that trainer during the event; it is restored from the history in `cnn/v1/`
(`python cnn/v1/train.py`, then `python cnn/v1/embed.py`) so the label-free model and the seed and patch-size study
in `experiments/patch_size_and_seeds/` can be rerun. The shipped V1 encoder is read by `cnn/v1net.py`.
