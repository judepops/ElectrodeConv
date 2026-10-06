"""Shared harmonisation and segmentation for the research-backed features. Not a feature itself (folders
starting with _ are skipped by the registry). Recipe numbers live in config.yaml next to this file.

Why it exists: image height marks 13 microscope sessions, and session explains 69-95 % of the variance of the
first features (black level, noise and grey mapping differ per session). The 1-99 % stretch in preprocessing
depends on how much bright phase an image holds, so a threshold on `sample.bse` does not mean the same thing
in every image. This module measures every spot the same way:

    1. crop      the same central area of every image, away from the top-of-frame artefact
    2. anchor    raw BSE in graphite units: 0 = black level, 1 = graphite (mode of a blurred histogram)
    3. noise     top every image up with Gaussian noise to one fixed noise level (counts and edges depend on noise)
    4. segment   void (Otsu between pore and graphite), Si-like bright phase (midpoint between graphite and the
                 image's own bright mode), a fixed-threshold bright mask for sensitivity, and the dim-grey band

    from features._common.harmonise import harmonised, fraction_se, PX_UM
    h = harmonised(sample)     # cached: every feature on the same sample reuses it
    h.void, h.bright, h.solid  # bool masks, all the same shape (the crop)
    h.bse, h.bse_blur          # anchored, noise-matched BSE (float32, graphite units)
    h.inlens, h.se             # rank-normalised (0..1), noise-matched; use edges/ridges, not grey levels
    h.acq                      # acquisition descriptors (black level, raw graphite level, noise, ...)

Only uses numpy + scipy, so it behaves the same on every machine and on Modal.
"""
import hashlib
import json
import math
import os
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.signal import find_peaks

from features import load_config
from preprocessing import PIXEL_SIZE_UM, PROCESSED_DIR

CFG = load_config(__file__)
PX_UM = PIXEL_SIZE_UM
_cache = {"sample": None, "value": None}


# ----------------------------------------------------------------------------------------------------
# small image tools
# ----------------------------------------------------------------------------------------------------
def disk(radius):
    """Boolean disk structuring element."""
    r = int(radius)
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def drop_small(mask, min_px, connectivity=2):
    """Remove connected components smaller than min_px pixels."""
    structure = ndi.generate_binary_structure(2, connectivity)
    labels, n = ndi.label(mask, structure)
    if n == 0:
        return mask.copy()
    keep = np.bincount(labels.ravel()) >= min_px
    keep[0] = False
    return keep[labels]


def fill_small_holes(mask, max_px):
    """Fill background components (holes) smaller than max_px pixels."""
    return ~drop_small(~mask, max_px, connectivity=1)


def otsu(values, bins=256):
    """Otsu threshold of a 1D array."""
    hist, edges = np.histogram(values, bins=bins)
    centres = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centres) / np.maximum(w0, 1)
    m1 = (np.sum(hist * centres) - np.cumsum(hist * centres)) / np.maximum(w1, 1)
    return float(centres[np.argmax(w0 * w1 * (m0 - m1) ** 2)])


def histogram_mode(values, lo, hi, bin_width, smooth_bins, min_density=0.0):
    """Mode of `values` in [lo, hi): smoothed histogram, parabola-refined. None if the peak holds fewer than
    min_density * len(values) values per bin."""
    edges = np.arange(lo, hi + bin_width, bin_width)
    if len(edges) < 4 or len(values) == 0:
        return None
    hist, _ = np.histogram(values, edges)
    smooth = ndi.gaussian_filter1d(hist.astype(float), smooth_bins)
    i = int(np.argmax(smooth))
    if smooth[i] < min_density * len(values):
        return None
    shift = 0.0
    if 0 < i < len(smooth) - 1:
        a, b, c = smooth[i - 1], smooth[i], smooth[i + 1]
        if a - 2 * b + c != 0:
            shift = 0.5 * (a - c) / (a - 2 * b + c)
    return float(edges[i] + (0.5 + shift) * bin_width)


def immerkaer_sigma(img):
    """Noise standard deviation by Immerkaer (1996): Laplacian-difference filter, mean absolute response."""
    kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    response = ndi.convolve(img.astype(np.float32), kernel, mode="reflect")[1:-1, 1:-1]
    return float(math.sqrt(math.pi / 2) * np.abs(response).mean() / 6)


