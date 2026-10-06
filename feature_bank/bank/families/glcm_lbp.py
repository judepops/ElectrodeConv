"""glcm_lbp: grey-level co-occurrence statistics and uniform local binary patterns of the harmonised BSE and Inlens views.

Input
    The harmonised view (anchored intensities plus noise up to one fixed level) at block-mean scales 1, 2 and 4
    (25, 50 and 100 nm pixels; block means, never interpolated). Pixels where the raw BSE is saturated (crop.valid,
    at most 6e-6 of a crop) are left out of every count, as are pixel pairs and patterns that reach outside the window.
    Directions are pixel offsets, with the angle measured from +x (columns, in-plane) towards +y (rows, downward,
    through-thickness): a0 = (dx, dy) = (d, 0), a45 = (d, d) down-right, a90 = (0, d), a135 = (-d, d) down-left.
    A diagonal offset of d steps is d * sqrt(2) pixels long, and 45 and 135 are never merged.

GLCM (skimage graycomatrix, symmetric, 32 grey levels over the fixed global range of core.quantise:
      BSE -0.5..3.0 graphite units, 0.109 per level; Inlens 0..1 rank units, 0.031 per level)
    <prop>_d<D>_a<A>    prop in contrast, homogeneity, energy, correlation, entropy; D = offset in pixels of the scale
                        named in the column; A in 0, 45, 90, 135.
                        scale 25 nm:  D = 1, 2, 4, 8, 16, 32, 64   (25 nm to 1.6 um; diagonals 35 nm to 2.3 um)
                        scale 100 nm: D = 1, 2, 4, 8, 16           (0.1 to 1.6 um; the same lengths as D = 4..64 at 25 nm,
                                                                    with pixel noise averaged down 4-fold)
                        contrast     mean squared level difference of a pixel pair, in levels^2
                        homogeneity  mean of 1 / (1 + difference^2), 0..1
                        energy       square root of the sum of squared pair probabilities, 0..1
                        correlation  Pearson correlation of the two levels of a pair, -1..1
                        entropy      Shannon entropy of the pair distribution, in nats
    con_xy_d<D>         ln(contrast at a0 / contrast at a90). Dimensionless; negative when grey levels change faster
                        through the thickness than in-plane (horizontal layering).
    length_um is the length of the offset.

LBP (skimage local_binary_pattern, method "uniform": rotation-invariant by construction, so not angle-resolved)
    (P, R) = (8, 1), (16, 2), (24, 3) at scales 25, 50 and 100 nm: ring radii 25 to 300 nm (length_um = radius).
    The code of a pixel is the number of ring neighbours at least as bright as it when the ring has at most two
    dark/bright transitions (0..P), and P + 1 otherwise.
    lbp_p<P>_r<R>_edge     share of pixels with 3P/8 <= code <= 5P/8: about half the ring brighter (an edge)
    lbp_p<P>_r<R>_peak     share with code 0: every neighbour darker (a bright spot)
    lbp_p<P>_r<R>_pit      share with code P: no neighbour darker (a dark spot or a flat patch)
    lbp_p<P>_r<R>_nonuni   share with code P + 1: more than two transitions (noise-like)
    lbp_p<P>_r<R>_entropy  Shannon entropy of the code histogram, in nats
  Blocks   lbp_p<P>_r<R>_hist (P + 2): the code histogram (shares, sum 1), one block per (P, R) and scale.
  Tiles    lbp_tiles (26, 54) per scale: the three histograms of every 12.8 um tile side by side (fixed tile order).

Tags
    imaging   every statistic whose offset or ring radius is shorter than 100 nm (GLCM at 25 nm with D <= 2; LBP at
              25 nm, and (8, 1) at 50 nm). Over 1-3 px the harmonised BSE is mostly noise (0.235 graphite units, about
              2 grey levels), so these read how white the noise is, the fast-scan low-pass and focus: acquisition.
    mixed     everything else. Longer offsets and radii see real structure (void edges, bright grains, cracks, binder
              texture), but through fixed grey levels that a tone curve shifts (BSE), with a noise share that is only
              equal across crops as far as the top-up is exact, and with blur sensitivity below about 500 nm. Inlens
              is rank-normalised (tone changes cancel) but its contrast depends on charging and detector settings.
    Nothing here is tagged material. LBP ignores any monotonic grey-level change of the picture it is given, and for
    the rank-normalised Inlens a tone change indeed moved nothing. For BSE the noise top-up is fixed in graphite units,
    so a tone curve still changes the signal-to-noise LBP sees (gamma 0.8 moved the BSE edge shares by 0.003-0.007).
    On the two smoke crops the steadiest statistics were the BSE con_xy at 100 nm, and the most blur-bound were the
    Inlens LBP shares at 50 and 100 nm (a 1 px blur moved the edge share by 0.012-0.028, as much as or more than the
    two crops differ).
"""
import warnings

import numpy as np
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern

from bank.core import PX_NM, FeatureResult, block_mean, quantise, tiles

