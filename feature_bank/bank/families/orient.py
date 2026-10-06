"""Orientation of the microstructure from the structure tensor: which way edges and layers run, and how ordered they are.

Calendering lays flakes flat, so layers and gaps run along x (in-plane) and grey-level gradients point along y
(through-thickness). The image is never turned or mirrored: angles are measured in the window as it was acquired.

How it is measured. skimage.feature.structure_tensor(order='rc') gives, per pixel, the Sobel gradient products
(Arr, Arc, Acc) averaged over a Gaussian window of sigma = 4 px of the scale in use. From them:
    energy     E = Arr + Acc                         gradient energy in the window
    coherence  c = (l1 - l2) / (l1 + l2), 0..1       1 = one edge direction in the window, 0 = none preferred
    angle      theta = 0.5 * atan2(2 Arc, Arr - Acc)  direction the edge or layer RUNS along, in degrees:
               0 = horizontal, +-90 = vertical, positive = rising to the right as the image is displayed.
Pixels within 13 px of the window edge are left out, as are saturated BSE pixels and Inlens pixels on the darkest or
brightest grey code present, where clipped pixels pile up (at scale 4, any 4x4 block that holds one).

Three kinds of input, each catalogued under its own view:
    BSE|smoothed|25 and |100       gradient of the smoothed BSE at 25 nm and 100 nm pixels (window sigma 0.1 / 0.4 um)
    Inlens|harmonised|25 and |100  gradient of the noise-matched Inlens at the same two scales
    BSE|phase|25                   gradient of the void map and of the bright map (blurred by sigma 2 px so that the
                                   direction of a pixel staircase is read correctly): energy is then proportional to
                                   boundary length, so these are statistics of boundary direction alone.

Scalars on the two grey-level inputs (all tagged mixed: gradient energy weights every edge by its contrast and
sharpness, and noise adds energy with no direction, so noise, blur and gamma all move them):
  coh_mean, coh_median, coh_p10, coh_p90    coherence over pixels, 0..1, unweighted. Probes the window, 0.1 / 0.4 um.
  coh_ewmean           energy-weighted mean coherence, 0..1.
  nematic_s            nematic order parameter S = |sum E exp(2 i theta)| / sum E, 0..1: 0 = edges in all
                       directions, 1 = all parallel. Uses each window's own direction.
  nematic_s_global     the same from the summed tensor, (L1 - L2) / (L1 + L2): incoherent windows pull it down.
  director_deg         the mean direction, 0.5 * arg(sum E exp(2 i theta)), degrees in -90..90.
  energy_frac_h15      share of energy with |theta| <= 15 degrees: edges and layers lying flat. 1/6 if isotropic.
  energy_frac_v15      share with |theta| >= 75 degrees: edges standing upright.
  energy_frac_d15      share within 15 degrees of the director (does not depend on how the sample was mounted).
  abs_theta_mean_deg   energy-weighted mean |theta| in degrees: 45 if isotropic, 0 if everything lies flat.

Scalars on the phase maps, {void,bright}_<stat>_mid for coh_ewmean and the seven statistics from nematic_s on, and
{void,bright}_{nematic_s,energy_frac_h15}_{lo,hi} at the other two thresholds of the Crop's band. They probe the
boundary over about 0.1 um. coh_ewmean, nematic_s, nematic_s_global and energy_frac_d15 are tagged material: they
are read off the phase maps and do not change if the whole image is tilted. director_deg, energy_frac_h15,
energy_frac_v15 and abs_theta_mean_deg are tagged mixed: a few degrees of sample or scan tilt, which is imaging,
moves them.

Blocks (tagged mixed, for the tilt reason and, on grey levels, the contrast reason):
  theta_hist36 and {void,bright}_theta_hist36    share of gradient energy per 5 degree bin of theta, from -90 to 90
                       (bin 0 is -90..-85, bin 18 is 0..5), summing to 1.

An input with no gradient energy (an empty phase map) returns the isotropic values: coherence and S = 0,
director 0, each 15 degree share 1/6, mean |theta| 45, a flat histogram.
"""
import numpy as np
from scipy import ndimage as ndi
from skimage.feature import structure_tensor

from bank.core import PX_NM, FeatureResult, block_mean

FAMILY = "orient"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {
    "scales": [1, 4],              # block-mean factors of the two grey-level inputs
    "window_sigma_px": 4.0,        # Gaussian window of the structure tensor, in pixels of the scale in use
    "margin_sigmas": 3.0,          # pixels closer to the window edge than this many sigmas (plus 1 px) are left out
    "hist_bins": 36,               # 5 degree bins over -90..90
    "cone_deg": 15.0,              # half-width of the "within 15 degrees" shares
    "map_blur_px": 2.0,            # phase maps are blurred by this before the gradient
}
GREY_INPUTS = (("BSE", "smoothed"), ("Inlens", "harmonised"))
DIRECTION_STATS = ("nematic_s", "nematic_s_global", "director_deg", "energy_frac_h15", "energy_frac_v15",
                   "energy_frac_d15", "abs_theta_mean_deg")
COHERENCE_STATS = ("coh_mean", "coh_median", "coh_p10", "coh_p90")
TILT_FREE = ("coh_ewmean", "nematic_s", "nematic_s_global", "energy_frac_d15")     # unchanged if the image is tilted


