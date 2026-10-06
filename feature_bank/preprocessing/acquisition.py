"""Step 5 of preprocessing: was each spot imaged like the known ones? Prints warnings, never changes an image.

Image height marks 13 microscope sessions, and black level, noise, grey mapping, focus and curtaining are set
per session. The harmonisation (features/_common) evens out black level, grey mapping and noise, but it cannot
undo polishing stripes (curtaining), blur or burnt-out Inlens pixels. This step measures how each spot was
imaged and warns when a spot falls outside what the known spots cover, because its features are then biased.

These numbers describe the microscope, not the material: they go to processed/acquisition.csv, never into
features.csv, and must never be model inputs (they identify the session, not the batch).

    from preprocessing.acquisition import measure, gate_status, warnings_for
    values = measure(sample)                  # {"acq_bse_black_level": ..., ...}
    status, detail = gate_status(values)      # "G-A" | "G-B" | "G-C"
    for text in warnings_for(values): print(text)

Columns (all on the central crop of features/_common, h.acq["crop"], raw coordinates):
    acq_bse_black_level          raw grey   BSE black level (0.5th percentile of the blurred crop)   CHECKED
    acq_bse_graphite_level       raw grey   BSE graphite mode                                         info
    acq_bse_noise_sigma          graphite units  Immerkaer noise of the anchored BSE, before top-up  CHECKED
    acq_bse_noise_above_target   0/1        1 = noisier than the harmonisation target (not equalised) CHECKED
    acq_bse_clip0_frac           fraction   raw BSE pixels == 0 (follows porosity, so never checked)  info
    acq_cnr                      ratio      (graphite - black) / noise sigma on graphite interiors    info
    acq_inlens_sat255_frac       fraction   raw Inlens pixels == 255                                  CHECKED
    acq_inlens_noise_sigma       rank units Immerkaer noise of the rank-normalised Inlens             info
    acq_curtain_index            ratio      vertical-stripe (curtain) power in the SE spectrum, ~1 = none CHECKED
    acq_focus                    graphite units^2  Laplacian variance on graphite minus white noise   CHECKED

Grades (limits frozen in acquisition.yaml): G-A every checked value inside the known-session envelope;
G-B outside it but inside the range the perturbation test covered (features still usable, with a warning);
G-C outside even that (features from this spot are not comparable: re-image next to a retained reference).
Evidence and limits: preprocessing/acquisition.md.
"""
import math
from pathlib import Path

import numpy as np
import yaml
from scipy import ndimage as ndi

with open(Path(__file__).with_name("acquisition.yaml")) as f:
    CFG = yaml.safe_load(f)

COLUMNS = ["acq_bse_black_level", "acq_bse_graphite_level", "acq_bse_noise_sigma", "acq_bse_noise_above_target",
           "acq_bse_clip0_frac", "acq_cnr", "acq_inlens_sat255_frac", "acq_inlens_noise_sigma", "acq_curtain_index",
           "acq_focus"]

# What each checked value means when it is out of range, in plain words: (too low, too high)
PROBLEMS = {
    "acq_bse_black_level": ("BSE black level unusual", "BSE black level (brightness offset) raised"),
    "acq_bse_noise_sigma": ("BSE unusually clean", "BSE image noisier than usual: small pores, thin binder and "
                            "edges may be lost or invented, pore sizes and porosity biased"),
    "acq_inlens_sat255_frac": ("", "Inlens burnt out to white (gain too high or charging): binder and edge "
                               "features from Inlens biased"),
    "acq_curtain_index": ("", "vertical polishing stripes (curtaining): orientation, size and gradient features "
                          "biased, porosity may shift"),
    "acq_focus": ("image blurred (defocus): edges soften, small objects merge, sizes inflate", "image unusually sharp"),
}
_IMMERKAER = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)


def _harmonised(sample):
    from features._common.harmonise import harmonised   # imported here: features imports preprocessing
    return harmonised(sample)


