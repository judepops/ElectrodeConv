"""Final 3-phase segmenter for the BSE + Inlens + SE/ETD SEM cross-sections of the graphite/Si anode.

    labels, conf = segment(bse, inlens, se)       # 0 pore, 1 graphite/carbon, 2 Si-like, 255 excluded (not electrode)
    P = estimate_params(bse, inlens, se); labels, conf = segment(tile_b, tile_i, tile_s, params=P, offset=(r0, c0))

Base method: m4_cluster (winner of the seg3 comparison, see DECISION.md): a per-image, unsupervised Gaussian
mixture on 5 physically normalised features from all three detectors, with components named by physical rules.
Grafts (each fixes a documented m4 error; DECISION.md has the evidence):
  G1 soft component naming      p(pore) = sum_k posterior_k * (share of component k's pixels that the pore rule
                                 calls pore) instead of a hard 0/1 name per component. Removes the naming flip
                                 that moved m4's cfe5vt7s pore fraction by +8 points under small perturbations.
  G2 smooth cut-plane veto      (m1_rules / characterisation) smooth in Inlens AND SE, on the SE plane and above
                                 0.6 gu = cut-plane carbon, never pore (uhdslk0o flake interiors called pore).
  G3 recess growth              (m1_rules geodesic growth / m3_dino back-wall seeds) SE-shaded (dev < -3.5)
                                 material below 1.15 gu, >= 9 px wide and touching a pore = pore (71vgq3fw
                                 sub-surface rounded particle called graphite).
  G4 Si rescue                  (m1_rules) an object at the Si-mode brightness (>= 0.9 x mode), raised in SE
                                 (>= +3) with smooth Inlens is cut-plane Si even if milling striations make its SE
                                 rough; m4's debris rule had dropped real particles (rxax5ozo 9.2k px, fzrt2k6r).
  G5 dim-sliver reject          (judges' Si lens / m3 object width rule) objects whose interior BSE is < 0.82 x
                                 the Si mode and whose inscribed radius is < 10 px are edge-lit rims -> carbon
                                 (iv6g2oq0 rim band, 71vgq3fw sliver).
  G6 mixture ensemble           48 fits (seeds 0-47) on rounded z-scores, soft pore probabilities averaged; all
                                 480 component densities evaluated as one quadratic-feature matrix product.
  G7 tilted back wall           (refinement round 1) region-level: tilt-brightened BSE (>= 1.22 gu), raised and rough
                                 SE, BSE/Inlens texture below cut-plane CBD level, >= 60% pore-enclosed -> pore
                                 (pl8uabbv nodular cavity, avn74qx1 rough body in a pore).
  G8 foreign phase              (refinement round 1) BSE >= 1.4 x Si mode in >= 2000 px regions -> label 255,
                                 excluded from phase fractions (Cu current-collector foil in epqdaau9).
Full-size images: the expensive per-pixel features and mixture posteriors are computed in overlapping tiles and
stitched; all region-level steps (Potts smoothing, recess growth, Si objects) run once on the stitched maps, so
there are no tile seams in object decisions.
"""
import math
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy import ndimage as ndi
from scipy.signal import find_peaks
from skimage.filters import rank
from skimage.morphology import disk, remove_small_holes, remove_small_objects
from sklearn.mixture import GaussianMixture

K = 10                      # mixture components
SEED = 0
N_ENS = 48                  # G6: mixtures fitted with seeds SEED..SEED+N_ENS-1; their pore probabilities are averaged.
                            # Single fits land in a few discrete optima whose pore shares differ by up to ~4 points, so
                            # the ensemble mean is a Monte-Carlo average over optima: 4 members left +-1-2 points.
Z_ROUND = 3                 # G6: z-scored fit data rounded to 1e-3 (z_mu / z_sd to 1e-4), so float-level input noise
                            # (e.g. an exact BSE black-level shift) gives a bit-identical fit
N_FIT = 60000               # pixels used to fit the mixture
ANCHOR_WIN = 448            # local graphite anchor window (px); grid step = ANCHOR_WIN / 2
MARGIN = 64                 # feature tile margin (sigma-2 std + disk-7 median + destripe profile smoothing)
TILE = 1536
FIT_THREADS = 4             # mixture fits run in 4 threads (about 1.9x faster than serial)
CHUNK_CELLS = 2 ** 24       # ensemble-posterior block size in (rows x members x components) float64 cells (128 MB)
EDGE = 2                    # px dropped at each side (colour-tinted edge columns)

