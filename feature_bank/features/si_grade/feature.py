"""si_grade: what the bright (Si-based) particles look like inside, on the BSE image. DIAGNOSTIC ONLY.

Columns:
    bright_contrast_ratio      median BSE level of the eroded particle cores, in graphite units (black 0, graphite 1).
                               A higher mean atomic number reads brighter (Si-richer), an O- or C-richer or porous
                               particle reads darker. Session explains about 95 % of it (kV, detector and tone curve
                               are not recorded), so it only compares spots imaged in the same session.
    bright_dim_frac            area fraction of the dim-grey band (h.dim: compact objects between graphite and the
                               bright threshold, away from bright edges): a second, lower-Z bright population.
    bright_internal_dark_frac  share of the hole-filled particle interior that is darker than 0.85 x that particle's
                               own core level: internal pores or carbon inside a particle (the porous Si-C composite
                               test). Dense SiOx shards give about 1 % (Batch_3 0.011 +- 0.005).
    bright_core_cv             [not a features.csv column since the team audit, 2026-10-03; see the comment on the function] within-particle coefficient of variation of the core BSE, noise-free: the variance is
                               the covariance of pixel pairs 4 px (100 nm) apart inside the same particle, where pixel
                               noise is uncorrelated but real texture (granular, porous, two-phase) is not.

Image: BSE (anchored, noise-matched, features/_common/harmonise.py), shared h.bright mask. Tuning in config.yaml.

Why it matters: the dose (si_fraction) is not the whole story. The Si-phase grade (SiOx stoichiometry, carbon content,
internal porosity) sets capacity, first-cycle efficiency and how much the particle swells. These columns are the
image-side evidence for the Batch_1 session-2316 lead (darker, coarser, more granular Si phase); they point to EDS,
they never gate a verdict on their own.
"""
import math

import numpy as np
from scipy import ndimage as ndi

from features import feature, load_config
from features._common.harmonise import disk, fill_small_holes, harmonised

CFG = load_config(__file__)
_cache = {"sample": None, "value": None}


def particle_cores(sample):
    """-> dict with the particle labels, eroded cores and per-particle core level. Cached per sample."""
    if _cache["sample"] is sample:
        return _cache["value"]
    h = harmonised(sample)
    eight = ndi.generate_binary_structure(2, 2)

    # particles = bright mask with internal holes up to max_hole_px filled; labelled once
    filled = fill_small_holes(h.bright, CFG["max_hole_px"])
    labels, n = ndi.label(filled, eight)

    # core = bright pixels at least core_erosion_px from the particle edge (BSE edge blur is 4-5 px)
    core = ndi.binary_erosion(h.bright, disk(CFG["core_erosion_px"])) & (labels > 0)
    core_px = np.bincount(labels[core], minlength=n + 1)
    valid = core_px >= CFG["min_core_px"]
    valid[0] = False
    core &= valid[labels]

    # per-particle core level: median of the blurred BSE over its core (robust to the odd hole or crack)
    level = np.full(n + 1, np.nan)
    if valid.any():
        values, owner = h.bse_blur[core], labels[core]
        order = np.argsort(owner, kind="stable")
        values, owner = values[order], owner[order]
        starts = np.searchsorted(owner, np.arange(n + 1))
        ends = np.searchsorted(owner, np.arange(n + 1), side="right")
        for i in np.flatnonzero(valid):
            level[i] = np.median(values[starts[i]:ends[i]])

    value = {"h": h, "labels": labels, "filled": filled, "core": core, "valid": valid, "level": level}
    _cache["sample"], _cache["value"] = sample, value
    return value


@feature
def bright_contrast_ratio(sample):
    p = particle_cores(sample)
    return float(np.median(p["h"].bse[p["core"]])) if p["core"].any() else math.nan


@feature
def bright_dim_frac(sample):
    return float(harmonised(sample).dim.mean())


@feature
def bright_internal_dark_frac(sample):
    p = particle_cores(sample)
    labels, valid = p["labels"], p["valid"]
    # interior of each hole-filled particle, away from its outer edge (whose blur ramp would read as dark)
    interior = ndi.binary_erosion(p["filled"], disk(CFG["rim_px"])) & valid[labels]
    if not interior.any():
        return math.nan
    threshold = CFG["dark_fraction_of_core"] * p["level"][labels[interior]]
    dark = p["h"].bse_blur[interior] < threshold
    return float(dark.mean())


def _pair_covariance(img, labels, lag):
    """Pooled within-particle covariance of pixel pairs `lag` px apart (x and y), both in the same particle core.

    Pixel noise is uncorrelated beyond 2-3 px (x and y lag covariances agree from 3-4 px on), so this is the core's
    real texture variance without the noise (the plain variance of a core is 93-98 % noise on the spots checked)."""
    n = labels.max()
    inside = labels > 0
    count = np.bincount(labels[inside], minlength=n + 1)
    mean = np.bincount(labels[inside], img[inside], minlength=n + 1) / np.maximum(count, 1)
    resid = np.where(inside, img - mean[labels], 0.0)
    products, pairs = 0.0, 0
    for a, b, la, lb in ((resid[:, :-lag], resid[:, lag:], labels[:, :-lag], labels[:, lag:]),
                         (resid[:-lag], resid[lag:], labels[:-lag], labels[lag:])):
        same = (la > 0) & (la == lb)
        products += float((a[same] * b[same]).sum())
        pairs += int(same.sum())
    return products / pairs if pairs else math.nan


# Not a features.csv column (team audit, 2026-10-03): rho 0.80 with bright_internal_dark_frac; half of it comes from ~1 % of the darkest core pixels.
def bright_core_cv(sample):
    p = particle_cores(sample)
    if not p["core"].any():
        return math.nan
    core_labels = np.where(p["core"], p["labels"], 0)
    cov = _pair_covariance(p["h"].bse.astype(np.float64), core_labels, CFG["texture_lag_px"])
    level = float(np.median(p["h"].bse[p["core"]]))
    return math.sqrt(max(cov, 0.0)) / level if level > 0 else math.nan
