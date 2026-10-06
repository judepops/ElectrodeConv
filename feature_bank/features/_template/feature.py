"""Copy this folder to make a new feature (folders starting with _ are ignored).

    cp -r features/_template features/my_feature     # edit feature.py and config.yaml
    python features/run_features.py                  # your columns appear in processed/features.csv

Replace this docstring with: what the feature measures, which image it uses, the unit, why it matters.

sample gives you (see preprocessing/process_data.py):
    sample.bse, sample.se, sample.inlens   2D uint8 images, same shape, cleaned with a 1-99 % stretch (display only:
                                           the stretch depends on how much bright phase an image holds)
    sample.batch, sample.sample_id, sample.is_baseline
Measure on the shared harmonised spot instead (same crop, anchoring and noise level for every spot; cached):
    from features._common.harmonise import harmonised, PX_UM
    h = harmonised(sample)    # h.void, h.bright, h.solid masks; h.bse in graphite units; h.inlens rank-normalised
Graphite particles, cut along Inlens rims / BSE gaps:  from features._particles.particles import graphite_particles
"""
import math

import numpy as np
from skimage.measure import label

from features import feature, load_config
from preprocessing import MODELS_DIR, PIXEL_SIZE_UM

CFG = load_config(__file__)   # config.yaml in this folder


# 1. One number -> one column named after the function. Put the unit in the name (_frac, _um, _um2).
@feature
def mean_brightness_frac(sample):
    return float(sample.bse.mean() / 255)


# 2. Several numbers -> return a dict, one column per key: dark_spots_count_per_1000um2, dark_spots_median_diameter_um.
#    Use PIXEL_SIZE_UM for real units, normalise counts by area (image heights differ), return nan instead of crashing.
@feature
def dark_spots(sample):
    labels = label(sample.bse < CFG["dark_threshold"])
    areas_px = np.bincount(labels.ravel())[1:]
    areas_px = areas_px[areas_px >= CFG["min_spot_px"]]
    image_um2 = sample.bse.size * PIXEL_SIZE_UM ** 2
    if len(areas_px) == 0:
        return {"count_per_1000um2": 0.0, "median_diameter_um": math.nan}
    diameters_um = 2 * np.sqrt(areas_px * PIXEL_SIZE_UM ** 2 / np.pi)
    return {
        "count_per_1000um2": len(areas_px) / image_um2 * 1000,
        "median_diameter_um": float(np.median(diameters_um)),
    }


# 3. Optional: a feature that learns from the baseline first. `run_features.py --train` calls train()
#    with the baseline samples. Save small files only into models/ and commit them. Delete if not needed.
MODEL_FILE = MODELS_DIR / "my_feature.npz"


def train(baseline_samples):
    values = [s.bse.mean() for s in baseline_samples]
    np.savez(MODEL_FILE, mean=np.mean(values), std=max(np.std(values), 1e-6))


@feature
def brightness_vs_baseline_z(sample):
    if not MODEL_FILE.exists():
        raise FileNotFoundError(f"{MODEL_FILE} is missing: run  python features/run_features.py --train")
    model = np.load(MODEL_FILE)
    return float((sample.bse.mean() - model["mean"]) / model["std"])