# physical rules (units: BSE gu, roughness x image median, SE plane-noise)
PORE_CORE = 0.5
TEX_INL = 1.8
TEX_SE = 1.8
SMOOTH = 1.25
RECESS = -3.0
PLANE_B = 0.88
TEX_B = 1.8
SI_MIN_SEDEV = 2.0
SI_MAX_SET = 3.0
SI_MIN_RADIUS = 4.0
# grafts
VETO_SEDEV = 3.0            # G2: |SE dev| below this ...
VETO_B = 0.6                # ... and BSE above this, smooth in Inlens and SE -> never pore
VETO_OPEN = 3               # G2: veto regions must contain a disk of this radius
RECESS_GROW = -3.5          # G3: SE dev below this ...
RECESS_B = 1.15             # ... and BSE below this ...
RECESS_OPEN = 4             # ... in regions containing a disk of this radius, touching pore -> pore
RESCUE_REL, RESCUE_SEDEV, RESCUE_SET, RESCUE_INL = 0.9, 3.0, 3.5, 1.6     # G4
SLIVER_REL, SLIVER_RADIUS = 0.82, 10.0                                    # G5
# G7 tilted back wall: region-level features = carbon-only gaussian means (sigma TILT_SIG)
TILT_SIG = 6
TILT_CAND = (1.12, 2.2, 0.0)        # candidate pixels: smoothed b2 >=, SE roughness >=, SE dev >
TILT_OPEN = 4                       # candidate regions must contain a disk of this radius
TILT_AREA = 600                     # px
TILT_B, TILT_SEDEV, TILT_SET = 1.22, 2.0, 3.0      # region medians: raised in BSE and SE, rough SE relief ...
TILT_BT, TILT_INL = 2.4, 2.4                       # ... but not the fine granular texture of cut-plane CBD
TILT_RING = 0.6                     # share of a 10-px ring around the region that is pore
# G8 foreign phase (Cu current collector): BSE >= FOIL_REL x Si mode, region >= FOIL_AREA px -> label EXCLUDED
FOIL_REL, FOIL_AREA = 1.4, 2000
EXCLUDED = 255

GRAFTS = {"G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"}   # all on in production; switchable for the ablation in dev/

COLOURS = np.array([[0x2f, 0x6f, 0xdb], [0x4c, 0xaf, 0x50], [0xf0, 0xa0, 0x20]], np.uint8)
EXCL_COLOUR = np.array([0x9e, 0x9e, 0x9e], np.uint8)          # grey: outside the electrode (G8)
LUT = np.zeros((256, 3), np.uint8); LUT[:3] = COLOURS; LUT[EXCLUDED] = EXCL_COLOUR


# --------------------------------------------------------------------------------------------------- helpers
def lstd(x, s):
    m = ndi.gaussian_filter(x, s)
    m2 = ndi.gaussian_filter(x * x, s)
    return np.sqrt(np.maximum(m2 - m * m, 0))


def hmode(v, lo, hi, bw, sm):
    e = np.arange(lo, hi + bw, bw)
    h, _ = np.histogram(v, e)
    s = ndi.gaussian_filter1d(h.astype(float), sm)
    i = int(np.argmax(s))
    shift = 0.0
    if 0 < i < len(s) - 1:
        a, b, c = s[i - 1], s[i], s[i + 1]
        if a - 2 * b + c != 0:
            shift = 0.5 * (a - c) / (a - 2 * b + c)
    return float(e[i] + (0.5 + shift) * bw)


def tiles(h, w, size=TILE, margin=MARGIN):
    """Yield (inner box, outer box) in image coordinates."""
    for r0 in range(0, h, size):
        for c0 in range(0, w, size):
            r1, c1 = min(r0 + size, h), min(c0 + size, w)
            yield (r0, c0, r1, c1), (max(r0 - margin, 0), max(c0 - margin, 0), min(r1 + margin, h), min(c1 + margin, w))


def destripe(se, row0=0):
    """Remove vertical curtain stripes: subtract the high-pass part of the column-median profile in 256-row blocks.
    Blocks are aligned to image rows (row0 = tile offset), so tiles and whole images destripe identically."""
    out = se.copy()
    start = -(row0 % 256)
    for r in range(start, se.shape[0], 256):
        a, b = max(r, 0), min(r + 256, se.shape[0])
        if b <= a:
            continue
        prof = np.median(se[a:b], axis=0)
        out[a:b] -= (prof - ndi.gaussian_filter1d(prof, 15, mode="nearest"))[None, :]
    return out


MED_R = 7


def _rough(x, scale, r=MED_R):
    """Edge-preserving roughness: sigma-2 local std of a sigma-1 pre-blur / image median, then disk-7 median."""
    t = lstd(ndi.gaussian_filter(x, 1), 2) / scale
    q = np.clip(t * 32, 0, 255).astype(np.uint8)
    return rank.median(q, disk(r)).astype(np.float32) / 32


def _se_inl_feats(inl, se, P, row0=0):
    ir = P["inl_lut"][inl]
    inl_t = _rough(ir, P["inl_t0"])
    s = destripe(se.astype(np.float32), row0)
    s1 = np.clip(ndi.gaussian_filter(s, 1), 0, 255).astype(np.uint8)
    se_med = rank.median(s1, disk(4)).astype(np.float32)
    se_dev = (ndi.gaussian_filter(se_med, 1) - P["se_mode"]) / P["se_noise"]
    se_t = _rough(s, P["se_t0"])
    return inl_t, se_dev, se_t


def _anchor_field(shape, offset, P):
    g, step = P["anchor_grid"], P["anchor_step"]
    rr = np.clip((np.arange(shape[0]) + offset[0]) / step, 0, g.shape[0] - 1)
    cc = np.clip((np.arange(shape[1]) + offset[1]) / step, 0, g.shape[1] - 1)
    r0 = np.floor(rr).astype(int); r1 = np.minimum(r0 + 1, g.shape[0] - 1); fr = (rr - r0)[:, None]
    c0 = np.floor(cc).astype(int); c1 = np.minimum(c0 + 1, g.shape[1] - 1); fc = (cc - c0)[None, :]
    top = g[r0][:, c0] * (1 - fc) + g[r0][:, c1] * fc
    bot = g[r1][:, c0] * (1 - fc) + g[r1][:, c1] * fc
    return (top * (1 - fr) + bot * fr).astype(np.float32)