def rank_normalise(img_uint8):
    """Map grey levels to their mid-rank CDF (0..1): removes any monotonic brightness/contrast mapping."""
    hist = np.bincount(img_uint8.ravel(), minlength=256).astype(np.float64)
    cdf = (np.cumsum(hist) - hist / 2) / hist.sum()
    return cdf[img_uint8].astype(np.float32)


def top_up_noise(img, sigma, target, seed):
    """Add Gaussian noise so the image's noise reaches `target`. Returns (image, was_already_noisier)."""
    extra = math.sqrt(max(target ** 2 - sigma ** 2, 0.0))
    if extra == 0.0:
        return img, sigma > target
    rng = np.random.default_rng(seed)
    return img + rng.standard_normal(img.shape, dtype=np.float32) * np.float32(extra), False


def crop_box(height, width):
    """(r0, r1, c0, c1): the same-size central window of every image, inside the artefact-free rows."""
    c = CFG["crop"]
    top, bottom = c["top_px"], height - c["bottom_px"]
    n = min(c["height_px"], bottom - top)
    r0 = top + (bottom - top - n) // 2
    return r0, r0 + n, c["side_px"], width - c["side_px"]


# ----------------------------------------------------------------------------------------------------
# the harmonised spot
# ----------------------------------------------------------------------------------------------------
@dataclass
class Harmonised:
    bse: np.ndarray          # anchored + noise-matched BSE, graphite units (float32)
    bse_blur: np.ndarray     # bse blurred by segmentation.blur_sigma_px
    inlens: np.ndarray       # rank-normalised + noise-matched Inlens (0..1)
    se: np.ndarray           # rank-normalised SE/ETD (0..1)
    void: np.ndarray         # bool: open pore (dark in BSE)
    bright: np.ndarray       # bool: Si-like bright phase (adaptive midpoint recipe, the decision recipe)
    bright_fixed: np.ndarray # bool: bright phase by the fixed threshold (sensitivity recipe)
    dim: np.ndarray          # bool: compact objects in the dim-grey band between graphite and bright phase
    acq: dict = field(default_factory=dict)

    @property
    def solid(self):
        return ~self.void

    @property
    def shape(self):
        return self.void.shape

    @property
    def area_um2(self):
        return self.void.size * PX_UM ** 2


def _anchor(raw_crop):
    a = CFG["anchor"]
    blur = ndi.gaussian_filter(raw_crop.astype(np.float32), a["blur_sigma_px"])
    sub = blur[::2, ::2].ravel()
    black = float(np.percentile(sub, a["black_percentile"]))
    lo, hi = np.percentile(sub, a["graphite_window_pct"])
    inside = sub[(sub >= lo) & (sub <= hi)]
    graphite = histogram_mode(inside, lo, hi, a["bin_width"], a["smooth_bins"]) or float(np.median(inside))
    return black, graphite


def _bright_mode(bright_blur):
    """The bright phase's own grey level in graphite units: the tallest real peak of the histogram above graphite.

    The histogram falls steeply from graphite (the tail and particle edges fill 1.25-1.5), so the plain argmax
    lands on that tail; a peak must stand out from its surroundings (prominence) and hold enough pixels.
    """
    s = CFG["segmentation"]
    lo, hi = s["bright_mode_range"]
    clamp_lo, clamp_hi = s["bright_mode_clamp"]
    sub = bright_blur[::2, ::2].ravel()
    edges = np.arange(lo, hi + 0.01, 0.01)
    hist = ndi.gaussian_filter1d(np.histogram(sub, edges)[0].astype(float), 3)
    centres = (edges[:-1] + edges[1:]) / 2
    peaks, props = find_peaks(hist, prominence=hist.max() * 0.05 if hist.max() > 0 else 1)
    best = None
    for i in peaks[np.argsort(-hist[peaks])]:
        share = (np.abs(sub - centres[i]) < 0.05).mean()
        if clamp_lo <= centres[i] <= clamp_hi and share >= s["bright_min_peak_frac"]:
            best = float(centres[i])
            break
    if best is None:
        # no clear peak: use the image's own bright cores (pixels above the fixed threshold) rather than a fixed
        # default, so a contrast or gamma change moves the threshold with the phase instead of leaving it behind
        cores = sub[sub > s["bright_fixed_k"] + s["bright_core_margin"]]
        if cores.size >= s["bright_min_peak_frac"] * sub.size:
            return float(np.clip(np.median(cores), clamp_lo, clamp_hi)), False
    return (best if best is not None else s["bright_mode_default"]), best is not None


