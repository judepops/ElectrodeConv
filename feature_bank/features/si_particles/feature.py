"""si_particles: size, shape, alignment, clustering and pore contact of the Si-based bright particles (BSE).

Columns (all from the shared harmonised bright mask, features/_common):
    bright_d50_um, bright_d90_um   area-weighted equivalent-circle diameter (ECD) quantiles of the particles, um
    bright_solidity_aw             area-weighted median of area / convex-hull area (1 = compact, convex shard)
    bright_aspect_aw               area-weighted median second-moment aspect ratio (1 = round)
    bright_orient_order            nematic order <cos 2 theta> of the long axes of elongated particles against the
                                   image horizontal, one vote per particle (+1 all flat-lying, 0 random, -1 upright)
    bright_agglom_d50_um           area-weighted ECD d50 of agglomerates: particles closer than 2 x 0.5 um merged
                                   (edge-touching agglomerates kept at their visible size)
    bright_contact_pore_frac       share of the particle outline with a void pixel within 6 px (150 nm)
    bright_quadrat_cv              [not a features.csv column since the team audit, 2026-10-03; see the comment on the function] coefficient of variation of the bright area fraction over 10 x 10 um quadrats

Why it matters: the bright phase is the Si-based additive (most likely SiOx). Its particle size sets the
lithiation stress (fracture, contact loss) against surface area (SEI, first-cycle loss); agglomerates are
local swelling hot-spots; particles facing pores instead of carbon risk electrical isolation; patchiness
means uneven mixing. A shift points at the Si powder lot (milling, classification) or the mixing step.

Sizes are 2D section sizes. A plane cuts most particles away from their equator, so section ECDs are
smaller than the 3D diameter (the Wicksell problem): read them as relative indices, never as a laser-
diffraction D50. Particles that touch the crop edge are dropped and the rest are Miles-Lantuejoul
weighted, so large particles are not under-counted. With ~30-80 measurable particles per spot, site values
are noisy: compare batches on particles pooled per batch (README). Tuning numbers in config.yaml.
"""
import math

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import ConvexHull

from features import feature, load_config
from features._common.harmonise import PX_UM, harmonised

CFG = load_config(__file__)
EIGHT = np.ones((3, 3), bool)            # 8-connected labelling
KEYS = ("d50_um", "d90_um", "solidity_aw", "aspect_aw", "orient_order", "agglom_d50_um",
        "contact_pore_frac", "quadrat_cv")
_cache = {"sample": None, "value": None}


# ----------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------
def weighted_quantile(values, weights, q):
    """Quantile q of `values` with `weights` (mid-point cumulative weights, linear interpolation)."""
    values, weights = np.asarray(values, float), np.asarray(weights, float)
    ok = np.isfinite(values) & (weights > 0)
    if not ok.any():
        return math.nan
    order = np.argsort(values[ok])
    v, w = values[ok][order], weights[ok][order]
    cum = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(q, cum, v))


def miles_weights(slices, shape):
    """Miles-Lantuejoul edge correction per object: 0 if its bounding box touches the image edge, else
    H*W / ((H - h) * (W - w)), the inverse chance that an object of that box size lies wholly inside."""
    H, W = shape
    w = np.zeros(len(slices))
    for i, (rows, cols) in enumerate(slices):
        h, b = rows.stop - rows.start, cols.stop - cols.start
        if rows.start > 0 and cols.start > 0 and rows.stop < H and cols.stop < W:
            w[i] = H * W / ((H - h) * (W - b))
    return w


def shape_of(obj):
    """(solidity, aspect ratio, cos 2 theta) of one particle given as a bool array (its bounding box)."""
    ys, xs = np.nonzero(obj)
    # second moments: x = columns (horizontal), y = rows
    dx, dy = xs - xs.mean(), ys - ys.mean()
    mu20, mu02, mu11 = (dx * dx).sum(), (dy * dy).sum(), (dx * dy).sum()
    d = math.sqrt(4 * mu11 ** 2 + (mu20 - mu02) ** 2)
    l1, l2 = (mu20 + mu02 + d) / 2, (mu20 + mu02 - d) / 2
    aspect = math.sqrt(l1 / max(l2, 1e-9))
    cos2 = (mu20 - mu02) / d if d > 0 else 0.0          # cos(2 theta) of the long axis vs horizontal
    # solidity: pixel area / area of the convex hull of the outline pixels' corners
    edge = obj & ~ndi.binary_erosion(obj, EIGHT)
    ey, ex = np.nonzero(edge)
    corners = np.concatenate([np.stack([ex + sx, ey + sy], 1) for sx in (-0.5, 0.5) for sy in (-0.5, 0.5)])
    solidity = len(xs) / ConvexHull(corners).volume      # in 2D, .volume is the area
    return solidity, aspect, cos2


def outline(mask):
    """Outline pixels of a mask (8-connected erosion), excluding the image's own edge rows/columns."""
    edge = mask & ~ndi.binary_erosion(mask, EIGHT, border_value=1)
    edge[[0, -1], :] = False
    edge[:, [0, -1]] = False
    return edge


