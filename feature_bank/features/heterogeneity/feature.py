"""heterogeneity: how unevenly the pores and the Si-like bright phase are spread across one image.

    porosity_tile_cv            coefficient of variation of the void fraction over 512-px tiles of the crop
    bright_tile_cv              the same for the bright (Si-like) phase
    porosity_excess_het_ratio   [not a features.csv column since the team audit, 2026-10-03; see the comment on the function] observed variance of the tile void fractions / variance a random medium with the
                                same short-range structure would give at that tile size
    bright_excess_het_ratio     the same for the bright phase

Image: BSE only, through the shared harmonised masks of features/_common (h.void, h.bright) on the same central
crop of every spot. Units: the CVs are dimensionless (sd / mean); the excess ratios are dimensionless, about 1 for
a random medium, > 1 = clustered beyond chance, < 1 = more even than chance.

Why it matters: a well-mixed, evenly calendered electrode has the same pore and Si content everywhere. Patches
rich in Si phase swell more and carry more current locally; dense, pore-poor patches are where ions run short
and lithium plates first at fast charge. Uneven tiles point at mixing / dispersion (agglomerates, segregation
during coating or drying) or uneven calendering. This is Polaron's "spatial heterogeneity" KPI.

Why the excess ratio and not just the CV: a sparse phase made of large particles is uneven by pure chance (a
164-um2 tile holds only a handful of 2-10 um Si particles), so the raw CV mostly says "the phase is sparse and
coarse". The two-point correlation of the whole mask (integral range A_IR, the ImageRep idea, computed in
features/_common/harmonise.fraction_se) predicts the tile-to-tile variance of a statistically homogeneous medium
with the same structure: var = phi (1 - phi) A_IR / A_tile. A_IR only counts correlations within a few um
(the window in _common/config.yaml), so a ratio above 1 means variation on larger scales: gradients, bands or
patches tens of um across.

Tiles overlap (one every stride_px): the variance is averaged over all grid offsets, because with a single grid of
26 tiles the answer depended on where the grid happened to sit.
"""
import math

import numpy as np

from features import feature, load_config
from features._common.harmonise import PX_UM, fraction_se, harmonised

CFG = load_config(__file__)
_cache = {"sample": None, "stats": {}}


def tile_fractions(mask, tile_px, stride_px):
    """Area fraction of `mask` in every tile_px x tile_px window placed every stride_px. None if too few tiles fit."""
    h, w = mask.shape
    if (h // tile_px) * (w // tile_px) < CFG["min_tiles"]:
        return None
    # integral image: the pixel count of any window is four lookups
    integral = np.pad(mask.astype(np.int64).cumsum(axis=0).cumsum(axis=1), ((1, 0), (1, 0)))
    # offsets start at 0: when (h - tile_px) is not a multiple of stride_px, the last rows/columns are in no window
    # (56 rows and 4-32 columns of the 1336-row crop). Same for every spot; see README "How it is computed".
    r = np.arange(0, h - tile_px + 1, stride_px)[:, None]
    c = np.arange(0, w - tile_px + 1, stride_px)[None, :]
    counts = (integral[r + tile_px, c + tile_px] - integral[r, c + tile_px]
              - integral[r + tile_px, c] + integral[r, c])
    return (counts / tile_px ** 2).ravel()


def mask_heterogeneity(mask):
    """(tile CV, excess heterogeneity ratio) of one boolean phase mask; nan where it cannot be measured."""
    tile_px = CFG["tile_px"]
    fracs = tile_fractions(mask, tile_px, CFG["stride_px"])
    if fracs is None or fracs.mean() <= 0:
        return math.nan, math.nan
    observed_var = float(fracs.var(ddof=1))
    cv = math.sqrt(observed_var) / float(fracs.mean())

    # tile-to-tile variance a statistically homogeneous medium with this mask's two-point correlation would give
    phi = float(mask.mean())
    _, integral_range_um2 = fraction_se(mask)            # nan if the phase is absent or fills the crop
    predicted_var = phi * (1 - phi) * integral_range_um2 / (tile_px * PX_UM) ** 2
    if not (math.isfinite(predicted_var) and predicted_var > 0):
        return cv, math.nan
    return cv, observed_var / predicted_var


def tile_stats(sample, phase):
    """mask_heterogeneity of h.void ('void') or h.bright ('bright'), computed once per sample."""
    if _cache["sample"] is not sample:
        _cache["sample"], _cache["stats"] = sample, {}
    if phase not in _cache["stats"]:
        _cache["stats"][phase] = mask_heterogeneity(getattr(harmonised(sample), phase))
    return _cache["stats"][phase]


@feature
def porosity_tile_cv(sample):
    return tile_stats(sample, "void")[0]


@feature
def bright_tile_cv(sample):
    return tile_stats(sample, "bright")[0]


# Not a features.csv column (team audit, 2026-10-03): blind to lateral patchiness by design (a patchy phantom scores inside the real range).
def porosity_excess_het_ratio(sample):
    return tile_stats(sample, "void")[1]


@feature
def bright_excess_het_ratio(sample):
    return tile_stats(sample, "bright")[1]
