"""si_fraction: how much of the electrode is the bright, Si-based phase (likely SiOx), on the BSE image.

Columns (all on the shared harmonised crop, about 5800 um2 per spot):
    bright_solid_frac        bright area / solid area (solid = not void). The decision KPI: SiOx and graphite have
                             similar densities (both about 2.2 g/cm3), so this is a first-order proxy for the Si-phase
                             weight fraction of the active material, and it does not move when porosity moves.
    bright_frac              [not a features.csv column since the team audit, 2026-10-03; see the comment on the function] bright area / total area.
    bright_frac_ci95         95 % half-width of bright_frac from this one image (1.96 x the two-point-correlation
                             standard error, ImageRep idea). Sampling error only: segmentation and site-to-site
                             variation come on top.
    bright_fixed_solid_frac  bright_solid_frac with the fixed-threshold mask (h.bright_fixed, 1.45 x graphite):
                             the sensitivity recipe. Primary and fixed must move in the same direction.
    bright_n_per_1000um2     bright objects >= 1 um equivalent-circle diameter per 1000 um2, edge-corrected
                             (Miles-Lantuejoul: objects touching the crop edge are dropped, the rest are weighted up
                             by the chance that an object of their size fits inside the crop).

Image: BSE (anchored to graphite units, noise-matched, see features/_common/harmonise.py). Masks are the shared
h.bright (adaptive midpoint between graphite and the image's own bright mode) and h.bright_fixed. No re-segmentation.

Why it matters: the Si-based phase carries 4x the specific capacity of graphite, but it also lowers first-cycle
efficiency, swells and fades faster. A dose change is the most consequential hidden supplier change
(notes/research_report.md section 3 rank 1, section 8). Tuning in config.yaml.
"""
import math

import numpy as np
from scipy import ndimage as ndi

from features import feature, load_config
from features._common.harmonise import PX_UM, fraction_se, harmonised

CFG = load_config(__file__)


def _solid_share(mask, solid):
    """Area of mask divided by the solid area (nan if there is no solid)."""
    n_solid = int(solid.sum())
    return float((mask & solid).sum() / n_solid) if n_solid else math.nan


@feature
def bright_solid_frac(sample):
    h = harmonised(sample)
    return _solid_share(h.bright, h.solid)


# Not a features.csv column (team audit, 2026-10-03): rho > 0.9 with bright_solid_frac, same profile; bright_solid_frac is the KPI.
def bright_frac(sample):
    return float(harmonised(sample).bright.mean())


@feature
def bright_frac_ci95(sample):
    se, _ = fraction_se(harmonised(sample).bright)          # nan when the image holds no bright phase
    return float(CFG["ci_z"] * se)


@feature
def bright_fixed_solid_frac(sample):
    h = harmonised(sample)
    return _solid_share(h.bright_fixed, h.solid)


def edge_corrected_count(mask, min_area_px):
    """Miles-Lantuejoul number of objects >= min_area_px in mask.

    An object whose bounding box is bh x bw pixels fits fully inside an H x W window with probability
    (H - bh)(W - bw) / (H W). Objects touching the window edge are dropped and every other object is weighted by the
    inverse of that probability, so big objects (more often cut by the edge) are not under-counted.
    """
    labels, n = ndi.label(mask, ndi.generate_binary_structure(2, 2))
    if n == 0:
        return 0.0
    H, W = mask.shape
    areas = np.bincount(labels.ravel(), minlength=n + 1)
    total = 0.0
    for i, box in enumerate(ndi.find_objects(labels), start=1):
        if box is None or areas[i] < min_area_px:
            continue
        rows, cols = box
        if rows.start == 0 or cols.start == 0 or rows.stop == H or cols.stop == W:
            continue                                         # touches the edge: weight 0
        bh, bw = rows.stop - rows.start, cols.stop - cols.start
        total += H * W / ((H - bh) * (W - bw))
    return total


@feature
def bright_n_per_1000um2(sample):
    h = harmonised(sample)
    min_area_px = math.pi * (CFG["min_object_ecd_um"] / 2) ** 2 / PX_UM ** 2   # 1 um ECD = 1257 px
    return edge_corrected_count(h.bright, min_area_px) / h.area_um2 * 1000
