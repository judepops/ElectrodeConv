"""The whole pipeline in one command: tiles -> tile features -> FusionNet (13 folds + full) -> nested score -> test calls -> probe.

    python pipeline.py --name v2 --quick          # laptop check: 6 spots, 2 short epochs, the full model only, 20 permutations
    python pipeline.py --name v2 --gpu 0          # on the GPU box: 13 held-out-session folds + the full model, 3 at a time

Steps that already have their output are skipped (preprocessing, tile features); --force redoes them.
Results: cnn/processed/supcon/<name>/{score.json, fold00..12/, full/{embeddings.npz, predictions.json, probe.md}}.
The honest number is score.json (every spot called by an encoder that never saw its session); predictions.json
and probe.md describe the full model, whose encoder saw every label.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from preprocessing.preprocess import PROCESSED_NAME  # noqa: E402  (LOSSLARP_MASKS: seg3 | harmonise)
PY = sys.executable
TILES_CSV = ROOT / "preprocessing" / PROCESSED_NAME / "tiles.csv"
TILE_FEATURES = ROOT / "cnn" / PROCESSED_NAME / "tile_features.csv"


def run(step, cmd):
    print(f"\n### {step}: {' '.join(cmd)}", flush=True)
    t0 = time.time()
    subprocess.run(cmd, cwd=ROOT, check=True)
    print(f"### {step} done in {(time.time() - t0) / 60:.1f} min", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="v2")
    ap.add_argument("--arch", default="k7")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--crop", type=int, default=320)
    ap.add_argument("--w-seg", type=float, default=0.2)
    ap.add_argument("--gpu", default="0")
    ap.add_argument("--n-perm", type=int, default=200)
    ap.add_argument("--quick", action="store_true", help="6 spots, 2 epochs at crop 128, full model only, 20 permutations")
    ap.add_argument("--force", action="store_true", help="redo preprocessing and tile features")
    a = ap.parse_args()
    t0 = time.time()

    if a.force or not TILES_CSV.exists():
        run("preprocess", [PY, "preprocessing/preprocess.py"])
    else:
        print(f"preprocess: {TILES_CSV} exists, skipping")
    if a.force or not TILE_FEATURES.exists():
        run("tile features", [PY, "cnn/tile_features.py"])
    else:
        print(f"tile features: {TILE_FEATURES} exists, skipping")

    common = ["--name", a.name, "--arch", a.arch, "--w-seg", str(a.w_seg)]
    full = f"supcon/{a.name}/full"
    if a.quick:
        run("train (smoke, full model)", [PY, "cnn/supcon.py", "train", *common, "--fold", "-1", "--smoke", "--epochs", "2", "--crop", "128"])
        run("probe", [PY, "cnn/probe_features.py", "--name", full, "--n-perm", str(min(a.n_perm, 20))])
    else:
        run("train (13 folds + full)", [PY, "cnn/supcon.py", "run", *common, "--epochs", str(a.epochs), "--crop", str(a.crop), "--gpu", a.gpu])
        run("score (nested)", [PY, "cnn/supcon.py", "score", "--name", a.name])
        run("predict", [PY, "cnn/predict.py", "--run", full, "--n-perm", str(a.n_perm)])
        run("probe", [PY, "cnn/probe_features.py", "--name", full, "--n-perm", str(a.n_perm)])
    out = ROOT / "cnn" / PROCESSED_NAME / "supcon" / a.name
    print(f"\nALL DONE in {(time.time() - t0) / 60:.1f} min. Honest number: {out / 'score.json'}; full model: {out / 'full'}")


if __name__ == "__main__":
    main()
