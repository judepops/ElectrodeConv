# results

Every number in the main README, and the file it comes from. Scores are balanced accuracy (the mean of the three
per-batch hit rates; chance 0.33) on spots a model never saw, with intervals from resampling the 13 source images.
With 31 labelled spots one Batch_1 or Batch_2 spot is worth 0.05.

## Headline

| Model | Balanced accuracy | Source |
|---|---|---|
| **Final: label-free + four supervised runs, joined at the decision** | **0.71** [0.58, 0.88] (90 %) | `models/README.md`, `cnn/compare.py` |
| Label-free + one supervised run | 0.76 / 0.66 / 0.68 over three seeds | `cnn/results/compare.md`, `v2s1_score.json` |
| Label-free alone (V1) | 0.64 [0.48, 0.81] | `cnn/results/compare.md` |
| Supervised alone (V2) | 0.54 [0.37, 0.69] | `cnn/results/v2_score.json` |
| Imaging cues alone (four numbers) | 0.66 | `cnn/results/baselines.json` |
| Hand-built material features | 0.45 | `cnn/results/baselines.json` |
| Half a million frozen features | 0.61 [0.41, 0.78] (95 %) | `feature_bank/harness_v1_quick/results.md` |
| Imaging descriptors alone, feature-bank harness | 0.75 [0.56, 0.92] (95 %) | `feature_bank/harness_v1_quick/results.md` |

Held-back images: 5 of 6 on the judged evaluation set (`cnn/results/classify_Hackathon-Polaron-eval*.json`);
on the earlier three-spot set 3 of 3 with the one-per-batch rule and 2 of 3 without
(`cnn/results/test_calls.json`).

## Where everything is

| Folder | What it holds |
|---|---|
| `cnn/results/` | Every network variant tried, its score and what it means (`README.md` there is the full account); the comparison on shared folds; held-back calls; what each embedding knows about named features |
| `models/` | Embeddings and configs of the five encoders in the final model |
| `results/feature_bank/` | Status of the 12 feature families, three harness runs with out-of-fold predictions, and the label-free structure report |
| `experiments/patch_size_and_seeds/` | Eight laptop training runs: seed spread and session leak against patch size |
| `experiments/data_audit/` | The strip and session map and the edge-match evidence |
| `literature/` | `EVIDENCE.md` (114 questions, 268 checked answers from 159 papers) and `BATCH_OUTLOOK.md` (measured shifts against paper directions, with the sensitivity table) |
| `ledger/` | The 45 feature ideas, each with papers and its result |
| `docs/figures/` | The charts (`docs/make_figures.py`) and frames of the deck (`docs/capture_deck.py`) |

## The three feature-bank harness runs

| Folder | What it is |
|---|---|
| `harness_v1_quick/` | The run quoted everywhere: all 12 families, 100 permutations, 200 bootstrap resamples |
| `harness_quick/` | The harness on the first evening, before the families had run: only the first repository's older features (acquisition numbers, DINOv2-S) |
| `harness_full_legacy/` | The same early state with full settings: 1000 permutations, 2000 bootstrap resamples |