FAMILY = "glcm_lbp"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {
    "detectors": ["BSE", "Inlens"],
    "view": "harmonised",
    "levels": 32,                                                # fixed global quantisation (core.quantise)
    "glcm_scales": [[1, [1, 2, 4, 8, 16, 32, 64]], [4, [1, 2, 4, 8, 16]]],   # [scale, offsets in pixels of that scale]
    "glcm_props": ["contrast", "homogeneity", "energy", "correlation", "entropy"],
    "lbp": [[8, 1], [16, 2], [24, 3]],                           # (P, R)
    "lbp_scales": [1, 2, 4],
    "tile_px": 512,                                              # 12.8 um, at 25 nm; the same field at every scale
    "imaging_below_um": 0.1,
}
ANGLES = (0, 45, 90, 135)
SKIP = 255                                                       # LBP code of a pixel that is not counted
TINY = 1e-30


def _glcm(levels_img, distances, n_levels):
    """Pair counts (n_levels, n_levels, n_distances, 4 angles). Level n_levels marks pixels to leave out."""
    kw = dict(levels=n_levels + 1, symmetric=True, normed=False)
    axis = graycomatrix(levels_img, distances, [0, np.pi / 2], **kw)                                    # (0, d) and (d, 0)
    diag = graycomatrix(levels_img, [d * np.sqrt(2) for d in distances], [np.pi / 4, 3 * np.pi / 4], **kw)   # (d, d) and (d, -d)
    out = np.stack([axis[..., 0], diag[..., 0], axis[..., 1], diag[..., 1]], axis=-1)                   # a0, a45, a90, a135
    return out[:n_levels, :n_levels]


def _lbp_codes(img, valid, p, r):
    """uint8 code map; SKIP where the ring leaves the window or the pixel is not valid."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)             # float input is intended: the view is continuous, ties are rare
        codes = local_binary_pattern(img, p, r, method="uniform").astype(np.uint8)
    m = int(np.ceil(r)) + 1
    keep = np.zeros(codes.shape, bool)
    keep[m:-m, m:-m] = valid[m:-m, m:-m]
    codes[~keep] = SKIP
    return codes


def _hist(codes, n_codes):
    counts = np.bincount(codes.ravel(), minlength=256)[:n_codes].astype(np.float64)
    return counts / max(counts.sum(), 1.0)


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    view, n_levels = cfg["view"], cfg["levels"]
    limit = cfg["imaging_below_um"]
    valid = {s: block_mean(crop.valid, s) == 1 for s in sorted({s for s, _ in cfg["glcm_scales"]} | set(cfg["lbp_scales"]))}

    for det in cfg["detectors"]:
        # ---- GLCM
        for scale, distances in cfg["glcm_scales"]:
            scale_nm = PX_NM * scale
            q = quantise(crop.view(det, view, scale), det, n_levels).astype(np.uint8)
            q[~valid[scale]] = n_levels
            pairs = _glcm(q, distances, n_levels)
            props = {p: graycoprops(pairs, p) for p in cfg["glcm_props"]}                # each (n_distances, 4)
            for i, d in enumerate(distances):
                for j, a in enumerate(ANGLES):
                    length = d * scale_nm / 1000 * (np.sqrt(2) if a in (45, 135) else 1.0)
                    for p in cfg["glcm_props"]:
                        res.scalar(det, view, scale_nm, f"{p}_d{d}_a{a}", props[p][i, j], length_um=length,
                                   tag="imaging" if length < limit else "mixed")
                length = d * scale_nm / 1000
                ratio = np.log(max(props["contrast"][i, 0], TINY) / max(props["contrast"][i, 2], TINY))
                res.scalar(det, view, scale_nm, f"con_xy_d{d}", ratio, length_um=length, tag="imaging" if length < limit else "mixed")

        # ---- LBP
        for scale in cfg["lbp_scales"]:
            scale_nm = PX_NM * scale
            img = crop.view(det, view, scale)
            per_tile, lengths = [], []
            for p, r in cfg["lbp"]:
                length = r * scale_nm / 1000
                lengths.append(length)
                tag = "imaging" if length < limit else "mixed"
                codes = _lbp_codes(img, valid[scale], p, r)
                hist = _hist(codes, p + 2)
                stat = f"lbp_p{p}_r{r}"
                res.block(det, view, scale_nm, f"{stat}_hist", hist, length_um=length, tag=tag)
                code = np.arange(p + 2)
                edge = hist[(code >= 3 * p / 8) & (code <= 5 * p / 8)].sum()
                nonzero = hist[hist > 0]
                for name, value in (("edge", edge), ("peak", hist[0]), ("pit", hist[p]), ("nonuni", hist[p + 1]),
                                    ("entropy", -(nonzero * np.log(nonzero)).sum())):
                    res.scalar(det, view, scale_nm, f"{stat}_{name}", value, length_um=length, tag=tag)
                per_tile.append(np.array([_hist(t, p + 2) for t in tiles(codes, cfg["tile_px"] // scale)]))
            res.tile_block(det, view, scale_nm, "lbp_tiles", np.concatenate(per_tile, axis=1), length_um=float(np.mean(lengths)),
                           tag="imaging" if max(lengths) < limit else "mixed")
    return res
