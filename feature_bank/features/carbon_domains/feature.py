"""carbon_domains: is there a second, darker graphite grade in the electrode, and does it come as whole particles?

    carbon_dark_domain_frac                 share of the graphite interior that sits in the darker of two graphite
                                            grey levels, in patches >= 25 um2. 0 = one graphite level only.
    carbon_domain_boundary_on_particle_frac [not a features.csv column since the team audit, 2026-10-03; see the comment on the function] share of the dark/main domain interfaces that lie on a particle
                                            boundary (within 0.5 um of a void or bright-phase edge or an Inlens
                                            ridge). nan when there are no domains to test.

Image: BSE (levels) and Inlens (particle-boundary ridges), harmonised by features/_common (same central crop of
every spot, BSE in graphite units, noise-matched) and downsampled 2x to 50 nm/px. Units: area fractions (0-1).

What it is: about a third of the spots show particle-sized graphite regions (~7-10 um across) 8-17 % darker in
BSE than the main graphite (raw ~49 vs 58-62 grey). Two explanations predict different geometry:
  - a BLEND of two graphite grades (e.g. natural + synthetic): the contrast belongs to whole particles, so the
    level changes AT particle boundaries -> boundary share near 1;
  - electron CHANNELLING (BSE yield depends on crystal orientation to the beam): it can vary inside one
    particle (bent flakes, polycrystalline secondary particles) -> interfaces also inside particles.
A boundary share well above its chance level supports the blend reading; it cannot prove it (a single-crystal
flake also channels as a whole), and pore-back (sub-surface material seen through pores, also ~0.7-0.9 g) can
mimic dark graphite. Compare within sessions only: kV, detector and tilt change channelling contrast.

Why it matters: the natural/synthetic graphite ratio is a classic hidden supplier change. The grades differ in
crystallinity, surface area and particle shape, which move reversible capacity, first-cycle efficiency, rate
capability and swelling; a CoA reports neither the blend ratio nor how the grades are mixed.

Method:
  1. graphite interior = solid, not bright phase, > 0.3 um from void and bright edges;
  2. level map = Gaussian-weighted mean of the blurred BSE over graphite interior pixels only (0.5 um), divided by
     the slow-scan drift (median over column blocks of the top-to-bottom slope);
  3. main level = mode of the level map; a 2-component sklearn GaussianMixture is fitted to the levels in
     [mode - 0.25, mode + 0.05]; the darker component counts as a second level only if it is >= 6 % darker and
     holds >= 2 % of the window;
  4. dark = level below the mixture's decision boundary, opened (0.15 um), patches >= 25 um2;
  5. interfaces = dark pixels touching main-level graphite; on-boundary = within 0.5 um of void/bright edges or
     Inlens ridges (top 10 % of a Hessian ridge filter).
"""
import math

import numpy as np
from scipy import ndimage as ndi
from sklearn.mixture import GaussianMixture

from features import feature, load_config
from features._common.harmonise import PX_UM, disk, drop_small, harmonised

CFG = load_config(__file__)
_cache = {"sample": None, "value": None}


def block_mean(img, f):
    """Downsample by f with an f x f area mean (crops the ragged edge)."""
    h, w = (img.shape[0] // f) * f, (img.shape[1] // f) * f
    return img[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3))


def drift_slope(level, graphite):
    """Top-to-bottom brightness change across the crop (fraction of the level), robust to domains."""
    h, w = level.shape
    ey = np.linspace(0, h, CFG["drift_row_bands"] + 1).astype(int)
    ex = np.linspace(0, w, CFG["drift_column_blocks"] + 1).astype(int)
    y = (ey[:-1] + ey[1:]) / 2 / h - 0.5                                   # band centres, -0.5 .. 0.5
    slopes = []
    for c0, c1 in zip(ex[:-1], ex[1:]):
        med = np.array([np.median(level[r0:r1, c0:c1][graphite[r0:r1, c0:c1]])
                        if graphite[r0:r1, c0:c1].sum() > 200 else np.nan for r0, r1 in zip(ey[:-1], ey[1:])])
        ok = np.isfinite(med)
        if ok.sum() >= 4:
            slopes.append(np.polyfit(y[ok], med[ok], 1)[0])
    return float(np.median(slopes)) if slopes else 0.0


def level_map(bse_blur, void, bright):
    """Graphite interior mask and its smoothed, drift-corrected BSE level (graphite units)."""
    m = CFG["edge_margin_px"]
    graphite = (ndi.distance_transform_edt(~void) > m) & (ndi.distance_transform_edt(~bright) > m)
    w = graphite.astype(np.float32)
    s = CFG["level_sigma_px"]
    level = ndi.gaussian_filter(bse_blur * w, s) / np.maximum(ndi.gaussian_filter(w, s), 1e-3)
    slope = drift_slope(level, graphite)
    y = np.arange(level.shape[0]) / level.shape[0] - 0.5
    return graphite, level / (1 + slope * y)[:, None]


