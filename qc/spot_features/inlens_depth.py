"""inlens_depth: does the dark Inlens phase inside the solid change with distance from the bottom (current-collector) edge?

Ledger: binder_depth_profile (Inlens columns added to the BSE depth profile of qc/depth_profile.py).
    inlens_depth_dark_b0_frac          share of the solid in the bottom 11.2 um band that is Inlens-dark (fraction;
                                       0.25 = the spot's own average by construction)
    inlens_depth_dark_slope_per_10um   least-squares change of that share per 10 um TOWARDS the bottom (> 0: more
                                       Inlens-dark solid near the current collector)
    inlens_depth_pore_slope_per_10um   shading control: the same slope for pore pixels (same threshold). Inlens
                                       images carry a top-to-bottom brightness drift (4ih2ggld raw 116 -> 62 grey,
                                       pores darken with the solid), which a dark share by depth cannot tell from
                                       material; a solid slope that only tracks this one is shading.
Image: Inlens (rank-normalised, noise-matched) inside the BSE solid (not void, not bright phase), FULL image height
(rows CROP_TOP .. H - CROP_BOTTOM, as qc/depth_profile.py), bands of 11.2 um counted up from the bottom edge.
"Dark" = below the 25th percentile of the blurred Inlens over the spot's whole solid, so the spot-level share is
0.25 and only its redistribution with depth is measured: session contrast and the rank curve cancel.
Why: fast drying drives binder and carbon black towards the top surface and leaves the current-collector side
binder-poor (adhesion, delamination); a through-thickness change of the carbon/binder phase is the signature.
Caveat (visual check, 4ih2ggld / 0grcilhi): the dark Inlens phase inside the solid is mostly polished graphite faces;
the carbon-binder web shows as bright, fluffy Inlens texture. So a gain in dark share towards the bottom more likely
means more flat graphite (less CBD) there, not more binder. Bottom = current collector is assumed (Cu band seen in
epqdaau9 only). Constants fixed before looking at batch labels.
"""
import math

import numpy as np
from scipy import ndimage as ndi

from preprocessing import preprocess as pp

COLUMNS = ["inlens_depth_dark_b0_frac", "inlens_depth_dark_slope_per_10um", "inlens_depth_pore_slope_per_10um"]
LABELS = {"inlens_depth_dark_b0_frac": "Inlens-dark share of the solid, bottom 11.2 µm",
          "inlens_depth_dark_slope_per_10um": "Inlens-dark share: change per 10 µm towards the bottom",
          "inlens_depth_pore_slope_per_10um": "Inlens shading control: pore dark-share change per 10 µm"}
BAND_PX = 448                          # 11.2 um bands, as qc/depth_profile.py
DARK_Q = 0.25                          # dark = lowest quarter of the solid's blurred Inlens
BLUR_PX = 2.0                          # = pp.SEG_BLUR: suppress pixel noise before thresholding
EDGE_PX = 3                            # drop solid pixels this close to a pore or bright edge (edge halo)


def measure(spot, raw):
    H, W = raw.bse.shape
    full = pp.preprocess(raw, box=(pp.CROP_TOP, H - pp.CROP_BOTTOM, pp.CROP_SIDE, W - pp.CROP_SIDE))
    solid = ndi.binary_erosion(~full.void & ~full.bright, iterations=EDGE_PX)
    if solid.sum() < 1e5:
        return {c: math.nan for c in COLUMNS}
    inl = ndi.gaussian_filter(full.inlens.astype(np.float32), BLUR_PX)
    below = inl < np.quantile(inl[solid], DARK_Q)
    dark = solid & below
    pore = ndi.binary_erosion(full.void, iterations=EDGE_PX)
    n = solid.shape[0]
    band = (n - 1 - np.arange(n)) // BAND_PX                     # 0 = bottom
    share, pshare, depth = [], [], []
    for b in range(band.max() + 1):
        rows = band == b
        s = solid[rows].sum()
        if rows.sum() < BAND_PX // 2 or s < 1e4:
            continue
        share.append(dark[rows].sum() / s)
        p = pore[rows].sum()
        pshare.append((pore[rows] & below[rows]).sum() / p if p >= 1e3 else math.nan)
        depth.append((b + 0.5) * BAND_PX * pp.PIXEL_UM / 10)
    if not depth or depth[0] > BAND_PX * pp.PIXEL_UM / 10:      # no usable bottom band
        return {c: math.nan for c in COLUMNS}
    return {"inlens_depth_dark_b0_frac": float(share[0]), "inlens_depth_dark_slope_per_10um": slope_down(depth, share),
            "inlens_depth_pore_slope_per_10um": slope_down(depth, pshare)}


def slope_down(depth, values):
    """Least-squares change per 10 um towards the bottom (depth counts up from the bottom), nan with < 2 bands."""
    d, v = np.asarray(depth), np.asarray(values, dtype=float)
    ok = np.isfinite(v)
    return float(-np.polyfit(d[ok], v[ok], 1)[0]) if ok.sum() >= 2 else math.nan
