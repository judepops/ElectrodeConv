"""local_porosity: how much of the electrode sits in dense, pore-starved patches (BSE void mask, standard window).

Ledger: local_porosity (Luca, first repo features/local_porosity; ported unchanged, constants as there).
    local_porosity_q25_frac           25th percentile of the porosity of 5 x 5 um tiles: the densest quarter (fraction)
    local_porosity_dense_window_frac  share of 2.5 um windows (half-overlapping) whose porosity is below 25 % of the
                                      spot's own porosity (fraction of windows); relative, so a uniformly denser
                                      electrode does not count
Why: ions reach the active material through the electrolyte in the pores. Material in a pore-starved patch is served
only through long solid or dead-end paths, lithiates last and pushes its neighbours towards plating at fast charge.
Uneven calendering or mixing makes such patches without moving the mean porosity much, so the tail is reported.
2D caveat: a window that looks pore-free can be served by pores above or below the plane: relative indices only.
"""
import math

import numpy as np

COLUMNS = ["local_porosity_q25_frac", "local_porosity_dense_window_frac"]
LABELS = {"local_porosity_q25_frac": "porosity of the densest quarter (5 µm tiles)",
          "local_porosity_dense_window_frac": "share of pore-starved 2.5 µm windows"}
TILE_PX, QUANTILE, WINDOW_PX, STRIDE_PX, DENSE_REL = 200, 0.25, 100, 50, 0.25


def window_fractions(mask, size, stride):
    """Phase fraction in every size x size window on a stride grid (integral image)."""
    c = np.pad(mask.astype(np.float64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    ys, xs = np.arange(0, mask.shape[0] - size + 1, stride), np.arange(0, mask.shape[1] - size + 1, stride)
    if len(ys) == 0 or len(xs) == 0:
        return np.array([])
    Y, X = np.meshgrid(ys, xs, indexing="ij")
    return ((c[Y + size, X + size] - c[Y, X + size] - c[Y + size, X] + c[Y, X]) / (size * size)).ravel()


def measure(spot, raw):
    void = spot.void
    phi = float(void.mean())
    tiles, windows = window_fractions(void, TILE_PX, TILE_PX), window_fractions(void, WINDOW_PX, STRIDE_PX)
    if len(tiles) < 20 or len(windows) < 20 or phi <= 0:
        return {c: math.nan for c in COLUMNS}
    return {"local_porosity_q25_frac": float(np.quantile(tiles, QUANTILE)),
            "local_porosity_dense_window_frac": float((windows < DENSE_REL * phi).mean())}