def histogram_mode(values):
    bw = CFG["mode_bin"]
    edges = np.arange(0.5, 1.5 + bw, bw)
    hist = ndi.gaussian_filter1d(np.histogram(values, edges)[0].astype(float), 2)
    return float(edges[np.argmax(hist)] + bw / 2)


def dark_threshold(values):
    """Decision boundary between the darker and the main graphite level, or None if there is one level only."""
    main = histogram_mode(values)
    window = values[(values > main - CFG["band_below"]) & (values < main + CFG["band_above"])]
    window = window[::max(1, len(window) // CFG["gmm_max_values"])]
    if len(window) < 1000:
        return None
    gmm = GaussianMixture(2, random_state=CFG["gmm_seed"]).fit(window[:, None])
    mu, sd, wt = gmm.means_.ravel(), np.sqrt(gmm.covariances_.ravel()), gmm.weights_
    lo, hi = np.argsort(mu)
    if mu[hi] - mu[lo] < CFG["min_contrast"] * mu[hi] or wt[lo] < CFG["min_weight"]:
        return None
    x = np.linspace(mu[lo], mu[hi], 512)                                   # where the two weighted densities cross
    dens = [wt[k] / sd[k] * np.exp(-0.5 * ((x - mu[k]) / sd[k]) ** 2) for k in (lo, hi)]
    return float(x[np.argmin(np.abs(dens[0] - dens[1]))])


def particle_boundaries(inlens, void, bright):
    """Void and bright-phase pixels plus Inlens ridges (bright thin lines: particle contacts, cracks, CBD seams)."""
    s = CFG["ridge_sigma_px"]
    ixx = ndi.gaussian_filter(inlens, s, order=(0, 2))
    iyy = ndi.gaussian_filter(inlens, s, order=(2, 0))
    ixy = ndi.gaussian_filter(inlens, s, order=(1, 1))
    ridge = -((ixx + iyy) / 2 - np.sqrt(((ixx - iyy) / 2) ** 2 + ixy ** 2))   # minus the smaller Hessian eigenvalue
    solid = ~void
    ridges = solid & (ridge > np.percentile(ridge[solid], CFG["ridge_percentile"]))
    return void | bright | ridges


def domain_stats(bse_blur, void, bright, inlens):
    """On working-resolution arrays -> {'dark_frac', 'on_particle_frac', 'chance_frac', 'threshold'}."""
    out = {"dark_frac": math.nan, "on_particle_frac": math.nan, "chance_frac": math.nan, "threshold": math.nan}
    graphite, level = level_map(bse_blur.astype(np.float32), void, bright)
    if graphite.mean() < CFG["min_graphite_frac"]:
        return out
    t = dark_threshold(level[graphite])
    if t is None:                                                          # one graphite level only
        out["dark_frac"] = 0.0
        return out
    dark = ndi.binary_opening(graphite & (level < t), structure=disk(CFG["open_radius_px"]))
    dark = drop_small(dark, CFG["min_patch_um2"] / (PX_UM * CFG["downsample"]) ** 2)
    out["dark_frac"], out["threshold"] = float(dark.sum() / graphite.sum()), t

    # blend vs channelling: dark pixels that touch main-level graphite, and how many sit on a particle boundary
    main = graphite & ~dark
    interface = dark & ndi.binary_dilation(main, structure=np.ones((3, 3), bool))
    if interface.sum() < CFG["min_interface_px"]:
        return out
    near = ndi.distance_transform_edt(~particle_boundaries(inlens, void, bright)) <= CFG["boundary_tolerance_px"]
    out["on_particle_frac"] = float(near[interface].mean())
    out["chance_frac"] = float(near[graphite].mean())                      # same share for any graphite pixel
    return out


def carbon_domains(sample):
    """All values for one spot, computed once and reused by both columns."""
    if _cache["sample"] is not sample:
        h = harmonised(sample)
        f = CFG["downsample"]
        _cache["value"] = domain_stats(block_mean(h.bse_blur, f),
                                       block_mean(h.void.astype(np.float32), f) >= 0.5,
                                       block_mean(h.bright.astype(np.float32), f) >= 0.5,
                                       block_mean(h.inlens, f).astype(np.float32))
        _cache["sample"] = sample
    return _cache["value"]


@feature
def carbon_dark_domain_frac(sample):
    return carbon_domains(sample)["dark_frac"]


# Not a features.csv column (team audit, 2026-10-03): NaN on 22/31 spots and the missingness carries meaning.
def carbon_domain_boundary_on_particle_frac(sample):
    return carbon_domains(sample)["on_particle_frac"]