def _bright_mask(bright_blur, threshold):
    s = CFG["segmentation"]
    mask = ndi.binary_opening(bright_blur > threshold, structure=disk(1))
    mask = fill_small_holes(mask, s["fill_bright_holes_px"])
    mask = drop_small(mask, s["min_bright_px"])
    labels, n = ndi.label(mask, ndi.generate_binary_structure(2, 2))
    if n == 0:
        return mask
    peak = ndi.maximum(bright_blur, labels, index=np.arange(1, n + 1))
    keep = np.concatenate([[False], peak >= threshold + s["bright_core_margin"]])
    return keep[labels]


def harmonise_arrays(raw_bse, raw_inlens, raw_se, seed=0):
    """The whole recipe on three raw uint8 images of one spot -> Harmonised. Exposed for perturbation tests."""
    seg, noise = CFG["segmentation"], CFG["noise"]
    r0, r1, c0, c1 = crop_box(*raw_bse.shape)
    bse_raw = raw_bse[r0:r1, c0:c1]

    black, graphite = _anchor(bse_raw)
    scale = max(graphite - black, 1.0)
    bse = (bse_raw.astype(np.float32) - black) / np.float32(scale)
    bse_sigma = immerkaer_sigma(bse)
    bse, bse_noisier = top_up_noise(bse, bse_sigma, noise["bse_target_sigma"], seed)
    bse_blur = ndi.gaussian_filter(bse, seg["blur_sigma_px"])

    inlens = rank_normalise(raw_inlens[r0:r1, c0:c1])
    inlens_sigma = immerkaer_sigma(inlens)
    inlens, inlens_noisier = top_up_noise(inlens, inlens_sigma, noise["inlens_target_sigma"], seed + 1)
    se = rank_normalise(raw_se[r0:r1, c0:c1])

    # void: Otsu between the pore and graphite populations of the anchored image
    lo, hi = seg["void_otsu_range"]
    sub = bse_blur[::4, ::4].ravel()
    t_void = float(np.clip(otsu(sub[(sub >= lo) & (sub < hi)]), *seg["void_threshold_clamp"]))
    void = drop_small(bse_blur < t_void, seg["min_void_px"])
    void = fill_small_holes(void, seg["min_void_px"])

    # bright (Si-like) phase: midpoint between graphite (1) and this image's own bright mode
    bright_blur = ndi.gaussian_filter(bse, seg["bright_blur_sigma_px"])
    bright_mode, mode_found = _bright_mode(bright_blur)
    t_bright = (1.0 + bright_mode) / 2
    bright = _bright_mask(bright_blur, t_bright)
    bright_fixed = _bright_mask(bright_blur, seg["bright_fixed_k"])

    # dim-grey band: compact objects between graphite and the bright threshold, away from bright edges
    d_lo, d_hi = seg["dim_range"]
    far = ndi.distance_transform_edt(~bright) > 7
    dim = (bright_blur > d_lo) & (bright_blur < min(d_hi, t_bright)) & far
    dim = drop_small(ndi.binary_opening(dim, structure=disk(3)), seg["min_dim_px"])

    acq = {
        "bse_black_raw": black, "bse_graphite_raw": graphite, "bse_noise_sigma": bse_sigma,
        "bse_noise_above_target": bse_noisier, "inlens_noise_sigma": inlens_sigma,
        "inlens_noise_above_target": inlens_noisier, "void_threshold": t_void,
        "bright_mode": bright_mode, "bright_mode_found": mode_found, "bright_threshold": t_bright,
        "crop": (r0, r1, c0, c1),
    }
    return Harmonised(bse, bse_blur, inlens, se, void, bright, bright_fixed, dim, acq)


