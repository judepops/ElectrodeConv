# models: the best classifier (final)

**V1 + V2, four V2 members averaged (seeds 0, 1, 2 and v2_noseg).** Balanced accuracy 0.71 [0.58, 0.88] on spots the models never saw (chance 0.33;
V1 alone 0.64). On the earlier 3-spot test set (labels now known) it gets 3/3 with the one-spot-per-batch rule at
79 % confidence, 2/3 without the rule.

```bash
python cnn/classify.py --dir /path/to/images                       # per spot: P(Batch_1, Batch_2, Batch_3), call, stability
python cnn/classify.py --dir /path/to/images --per-batch 2         # if the set holds exactly 2 spots of each batch
python cnn/classify.py --dir /path/to/images --add-labelled 3e122cbj=Batch_2,fn0mhxef=Batch_1,xrv9xvzb=Batch_3   # 34 training spots
```

## How it works

1. **Fair preprocessing** (`preprocessing/preprocess.py`): every image cropped to the same window, BSE anchored to its
   own black and graphite levels, noise topped up to one level, Inlens and SE rank-normalised. Image height, black
   level and noise never reach a model. Then 26 tiles of 512 x 512 px per spot.
2. **Two encoders, trained separately, describe each spot** (mean over its tiles):
   - `v1/` **V1, label-free** (`cnn/v1net.py`): one encoder per detector image; trained to paint pores / graphite /
     Si and to match the BSE, Inlens and SE views of the same tile. It never saw a batch label, so it describes the
     material in general and does not group spots by microscope session.
   - `v2/`, `v2s1/`, `v2s2/` **V2, batch-supervised** (`cnn/supcon.py`, seeds 0, 1, 2): the three detector images as
     one 3-channel input; trained to pull tiles of the same batch together (other spots only) and push other
     batches apart, plus a batch classifier head. It sees what separates the batches, but alone it overfits (0.54).
3. **One small classifier on both descriptions** (logistic regression, each description standardised and weighted
   equally), fitted on the 31 labelled spots, once per V2 seed; the three probability sets are averaged.

Why both: the two views are complementary. V1 is reliable and interpretable (its batch direction runs along named
material features, 22x a random direction) but weak at Batch_1 vs Batch_2; V2 adds that. Side by side they beat
either alone on every seed (0.76 / 0.66 / 0.68 with V1, against 0.64 for V1 and 0.45-0.54 for V2).

## What did not work (so nobody repeats it)

Training the two together as one network with summed losses (V2's batch losses stayed at chance), fine-tuning V1's
encoder with labels, a session-adversarial head, rotations / vertical flips (the electrode has a direction),
up-weighting Batch_1 vs Batch_2 pairs, removing the material map, a contrastive loss without a classifier head, and
the sharper loss (centring, temperature 0.05, margin) on a from-scratch V2. Details and numbers: `cnn/results/README.md`.

## Files

| folder | contents |
|---|---|
| `v1/` | `best.pt`, `embeddings.npz` (806 tiles, 31 spots), `test_embeddings.npz` (the 3 earlier test spots), `config.json` |
| `v2/`, `v2s1/`, `v2s2/`, `v2_noseg/` | `last.pt` (trained on all 31 spots), `embeddings.npz` (training spots + the 3 earlier test spots), `config.json` |

The `.pt` checkpoints are not in git (`.gitignore`): they were trained on Polaron's images. The embeddings and
configs are, so every score, the embedding map and the explanations reproduce without them. Calling new images
(`cnn/classify.py`) needs the checkpoints: retrain with `cnn/v1/train.py` and `cnn/supcon.py`.
