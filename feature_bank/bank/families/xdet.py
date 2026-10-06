"""xdet: what the BSE and Inlens pictures of one crop say about each other, pixel by pixel.

The two detectors are co-registered and only partly correlated: BSE shows composition (void dark, bright grains
bright), Inlens shows surface, edges and charging. Everything here needs both, except the two descriptors from
notes/feature_screen.md at the end, which are kept in this family because the screen found them together.

Inputs. BSE is graphite-anchored (0 = black level, 1 = graphite). Inlens is rank-normalised (0..1), so any
monotonic brightness / contrast / gamma change of the Inlens picture cancels exactly. Before any fixed-bin count a
dither of less than one stored grey level is added (BSE: uniform +-0.5 level; Inlens: uniform inside the rank
interval its grey level occupies), seeded from the crop content. Without it the 256 stored levels fall unevenly
into the fixed bins and the bin counts would carry the black level and gain. Saturated BSE pixels (crop.valid)
are left out. At scale s both pictures are block means over s x s pixels (scale_nm = 25 s).

Detector BSExInlens: scalars at 25, 50, 100, 200 nm (views harmonised = noise-matched, and anchored = no noise added)
    pearson             -1..1   Pearson correlation of BSE and Inlens rank
    spearman            -1..1   the same on ranks of both (4096 fixed bins): also immune to BSE gamma
    mi_bits             bits    mutual information from the fixed 32 x 32 joint histogram (plug-in estimate; its
                                bias is below 0.001 bit at 25 nm and about 0.005 bit at 200 nm)
    mi_norm             0..1    mi_bits / the smaller of the two marginal entropies
    pearson_graphite    -1..1   harmonised only: Pearson inside graphite (blocks that are entirely graphite), i.e.
                                whether the two detectors share texture once the phase contrast is taken away
  block joint_hist (1024)       harmonised, each scale: the 32 x 32 joint histogram, row = BSE bin over -0.5..3 g,
                                column = Inlens bin over 0..1, flattened row by row, sums to 1
  tiles tile_pearson (26, 4)    harmonised: pearson at 25, 50, 100, 200 nm inside each 512 px (12.8 um) tile
  All tagged mixed: pixel agreement depends on the material (which phases, how much edge) and on noise, focus and
  charging. Length probed = the block size.

Detector BSExInlens: Inlens inside each BSE phase, 25 nm. Phases are exclusive: void, bright (not void), dim (neither),
graphite = none of those.
    inlens_mean_<phase>             rank    mean Inlens rank in the phase (anchored; 0.5 = the crop average)
    inlens_p10_ / p50_ / p90_<phase> rank   quantiles of the Inlens rank in the phase (anchored)
    inlens_top10_share_<phase>      0..1    share of the phase in the brightest tenth of the Inlens picture (0.1 = no
                                            association); inlens_bot10_share_<phase> the same for the darkest tenth
    inlens_auc_void / _bright / _dim 0..1   chance that a pixel of the phase is brighter in Inlens than a graphite
                                            pixel (ties count half): 0.5 = Inlens cannot tell the phase from graphite
    inlens_std_<phase>              rank    spread of the Inlens rank in the phase (harmonised: noise-matched)
    inlens_grad_<phase>             rank/px mean Inlens gradient magnitude in the phase, Gaussian derivative sigma
                                            1 px (harmonised); probes 50 nm
  block inlens_hist_by_phase (64)   anchored: 16-bin histogram of the Inlens rank per phase (void, bright, dim,
                                    graphite), each normalised to 1
  tiles tile_inlens_by_phase (26, 4)  anchored: inlens_mean of void, bright, dim, graphite inside each 512 px tile
  Tagged mixed: built on phase maps and anchored ranks, but the Inlens contrast between phases is set by charging and
  edge brightening, which depend on the session as well as on the material. An absent phase gives the neutral value
  (mean, quantiles and auc 0.5, shares 0.1, spread and gradient 0, histogram 0).

Detector BSExInlens: Inlens across the BSE phase boundaries, 25 nm, anchored
  block inlens_profile_void (28), inlens_profile_bright (28)   mean Inlens rank against distance to the phase
                                    boundary: 8 steps inside (200 nm ... 25 nm) then 20 steps outside (25 ... 500 nm)
    inlens_rim_void, inlens_rim_bright   rank   mean Inlens rank 25-100 nm outside the phase minus the mean in graphite
                                    more than 500 nm from any void or bright grain: edge brightening / coating rim
  Tagged mixed (edge brightening is a detector effect, a coating rim is material). Probes 25-500 nm.

Detector BSExInlens: displacement and decay, 25 nm, anchored
    shift_x_nm, shift_y_nm          nm      lag of the cross-correlation peak (parabola through the three highest
                                            lags within +-8 px; positive = the Inlens picture sits right / down).
                                            Tagged imaging: detector registration and drift, not the material.
  block xcorr_x (17), xcorr_y (17)          correlation of BSE with Inlens displaced by -8..8 px along x and along
                                            y, kept apart (x = in plane, y = through plane). Tagged mixed. 0-200 nm.

Detector BSExInlens: do the detectors see the same edges, 25 nm, harmonised; sigma = 1, 2, 4 px (25, 50, 100 nm)
    gradx_corr_s<sigma>, grady_corr_s<sigma>   -1..1   Pearson of the x derivatives and of the y derivatives, kept apart
    gradmag_corr_s<sigma>           -1..1   Pearson of the gradient magnitudes (edge strength in the same places)
    grad_align_s<sigma>             -1..1   mean cos 2(angle between the two gradients), weighted by both magnitudes:
                                            1 = edges parallel whatever their polarity, 0 = unrelated
  Tagged mixed (fine texture below 500 nm on noise-matched views).

Detector BSE: shell around the bright grains (notes/feature_screen.md, "Shell dark-grey fraction"), 25 nm, harmonised
    shell_darkgrey_frac_lo / _mid / _hi   fraction   share of the shell 75-500 nm (3-20 px) outside the bright map
                                            whose blurred BSE (sigma 1.5 px) lies in 0.5-0.8 g: darker than graphite,
                                            not void (binder-like). On bright_lo, bright, bright_hi.
                                            Tagged mixed: it ordered the folders the same way inside every mixed
                                            session, but moves about 1 between-crop SD under gamma or blur.
    shell_void_enrich               ratio   void fraction of that shell / void fraction of everything outside the bright
                                            map. Tagged material: maps only. No bright grains or no void gives 1.
  tiles tile_shell_darkgrey (26, 1)         shell_darkgrey_frac_mid inside each 512 px tile (0 where a tile has no shell)

Detector Inlens: local binary patterns (notes/feature_screen.md, "Inlens LBP edge-pattern fraction at 100-200 nm"),
25 nm, views harmonised and anchored, radius R = 4 and 8 px (100 and 200 nm), 8 neighbours on a circle (the four
diagonal ones read bilinearly between pixels), picture blurred by sigma = R / 2 first, rotation-invariant uniform codes
    lbp_edge_r4, lbp_edge_r8        fraction   codes 3 + 4 + 5: half the circle brighter than the centre, an edge
    lbp_spot_r4, lbp_spot_r8        fraction   codes 0 + 8: the whole circle darker or brighter than the centre
  block lbp_riu2_r4 (10), lbp_riu2_r8 (10)    the full code histogram (0..8 = number of neighbours >= centre for
                                            uniform patterns, 9 = every non-uniform pattern)
    lbp_edge_cos2_r4, lbp_edge_cos2_r8, lbp_edge_sin2_r4, lbp_edge_sin2_r8   -1..1   the codes above pool every
                                            direction, so the direction is kept here: mean cos 2 phi and sin 2 phi
                                            over the edge patterns, phi = where the brighter side lies, counter-
                                            clockwise from +x as displayed. cos2 > 0: brighter side left or right,
                                            the edge runs through plane; cos2 < 0: brighter side above or below, the
                                            edge runs in plane. sin2: lean towards one diagonal.
  block lbp_edge_dir_r4 (16), lbp_edge_dir_r8 (16)   share of pixels that are an edge pattern with the brighter side
                                            in each of 16 directions (22.5 degree steps from +x); sums to lbp_edge
  tiles tile_lbp_edge (26, 2)               lbp_edge_r4 and lbp_edge_r8 inside each 512 px tile
  Tagged mixed: fine texture, and the screen found it moves 1.3-2 between-crop SD under a 1 px blur. The harmonised
  version adds white noise up to one level, which the screen showed can itself create a difference between sessions
  (native noise is not white); the anchored version has no noise added and carries the native noise instead.

Tiles are the 26 non-overlapping 512 px tiles of core.tiles, in its fixed order and without positions; the tile
arrays carry the same tag as the scalar they repeat.

Totals: 107 scalars, 17 blocks, 5 tile arrays. Cost: about 12 s per crop version on one core, about 1.5 GB.
"""
import numpy as np
from scipy import ndimage as ndi

