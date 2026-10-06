# Who built what

ElectrodeConv is a team project from the London AI x Science Hackathon, 3-4 October 2026. This repository is a
cleaned-up assembly of the team's two working repositories (`a-rune/losslarp`, then
`LucaVendruscolo/losslarpV2`), made after the event. The original commit history is not carried over, so this
file records authorship. It is drawn from the commit logs of both repositories.

## The team

| Person | Main contributions |
|---|---|
| **Luca Vendruscolo** | Pipeline architecture and repository lead. Session-fair preprocessing and its fairness check. Both networks: the label-free V1 (per-detector encoder, material-map decoder, cross-detector contrastive loss) and the batch-supervised V2 (early fusion, supervised contrastive loss), their training, the held-out scoring kit, bootstrap intervals, the V1 / V2 comparison and the seed ensemble. The classifier for new spots. The QC verdict and battery-property rules. Most of the team page and the animated judging deck. |
| **Adarsh Arun Ganeshbabu** | The feature ledger: every feature idea with its papers, verified DOIs and result. Hand-built microstructure features, depth profiles from the current-collector edge and the plug-in feature system. The analysis linking literature features to an embedding's batch axes. Pretrained-embedding experiments in the first repository. |
| **Fivos Papathanasiou** | The three-detector pore / graphite / silicon segmentation that replaced brightness thresholds as the mask source. The pitch layout of the team page. |
| **Yasith Medagama Disanayakage** | Deep literature research on electrode microstructure and battery performance that fed the feature ledger. |
| **Jude Popham** | See below. |

## Jude Popham

- **Data audit.** Found by edge matching that 18 of the 31 spots are neighbouring pieces of longer strips and
  that three strips cross batch folders; took it to Polaron, who confirmed how the batches were constructed.
  This set the team's unit of independence and its held-out-session tests. `experiments/data_audit/`
- **The frozen feature bank.** The contract, runner, twelve feature families, evaluation harness (nested folds,
  kernel models, baselines, two nulls), leakage tests and cloud runner. Its result, that no frozen feature family
  beats imaging descriptors alone, is why the team trained its own network. `feature_bank/`
- **The literature layer.** Tested the two sponsor literature tools, built the paper index (about 17,000 papers
  from 184 searches each), then the evidence step that puts one question per feature and battery outcome to
  full-text papers and keeps only answers whose quoted sentence is found in the paper; the batch outlook with its
  sensitivity table; the feature picture cards; and the page section that shows them. `literature/`,
  `ledger/papers/`
- **Leakage study.** The seed and patch-size experiment on the label-free model, which showed that single runs
  are unstable, that small training patches make the network recognise the imaging session, and that removing the
  material map does not help. `experiments/patch_size_and_seeds/`
- **Checks on the model.** The "does this spot look like any training batch" novelty score (`cnn/novelty.py`)
  and the embedding map (`cnn/pca_plot.py`).
- **Framing and pitch.** Liaison with Polaron on what the task was, and the presentation.
- **This repository.** The reorganisation, the restored V1 training scripts (`cnn/v1/`), the figures and this
  documentation.

## Shared

The team page (`dashboard/`) has commits from four people. The battery-property rules in `qc/impact_rules.yaml`
were written by Luca and Adarsh and checked against the literature evidence by Jude.

## Licence

No licence has been chosen yet. The code belongs to its authors above; ask before reusing it. The input images
are Polaron's and are not included.
