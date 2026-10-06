"""local_porosity: how much of the electrode sits in dense, pore-starved patches (BSE, harmonised void mask).

Columns:
    local_porosity_q25_frac   25th percentile of the porosity of 5 um x 5 um tiles: the porosity of the densest
                              quarter of the cross-section (fraction)
    local_porosity_dense_window_frac  share of 2.5 um windows whose porosity is below 25 % of the spot's own porosity
                              (fraction of windows); relative, so a uniformly denser electrode does not count

Why it matters: lithium ions reach the active material through the electrolyte in the pores. Material inside a
pore-starved patch is served only through long solid or dead-end paths, so its local ionic resistance is higher; it
lithiates last and pushes the neighbouring surface towards lithium plating at fast charge. Uneven calendering or
mixing creates such patches without moving the mean porosity much, which is why the tail is reported, not the mean.

2D caveat: a window that looks pore-free in one section can be served by pores just above or below the plane, so
these are relative indices of compaction uniformity, not 3D transport numbers. Tuning numbers in config.yaml.
"""
import math

import numpy as np

from features import feature, load_config
from features._common.harmonise import harmonised

CFG = load_config(__file__)


def window_fractions(mask, size, stride):
    """Phase fraction in every size x size window on a stride grid (integral image)."""
    c = np.pad(mask.astype(np.float64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    ys = np.arange(0, mask.shape[0] - size + 1, stride)
    xs = np.arange(0, mask.shape[1] - size + 1, stride)
    if len(ys) == 0 or len(xs) == 0:
        return np.array([])
    Y, X = np.meshgrid(ys, xs, indexing="ij")
    s = c[Y + size, X + size] - c[Y, X + size] - c[Y + size, X] + c[Y, X]
    return (s / (size * size)).ravel()


@feature
def local_porosity(sample):
    void = harmonised(sample).void
    phi = float(void.mean())
    tiles = window_fractions(void, CFG["tile_px"], CFG["tile_px"])
    windows = window_fractions(void, CFG["window_px"], CFG["window_stride_px"])
    if len(tiles) < 20 or len(windows) < 20 or phi <= 0:
        return {"q25_frac": math.nan, "dense_window_frac": math.nan}
    return {"q25_frac": float(np.quantile(tiles, CFG["quantile"])),
            "dense_window_frac": float((windows < CFG["dense_rel"] * phi).mean())}
