"""particle_size: size of the solid particles, as equivalent-circle diameters in um.

Columns: particle_size_d10_um, particle_size_d50_um, particle_size_d90_um.
Uses pore_mask from porosity (everything not pore is solid). Tuning in config.yaml.

Why it matters: d10 / d50 / d90 are what a powder supplier quotes. A shift means a different
powder lot or milling step.

Method: particles touch, so a threshold alone gives one blob. Distance transform -> local
maxima as particle centres -> watershed out to the pore edges -> area -> diameter.
Known limit: a big flat flake with no pores inside gets cut into ~1 um pieces, so d50 is a
lower bound. Same bias for every batch, so batch differences are still meaningful.
"""
import math

import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.segmentation import watershed

from features import feature, load_config
from features._retired.porosity.feature import pore_mask
from preprocessing import PIXEL_SIZE_UM

CFG = load_config(__file__)
EMPTY = {"d10_um": math.nan, "d50_um": math.nan, "d90_um": math.nan}


def particle_labels(sample):
    """Label image (every scale-th pixel): 0 = pore, 1..N = one number per particle."""
    s = CFG["scale"]
    solid = ~pore_mask(sample)[::s, ::s]
    distance = ndi.distance_transform_edt(solid)
    centres = peak_local_max(distance, min_distance=CFG["min_distance_px"],
                             threshold_abs=CFG["min_centre_depth_px"], exclude_border=False)
    markers = np.zeros(distance.shape, dtype=np.int32)
    markers[tuple(centres.T)] = np.arange(1, len(centres) + 1)
    return watershed(-distance, markers, mask=solid)


@feature
def particle_size(sample):
    labels = particle_labels(sample)
    areas_px = np.bincount(labels.ravel())[1:]
    areas_px = areas_px[areas_px >= CFG["min_particle_px"]]
    if len(areas_px) == 0:
        return dict(EMPTY)
    areas_um2 = areas_px * (PIXEL_SIZE_UM * CFG["scale"]) ** 2
    diameters_um = 2 * np.sqrt(areas_um2 / np.pi)
    d10, d50, d90 = np.percentile(diameters_um, [10, 50, 90])
    return {"d10_um": float(d10), "d50_um": float(d50), "d90_um": float(d90)}
