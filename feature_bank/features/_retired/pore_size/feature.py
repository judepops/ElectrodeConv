"""pore_size: how big the pores are and how many there are.

Columns: pore_size_median_um2, pore_size_p90_um2, pore_size_count_per_1000um2.
Uses pore_mask from porosity. Tuning in config.yaml.

Why it matters: same porosity can come from many small pores (good mixing) or a few big ones
(cracks, poor dispersion). Count is per area, not per image, because image heights differ.
"""
import math

import numpy as np
from skimage.measure import label

from features import feature, load_config
from features._retired.porosity.feature import pore_mask
from preprocessing import PIXEL_SIZE_UM

CFG = load_config(__file__)


@feature
def pore_size(sample):
    mask = pore_mask(sample)
    labels = label(mask)                            # 0 = solid, 1..N = one number per pore
    areas_px = np.bincount(labels.ravel())[1:]
    areas_px = areas_px[areas_px >= CFG["min_pore_px"]]
    image_um2 = mask.size * PIXEL_SIZE_UM ** 2
    if len(areas_px) == 0:
        return {"median_um2": math.nan, "p90_um2": math.nan, "count_per_1000um2": 0.0}
    areas_um2 = areas_px * PIXEL_SIZE_UM ** 2
    return {
        "median_um2": float(np.median(areas_um2)),
        "p90_um2": float(np.percentile(areas_um2, 90)),
        "count_per_1000um2": len(areas_um2) / image_um2 * 1000,
    }
