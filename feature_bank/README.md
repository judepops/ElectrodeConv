# feature_bank

The largest trustworthy set of frozen features that could be computed for the 31 crops in a night, with only a
small metric learned from the batch labels, and a harness that says honestly what those features know.

This is a self-contained sub-project from the team's first repository. Run everything from this folder.

**Result: nothing in the bank beats descriptors of the image acquisition alone.** That finding is why the team
went on to train a network on these images and to test every model for session leakage.

![Balanced accuracy of each feature family; imaging descriptors alone score highest](../docs/figures/fig_feature_bank.png)

## What is in it

| Folder | What it is |
|---|---|
| `bank/core.py` | The contract. A `Crop` is the same 1336 x 6944 px window of every spot at 25 nm, with graphite-anchored views and phase maps. A feature family sees only the Crop: never the spot id, a file name, the image size, the source image or a tile position |
| `bank/families/` | Twelve families, one file each (below) |
| `bank/run.py` | Runner: make crop versions, run a family, show status |
| `bank/harness.py` | Evaluation: nested folds with one source image held out, multiple-kernel models, baselines, two nulls, bootstrap intervals |
| `bank/labelfree.py` | Label-free structure of every feature space (clustering against batch and against source image), for diagnostics only |
| `bank/qa.py` | Status table and review markers |
| `tests/` | 50 test functions (89 cases pass; 35 skip until a family's outputs exist): the contract, the harness against plain rewrites and scikit-learn, and leakage (image width, provenance by value, forbidden name tokens) |
| `cloud/` | The same jobs on Modal, one container per crop, with a parity check against local results |
| `meta/` | Crop list and labels for scoring; source-image facts used only for nulls and diagnostics |
| `preprocessing/`, `features/`, `representation/` | The first repository's shared preprocessing, the team's named features and the perturbation code the bank builds on |

## The families

| Family | What it measures | Values per crop |
|---|---|---|
| `imgqc` | Imaging quality per detector: black level, noise, focus, drift, scan lines. Tagged *imaging*: the acquisition-only baseline | 277 |
| `phase` | Phase fractions, Minkowski curves, two-point correlation and chord lengths per axis | 104 |
| `psd` | Radial and angular log power spectra | 154 |
| `orient` | Structure-tensor coherence, direction histograms, nematic order | 72 |
| `glcm_lbp` | Co-occurrence statistics and uniform local binary patterns | 594 |
| `fbank` | Gabor bank, Laplacian-of-Gaussian blobs, Sato ridges | 282 |
| `xdet` | What the backscatter and in-lens images say about each other | 107 |
| `registry` | The team's named features, run on a Crop | 53 |
| `emb_dinov2l`, `emb_dinov3l` | Frozen DINOv2 ViT-L/14 and DINOv3 ViT-L/16 embeddings | 82,000 each |
| `emb_convnextb` | Frozen DINOv3 ConvNeXt-B stage statistics and Gram matrices | 187,696 |
| `emb_micronet` | Frozen MicroNet ResNet50 stage statistics | 177,712 |

`scat` (wavelet scattering) is written but was not run on all crops. Every value carries a tag: `material`,
`imaging`, `mixed`, or `leakrisk` (anything from the side-mounted detector, whose file name differs by batch).

## Safeguards

- **Perturbation and injection.** Each family is also run on six imaging changes of the same crop (black level,
  two gammas, contrast, noise, blur) and five injected material changes (pores grown by 2, 4 and 8 pixels; half
  or all bright particles removed). A material feature should ignore the first set and respond to the second.
- **Nothing is fitted in the bank.** Scalers, PCA, codebooks and kernel weights are fitted inside training folds.
- **Two nulls.** Batch labels permuted inside each source image, and shuffled across crops.
- **A provenance oracle.** How well the batch can be guessed from which source image a crop's neighbour came from.

## Run it

```bash
export LOSSLARP_DATA_DIR=$PWD/../data
pip install -r requirements.txt                               # cloud/requirements-gpu.txt for the embedding families

python -m bank.run views --sites smoke --perts P0             # the two smoke crops
python -m bank.run fam phase --sites all --perts P0 --workers 4
python -m bank.run status
python -m bank.harness --out processed/bank/harness --quick   # 100 permutations, 200 bootstrap resamples
python -m bank.labelfree
pytest tests -q
```

## Results

In `../results/feature_bank/`: the status table, three harness runs (`results.md`, `harness.json`, out-of-fold
predictions) and the label-free report. Headline, from `harness_v1_quick`, 31 crops, 13 source images, one held
out at a time:

| Model | Balanced accuracy [95 %] |
|---|---|
| Imaging descriptors only | 0.75 [0.56, 0.92] |
| Best frozen embeddings (DINOv2 / DINOv3 ViT-L) | 0.66 [0.46, 0.84] |
| All families except leak-risk, learned kernel weights | 0.61 [0.41, 0.78] |
| All material-side families | 0.54 [0.35, 0.72] |
| Chance | 0.33 |

`bank/README.md` is the working contract the family authors followed during the event, kept as written.
