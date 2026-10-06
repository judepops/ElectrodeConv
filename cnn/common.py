"""Shared bits for cnn: paths, device, seeding, the material-map placeholder, run folders."""
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from preprocessing.preprocess import PROCESSED_DIR as TILES_DIR, PROCESSED_NAME, load_tile  # noqa: E402

TILES_CSV = TILES_DIR / "tiles.csv"
RUNS_DIR = HERE / PROCESSED_NAME                 # git-ignored; processed_seg3/ when LOSSLARP_MASKS=seg3 (the default)
DETECTORS = ("bse", "inlens", "se")
N_CLASSES = 3                                    # 0 pore, 1 graphite, 2 Si-like
CLASS_NAMES = ("pore", "graphite", "si")


def pick_device(prefer: str = "auto"):
    import torch
    if prefer != "auto":
        return torch.device(prefer)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def seed_all(seed: int = 0):
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def material_map_from_masks(void, bright) -> np.ndarray:
    """Per-pixel material class (int64): 1 graphite, 0 where `void`, 2 where `bright` (Si-like)."""
    m = np.ones(void.shape, np.int64)
    m[void] = 0
    m[bright] = 2
    return m


def material_map(tile) -> np.ndarray:
    """Per-pixel material class (int64, 512 x 512) from the tile's masks (BSE thresholds, or seg3 when
    LOSSLARP_MASKS=seg3: see preprocessing/preprocess.py)."""
    return material_map_from_masks(tile.void, tile.bright)


def run_dir(name: str) -> Path:
    d = RUNS_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1, default=float))


def load_json(path):
    return json.loads(Path(path).read_text())