def _isotropic(cfg):
    cone = 2.0 * cfg["cone_deg"] / 180.0
    stats = dict(coh_mean=0.0, coh_median=0.0, coh_p10=0.0, coh_p90=0.0, coh_ewmean=0.0, nematic_s=0.0,
                 nematic_s_global=0.0, director_deg=0.0, energy_frac_h15=cone, energy_frac_v15=cone,
                 energy_frac_d15=cone, abs_theta_mean_deg=45.0)
    return stats, np.full(cfg["hist_bins"], 1.0 / cfg["hist_bins"])


def _orientation(img, keep, cfg):
    """Structure tensor of one image -> ({stat: value}, energy-weighted histogram of theta).

    keep: bool array of the pixels that may be used, or None for all of them."""
    sigma = float(cfg["window_sigma_px"])
    arr, arc, acc = structure_tensor(img.astype(np.float32), sigma=sigma, mode="reflect", order="rc")
    m = int(np.ceil(cfg["margin_sigmas"] * sigma)) + 1
    inner = (slice(m, -m), slice(m, -m))
    arr, arc, acc = arr[inner], arc[inner], acc[inner]
    if keep is None:
        arr, arc, acc = arr.ravel(), arc.ravel(), acc.ravel()
    else:
        ok = keep[inner]
        arr, arc, acc = arr[ok], arc[ok], acc[ok]
    energy = (arr + acc).astype(np.float64)
    total = float(energy.sum())
    if energy.size == 0 or not total > 0.0:
        return _isotropic(cfg)
    dq = (arr - acc).astype(np.float64)                       # E c cos(2 theta)
    du = (2.0 * arc).astype(np.float64)                       # E c sin(2 theta)
    aniso = np.hypot(dq, du)                                  # E c = l1 - l2
    coherence = np.divide(aniso, energy, out=np.zeros_like(aniso), where=energy > 0)
    theta = np.degrees(0.5 * np.arctan2(du, dq))              # -90..90, the direction the edge runs along
    theta[theta >= 90.0] -= 180.0
    unit = np.divide(energy, aniso, out=np.zeros_like(aniso), where=aniso > 0)
    sum_c, sum_s = float((dq * unit).sum()), float((du * unit).sum())      # sum of E cos / sin (2 theta)
    director = float(np.degrees(0.5 * np.arctan2(sum_s, sum_c)))
    cone = float(cfg["cone_deg"])
    off = np.abs((theta - director + 90.0) % 180.0 - 90.0)   # angle to the director, 0..90
    p10, p50, p90 = np.percentile(coherence, [10, 50, 90])
    stats = dict(
        coh_mean=float(coherence.mean()), coh_median=float(p50), coh_p10=float(p10), coh_p90=float(p90),
        coh_ewmean=float(aniso.sum()) / total,
        nematic_s=float(np.hypot(sum_c, sum_s)) / total,
        nematic_s_global=float(np.hypot(dq.sum(), du.sum())) / total,
        director_deg=director,
        energy_frac_h15=float(energy[np.abs(theta) <= cone].sum()) / total,
        energy_frac_v15=float(energy[np.abs(theta) >= 90.0 - cone].sum()) / total,
        energy_frac_d15=float(energy[off <= cone].sum()) / total,
        abs_theta_mean_deg=float((energy * np.abs(theta)).sum()) / total,
    )
    hist = np.histogram(theta, bins=cfg["hist_bins"], range=(-90.0, 90.0), weights=energy)[0] / total
    return stats, hist


def _usable(crop, det, scale):
    """Pixels whose grey level was not clipped, at one scale."""
    if det == "BSE":
        ok = crop.valid
    else:
        raw = crop.view(det, "raw")
        ok = (raw > raw.min()) & (raw < raw.max())          # clipped pixels pile up on the darkest and brightest code
    return ok if scale == 1 else block_mean(ok.astype(np.float32), scale) > 0.999


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    bins = cfg["hist_bins"]

    # --- grey-level inputs: smoothed BSE and noise-matched Inlens at each scale -------------------------
    for det, view in GREY_INPUTS:
        for s in cfg["scales"]:
            stats, hist = _orientation(crop.view(det, view, s), _usable(crop, det, s), cfg)
            window_um = cfg["window_sigma_px"] * PX_NM * s / 1000.0
            for stat in COHERENCE_STATS + ("coh_ewmean",) + DIRECTION_STATS:
                res.scalar(det, view, PX_NM * s, stat, stats[stat], length_um=window_um, tag="mixed")
            res.block(det, view, PX_NM * s, f"theta_hist{bins}", hist, length_um=window_um, tag="mixed")

    # --- phase maps: direction of the void and bright boundaries ------------------------------------------
    window_um = cfg["window_sigma_px"] * PX_NM / 1000.0
    for phase in ("void", "bright"):
        for band in ("lo", "mid", "hi"):
            mask = crop.phase(phase if band == "mid" else f"{phase}_{band}")
            soft = ndi.gaussian_filter(mask.astype(np.float32), cfg["map_blur_px"])
            stats, hist = _orientation(soft, None, cfg)
            for stat in (("coh_ewmean",) + DIRECTION_STATS if band == "mid" else ("nematic_s", "energy_frac_h15")):
                res.scalar("BSE", "phase", PX_NM, f"{phase}_{stat}_{band}", stats[stat], length_um=window_um,
                           tag="material" if stat in TILT_FREE else "mixed")
            if band == "mid":
                res.block("BSE", "phase", PX_NM, f"{phase}_theta_hist{bins}", hist, length_um=window_um, tag="mixed")
    return res
