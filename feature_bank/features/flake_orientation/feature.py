"""flake_orientation: how well the graphite flakes are aligned with the electrode plane (calendering texture).

    flake_orient_order        nematic order parameter S = <cos 2 theta>, theta = local layer direction measured
                              from the image horizontal. 1 = every flake edge horizontal, 0 = isotropic, -1 = all
                              vertical. Dimensionless.
    flake_orient_spread_deg   [not a features.csv column since the team audit, 2026-10-03; see the comment on the function] axial circular SD of theta about its own mean, sqrt(-2 ln R) / 2 in degrees
                              (R = mean resultant length of 2 theta). 0 = perfect alignment, about 60+ = isotropic.
                              Rotation-invariant: a tilted mount or scan rotation does not change it.
    flake_tilt_deg            the mean layer direction, 0.5 * arg(sum w e^{2 i theta}) in degrees, positive =
                              counter-clockwise as the image is displayed (layers rising to the right). A
                              DIAGNOSTIC for sample mounting / scan rotation, not a material property.

Image: BSE, harmonised by features/_common (same central crop of every spot, graphite units, noise-matched) and
downsampled 2x to 50 nm/px. Units: dimensionless / degrees.

Method: structure tensor of the BSE image (derivative-of-Gaussian gradients at 75 nm, averaged over a 400 nm
window). Its dominant eigenvector is the local gradient direction; the layer (flake-edge) direction is
perpendicular to it. Each pixel is weighted by its coherence ((l1 - l2) / (l1 + l2))^2, so only clearly
oriented edges count. Only pixels on the graphite/void boundary are used (the void mask from _common, minus a
0.2 um zone around the Si-like bright phase, whose shards are isotropic): that is where flake faces meet the
pores, the interfaces that set the through-plane ion path.

Why it matters: calendering presses platelet graphite flat, parallel to the current collector. Aligned flakes
make the pore path through the thickness much longer than along the plane (tortuosity anisotropy), which lowers
rate capability and raises the lithium-plating risk at fast charge. A change in the graphite's shape
(flake vs spheroidised) or in calendering pressure would move S and the spread. Here it is an EXPECTED-STABLE
check: on the 31 spots it shows no batch difference, so a shift on a new batch is news.

Caveats: vertical FIB curtaining stripes and fast-scan blur are oriented too and bias S (session 2316 has the
strongest curtains); sample tilt biases S but not the spread; image vertical is assumed to be through-thickness.
"""
import math

import numpy as np
from scipy import ndimage as ndi

from features import feature, load_config
from features._common.harmonise import harmonised

CFG = load_config(__file__)
_cache = {"sample": None, "value": None}


def block_mean(img, f):
    """Downsample by f with an f x f area mean (crops the ragged edge)."""
    h, w = (img.shape[0] // f) * f, (img.shape[1] // f) * f
    return img[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3))


def layer_direction(img, grad_sigma, int_sigma):
    """Structure tensor -> (cos 2theta, sin 2theta, coherence) of the LAYER direction, theta from the x axis.

    Angles are in array coordinates (x to the right, y DOWN). The gradient direction phi has
    tan 2phi = 2 Jxy / (Jxx - Jyy); the layer direction is phi + 90 deg, which flips the sign of both terms.
    """
    ix = ndi.gaussian_filter(img, grad_sigma, order=(0, 1))     # d/dx (along a row)
    iy = ndi.gaussian_filter(img, grad_sigma, order=(1, 0))     # d/dy (down a column)
    jxx = ndi.gaussian_filter(ix * ix, int_sigma)
    jyy = ndi.gaussian_filter(iy * iy, int_sigma)
    jxy = ndi.gaussian_filter(ix * iy, int_sigma)
    trace = jxx + jyy
    d = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) + 1e-12        # l1 - l2
    coherence = (d / (trace + 1e-12)) ** 2
    return (jyy - jxx) / d, -2 * jxy / d, coherence


def boundary_pixels(void, bright):
    """Graphite/void boundary band, away from the bright phase and the frame margin."""
    k = 2 * CFG["boundary_width_px"] + 1
    square = np.ones((k, k), bool)
    band = ndi.binary_dilation(void, square) & ~ndi.binary_erosion(void, square)
    near_bright = ndi.distance_transform_edt(~bright) <= CFG["bright_exclusion_px"]
    m = CFG["edge_margin_px"]
    inside = np.zeros_like(void)
    inside[m:-m, m:-m] = True
    return band & ~near_bright & inside


def orientation_stats(bse, void, bright):
    """On working-resolution arrays: anchored BSE (float), void and bright masks (bool) -> dict of the 3 values."""
    c2, s2, w = layer_direction(bse.astype(np.float32), CFG["gradient_sigma_px"], CFG["integration_sigma_px"])
    sel = boundary_pixels(void, bright)
    nan = {"order": math.nan, "spread_deg": math.nan, "tilt_deg": math.nan}
    if sel.sum() < CFG["min_boundary_px"]:
        return nan
    w, c2, s2 = w[sel], c2[sel], s2[sel]
    if w.sum() <= 0:
        return nan
    mc, ms = float((w * c2).sum() / w.sum()), float((w * s2).sum() / w.sum())    # weighted mean of e^{2i theta}
    r = min(math.hypot(mc, ms), 1.0)            # mean resultant length R (float rounding can exceed 1: log > 0)
    return {
        "order": mc,                                                              # S = <cos 2 theta>
        "spread_deg": math.degrees(math.sqrt(-2 * math.log(max(r, 1e-12))) / 2),
        # array y points down, so a positive array angle is clockwise on screen: flip to counter-clockwise
        "tilt_deg": -math.degrees(0.5 * math.atan2(ms, mc)),
    }


def flake_orientation(sample):
    """All three values for one spot, computed once and reused by the three columns."""
    if _cache["sample"] is not sample:
        h = harmonised(sample)
        f = CFG["downsample"]
        bse = block_mean(h.bse, f)
        void = block_mean(h.void.astype(np.float32), f) >= 0.5
        bright = block_mean(h.bright.astype(np.float32), f) >= 0.5
        _cache["value"] = orientation_stats(bse, void, bright)
        _cache["sample"] = sample
    return _cache["value"]


@feature
def flake_orient_order(sample):
    return flake_orientation(sample)["order"]


# Not a features.csv column (team audit, 2026-10-03): rho -0.98 with flake_orient_order.
def flake_orient_spread_deg(sample):
    return flake_orientation(sample)["spread_deg"]


@feature
def flake_tilt_deg(sample):
    return flake_orientation(sample)["tilt_deg"]