FEATS = ("b2", "b15", "bt", "inlt", "sedev", "set")


def features(bse, inl, se, P, offset=(0, 0)):
    inl_t, se_dev, se_t = _se_inl_feats(inl, se, P, offset[0])
    G = _anchor_field(bse.shape, offset, P)
    b = (bse.astype(np.float32) - P["black"]) / np.maximum(G - P["black"], 1.0)
    return {"b2": ndi.gaussian_filter(b, 2), "b15": ndi.gaussian_filter(b, 1.5),
            "bt": _rough(b, P["b_t0"]), "inlt": inl_t, "sedev": se_dev, "set": se_t}


def design(F):
    return np.stack([np.clip(F["b2"], -0.3, 3.2), np.log(F["bt"] + 0.3), np.log(F["inlt"] + 0.3),
                     np.arcsinh(np.clip(F["sedev"], -25, 25) / 2.0), np.log(F["set"] + 0.3)], axis=-1).reshape(-1, 5)


def pore_rule(b, inlt, sedev, set_, P):
    """Pixel-level version of the m4 naming rule (used for soft component naming)."""
    rough = (set_ > TEX_SE) | (inlt > TEX_INL)
    mid = (b < 1.15) & ((sedev < RECESS) | (rough & ((b < PLANE_B) | (sedev < -1.5))))
    bright_through = (b >= P["t_si"]) & (sedev < 1.0) & (inlt > TEX_INL) & (b < 0.92 * P["si_mode"])
    return (b < PORE_CORE) | ((b < P["t_si"]) & mid) | bright_through


# ------------------------------------------------------------------------------------- per-image statistics
def _bright_mode(vals):
    edges = np.arange(1.25, 3.41, 0.01)
    hist = ndi.gaussian_filter1d(np.histogram(vals, edges)[0].astype(float), 3)
    centres = (edges[:-1] + edges[1:]) / 2
    peaks, _ = find_peaks(hist, prominence=hist.max() * 0.05 if hist.max() > 0 else 1)
    for i in peaks[np.argsort(-hist[peaks])]:
        if 1.5 <= centres[i] <= 3.2 and (np.abs(vals - centres[i]) < 0.05).mean() >= 0.002:
            return float(centres[i])
    cores = vals[vals > 1.55]
    if cores.size >= 0.002 * vals.size:
        return float(np.clip(np.median(cores), 1.5, 3.2))
    return 2.1