from bank.core import PX_NM, FeatureResult, block_mean, quantise, tiles

FAMILY = "xdet"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {
    "scales": [1, 2, 4, 8],
    "hist_levels": 32,                   # joint histogram and mutual information: 32 x 32 fixed bins
    "rank_levels": 4096,                 # fixed bins behind the Spearman ranks
    "phase_hist_bins": 16,
    "profile_inside_px": 8,
    "profile_outside_px": 20,
    "rim_px": [1, 4],                    # the rim: 25-100 nm outside a phase
    "interior_px": 20,                   # graphite interior: more than 500 nm from void and bright
    "lag_max_px": 8,
    "grad_sigmas_px": [1, 2, 4],
    "shell_px": [3, 20],
    "shell_grey_g": [0.5, 0.8],
    "shell_blur_sigma_px": 1.5,
    "lbp_radii_px": [4, 8],
    "lbp_points": 8,
    "tile_px": 512,
}
DET = "BSExInlens"
PHASE_NAMES = ("void", "bright", "dim", "graphite")


def _pearson(a, b):
    """Pearson correlation of two equally long float64 vectors; 0 if either is constant or empty."""
    if a.size < 2:
        return 0.0
    da, db = a - a.mean(), b - b.mean()
    denom = np.sqrt(np.dot(da, da) * np.dot(db, db))
    return float(np.dot(da, db) / denom) if denom > 0 else 0.0


