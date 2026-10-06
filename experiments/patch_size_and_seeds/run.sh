#!/bin/bash
# Seeds and patch size: does the label-free model's score hold across random starts, and does it read the material
# or the imaging session? Eight runs of cnn/v1/train.py on an Apple M4 Pro laptop (about 3.5 hours in all).
#
#   bash experiments/patch_size_and_seeds/run.sh
#
# Needs the tiles of preprocessing/preprocess.py (LOSSLARP_MASKS=harmonise). Every run is 24-30 epochs, k7 encoder,
# contrastive weight 0.2. After each run all finished runs are re-scored, so partial results are usable.
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=${PYTHON:-python}
export LOSSLARP_MASKS=harmonise
LOG=cnn/processed/exp_patch_size.log
mkdir -p cnn/processed

run() {  # name  w_seg  seed  crop  batch  epochs
  echo "=== $(date '+%H:%M') start $1 (w_seg $2, seed $3, crop $4, batch $5)" >> "$LOG"
  $PY cnn/v1/train.py --name "$1" --arch k7 --w-seg "$2" --w-con 0.2 --seed "$3" --crop "$4" --batch "$5" --epochs "$6" >> "$LOG" 2>&1 \
    || { echo "!!! $1 training failed" >> "$LOG"; return; }
  $PY cnn/v1/embed.py --name "$1" --maps 2 >> "$LOG" 2>&1 || { echo "!!! $1 embedding failed" >> "$LOG"; return; }
  $PY experiments/patch_size_and_seeds/score_with_leak.py "exp_*" > cnn/processed/exp_scores_with_leak.txt 2>> "$LOG"
  echo "=== $(date '+%H:%M') done $1" >> "$LOG"
}

# 1. three seeds of each recipe at the laptop default (128 px patches, batch 16)
for seed in 0 1 2; do
  run exp_default_s$seed 1 $seed 128 16 30     # material map + cross-detector matching (the team's V1 recipe)
  run exp_conly_s$seed   0 $seed 128 16 30     # matching only: no threshold-made material map
done

# 2. one of each at 256 px patches (batch 8: the largest that fits 24 GB of unified memory).
#    The material-map run needs more GPU memory than the script's laptop cap allows; raise it for that run only.
run exp_big_conly_s0 0 0 256 8 24
PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.45 PYTORCH_MPS_LOW_WATERMARK_RATIO=0.35 run exp_big_default_s0 1 0 256 8 24
echo "=== $(date '+%H:%M') ALL DONE" >> "$LOG"