# ----------------------------------------------------------------------------------------------------
# the measurement (on masks, so it can be re-run on halves or perturbed images)
# ----------------------------------------------------------------------------------------------------
def measure(bright, void):
    """All columns from a bright mask and a void mask of the same crop -> dict (+ diagnostic counts)."""
    out = {k: math.nan for k in KEYS}
    labels, n = ndi.label(bright, EIGHT)
    out["n_particles"], out["n_shape"] = n, 0
    if n == 0:
        return out
    slices = ndi.find_objects(labels)
    area = np.bincount(labels.ravel(), minlength=n + 1)[1:].astype(float)
    weight = miles_weights(slices, bright.shape)          # 0 for edge-touching particles
    ecd = 2 * np.sqrt(area / math.pi) * PX_UM

    # size: area-weighted ECD quantiles (area x Miles weight)
    out["d50_um"] = weighted_quantile(ecd, area * weight, 0.5)
    out["d90_um"] = weighted_quantile(ecd, area * weight, 0.9)

    # shape and alignment: interior particles big enough for a meaningful outline
    rows = []
    for i in np.flatnonzero((area >= CFG["shape_min_px"]) & (weight > 0)):
        rows.append((*shape_of(labels[slices[i]] == i + 1), area[i], weight[i]))
    if rows:
        solidity, aspect, cos2, a, w = map(np.array, zip(*rows))
        out["n_shape"] = len(rows)
        out["solidity_aw"] = weighted_quantile(solidity, a * w, 0.5)
        out["aspect_aw"] = weighted_quantile(aspect, a * w, 0.5)
        # orientation: every elongated particle votes once (Miles weight only). Area weighting leaves ~14
        # effective particles per spot and its sampling error exceeds the between-spot spread (README).
        if CFG["orient_weighting"] not in ("number", "area"):
            raise ValueError(f"orient_weighting must be 'number' or 'area', not {CFG['orient_weighting']!r}")
        vote = w if CFG["orient_weighting"] == "number" else a * w
        elongated = aspect > CFG["orient_min_aspect"]     # round particles have no defined long axis
        if elongated.any():
            out["orient_order"] = float((cos2[elongated] * vote[elongated]).sum() / vote[elongated].sum())

    # agglomerates: grow every particle by agglom_dilate_px, relabel, measure on the original pixels
    # (every grown group holds at least one particle, so its labels 1..m all appear in `members`).
    # No edge correction by default: an agglomerate network can be as large as the 33 um-high window, and
    # dropping edge-touching groups then throws away most of the bright area and reverses the reading.
    near = ndi.distance_transform_edt(~bright) <= CFG["agglom_dilate_px"]
    groups, m = ndi.label(near, EIGHT)
    members = np.where(bright, groups, 0)
    g_area = np.bincount(members.ravel(), minlength=m + 1)[1:].astype(float)
    g_weight = miles_weights(ndi.find_objects(members), bright.shape) if CFG["agglom_edge_correction"] \
        else np.ones(m)
    g_ecd = 2 * np.sqrt(g_area / math.pi) * PX_UM
    out["agglom_d50_um"] = weighted_quantile(g_ecd, g_area * g_weight, 0.5)

    # pore contact: share of the outline with a void pixel within contact_radius_px
    edge = outline(bright)
    if edge.any():
        if void.any():
            to_void = ndi.distance_transform_edt(~void)
            out["contact_pore_frac"] = float((to_void[edge] <= CFG["contact_radius_px"]).mean())
        else:
            out["contact_pore_frac"] = 0.0

    # patchiness: CV of the bright fraction over a centred grid of square quadrats
    q = CFG["quadrat_px"]
    H, W = bright.shape
    ny, nx = H // q, W // q
    if ny * nx >= 2:
        r0, c0 = (H - ny * q) // 2, (W - nx * q) // 2
        tiles = bright[r0:r0 + ny * q, c0:c0 + nx * q].reshape(ny, q, nx, q).mean(axis=(1, 3))
        if tiles.mean() > 0:
            out["quadrat_cv"] = float(tiles.std() / tiles.mean())
    return out


def particles(sample):
    """measure() on the harmonised spot, computed once per sample and shared by every column below."""
    if _cache["sample"] is not sample:
        h = harmonised(sample)
        _cache["value"] = measure(h.bright, h.void)
        _cache["sample"] = sample
    return _cache["value"]


# ----------------------------------------------------------------------------------------------------
# the columns
# ----------------------------------------------------------------------------------------------------
@feature
def bright_d50_um(sample):
    return particles(sample)["d50_um"]


@feature
def bright_d90_um(sample):
    return particles(sample)["d90_um"]


@feature
def bright_solidity_aw(sample):
    return particles(sample)["solidity_aw"]


@feature
def bright_aspect_aw(sample):
    return particles(sample)["aspect_aw"]


@feature
def bright_orient_order(sample):
    return particles(sample)["orient_order"]


@feature
def bright_agglom_d50_um(sample):
    return particles(sample)["agglom_d50_um"]


@feature
def bright_contact_pore_frac(sample):
    return particles(sample)["contact_pore_frac"]


# Not a features.csv column (team audit, 2026-10-03): equals the random-placement null (obs/null 1.01 +- 0.09 in Batch_3); a grid shift moves it ~1 SD.
def bright_quadrat_cv(sample):
    return particles(sample)["quadrat_cv"]
