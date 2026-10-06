"""cc_interface: long horizontal pores at the current-collector side (BSE void mask, FULL image height).

Ledger: cc_interface (adarsh). Rows CROP_TOP .. H - CROP_BOTTOM with the standard recipe; the bottom edge is read as
the current-collector side (as qc/depth_profile.py; only epqdaau9 shows the Cu band itself). Pores are labelled on the
whole full-height mask (8-connected) and assigned to a band by centroid, so a band edge never cuts a pore's shape.
A pore is "horizontal elongated" when its second-moment aspect ratio (major / minor axis) > 3 and its major axis lies
within 20 deg of horizontal. Pores touching the bottom edge are dropped (cut shape; below the Cu band it is resin).
    cc_interface_horiz_share_bottom_frac  share of the pore area of the bottom 5 um in horizontal elongated pores
    cc_interface_horiz_share_far_frac     the same, 20-30 um above the bottom edge (within-spot reference)
    cc_interface_horiz_share_delta_frac   bottom minus far (> 0: more horizontal pore area at the interface)
    cc_interface_horiz_len_bottom_um      longest horizontal elongated pore in the bottom 5 um (major axis, um; 0 = none)
    cc_interface_horiz_len_far_um         the same 20-30 um up, as the mean of the 20-25 and 25-30 um bands so the
                                          searched area equals the bottom band's (a max grows with area)
Why: a debonding coating opens gaps parallel to the foil; in cross-section they are long, thin, horizontal pores
at the interface. Poor adhesion raises contact resistance and lets the coating peel on cycling or calendering.
Calendering also flattens pores everywhere, hence the far band as the within-spot reference. 2D caveat: a section
shows a gap's trace, not its area; relative indices only.
"""
import math

import numpy as np
from scipy import ndimage as ndi

from preprocessing import preprocess as pp

COLUMNS = ["cc_interface_horiz_share_bottom_frac", "cc_interface_horiz_share_far_frac",
           "cc_interface_horiz_share_delta_frac", "cc_interface_horiz_len_bottom_um", "cc_interface_horiz_len_far_um"]
LABELS = {"cc_interface_horiz_share_bottom_frac": "horizontal-pore share of pore area, bottom 5 µm",
          "cc_interface_horiz_share_far_frac": "horizontal-pore share of pore area, 20-30 µm up",
          "cc_interface_horiz_share_delta_frac": "horizontal-pore share, bottom minus 20-30 µm up",
          "cc_interface_horiz_len_bottom_um": "longest horizontal pore, bottom 5 µm",
          "cc_interface_horiz_len_far_um": "longest horizontal pore, 20-30 µm up"}
BAND_UM, FAR_UM = 5.0, (20.0, 30.0)
ASPECT_MIN, ANGLE_MAX_DEG, MIN_PORE_PX = 3.0, 20.0, 30


def pore_table(void):
    """Per pore: area, centroid row, aspect, angle from horizontal (deg), major-axis length (px), touches bottom."""
    lab, n = ndi.label(void, ndi.generate_binary_structure(2, 2))
    if n == 0:
        return {k: np.array([]) for k in ("area", "row", "aspect", "angle", "length", "bottom")}
    yy, xx = np.nonzero(void)
    yy, xx, k = yy.astype(np.float64), xx.astype(np.float64), lab[void] - 1
    area = np.bincount(k, minlength=n).astype(np.float64)
    mean = lambda v: np.bincount(k, v, minlength=n) / area     # noqa: E731
    my, mx = mean(yy), mean(xx)
    syy = mean(yy * yy) - my ** 2 + 1 / 12                     # +1/12: pixel extent, keeps 1-px lines finite
    sxx = mean(xx * xx) - mx ** 2 + 1 / 12
    sxy = mean(xx * yy) - mx * my
    half_tr, root = (sxx + syy) / 2, np.sqrt(((sxx - syy) / 2) ** 2 + sxy ** 2)
    l1, l2 = half_tr + root, np.maximum(half_tr - root, 1e-9)
    angle = np.degrees(0.5 * np.arctan2(2 * sxy, sxx - syy))     # major axis, from horizontal, in (-90, 90]
    bottom = np.zeros(n + 1, bool)
    bottom[np.unique(lab[-1])] = True
    return {"area": area, "row": my, "aspect": np.sqrt(l1 / l2), "angle": np.abs(angle),
            "length": 4 * np.sqrt(l1), "bottom": bottom[1:]}


def band_stats(p, sel):
    """Horizontal-pore share of the band's pore area, and the longest horizontal pore (um)."""
    if p["area"][sel].sum() <= 0:
        return math.nan, math.nan
    horiz = sel & (p["aspect"] > ASPECT_MIN) & (p["angle"] < ANGLE_MAX_DEG)
    share = float(p["area"][horiz].sum() / p["area"][sel].sum())
    length = float(p["length"][horiz].max() * pp.PIXEL_UM) if horiz.any() else 0.0
    return share, length


def measure(spot, raw):
    H, W = raw.bse.shape
    void = pp.preprocess(raw, box=(pp.CROP_TOP, H - pp.CROP_BOTTOM, pp.CROP_SIDE, W - pp.CROP_SIDE)).void
    n = void.shape[0]
    if n * pp.PIXEL_UM < FAR_UM[1]:
        return {c: math.nan for c in COLUMNS}
    p = pore_table(void)
    up = (n - 0.5 - p["row"]) * pp.PIXEL_UM                      # centroid height above the bottom edge, um
    ok = (p["area"] >= MIN_PORE_PX) & ~p["bottom"]
    share_b, len_b = band_stats(p, ok & (up < BAND_UM))
    share_f, _ = band_stats(p, ok & (up >= FAR_UM[0]) & (up < FAR_UM[1]))
    lens_f = [band_stats(p, ok & (up >= lo) & (up < lo + BAND_UM))[1] for lo in np.arange(FAR_UM[0], FAR_UM[1], BAND_UM)]
    return {"cc_interface_horiz_share_bottom_frac": share_b, "cc_interface_horiz_share_far_frac": share_f,
            "cc_interface_horiz_share_delta_frac": share_b - share_f,
            "cc_interface_horiz_len_bottom_um": len_b, "cc_interface_horiz_len_far_um": float(np.mean(lens_f))}