def estimate_params(bse, inl, se):
    """All per-image statistics + the fitted, softly named mixture. Run once on the whole (edge-cropped) image."""
    H, W = bse.shape
    P = {}
    sub_b = ndi.gaussian_filter(bse.astype(np.float32), 2)[::2, ::2].ravel()
    P["black"] = float(np.percentile(sub_b, 0.5))
    lo, hi = np.percentile(sub_b, [15, 92])
    g_glob = hmode(sub_b[(sub_b >= lo) & (sub_b <= hi)], lo, hi, 0.25, 4)
    del sub_b
    h = np.bincount(inl.ravel(), minlength=256).astype(np.float64)
    P["inl_lut"] = ((np.cumsum(h) - h / 2) / h.sum()).astype(np.float32)
    s2_sub, sstd_sub, set_sub, it_sub, bt_sub = [], [], [], [], []
    for (r0, c0, r1, c1), (R0, C0, R1, C1) in tiles(H, W):
        s = destripe(se[R0:R1, C0:C1].astype(np.float32), R0)
        sl = (slice(r0 - R0, r1 - R0), slice(c0 - C0, c1 - C0))
        s2_sub.append(ndi.gaussian_filter(s, 2)[sl][::2, ::2].ravel())
        sstd_sub.append(lstd(ndi.gaussian_filter(s, 1), 6)[sl][::4, ::4].ravel())
        set_sub.append(lstd(ndi.gaussian_filter(s, 1), 2)[sl][::4, ::4].ravel())
        ir = P["inl_lut"][inl[R0:R1, C0:C1]]
        it_sub.append(lstd(ndi.gaussian_filter(ir, 1), 2)[sl][::4, ::4].ravel())
        bt_sub.append(lstd(ndi.gaussian_filter(bse[R0:R1, C0:C1].astype(np.float32), 1), 2)[sl][::4, ::4].ravel())
    s2_sub = np.concatenate(s2_sub)
    P["se_mode"] = hmode(s2_sub, *np.percentile(s2_sub, [20, 95]), 0.25, 4)
    P["se_noise"] = float(max(np.median(np.concatenate(sstd_sub)), 0.5))
    P["se_t0"] = float(max(np.median(np.concatenate(set_sub)), 1e-3))
    P["inl_t0"] = float(max(np.median(np.concatenate(it_sub)), 1e-4))
    P["b_t0"] = float(max(np.median(np.concatenate(bt_sub)), 1e-3)) / max(g_glob - P["black"], 1.0)
    del s2_sub, sstd_sub, set_sub, it_sub, bt_sub
    # local graphite anchor: median raw BSE (blur 2) of smooth cut-plane pixels per 448-px window
    step = ANCHOR_WIN // 2
    gr, gc = int(math.ceil(H / step)) + 1, int(math.ceil(W / step)) + 1
    smooth_vals = [[[] for _ in range(gc)] for _ in range(gr)]
    for (r0, c0, r1, c1), (R0, C0, R1, C1) in tiles(H, W):
        inl8, sdev, stex = _se_inl_feats(inl[R0:R1, C0:C1], se[R0:R1, C0:C1], P, R0)
        b2 = ndi.gaussian_filter(bse[R0:R1, C0:C1].astype(np.float32), 2)
        bg = (b2 - P["black"]) / max(g_glob - P["black"], 1.0)
        sm = (inl8 < SMOOTH) & (stex < SMOOTH) & (np.abs(sdev) < 3) & (bg > 0.6) & (bg < 1.3)
        sl = (slice(r0 - R0, r1 - R0), slice(c0 - C0, c1 - C0))
        sm, b2 = sm[sl], b2[sl]
        rr, cc = np.nonzero(sm[::2, ::2])
        vv = b2[::2, ::2][rr, cc]
        rr = rr * 2 + r0
        cc = cc * 2 + c0
        for i in range(max(0, (r0 - step) // step), min(gr, r1 // step + 2)):
            for j in range(max(0, (c0 - step) // step), min(gc, c1 // step + 2)):
                m = (np.abs(rr - i * step) <= step) & (np.abs(cc - j * step) <= step)
                if m.any():
                    smooth_vals[i][j].append(vv[m])
    grid = np.full((gr, gc), np.nan, np.float32)
    for i in range(gr):
        for j in range(gc):
            v = np.concatenate(smooth_vals[i][j]) if smooth_vals[i][j] else np.empty(0)
            if v.size >= 750:
                grid[i, j] = np.median(v)
    del smooth_vals
    if np.isnan(grid).all():
        grid[:] = g_glob
    else:
        idx = ndi.distance_transform_edt(np.isnan(grid), return_distances=False, return_indices=True)
        grid = ndi.gaussian_filter(grid[tuple(idx)], 0.7, mode="nearest")
    P["anchor_grid"] = np.clip(grid, g_glob - 0.25 * (g_glob - P["black"]), g_glob + 0.25 * (g_glob - P["black"]))
    P["anchor_step"] = step
    P["graphite_global"] = g_glob
    # fixed-stride subsample -> Si mode + mixture fit
    X, bvals, phys = [], [], []
    stride = max(1, int(math.sqrt(H * W / N_FIT)))
    for (r0, c0, r1, c1), (R0, C0, R1, C1) in tiles(H, W):
        F = features(bse[R0:R1, C0:C1], inl[R0:R1, C0:C1], se[R0:R1, C0:C1], P, (R0, C0))
        sl = (slice(r0 - R0, r1 - R0), slice(c0 - C0, c1 - C0))
        F = {k: v[sl] for k, v in F.items()}
        rs, cs = slice((-r0) % stride, None, stride), slice((-c0) % stride, None, stride)
        Fs = {k: v[rs, cs] for k, v in F.items()}
        X.append(design(Fs))
        phys.append(np.stack([Fs[k].ravel() for k in ("b2", "bt", "inlt", "sedev", "set")], 1))
        bvals.append(F["b15"][::2, ::2].ravel())
        del F
    X, phys = np.concatenate(X), np.concatenate(phys)
    P["si_mode"] = _bright_mode(np.concatenate(bvals))
    P["t_si"] = (1.0 + P["si_mode"]) / 2
    mu, sd = np.round(X.mean(0), 4), np.round(X.std(0), 4) + 1e-4
    P["z_mu"], P["z_sd"] = mu, sd
    Z = np.round((X - mu) / sd, Z_ROUND)
    P["gmms"], P["comp_pore"], P["comp_stats"] = [], [], []
    fit = lambda e: GaussianMixture(K, covariance_type="full", random_state=SEED + e, n_init=1, max_iter=300,
                                    reg_covar=1e-3).fit(Z)
    with ThreadPoolExecutor(FIT_THREADS) as ex:           # independent fits; results identical to a serial loop
        gmms = list(ex.map(fit, range(N_ENS if "G6" in GRAFTS else 1)))
    for gmm in gmms:
        stats, score = name_components(gmm.predict_proba(Z), phys, P)
        P["gmms"].append(gmm)
        P["comp_pore"].append(score)
        P["comp_stats"].append(stats)
    P["ens_W"], P["ens_S"] = _pack_ensemble(P["gmms"], P["comp_pore"])
    return P


_IU = np.triu_indices(5)


def _pack_ensemble(gmms, scores):
    """Each component's Gaussian log-density (+ log weight) as a linear map of the quadratic features
    [x_i x_j (i<=j), x, 1], so the whole ensemble's log-densities are one matrix product per block."""
    cols = []
    for g in gmms:
        for k in range(g.n_components):
            L = g.precisions_cholesky_[k]
            prec, m = L @ L.T, g.means_[k]
            quad = -0.5 * prec[_IU] * np.where(_IU[0] == _IU[1], 1.0, 2.0)
            const = -0.5 * m @ prec @ m + np.log(np.diag(L)).sum() - 2.5 * np.log(2 * np.pi) + np.log(g.weights_[k])
            cols.append(np.concatenate([quad, prec @ m, [const]]))
    return np.array(cols).T, np.array(scores, np.float32)          # (21, M*K), (M, K)


def name_components(resp, phys, P):
    """G1 soft naming: pore score of component k = responsibility-weighted share of its subsample pixels that the
    pixel-level pore rule calls pore. A component that straddles a rule threshold contributes proportionally
    instead of flipping between 0 and 1 when the fit moves slightly."""
    names = ["b2", "bt", "inlt", "sedev", "set"]
    is_pore = pore_rule(phys[:, 0], phys[:, 2], phys[:, 3], phys[:, 4], P).astype(np.float64)
    hard = resp.argmax(1)
    stats, score = [], []
    for k in range(resp.shape[1]):
        w = resp[:, k]
        sw = max(w.sum(), 1e-9)
        s = {n: float((phys[:, i] * w).sum() / sw) for i, n in enumerate(names)}
        s["weight"] = float(w.mean())
        s["pore_score"] = float((is_pore * w).sum() / sw)
        if "G1" not in GRAFTS:            # m4 original: hard name from the medians of hard-assigned pixels
            m = hard == k
            med = np.median(phys[m], 0) if m.sum() >= 20 else np.array([s[n] for n in names])
            s["pore_score"] = float(pore_rule(*[np.array([med[i]]) for i in (0, 2, 3, 4)], P)[0])
        stats.append(s)
        score.append(s["pore_score"])
    return stats, np.array(score, np.float64)


# --------------------------------------------------------------------------------------------- prediction
def pore_prob(F, P):
    """Ensemble-mean soft pore probability: mean over members of sum_k posterior_k * pore_score_k
    (equal to averaging sklearn predict_proba @ score over the members, to ~1e-7)."""
    X = ((design(F) - P["z_mu"]) / P["z_sd"]).astype(np.float32)
    W, SC = P["ens_W"], P["ens_S"]
    M, Kc = SC.shape
    p = np.zeros(X.shape[0], np.float32)
    chunk = max(1024, CHUNK_CELLS // (M * Kc))
    for a in range(0, X.shape[0], chunk):
        x = X[a:a + chunk].astype(np.float64)
        Q = np.concatenate([x[:, _IU[0]] * x[:, _IU[1]], x, np.ones((len(x), 1))], 1)
        ll = (Q @ W).reshape(len(x), M, Kc)
        ll -= ll.max(2, keepdims=True)
        e = np.exp(ll.astype(np.float32))
        p[a:a + chunk] = ((e * SC[None]).sum(2) / e.sum(2)).mean(1)
        del Q, ll, e
    return p.reshape(F["b2"].shape)


def _icm(p_pore, beta=1.2, sweeps=4, sigma=1.5):
    """2-class Potts ICM: log p(class) + beta * 4 * (gaussian-weighted share of neighbours with that class)."""
    d = np.log(np.clip(p_pore, 1e-4, 1)) - np.log(np.clip(1 - p_pore, 1e-4, 1))   # log-odds of pore
    d -= beta * 4                                                                   # pore wins iff d + 8*beta*nb > 0
    lab = p_pore > 0.5
    for _ in range(sweeps):
        nb = ndi.gaussian_filter(lab.astype(np.float32), sigma)
        nb *= 2 * beta * 4
        new = (d + nb) > 0
        del nb
        if (new == lab).all():
            break
        lab = new
    return lab


def _clean_pore(pore):
    pore = remove_small_objects(pore, max_size=15)
    return ~remove_small_objects(~pore, max_size=15, connectivity=1)


def _si_objects(solid, F, P, p_pore):
    """Si-like objects inside the solid: BSE midpoint contour (sigma 1.5) + object vetting on interiors."""
    si = solid & (F["b15"] >= P["t_si"])
    si = ndi.binary_opening(si, structure=disk(2))
    si = remove_small_holes(si, max_size=400)
    si = remove_small_objects(si, max_size=159)
    L, n = ndi.label(si, ndi.generate_binary_structure(2, 2))
    if n == 0:
        return si, np.zeros_like(si)
    idx = np.arange(1, n + 1)
    dist = ndi.distance_transform_edt(si).astype(np.float32)
    width = ndi.maximum(dist, L, idx)
    peak = ndi.maximum(F["b15"], L, idx)
    Li = np.where(dist > 3, L, 0)
    has_in = np.bincount(Li.ravel(), minlength=n + 1)[1:] > 0
    Ls = np.where(np.isin(L, idx[has_in]), Li, L)
    del Li
    core = ndi.mean(F["b2"], Ls, idx)
    sedev = ndi.mean(F["sedev"], Ls, idx)
    bt = ndi.mean(F["bt"], Ls, idx)
    it = ndi.mean(F["inlt"], Ls, idx)
    st = ndi.mean(F["set"], Ls, idx)
    del Ls
    ring = ndi.grey_dilation(L, footprint=disk(8)) * (L == 0)
    ctx = np.nan_to_num(ndi.mean(p_pore, ring, idx), nan=0.0)
    del ring
    rel = core / P["si_mode"]
    through = (sedev < 1.0) & (it > TEX_INL) & (core < 0.92 * P["si_mode"])
    rescue = ("G4" in GRAFTS) & (rel >= RESCUE_REL) & (sedev >= RESCUE_SEDEV) & (st <= RESCUE_SET) & (it <= RESCUE_INL)   # G4
    debris = (st > SI_MAX_SET) & ~through & ~rescue
    cbd = (sedev < SI_MIN_SEDEV) & ((bt > TEX_B) | (it > TEX_INL)) & ~through & ~debris
    sliver = ("G5" in GRAFTS) & (rel < SLIVER_REL) & (width < SLIVER_RADIUS)                                           # G5
    keep = (peak >= P["t_si"] + 0.1) & (width >= SI_MIN_RADIUS) & ~through & ~debris & ~cbd & ~sliver
    to_pore = through | (debris & (ctx > 0.3))
    return np.concatenate([[False], keep])[L], np.concatenate([[False], to_pore])[L]


def _tilted_backwall(pore, F, P):
    """G7: material behind the cut plane whose surface is tilted toward the detector (back walls, nodular CBD
    aggregates and rounded particles seen through a pore). Tilt raises both BSE (b2 1.2-1.5 gu) and SE (dev > 0),
    so the pixel pore rule keeps it solid. Decided per region on carbon-only smoothed features: raised in BSE and
    SE, rough SE relief, BSE/Inlens texture below that of granular cut-plane CBD, and mostly enclosed by pore."""
    carbon = ~pore & (F["b15"] < P["t_si"])
    cw = ndi.gaussian_filter(carbon.astype(np.float32), TILT_SIG)
    np.maximum(cw, 1e-3, out=cw)
    sm = lambda x: ndi.gaussian_filter(np.where(carbon, np.clip(x.astype(np.float32), -20, 20), 0), TILT_SIG) / cw
    Sb2, Sset, Sdev = sm(F["b2"]), sm(F["set"]), sm(F["sedev"])
    cand = carbon & (Sb2 >= TILT_CAND[0]) & (Sset >= TILT_CAND[1]) & (Sdev > TILT_CAND[2])
    cand = ndi.binary_opening(cand, structure=disk(TILT_OPEN))
    L, n = ndi.label(cand)
    del cand
    if n == 0:
        return np.zeros_like(pore)
    idx = np.arange(1, n + 1)
    area = np.bincount(L.ravel(), minlength=n + 1)[1:]
    big = idx[area >= TILT_AREA]
    if big.size == 0:
        return np.zeros_like(pore)
    L = np.where(np.isin(L, big), L, 0)
    med = {k: ndi.median(v, L, big) for k, v in (("b2", Sb2), ("set", Sset), ("sedev", Sdev))}
    del Sb2, Sset, Sdev
    med["bt"] = ndi.median(sm(F["bt"]), L, big)
    med["inlt"] = ndi.median(sm(F["inlt"]), L, big)
    del cw
    ring = ndi.grey_dilation(L, footprint=disk(10)) * (L == 0)
    rp = np.nan_to_num(ndi.mean(pore, ring, big), nan=0.0)
    del ring
    ok = ((med["b2"] >= TILT_B) & (med["sedev"] >= TILT_SEDEV) & (med["set"] >= TILT_SET) & (med["bt"] < TILT_BT)
          & (med["inlt"] < TILT_INL) & (rp >= TILT_RING))
    return np.isin(L, big[ok])


def _foreign(F, P):
    """G8: very bright (>= FOIL_REL x Si mode), large regions are not electrode material (the Cu current collector
    in epqdaau9); the whole bright-phase object containing them is excluded, plus a 2-px margin."""
    core = ndi.binary_opening(F["b2"] >= FOIL_REL * P["si_mode"], structure=disk(3))
    L, n = ndi.label(core)
    if n == 0:
        return np.zeros_like(core)
    area = np.bincount(L.ravel(), minlength=n + 1)[1:]
    core = np.isin(L, np.arange(1, n + 1)[area >= FOIL_AREA])
    if not core.any():
        return core
    Lb, _ = ndi.label(F["b15"] >= P["t_si"])
    hit = np.unique(Lb[core])
    return ndi.binary_dilation(np.isin(Lb, hit[hit > 0]) | core, iterations=2)


def postprocess(F, p_pore, P):
    """Region-level decisions on (stitched) feature maps -> labels, conf."""
    pore = _icm(p_pore)
    # G3 recess growth: SE-shaded, sub-1.15 gu regions >= 9 px wide that touch a pore are pore
    rec = (F["sedev"] < RECESS_GROW) & (F["b2"] < RECESS_B)
    rec = ndi.binary_opening(rec, structure=disk(RECESS_OPEN))
    if rec.any() and "G3" in GRAFTS:
        L, n = ndi.label(rec)
        touch = np.unique(L[ndi.binary_dilation(pore, iterations=2) & rec])
        pore |= np.isin(L, touch[touch > 0])
        del L
    # G2 smooth cut-plane veto
    veto = (F["inlt"] < SMOOTH) & (F["set"] < SMOOTH) & (np.abs(F["sedev"]) < VETO_SEDEV) & (F["b2"] >= VETO_B)
    veto = ndi.binary_opening(veto, structure=disk(VETO_OPEN))
    if "G2" in GRAFTS:
        pore &= ~veto
    del veto, rec
    if "G7" in GRAFTS:
        pore |= _tilted_backwall(pore, F, P)
    pore = _clean_pore(pore)
    excl = _foreign(F, P) if "G8" in GRAFTS else np.zeros_like(pore)
    si, through = _si_objects(~pore & ~excl, F, P, p_pore)
    lab = np.ones(pore.shape, np.uint8)
    lab[pore | through] = 0
    lab[si] = 2
    lab[excl] = EXCLUDED
    conf = ndi.gaussian_filter(np.maximum(p_pore, 1 - p_pore), 1.0).astype(np.float32)
    return lab, conf


def predict_maps(bse, inl, se, P, tile=TILE, margin=MARGIN):
    """Tiled features + pore probability for a whole image, stitched into full-size float32 maps."""
    H, W = bse.shape
    F = {k: np.empty((H, W), np.float16) for k in FEATS}     # float16 storage: thresholds need ~1e-3 precision
    pp = np.empty((H, W), np.float32)
    for (r0, c0, r1, c1), (R0, C0, R1, C1) in tiles(H, W, tile, margin):
        f = features(bse[R0:R1, C0:C1], inl[R0:R1, C0:C1], se[R0:R1, C0:C1], P, (R0, C0))
        sl = (slice(r0 - R0, r1 - R0), slice(c0 - C0, c1 - C0))
        p = pore_prob(f, P)
        for k in FEATS:
            F[k][r0:r1, c0:c1] = f[k][sl]
        pp[r0:r1, c0:c1] = p[sl]
        del f, p
    return F, pp


def segment(bse, inlens, se, params=None, offset=(0, 0)):
    """labels (uint8 HxW: 0 pore, 1 graphite/carbon, 2 Si-like), conf (float32 HxW, pore-vs-solid confidence).
    params=None: the input is one whole image (statistics estimated on it, features tiled internally).
    params given: the input is a tile of the image those params came from, at `offset` (r0, c0)."""
    if params is None:
        P = estimate_params(bse, inlens, se)
        F, pp = predict_maps(bse, inlens, se, P)
    else:
        P = params
        F = features(bse, inlens, se, P, offset)
        pp = pore_prob(F, P)
    return postprocess(F, pp, P)


def segment_image(bse, inlens, se, edge=EDGE):
    """Full-size image: drop `edge` px at each side, segment, pad the dropped columns back by edge replication."""
    sl = (slice(None), slice(edge, -edge)) if edge else (slice(None), slice(None))
    P = estimate_params(bse[sl], inlens[sl], se[sl])
    F, pp = predict_maps(bse[sl], inlens[sl], se[sl], P)
    lab, conf = postprocess(F, pp, P)
    del F, pp
    if edge:
        lab = np.pad(lab, ((0, 0), (edge, edge)), mode="edge")
        conf = np.pad(conf, ((0, 0), (edge, edge)), mode="edge")
    return lab, conf, P


def overlay(bse, labels, alpha=0.5):
    grey = bse.astype(np.float32)[..., None]
    return np.clip((1 - alpha) * grey + alpha * LUT[labels].astype(np.float32), 0, 255).astype(np.uint8)


# ------------------------------------------------------------------------------------------------------ CLI
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.environ.get("LOSSLARP_DATA_DIR", os.path.join(_REPO, "data"))          # Batch_* folders of raw TIFs
OUT = os.path.join(_REPO, "segmentation", "processed", "out")                      # CLI outputs (git-ignored)
CSV_COLS = ["batch", "sample_id", "session_height", "pore", "graphite", "si", "mean_conf", "excluded", "third_detector",
            "width", "si_mode", "t_si", "anchor_min_raw", "anchor_max_raw", "seconds", "peak_rss_mb"]


def list_images(data=DATA):
    """[(batch, sample_id, bse_path, inlens_path, third_path, third_name)] for every field of view."""
    from pathlib import Path
    out = []
    for bdir in sorted(Path(data).glob("Batch_*")):
        for bse in sorted(bdir.glob("img_*_BSE.tif")):
            sid = bse.name[4:-8]
            third = next((bdir / f"img_{sid}_{n}.tif" for n in ("ETD", "SE") if (bdir / f"img_{sid}_{n}.tif").exists()))
            out.append((bdir.name, sid, bse, bdir / f"img_{sid}_Inlens.tif", third, third.stem.split("_")[-1]))
    return out


def _read(path):
    from PIL import Image
    a = np.asarray(Image.open(path))
    return np.ascontiguousarray(a[..., 0] if a.ndim == 3 else a)


def run_one(batch, sid, out=OUT):
    """Segment one full-size field of view and write its outputs; returns the CSV row."""
    import json, resource, time
    from pathlib import Path
    from PIL import Image
    rec = {r[1]: r for r in list_images()}[sid]
    o = Path(out)
    for d in ("labels", "overlays", "colour", "rows"):
        (o / d).mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    bse, inl, se = _read(rec[2]), _read(rec[3]), _read(rec[4])
    lab, conf, P = segment_image(bse, inl, se)
    del inl, se
    dt = time.perf_counter() - t
    stem = f"{batch}_{sid}"
    Image.fromarray(lab).save(o / "labels" / f"{stem}_labels.png", optimize=True)
    pal = Image.fromarray(lab, mode="P")
    pal.putpalette(LUT.ravel().tolist())
    pal.save(o / "colour" / f"{stem}_phases.png", optimize=True)
    ov = Image.fromarray(overlay(bse, lab))
    ov.save(o / "overlays" / f"{stem}_overlay.jpg", quality=90)
    ov.resize((ov.width // 2, ov.height // 2), Image.LANCZOS).save(o / "overlays" / f"{stem}_overlay_half.jpg", quality=90)
    del ov
    ele = lab != EXCLUDED
    n = int(ele.sum())                       # phase fractions are over the electrode area (G8 excluded pixels out)
    row = {"batch": batch, "sample_id": sid, "session_height": int(lab.shape[0]),
           "pore": round(float((lab == 0).sum() / n), 5), "graphite": round(float((lab == 1).sum() / n), 5),
           "si": round(float((lab == 2).sum() / n), 5), "mean_conf": round(float(conf[ele].mean()), 4),
           "excluded": round(float(1 - n / lab.size), 5),
           "third_detector": rec[5], "width": int(lab.shape[1]), "si_mode": round(P["si_mode"], 3),
           "t_si": round(P["t_si"], 3), "anchor_min_raw": round(float(P["anchor_grid"].min()), 1),
           "anchor_max_raw": round(float(P["anchor_grid"].max()), 1), "seconds": round(dt, 1),
           "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20)}
    (o / "rows" / f"{stem}.json").write_text(json.dumps(row))
    return row


def make_montage(out=OUT, width=1400):
    """All overlays downscaled to `width` px, two columns, each labelled '<id>  <batch>  (h=<height>)'."""
    from pathlib import Path
    from PIL import Image, ImageDraw, ImageFont
    o = Path(out)
    tiles_ = []
    for batch, sid, *_ in list_images():
        p = o / "overlays" / f"{batch}_{sid}_overlay_half.jpg"
        if not p.exists():
            continue
        im = Image.open(p)
        h_full = im.height * 2
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        tiles_.append((f"{sid}  {batch}  (h={h_full})", im))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except OSError:
        font = ImageFont.load_default()
    head, gap, ncol = 40, 12, 2
    col_h = [0] * ncol
    place = []
    for lbl, im in tiles_:                       # fill the shorter column
        c = int(np.argmin(col_h))
        place.append((c, col_h[c], lbl, im))
        col_h[c] += head + im.height + gap
    legend = 60
    can = Image.new("RGB", (ncol * (width + gap) + gap, max(col_h) + legend + gap), "white")
    d = ImageDraw.Draw(can)
    x = gap
    for name, colr in zip(("pore", "graphite / carbon", "Si-like", "excluded (Cu foil)"), list(COLOURS) + [EXCL_COLOUR]):
        d.rectangle([x, 15, x + 30, 45], fill=tuple(int(v) for v in colr))
        d.text((x + 40, 15), name, fill="black", font=font)
        x += 330
    for c, y, lbl, im in place:
        x = gap + c * (width + gap)
        d.text((x, legend + y + 6), lbl, fill="black", font=font)
        can.paste(im, (x, legend + y + head))
    can.save(o / "montage.jpg", quality=88)
    return len(tiles_)


def write_csv(out=OUT):
    import csv, json
    from pathlib import Path
    o = Path(out)
    rows = []
    for batch, sid, *_ in list_images():
        p = o / "rows" / f"{batch}_{sid}.json"
        if p.exists():
            rows.append(json.loads(p.read_text()))
    with open(o / "phase_fractions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        w.writerows(rows)
    return rows


def main(argv=None):
    import argparse, subprocess, sys, time
    from pathlib import Path
    ap = argparse.ArgumentParser(description="3-phase segmentation of the full-size BSE/Inlens/SE images.")
    ap.add_argument("--one", nargs=2, metavar=("BATCH", "ID"), help="segment one image in this process")
    ap.add_argument("--all", action="store_true", help="segment every image, one at a time (one subprocess each)")
    ap.add_argument("--force", action="store_true", help="redo images whose outputs already exist")
    ap.add_argument("--only", nargs="*", default=None, help="restrict --all to these sample ids")
    ap.add_argument("--finish", action="store_true", help="only rebuild phase_fractions.csv and montage.jpg")
    a = ap.parse_args(argv)
    if a.one:
        print(run_one(*a.one), flush=True)
        return 0
    failures = []
    if a.all:
        imgs = [r for r in list_images() if a.only is None or r[1] in a.only]
        for k, (batch, sid, *_) in enumerate(imgs, 1):
            if not a.force and (Path(OUT) / "rows" / f"{batch}_{sid}.json").exists():
                print(f"[{k}/{len(imgs)}] {batch} {sid}: done already", flush=True)
                continue
            t = time.time()
            r = subprocess.run([sys.executable, __file__, "--one", batch, sid], capture_output=True, text=True)
            ok = r.returncode == 0
            print(f"[{k}/{len(imgs)}] {batch} {sid}: {'ok' if ok else 'FAILED'} {time.time() - t:.0f}s "
                  f"{r.stdout.strip().splitlines()[-1] if ok and r.stdout.strip() else r.stderr[-2000:]}", flush=True)
            if not ok:
                failures.append((batch, sid))
    if a.all or a.finish:
        rows = write_csv()
        n = make_montage()
        print(f"phase_fractions.csv: {len(rows)} rows; montage: {n} overlays; failures: {failures or 'none'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
