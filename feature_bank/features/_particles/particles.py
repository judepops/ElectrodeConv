"""Shared graphite-particle label map: the graphite of a harmonised spot cut into individual particles.

Not a feature (folders starting with _ are skipped by the registry). Features that need per-particle graphite
measurements (flake length / thickness, fines, intra-particle pores, contacts, shape) call

    from features._particles.particles import graphite_particles
    p = graphite_particles(sample)       # cached per sample, like harmonised()
    p.labels                             # int32 label map at p.px_um per pixel (0 = not a graphite particle)
    p.valid                              # bool per label index: a real graphite particle (size + smooth interior)
    p.area_um2, p.major_um, p.minor_um, p.theta, p.touches_edge   # per label index (index 0 unused)

How it cuts: in a polished cross-section, touching graphite particles meet along thin lines that are dark in BSE
(a gap or carbon-binder film) and bright in Inlens (secondary-electron edge contrast). A Sato ridge filter finds
both; their normalised maximum is the boundary strength. Graphite-grey pixels far from any boundary seed a
marker-controlled watershed on that strength, restricted to graphite-grey solid. Labels that are small or
internally textured (carbon-binder sponge, pore-back seen through a pore) are marked invalid. Inlens is used
only as a ridge map (rank-normalised), never by its grey level, which differs between sessions.
"""
from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi
from skimage.filters import sato
from skimage.segmentation import watershed

from features import load_config
from features._common.harmonise import PX_UM, harmonised

CFG = load_config(__file__)
_cache = {"sample": None, "value": None}


@dataclass
class Particles:
    labels: np.ndarray       # int32, 0 = background
    px_um: float             # pixel size of `labels`
    graphite: np.ndarray     # bool: graphite-grey solid (where particles can be)
    boundary: np.ndarray     # float32 boundary strength (0..1)
    area_um2: np.ndarray     # per label index, index 0 unused
    major_um: np.ndarray     # second-moment full axis lengths (4 * sqrt(eigenvalue)), um
    minor_um: np.ndarray
    theta: np.ndarray        # long-axis angle from the image horizontal, radians (-pi/2, pi/2]
    texture: np.ndarray      # median local std inside the label (graphite units)
    touches_edge: np.ndarray # bool
    valid: np.ndarray        # bool: big enough and smooth (a graphite particle)


def block_mean(a, f):
    h, w = (a.shape[0] // f) * f, (a.shape[1] // f) * f
    return a[:h, :w].reshape(h // f, f, w // f, f).mean(axis=(1, 3))


def _scaled(x, mask):
    lo, hi = np.percentile(x[mask], CFG["ridge_norm_pct"]) if mask.any() else (0.0, 1.0)
    return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)


def label_particles(bse, inlens, void, bright):
    """Harmonised arrays (full resolution) -> Particles. Exposed for tests on synthetic images."""
    f = CFG["downsample"]
    b = ndi.gaussian_filter(block_mean(bse, f), CFG["smooth_sigma_px"])
    il = block_mean(inlens, f)
    v = block_mean(void.astype(np.float32), f) > 0.5
    br = block_mean(bright.astype(np.float32), f) > 0.5
    lo, hi = CFG["graphite_range"]
    graphite = ~v & ~br & (b > lo) & (b < hi)
    sig = CFG["ridge_sigmas_px"]
    strength = np.maximum(_scaled(sato(il, sigmas=sig, black_ridges=False), graphite),
                          _scaled(sato(b, sigmas=sig, black_ridges=True), graphite)).astype(np.float32)
    bound = (strength > CFG["boundary_threshold"]) | v | br
    interior = graphite & ~ndi.binary_dilation(bound)
    dist = ndi.distance_transform_edt(interior)
    markers = ndi.label(ndi.binary_opening(dist > CFG["core_min_dist_px"]))[0]
    labels = watershed(strength - 0.02 * dist / (dist.max() + 1e-9), markers, mask=graphite).astype(np.int32)

    n = int(labels.max())
    idx = np.arange(n + 1)
    px = PX_UM * f
    count = np.bincount(labels.ravel(), minlength=n + 1).astype(float)
    yy, xx = np.indices(labels.shape, dtype=np.float64)
    def s(w):
        return np.bincount(labels.ravel(), weights=w.ravel(), minlength=n + 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        my, mx = s(yy) / count, s(xx) / count
        cyy, cxx, cxy = s(yy * yy) / count - my ** 2, s(xx * xx) / count - mx ** 2, s(xx * yy) / count - mx * my
    tr, det = cxx + cyy, cxx * cyy - cxy ** 2
    disc = np.sqrt(np.maximum(tr ** 2 / 4 - det, 0))
    l1, l2 = np.maximum(tr / 2 + disc, 0), np.maximum(tr / 2 - disc, 0)
    theta = -0.5 * np.arctan2(2 * cxy, cxx - cyy)          # y points down: flip so + = counter-clockwise
    local_std = np.sqrt(np.maximum(ndi.uniform_filter(b * b, 3) - ndi.uniform_filter(b, 3) ** 2, 0))
    texture = np.zeros(n + 1)
    if n:
        texture[1:] = ndi.median(local_std, labels, index=idx[1:])
    edge = np.zeros(n + 1, bool)
    edge[np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))] = True
    area = count * px * px
    valid = (area >= CFG["min_particle_um2"]) & (texture <= CFG["max_texture"])
    valid[0] = False
    return Particles(labels, px, graphite, strength, area, 4 * np.sqrt(l1) * px, 4 * np.sqrt(l2) * px,
                     theta, texture, edge, valid)


def graphite_particles(sample):
    """The particle map of `sample`, computed once per sample and reused by every feature that asks for it."""
    if _cache["sample"] is not sample:
        h = harmonised(sample)
        _cache["value"] = label_particles(h.bse, h.inlens, h.void, h.bright)
        _cache["sample"] = sample
    return _cache["value"]
