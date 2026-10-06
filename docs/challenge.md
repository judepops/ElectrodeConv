# The challenge: Track 4, materials manufacturing (Polaron)

London AI x Science Hackathon, London Deep Tech Week, 3-4 October 2026.

## The brief

> Can you detect when a supplier's material has changed before it becomes a manufacturing problem?

Battery manufacturers need incoming electrode material to be consistent from batch to batch, but small shifts in
formulation or processing can change the microstructure in ways that only show up as defects much later in
production. Using electron-microscope images, teams were asked to build a trustworthy, interpretable,
uncertainty-aware quality-control system that compares incoming batches with a baseline: detect whether a batch
has changed, say what drives the difference, and explain the call to a materials expert.

Judged on the quality of the extracted material measures, accuracy on held-back images, interpretability, honest
handling of uncertainty and usability for a real QC decision. In Polaron's words on the day: "no one in
manufacturing trusts a black box model".

## What Polaron clarified during the event

These points came from Polaron's co-founder Steve Kench and Polaron's engineers, in the event channel and in
answer to the team's questions. They shaped the design more than the written brief did.

| Question | Answer |
|---|---|
| Is there a baseline? | Yes. Batch_3 is the baseline, "what's been promised by the supplier". Batch_1 and Batch_2 arrived afterwards. Baseline does not mean defect-free, and the other two are not better or worse by construction |
| What is a batch here? | A constructed group. Polaron cut about 20 large images into crops and grouped the crops on high-dimensional features of its own. So neighbouring crops of one strip can sit in different batches. The team found this from the pixels and Polaron confirmed it |
| What is the material? | Bright particles are silicon, dark are graphite, with pores in between |
| What is the task, exactly? | Say what is different from the baseline and in what way. That is measured by assigning held-back images to a batch. Always assign, with a confidence and an explanation; a low-confidence bet is acceptable, no bet is not |
| What is the hard part? | Overfitting: "this is the crux". Most source images sit entirely in one batch, so a model can learn the image and not the material. Polaron would not say whether held-back images came from the same source images |
| How do Polaron do it? | Hand-built, human-readable features alongside model embeddings, and the work of understanding how the two relate |

## How the held-back images were released

1. Three test spots on the first evening, one from each batch. Teams sent their calls and received the answers
   the next morning.
2. Six evaluation spots shortly before the pitches, two from each batch, marked by the organisers.

## How ElectrodeConv answered each judging criterion

| Criterion | Where |
|---|---|
| Material measures | 45 feature ideas with papers and results (`ledger/`); 12 frozen feature families (`feature_bank/`); three-detector segmentation (`segmentation/`) |
| Accuracy on held-back images | 5 of 6 on the evaluation set; 0.71 balanced accuracy on held-out training spots (`cnn/results/`) |
| Interpretability | Each call broken into named features, tiles and neighbours (`cnn/explain.py`); features linked to battery outcomes with quoted, checked sentences (`literature/`) |
| Honest uncertainty | Intervals on every score; a session-leak test on every model; seed checks; a sensitivity table on the batch outlook; a list of what did not work |
| Usability | One command to call new images (`cnn/classify.py`), a novelty score for images unlike any batch (`cnn/novelty.py`), an accept / investigate / reject rule against the baseline (`qc/verdict.py`) |