def raw_crop(sample, detector):
    """The raw uint8 image of one detector, cut to the shared harmonisation crop."""
    r0, r1, c0, c1 = _harmonised(sample).acq["crop"]
    return sample.raw(detector)[r0:r1, c0:c1]


def graphite_bse(sample):
    """-> (anchored BSE before the noise top-up, graphite-interior mask, noise sigma on that mask).

    The anchored image keeps the camera's own noise and sharpness (h.bse has extra noise added). The mask is
    flat graphite away from edges: blurred anchored BSE inside the graphite window, eroded. The noise is
    Immerkaer (1996) averaged over the mask only, so particle edges do not leak into it.
    """
    h = _harmonised(sample)
    a, g = h.acq, CFG["graphite_interior"]
    scale = max(a["bse_graphite_raw"] - a["bse_black_raw"], 1.0)
    img = (raw_crop(sample, "BSE").astype(np.float32) - np.float32(a["bse_black_raw"])) / np.float32(scale)
    lo, hi = g["range"]
    size = 2 * g["erode_px"] + 1     # erosion by a size x size square = a minimum filter (fast, separable)
    mask = ndi.minimum_filter((h.bse_blur > lo) & (h.bse_blur < hi), size=size, mode="constant", cval=0)
    sigma = math.nan
    if mask.sum() >= 1000:
        response = ndi.convolve(img, _IMMERKAER, mode="reflect")
        sigma = float(math.sqrt(math.pi / 2) * np.abs(response[mask]).mean() / 6)
    return img, mask, sigma