def harmonised(sample):
    """The harmonised spot for `sample`, computed once and reused by every feature that asks for it.

    Also kept on disk (processed/harmonised/, about 80 MB per spot) so that other processes and later runs skip the
    ~10 s recompute. Only spots read from their TIFs are stored: a Sample whose raw images were injected (perturbation
    tests) is always recomputed. The file name carries a hash of this file and config.yaml, so changing the recipe
    never reuses stale results.
    """
    if _cache["sample"] is not sample:
        injected = getattr(sample, "raw_injected", True)   # raw images handed in rather than read from data/
        path = None if injected else _disk_path(sample)
        value = _load(path) if path is not None and path.exists() else None
        if value is None:
            seed = zlib.crc32(f"{sample.batch}/{sample.sample_id}".encode())
            value = harmonise_arrays(sample.raw("BSE"), sample.raw("Inlens"), sample.raw("SE"), seed)
            if path is not None:
                _save(path, value)
        _cache["value"], _cache["sample"] = value, sample
    return _cache["value"]


# ----------------------------------------------------------------------------------------------------
# disk cache
# ----------------------------------------------------------------------------------------------------
_RECIPE_HASH = hashlib.sha1(Path(__file__).read_bytes()
                            + Path(__file__).with_name("config.yaml").read_bytes()).hexdigest()[:10]
_MASKS = ("void", "bright", "bright_fixed", "dim")


def _disk_path(sample):
    if os.environ.get("LOSSLARP_NO_HARMONISE_CACHE"):
        return None
    return PROCESSED_DIR / "harmonised" / sample.batch / f"{sample.sample_id}_{_RECIPE_HASH}.npz"


def _save(path, h):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + f".tmp{os.getpid()}.npz")   # write, then rename: readers never see half a file
    np.savez(tmp, bse=h.bse, inlens=h.inlens.astype(np.float16), se=h.se.astype(np.float16),
             acq=json.dumps(h.acq), shape=np.array(h.shape),
             **{m: np.packbits(getattr(h, m)) for m in _MASKS})
    os.replace(tmp, path)


def _load(path):
    try:
        z = np.load(path)
        shape = tuple(z["shape"])
        masks = {m: np.unpackbits(z[m], count=shape[0] * shape[1]).reshape(shape).astype(bool) for m in _MASKS}
        bse = z["bse"]
        acq = json.loads(str(z["acq"]))
        acq["crop"] = tuple(acq["crop"])
        return Harmonised(bse, ndi.gaussian_filter(bse, CFG["segmentation"]["blur_sigma_px"]),
                          z["inlens"].astype(np.float32), z["se"].astype(np.float32), acq=acq, **masks)
    except Exception:          # a damaged or old-format file: recompute instead
        return None


# ----------------------------------------------------------------------------------------------------
# uncertainty
# ----------------------------------------------------------------------------------------------------
def fraction_se(mask):
    """Single-image standard error of a phase area fraction from its two-point correlation.

    var(phi_hat) ~ (1 / A_image) * integral of the indicator covariance C(r) over r (Lantuejoul; the idea behind
    Polaron/Imperial's ImageRep). C is estimated by FFT on the block-averaged mask and summed over a window that
    covers the correlation length. Returns (se, integral_range_um2). This is sampling error only: segmentation
    and site-to-site variation come on top.
    """
    r = CFG["representativity"]
    b = r["block_px"]
    h, w = (mask.shape[0] // b) * b, (mask.shape[1] // b) * b
    m = mask[:h, :w].reshape(h // b, b, w // b, b).mean(axis=(1, 3))
    phi = float(mask.mean())
    if phi <= 0 or phi >= 1:
        return math.nan, math.nan
    x = m - m.mean()
    H, W = x.shape
    shape = (2 * H, 2 * W)
    spec = np.fft.rfft2(x, s=shape)
    cov = np.fft.irfft2(spec * np.conj(spec), s=shape)
    ones = np.fft.rfft2(np.ones_like(x), s=shape)
    counts = np.fft.irfft2(ones * np.conj(ones), s=shape)
    cov = cov / np.maximum(np.round(counts), 1)
    cell_um = b * PX_UM
    dy, dx = (int(round(v / cell_um)) for v in r["window_um"])
    rows = np.r_[0:dy + 1, 2 * H - dy:2 * H]
    cols = np.r_[0:dx + 1, 2 * W - dx:2 * W]
    integral = float(cov[np.ix_(rows, cols)].sum()) * cell_um ** 2      # um2 * (fraction variance units)
    se = math.sqrt(max(integral, 0.0) / (mask.size * PX_UM ** 2))
    return se, integral / (phi * (1 - phi))
