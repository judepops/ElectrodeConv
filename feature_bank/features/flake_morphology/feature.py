"""flake_morphology: size and shape of graphite fragments, bright (Si-like) phase excluded. BSE (harmonised).

Ledger: ledger/entries/flake_morphology.yaml (research report rank 14). Columns:
    flake_d50_um              median equivalent-circle diameter of graphite fragments
    flake_d50_aw_um           area-weighted median diameter (what a powder supplier's D50 is closer to)
    flake_thick_d50_um        median minor-axis length (2D flake thickness proxy)
    flake_aspect_median       median major / minor axis
    flake_n_per_1000um2       fragments per 1000 um2

Why this exists: particle_size_d50_um was the one old feature with a within-session batch signal. Decomposing it
(recomputed on the harmonised mask, without crack/speckle pores, without the bright phase, cut on Inlens ridges)
showed that Batch_1's larger d50 comes from the bright phase merging into fragments: with the bright phase
removed the Batch_1 excess disappears (3.27 / 3.42 / 3.26 um). And Inlens ridges are session-dominated (session
R2 0.95), so they can't be used as flake boundaries. This feature therefore measures graphite alone, on BSE only.

Method: graphite = harmonised solid minus bright phase; pores smaller than `min_pore_um2` (cracks, speckle) are
filled first so they don't chop flakes; distance-transform watershed with centres >= 1 um apart (as
particle_size); per-fragment regionprops. A 2D section of a flake, so sizes are relative (Wicksell), not a CoA D50.
"""
import math

import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.measure import regionprops_table
from skimage.segmentation import watershed

from features import feature, load_config
from features._common.harmonise import PX_UM, harmonised

CFG = load_config(__file__)
EMPTY = {k: math.nan for k in ("d50_um", "d50_aw_um", "thick_d50_um", "aspect_median")} | {"n_per_1000um2": 0.0}


def graphite_mask(sample):
    h, s = harmonised(sample), CFG["scale"]
    void = h.void[::s, ::s]
    labels, _ = ndi.label(void)
    sizes = np.bincount(labels.ravel())
    small = sizes < CFG["min_pore_um2"] / (PX_UM * s) ** 2
    small[0] = False
    void = void & ~small[labels]                       # fill crack / speckle pores
    return ~void & ~h.bright[::s, ::s]


def weighted_median(values, weights):
    order = np.argsort(values)
    cum = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cum, cum[-1] / 2)])


@feature
def flake(sample):
    s = CFG["scale"]
    solid = graphite_mask(sample)
    dist = ndi.distance_transform_edt(solid)
    centres = peak_local_max(dist, min_distance=CFG["min_distance_px"], threshold_abs=CFG["min_centre_depth_px"],
                             exclude_border=False)
    markers = np.zeros(dist.shape, np.int32)
    markers[tuple(centres.T)] = np.arange(1, len(centres) + 1)
    props = regionprops_table(watershed(-dist, markers, mask=solid),
                              properties=("area", "axis_major_length", "axis_minor_length"))
    keep = props["area"] >= CFG["min_particle_px"]
    if not keep.any():
        return dict(EMPTY)
    area = props["area"][keep] * (PX_UM * s) ** 2
    major, minor = props["axis_major_length"][keep] * PX_UM * s, props["axis_minor_length"][keep] * PX_UM * s
    diameter = 2 * np.sqrt(area / np.pi)
    return {"d50_um": float(np.median(diameter)), "d50_aw_um": weighted_median(diameter, area),
            "thick_d50_um": float(np.median(minor)), "aspect_median": float(np.median(major / np.maximum(minor, 1e-9))),
            "n_per_1000um2": keep.sum() / (solid.size * (PX_UM * s) ** 2) * 1000}