def _rank(values, kind, levels):
    """Mid-rank (0..1) of each value from a histogram over the fixed range of `kind`."""
    q = quantise(values, kind, levels)
    hist = np.bincount(q, minlength=levels).astype(np.float64)
    return ((np.cumsum(hist) - hist / 2) / max(hist.sum(), 1.0))[q]


def _mutual_information(joint):
    """(MI in bits, MI / smaller marginal entropy) of a joint histogram that sums to 1."""
    px, py = joint.sum(axis=1), joint.sum(axis=0)
    nz = joint > 0
    mi = float((joint[nz] * np.log2(joint[nz] / np.outer(px, py)[nz])).sum())
    hx = float(-(px[px > 0] * np.log2(px[px > 0])).sum())
    hy = float(-(py[py > 0] * np.log2(py[py > 0])).sum())
    return max(mi, 0.0), (max(mi, 0.0) / min(hx, hy) if min(hx, hy) > 0 else 0.0)


def _tile_sum(arr, size):
    """Sum of `arr` inside each tile (fixed order, no positions)."""
    return tiles(arr, size).sum(axis=(1, 2), dtype=np.float64)


def _tile_pearson(a, b, keep, size):
    """Pearson correlation of a and b inside each tile, over the pixels where `keep` is True; 0 where undefined."""
    k = keep.astype(np.float64)
    a, b = a.astype(np.float64) * k, b.astype(np.float64) * k
    n = np.maximum(_tile_sum(k, size), 1.0)
    sa, sb = _tile_sum(a, size), _tile_sum(b, size)
    cov = _tile_sum(a * b, size) - sa * sb / n
    var = (_tile_sum(a * a, size) - sa * sa / n) * (_tile_sum(b * b, size) - sb * sb / n)
    return np.where(var > 0, cov / np.sqrt(np.maximum(var, 1e-300)), 0.0)


