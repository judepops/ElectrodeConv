"""seg3 phase labels for one raw spot, for preprocessing/preprocess.py (MASK_SOURCE = "seg3").

    from segmentation.masks import seg3_labels
    lab = seg3_labels(raw)        # uint8, full raw size: 0 pore, 1 graphite/carbon, 2 Si-like, 255 not electrode

Lookup order, first hit wins (a stored map is used only if its shape equals the raw image's):
    1. segmentation/labels/<batch>_<id>_labels.png       the 31 training spots, committed (made by segment_phases.py)
    2. segmentation/processed/labels/<batch>_<id>_labels.png   maps computed on this machine (git-ignored)
    3. compute with segment_phases.segment_image (~2.5 min on 4 CPU threads, ~1.5 GB) and store it in 2.
Test spots arrive with batch "Test" (qc/features_table.py), so they are computed once and cached as Test_<id>.
Precompute them in parallel with: python segmentation/run_seg3.py --test
"""
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
COMMITTED = HERE / "labels"
CACHE = HERE / "processed" / "labels"


def label_path(batch, sample_id):
    for d in (COMMITTED, CACHE):
        p = d / f"{batch}_{sample_id}_labels.png"
        if p.exists():
            return p
    return None


def compute_labels(bse, inlens, se):
    from segmentation.segment_phases import segment_image
    lab, _conf, _params = segment_image(np.ascontiguousarray(bse), np.ascontiguousarray(inlens), np.ascontiguousarray(se))
    return lab


def seg3_labels(raw, verbose=True):
    """Full-size seg3 label map of a preprocessing.preprocess.RawSpot (uint8 detector arrays)."""
    p = label_path(raw.batch, raw.sample_id)
    if p is not None:
        lab = np.asarray(Image.open(p))
        if lab.shape == raw.bse.shape:
            return lab
        if verbose:
            print(f"seg3: stored map {p.name} has shape {lab.shape}, image {raw.bse.shape}: recomputing", flush=True)
    if verbose:
        print(f"seg3: segmenting {raw.batch}/{raw.sample_id} (~2.5 min) ...", flush=True)
    lab = compute_labels(raw.bse, raw.inlens, raw.se)
    CACHE.mkdir(parents=True, exist_ok=True)
    Image.fromarray(lab).save(CACHE / f"{raw.batch}_{raw.sample_id}_labels.png", optimize=True)
    return lab