def curtain_index(sample):
    """Vertical stripes (curtains) run along y, so their power sits on the ky = 0 line at kx != 0.

    Welch power spectrum of the SE crop (Hann-windowed tiles; the window stops the image border from painting
    its own line on the axes). Index = mean power on the stripe line |ky| <= band over mean power in the
    flanks (same kx, ky a little further out). White noise gives 1. A steep isotropic spectrum reads a little
    above 1, because at low kx the flank lies at a larger |k| (blurred noise, sigma 2 px: 1.17). Curtains: well
    above 1 (session 2316: 1.64-1.68). The SE crop is the rank-normalised h.se, so black level, gain and gamma
    cannot change the index.
    """
    c = CFG["curtain"]
    t = c["tile_px"]
    img = np.asarray(_harmonised(sample).se, dtype=np.float32)
    window = np.outer(np.hanning(t), np.hanning(t)).astype(np.float32)
    power = np.zeros((t, t // 2 + 1))
    n = 0
    for y in np.linspace(0, img.shape[0] - t, max(1, round(img.shape[0] / t))).astype(int):
        row = img[y:y + t]
        stack = np.stack([row[:, x:x + t] for x in range(0, img.shape[1] - t + 1, t)])
        stack -= stack.mean(axis=(1, 2), keepdims=True)
        power += (np.abs(np.fft.rfft2(stack * window)) ** 2).sum(axis=0)
        n += len(stack)
    ky = np.abs(np.fft.fftfreq(t))[:, None] * t           # in bins
    kx = np.fft.rfftfreq(t)[None, :]                      # in cycles per pixel
    in_kx = (kx >= c["kx_range"][0]) & (kx < c["kx_range"][1])
    line = in_kx & (ky <= c["band_ky_bins"])
    flank = in_kx & (ky >= c["flank_ky_bins"][0]) & (ky <= c["flank_ky_bins"][1])
    power /= n
    return float(power[line].mean() / power[flank].mean())


def focus(img, mask, sigma):
    """Variance of the Laplacian (Pech-Pacheco 2000) on graphite interiors, after 2x2 binning, minus what the
    camera noise alone would give. Higher = sharper (focus, detector bandwidth); can go slightly negative."""
    f = CFG["focus"]
    b = f["bin_px"]
    h, w = (img.shape[0] // b) * b, (img.shape[1] // b) * b
    binned = img[:h, :w].reshape(h // b, b, w // b, b).mean(axis=(1, 3))
    inside = mask[:h, :w].reshape(h // b, b, w // b, b).all(axis=(1, 3))
    if inside.sum() < 1000:
        return math.nan
    lap = ndi.laplace(binned, mode="reflect")
    return float(lap[inside].var() - f["laplacian_noise_gain"] * sigma ** 2 / b ** 2)


def measure(sample):
    """-> {column: value} for one spot (see COLUMNS). Uses (and fills) the harmonised cache."""
    a = _harmonised(sample).acq
    sat = CFG["saturation"]
    img, mask, sigma = graphite_bse(sample)
    return {
        "acq_bse_black_level": a["bse_black_raw"],
        "acq_bse_graphite_level": a["bse_graphite_raw"],
        "acq_bse_noise_sigma": a["bse_noise_sigma"],
        "acq_bse_noise_above_target": float(a["bse_noise_above_target"]),
        "acq_bse_clip0_frac": float((raw_crop(sample, "BSE") == sat["bse_black_code"]).mean()),
        "acq_cnr": 1.0 / sigma if sigma > 0 else math.nan,    # nan > 0 is False: no graphite interior -> nan
        "acq_inlens_sat255_frac": float((raw_crop(sample, "Inlens") == sat["inlens_white_code"]).mean()),
        "acq_inlens_noise_sigma": a["inlens_noise_sigma"],
        "acq_curtain_index": curtain_index(sample),
        "acq_focus": focus(img, mask, sigma),
    }


def gate_status(values):
    """values = {column: value} (e.g. from measure() or a row of processed/acquisition.csv).

    -> ("G-A" | "G-B" | "G-C", {column: "inside" | "extrapolated" | "outside" | "missing"}).
    G-A: every checked column inside the known-session envelope. G-B: some outside it but inside the range the
    perturbation test covered. G-C: some outside even that, or missing. Limits are frozen in acquisition.yaml.
    """
    detail = {}
    for column, limits in CFG["gate"].items():
        try:
            v = float(values.get(column, math.nan))
        except (TypeError, ValueError):          # None, a string or anything non-numeric counts as missing
            v = math.nan
        if not np.isfinite(v):
            detail[column] = "missing"
        elif limits["envelope"][0] <= v <= limits["envelope"][1]:
            detail[column] = "inside"
        elif limits["tested"][0] <= v <= limits["tested"][1]:
            detail[column] = "extrapolated"
        else:
            detail[column] = "outside"
    states = set(detail.values())
    status = "G-C" if states & {"outside", "missing"} else "G-B" if "extrapolated" in states else "G-A"
    return status, detail


def warnings_for(values):
    """-> list of plain-language warnings for one spot (empty = imaged like the known spots)."""
    out = []
    _, detail = gate_status(values)
    for column, state in detail.items():
        if state == "inside":
            continue
        limits = CFG["gate"][column]
        v = values.get(column, math.nan)
        if state == "missing":
            out.append(f"{column} could not be measured: features from this spot are NOT COMPARABLE")
            continue
        low, high = limits["envelope"]
        what = PROBLEMS[column][0 if v < low else 1] or column
        bound = f"known spots {low:.4g}-{high:.4g}"
        if state == "extrapolated":
            out.append(f"{what} ({column} = {v:.4g}, {bound}): beyond any known spot but inside the tested range; "
                       "features usable, treat with care")
        else:
            out.append(f"{what} ({column} = {v:.4g}, {bound}, tested to {limits['tested'][0]:.4g}-"
                       f"{limits['tested'][1]:.4g}): features from this spot are NOT COMPARABLE, re-image it")
    if values.get("acq_bse_noise_above_target") == 1.0:
        out.append("BSE noise above the harmonisation target: it could not be equalised with the other spots")
    return out