def _dithered(crop):
    """{view: (BSE, Inlens)} at full resolution with the sub-grey-level dither described in the docstring."""
    rng = np.random.default_rng(crop.anchors["seed"] + 101)
    shape = crop.shape
    bse_step = (rng.random(shape, dtype=np.float32) - np.float32(0.5)) / np.float32(crop.anchors["scale"])
    raw = crop.view("Inlens", "raw")
    hist = np.bincount(raw.ravel(), minlength=256).astype(np.float64)
    inlens_step = (rng.random(shape, dtype=np.float32) - np.float32(0.5)) * (hist / hist.sum()).astype(np.float32)[raw]
    return {view: (crop.view("BSE", view) + bse_step, crop.view("Inlens", view) + inlens_step)
            for view in ("harmonised", "anchored")}


def _agreement(res, views, ok, graphite, cfg):
    """Pearson, Spearman, mutual information and the joint histogram at every scale."""
    levels = cfg["hist_levels"]
    per_tile = []
    for view, (bse_full, inlens_full) in views.items():
        for s in cfg["scales"]:
            keep = ok if s == 1 else block_mean(ok, s) == 1
            bse, inlens = block_mean(bse_full, s), block_mean(inlens_full, s)
            b, i = bse[keep].astype(np.float64), inlens[keep].astype(np.float64)
            meta = dict(length_um=PX_NM * s / 1000, tag="mixed")
            res.scalar(DET, view, PX_NM * s, "pearson", _pearson(b, i), **meta)
            res.scalar(DET, view, PX_NM * s, "spearman",
                       _pearson(_rank(b, "BSE", cfg["rank_levels"]), _rank(i, "Inlens", cfg["rank_levels"])), **meta)
            joint = np.bincount(quantise(b, "BSE", levels) * levels + quantise(i, "Inlens", levels),
                                minlength=levels * levels).astype(np.float64)
            joint /= max(joint.sum(), 1.0)
            mi, mi_norm = _mutual_information(joint.reshape(levels, levels))
            res.scalar(DET, view, PX_NM * s, "mi_bits", mi, **meta)
            res.scalar(DET, view, PX_NM * s, "mi_norm", mi_norm, **meta)
            if view == "harmonised":
                res.block(DET, view, PX_NM * s, "joint_hist", joint, **meta)
                per_tile.append(_tile_pearson(bse, inlens, keep, cfg["tile_px"] // s))
                inside = (graphite & ok) if s == 1 else block_mean(graphite & ok, s) == 1
                res.scalar(DET, view, PX_NM * s, "pearson_graphite",
                           _pearson(bse[inside].astype(np.float64), inlens[inside].astype(np.float64)), **meta)
    res.tile_block(DET, "harmonised", PX_NM, "tile_pearson", np.stack(per_tile, axis=1),
                   length_um=PX_NM * max(cfg["scales"]) / 1000, tag="mixed")


def _per_phase(res, crop, views, label, ok, grad_mag, cfg):
    """Inlens statistics inside each exclusive BSE phase."""
    n_phase = len(PHASE_NAMES)
    lab = label[ok]
    count = np.bincount(lab, minlength=n_phase).astype(np.float64)
    safe = np.maximum(count, 1.0)
    anchored, harmonised = views["anchored"][1][ok], views["harmonised"][1][ok].astype(np.float64)
    mean = np.bincount(lab, weights=anchored, minlength=n_phase) / safe
    m1 = np.bincount(lab, weights=harmonised, minlength=n_phase) / safe
    m2 = np.bincount(lab, weights=harmonised * harmonised, minlength=n_phase) / safe
    std = np.sqrt(np.maximum(m2 - m1 * m1, 0.0))
    grad = np.bincount(lab, weights=grad_mag[ok], minlength=n_phase) / safe
    top = np.bincount(lab[anchored > 0.9], minlength=n_phase) / safe
    bottom = np.bincount(lab[anchored < 0.1], minlength=n_phase) / safe

    # quantiles from the per-phase histogram of stored Inlens grey levels, read on the crop-wide rank scale
    raw = crop.view("Inlens", "raw")[ok]
    by_level = np.bincount(lab.astype(np.int64) * 256 + raw, minlength=n_phase * 256).reshape(n_phase, 256).astype(np.float64)
    whole = np.bincount(crop.view("Inlens", "raw").ravel(), minlength=256).astype(np.float64)
    upper = np.cumsum(whole) / whole.sum()                       # crop-wide rank at the top of each grey level
    lower = upper - whole / whole.sum()

    bins = cfg["phase_hist_bins"]
    q = np.clip(np.floor(anchored * bins), 0, bins - 1).astype(np.int64)
    hist = np.bincount(lab.astype(np.int64) * bins + q, minlength=n_phase * bins).reshape(n_phase, bins) / safe[:, None]

    for k, name in enumerate(PHASE_NAMES):
        there = count[k] > 0
        a = dict(length_um=PX_NM / 1000, tag="mixed")
        res.scalar(DET, "anchored", PX_NM, f"inlens_mean_{name}", mean[k] if there else 0.5, **a)
        cum = np.cumsum(by_level[k])
        for pct in (10, 50, 90):
            value = 0.5
            if there:
                target = pct / 100 * count[k]
                level = int(min(np.searchsorted(cum, target), 255))
                below = cum[level - 1] if level > 0 else 0.0
                value = lower[level] + (target - below) / max(by_level[k, level], 1.0) * (upper[level] - lower[level])
            res.scalar(DET, "anchored", PX_NM, f"inlens_p{pct}_{name}", value, **a)
        res.scalar(DET, "anchored", PX_NM, f"inlens_top10_share_{name}", top[k] if there else 0.1, **a)
        res.scalar(DET, "anchored", PX_NM, f"inlens_bot10_share_{name}", bottom[k] if there else 0.1, **a)
        if name != "graphite":
            g = by_level[PHASE_NAMES.index("graphite")]
            pairs = count[k] * g.sum()
            auc = float((by_level[k] * (np.cumsum(g) - g / 2)).sum() / pairs) if pairs > 0 else 0.5
            res.scalar(DET, "anchored", PX_NM, f"inlens_auc_{name}", auc, **a)
        res.scalar(DET, "harmonised", PX_NM, f"inlens_std_{name}", std[k], **a)
        res.scalar(DET, "harmonised", PX_NM, f"inlens_grad_{name}", grad[k], length_um=2 * PX_NM / 1000, tag="mixed")
    res.block(DET, "anchored", PX_NM, "inlens_hist_by_phase", hist.ravel(), length_um=PX_NM / 1000, tag="mixed")

    per_tile = []
    for k in range(n_phase):
        inside = (label == k) & ok
        n = _tile_sum(inside, cfg["tile_px"])
        per_tile.append(np.where(n > 0, _tile_sum(views["anchored"][1] * inside, cfg["tile_px"]) / np.maximum(n, 1), 0.5))
    res.tile_block(DET, "anchored", PX_NM, "tile_inlens_by_phase", np.stack(per_tile, axis=1),
                   length_um=PX_NM / 1000, tag="mixed")


def _distance_to(mask):
    """Distance (px) of every pixel to the nearest True pixel of `mask`, 0 inside it. An empty map gives a distance
    beyond any band used here (scipy's transform would otherwise measure from a point outside the array)."""
    if not mask.any():
        return np.full(mask.shape, 1e6, np.float32)
    return ndi.distance_transform_edt(~mask).astype(np.float32)


def _profile(values, mask, d_in, d_out, ok, cfg):
    """Mean of `values` against distance to the boundary of `mask`: n_in steps inside (deepest first), n_out outside."""
    n_in, n_out = cfg["profile_inside_px"], cfg["profile_outside_px"]
    step = np.where(mask, n_in - np.ceil(d_in), n_in - 1 + np.ceil(d_out)).astype(np.int64)
    keep = ok & (step >= 0) & (step < n_in + n_out)
    total = np.bincount(step[keep], weights=values[keep], minlength=n_in + n_out)
    n = np.bincount(step[keep], minlength=n_in + n_out)
    return np.where(n > 0, total / np.maximum(n, 1), 0.5)


def _boundaries(res, crop, inlens, ok, graphite, cfg):
    """Inlens rank across the void and bright boundaries; returns the distance to the bright map for the shell."""
    r0, r1 = cfg["rim_px"]
    outside = {}
    for name in ("void", "bright"):
        mask = crop.phase(name)
        outside[name] = _distance_to(mask)
        profile = _profile(inlens, mask, ndi.distance_transform_edt(mask), outside[name], ok, cfg)
        res.block(DET, "anchored", PX_NM, f"inlens_profile_{name}", profile,
                  length_um=cfg["profile_outside_px"] * PX_NM / 1000, tag="mixed")
    interior = graphite & ok & (outside["void"] > cfg["interior_px"]) & (outside["bright"] > cfg["interior_px"])
    base = float(inlens[interior].mean()) if interior.any() else 0.5
    for name in ("void", "bright"):
        rim = ok & (outside[name] > r0 - 1) & (outside[name] <= r1) & ~crop.phase(name)
        value = float(inlens[rim].mean()) - base if rim.any() else 0.0
        res.scalar(DET, "anchored", PX_NM, f"inlens_rim_{name}", value, length_um=r1 * PX_NM / 1000, tag="mixed")
    return outside["bright"]


def _lags(res, bse, inlens, ok, cfg):
    """Correlation of BSE with a displaced Inlens, along x and along y, and the displacement of its peak."""
    n = cfg["lag_max_px"]
    zb, zi = bse.astype(np.float64), inlens.astype(np.float64)
    for z in (zb, zi):
        z -= z[ok].mean()
        z /= max(z[ok].std(), 1e-12)
        z[~ok] = 0.0
    for axis, name in ((1, "x"), (0, "y")):
        curve = []
        for lag in range(-n, n + 1):
            a = zb[:, max(-lag, 0):zb.shape[1] - max(lag, 0)] if axis == 1 else zb[max(-lag, 0):zb.shape[0] - max(lag, 0)]
            b = zi[:, max(lag, 0):zi.shape[1] - max(-lag, 0)] if axis == 1 else zi[max(lag, 0):zi.shape[0] - max(-lag, 0)]
            curve.append(float((a * b).mean()))
        curve = np.array(curve)
        k = int(np.argmax(curve))
        shift = float(k - n)
        if 0 < k < 2 * n:
            bend = curve[k - 1] - 2 * curve[k] + curve[k + 1]
            if bend < 0:
                shift += 0.5 * (curve[k - 1] - curve[k + 1]) / bend
        res.block(DET, "anchored", PX_NM, f"xcorr_{name}", curve, length_um=n * PX_NM / 1000, tag="mixed")
        res.scalar(DET, "anchored", PX_NM, f"shift_{name}_nm", shift * PX_NM, length_um=n * PX_NM / 1000, tag="imaging")


def _gradients(res, bse, inlens, ok, cfg):
    """Agreement of the two detectors' gradients at each sigma; returns the Inlens gradient magnitude at the first
    sigma (1 px) for the per-phase statistics."""
    first = None
    for sigma in cfg["grad_sigmas_px"]:
        bx, by = (ndi.gaussian_filter(bse, sigma, order=o) for o in ((0, 1), (1, 0)))
        ix, iy = (ndi.gaussian_filter(inlens, sigma, order=o) for o in ((0, 1), (1, 0)))
        mag_b, mag_i = np.hypot(bx, by), np.hypot(ix, iy)
        if first is None:
            first = mag_i
        meta = dict(length_um=sigma * PX_NM / 1000, tag="mixed")
        pick = lambda z: z[ok].astype(np.float64)                 # noqa: E731
        res.scalar(DET, "harmonised", PX_NM, f"gradx_corr_s{sigma}", _pearson(pick(bx), pick(ix)), **meta)
        res.scalar(DET, "harmonised", PX_NM, f"grady_corr_s{sigma}", _pearson(pick(by), pick(iy)), **meta)
        res.scalar(DET, "harmonised", PX_NM, f"gradmag_corr_s{sigma}", _pearson(pick(mag_b), pick(mag_i)), **meta)
        weight = pick(mag_b) * pick(mag_i)
        dot = pick(bx) * pick(ix) + pick(by) * pick(iy)
        total = weight.sum()
        align = float((2 * dot * dot / np.maximum(weight, 1e-30) - weight).sum() / total) if total > 0 else 0.0
        res.scalar(DET, "harmonised", PX_NM, f"grad_align_s{sigma}", align, **meta)
    return first


def _shell(res, crop, ok, d_bright_mid, cfg):
    """The dark-grey share of the shell around the bright grains, on the three bright maps, and its void enrichment."""
    lo_px, hi_px = cfg["shell_px"]
    g_lo, g_hi = cfg["shell_grey_g"]
    blurred = ndi.gaussian_filter(crop.view("BSE", "harmonised"), cfg["shell_blur_sigma_px"])
    darkgrey = (blurred >= g_lo) & (blurred < g_hi)
    meta = dict(length_um=hi_px * PX_NM / 1000)
    for band in ("lo", "mid", "hi"):
        dist = d_bright_mid if band == "mid" else _distance_to(crop.phase(f"bright_{band}"))
        shell = ok & (dist >= lo_px) & (dist <= hi_px)
        res.scalar("BSE", "harmonised", PX_NM, f"shell_darkgrey_frac_{band}", darkgrey[shell].mean() if shell.any() else 0.0,
                   tag="mixed", **meta)
        if band == "mid":
            n = _tile_sum(shell, cfg["tile_px"])
            per_tile = np.where(n > 0, _tile_sum(darkgrey & shell, cfg["tile_px"]) / np.maximum(n, 1), 0.0)
            res.tile_block("BSE", "harmonised", PX_NM, "tile_shell_darkgrey", per_tile[:, None], tag="mixed", **meta)
            void, elsewhere = crop.phase("void"), ok & ~crop.phase("bright")
            base = void[elsewhere].mean() if elsewhere.any() else 0.0
            enrich = void[shell].mean() / base if shell.any() and base > 0 else 1.0
            res.scalar("BSE", "phase", PX_NM, "shell_void_enrich", enrich, tag="material", **meta)


def lbp_codes(img, radius, points=8):
    """(code, direction) of every pixel, both uint8; the margin and undefined directions hold 255.

    Neighbour k sits at angle 2 pi k / points on a circle of `radius` px (counter-clockwise from +x as the picture
    is displayed) and is read bilinearly; its bit is neighbour >= centre. Code = number of set bits if the circle
    has at most two 0/1 changes (a uniform pattern), else points + 1: rotation-invariant.
    Direction = the middle of the run of set bits of a uniform pattern with both set and clear bits, in steps of
    180 / points degrees: where the brighter side lies. A margin of ceil(radius) + 1 px is left out, nothing is padded.
    """
    m = int(np.ceil(radius)) + 1
    h, w = img.shape[0] - 2 * m, img.shape[1] - 2 * m
    centre = img[m:m + h, m:m + w]
    bits = []
    for k in range(points):
        angle = 2 * np.pi * k / points
        dy, dx = round(-radius * np.sin(angle), 9), round(radius * np.cos(angle), 9)
        y0, x0 = int(np.floor(dy)), int(np.floor(dx))
        fy, fx = np.float32(dy - y0), np.float32(dx - x0)
        neighbour = np.zeros((h, w), np.float32)
        for oy, ox, weight in ((0, 0, (1 - fy) * (1 - fx)), (0, 1, (1 - fy) * fx), (1, 0, fy * (1 - fx)), (1, 1, fy * fx)):
            if weight > 0:
                neighbour += np.float32(weight) * img[m + y0 + oy:m + y0 + oy + h, m + x0 + ox:m + x0 + ox + w]
        bits.append(neighbour >= centre)
    ones = np.zeros((h, w), np.uint8)
    changes = np.zeros((h, w), np.uint8)
    start = np.zeros((h, w), np.uint8)                              # first set bit of the run (uniform patterns only)
    for k in range(points):
        ones += bits[k]
        changes += bits[k] != bits[(k + 1) % points]
        start += np.uint8(k) * (bits[k] & ~bits[k - 1])
    uniform = changes <= 2
    codes = np.full(img.shape, 255, np.uint8)
    codes[m:m + h, m:m + w] = np.where(uniform, ones, points + 1)
    direction = np.full(img.shape, 255, np.uint8)
    middle = (2 * start.astype(np.int16) + ones - 1) % (2 * points)
    direction[m:m + h, m:m + w] = np.where(uniform & (ones > 0) & (ones < points), middle, 255)
    return codes, direction


def lbp_riu2(img, radius, points=8):
    """Histogram (points + 2 bins, sums to 1) of the codes of lbp_codes."""
    codes, _ = lbp_codes(img, radius, points)
    return np.bincount(codes[codes != 255], minlength=points + 2) / max(int((codes != 255).sum()), 1)


def _patterns(res, crop, cfg):
    for view in ("harmonised", "anchored"):
        inlens = crop.view("Inlens", view)
        per_tile = []
        for radius in cfg["lbp_radii_px"]:
            n_dir = 2 * cfg["lbp_points"]
            codes, direction = lbp_codes(ndi.gaussian_filter(inlens, radius / 2), radius, cfg["lbp_points"])
            coded, edge = codes != 255, (codes >= 3) & (codes <= 5)
            hist = np.bincount(codes[coded], minlength=cfg["lbp_points"] + 2) / max(int(coded.sum()), 1)
            meta = dict(length_um=radius * PX_NM / 1000, tag="mixed")
            res.scalar("Inlens", view, PX_NM, f"lbp_edge_r{radius}", hist[3:6].sum(), **meta)
            res.scalar("Inlens", view, PX_NM, f"lbp_spot_r{radius}", hist[0] + hist[cfg["lbp_points"]], **meta)
            res.block("Inlens", view, PX_NM, f"lbp_riu2_r{radius}", hist, **meta)
            by_direction = np.bincount(direction[edge], minlength=n_dir)[:n_dir].astype(np.float64)
            phi = np.arange(n_dir) * 2 * np.pi / n_dir
            total = by_direction.sum()
            res.scalar("Inlens", view, PX_NM, f"lbp_edge_cos2_r{radius}",
                       (by_direction * np.cos(2 * phi)).sum() / total if total > 0 else 0.0, **meta)
            res.scalar("Inlens", view, PX_NM, f"lbp_edge_sin2_r{radius}",
                       (by_direction * np.sin(2 * phi)).sum() / total if total > 0 else 0.0, **meta)
            res.block("Inlens", view, PX_NM, f"lbp_edge_dir_r{radius}", by_direction / max(int(coded.sum()), 1), **meta)
            per_tile.append(_tile_sum(edge, cfg["tile_px"]) / np.maximum(_tile_sum(coded, cfg["tile_px"]), 1))
        res.tile_block("Inlens", view, PX_NM, "tile_lbp_edge", np.stack(per_tile, axis=1),
                       length_um=max(cfg["lbp_radii_px"]) * PX_NM / 1000, tag="mixed")


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    ok = crop.valid
    void, bright, dim = crop.phase("void"), crop.phase("bright"), crop.phase("dim")
    label = np.full(crop.shape, PHASE_NAMES.index("graphite"), np.uint8)       # exclusive, void first
    label[dim] = PHASE_NAMES.index("dim")
    label[bright] = PHASE_NAMES.index("bright")
    label[void] = PHASE_NAMES.index("void")
    graphite = label == PHASE_NAMES.index("graphite")

    views = _dithered(crop)
    _agreement(res, views, ok, graphite, cfg)
    grad_mag = _gradients(res, crop.view("BSE", "harmonised"), crop.view("Inlens", "harmonised"), ok, cfg)
    _per_phase(res, crop, views, label, ok, grad_mag, cfg)
    d_bright = _boundaries(res, crop, views["anchored"][1], ok, graphite, cfg)
    _lags(res, crop.view("BSE", "anchored"), crop.view("Inlens", "anchored"), ok, cfg)
    _shell(res, crop, ok, d_bright, cfg)
    _patterns(res, crop, cfg)
    return res
