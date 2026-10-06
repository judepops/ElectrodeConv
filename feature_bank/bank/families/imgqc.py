"""imgqc: how each picture was taken. The acquisition-only baseline that every material result is compared against.

Everything is measured on the raw grey levels (DN, 0..255) of one detector, because that is where the microscope
settings live: brightness (black level), contrast (graphite level), digital gain (histogram comb), dwell and beam
current (noise), focus and astigmatism (gradients, high-frequency spectrum), scan electronics (line statistics) and
slow drift. No pixel is masked for saturation: clipping is one of the things being described.

Tags. BSE and Inlens columns are `imaging`: each one is set, or can be set, by a microscope control (brightness,
contrast, digital gain, dwell, focus, stigmators, scan speed, drift), so they stay out of the material model and form
the baseline a material result has to beat. SE columns are `leakrisk`, like everything from that detector. `imaging`
does not mean blind to the material: on the smoke crops the injected pore growth also moved the void-interior
statistics, the edge blur and, on Inlens, most noise and line statistics, and removing bright grains moved the upper
percentiles. None of these columns may be read as a material result; a column that moves under no synthetic imaging
change (the drift columns) is still imaging, because the six synthetic changes contain no drift.

Axes. x = along a scan line (the fast scan, horizontal); y = from one scan line to the next (the slow scan, vertical,
later in time further down). x and y statistics are always kept apart.

Scalars, per detector (view `raw`, 25 nm, no length scale, unless stated):

  Tone
    p0.5 p1 p2 p5 p25 p50 p75 p95 p98 p99 p99.5   DN. Percentiles of the grey codes (each code a bin k +- 0.5).
    mean_dn, std_dn                  DN. Mean and standard deviation of all pixels.
    sat0_frac, sat255_frac           fraction of pixels at code 0 / at code 255 (clipped black, clipped white).
    floor_dn, floor_frac             DN, fraction. Lowest code holding >= 10 ppm of the pixels, and the share of pixels
                                     piled on it: finds a clipped black level even after an offset was added.
    ceil_dn, ceil_frac               the same at the top of the range.
    comb_empty_frac                  fraction of grey codes between the 1st and 99th percentile that hold no pixel
                                     (a digital gain leaves a comb of unused codes).
    comb_low_frac                    the same, counting codes below 10 % of their taller neighbour (survives stray pixels).
    comb_ragged                      RMS second difference of the histogram / its mean, 1st-99th percentile (0 = smooth).
    hist_entropy_bits, hist_max_frac bits, fraction. Entropy of the 256-code histogram; share of the fullest code.
    black_dn, graphite_dn, scale_dn  DN. Black level, graphite level and their difference. For BSE these are
                                     crop.anchors (0.5th percentile and histogram mode of the sigma = 2 px blurred
                                     picture). For Inlens and SE: the same percentile, and the median of the blurred
                                     picture over the solid interior, i.e. that detector's grey level on graphite.
                                     (Their histograms can have two peaks and a mode then jumps between them: by
                                     32 DN under an injected pore change on one smoke crop.)
    graphite_fwhm_dn                 DN. Full width at half maximum of the histogram of the blurred picture over the
                                     solid interior (the graphite peak without voids and bright grains). The peak is
                                     searched between the 10th and 90th percentile, so a spike of saturated pixels at
                                     255 is not taken for it.
    rawmode_dn, rawmode_fwhm_dn      DN. Mode and FWHM of the main peak of the unblurred histogram (width = noise + texture).
    void_level_dn, solid_level_dn, bright_level_dn   DN. Median grey level inside void interiors, inside the solid away
                                     from voids and bright grains, and inside bright-grain interiors: three points of the
                                     tone curve. A phase with < 1000 interior px returns the detector's median.
  Noise (length = 2 px of the scale used: 0.05, 0.1, 0.2 um)
    noise_immerkaer_dn               DN, at 25, 50 and 100 nm. Immerkaer noise sigma of the picture and of its 2x2 and
                                     4x4 block means (white noise halves per step; correlated noise does not).
    noise_void_dn, noise_solid_dn, noise_bright_dn   DN. The same estimator inside the three phase interiors: noise at
                                     three signal levels (an empty phase returns the whole-picture value).
    noise_gain_dn                    DN. Slope of noise variance against grey level over those phases (photon-transfer
                                     gain; 0 if fewer than two phases are measurable).
    psd_floor_dn                     DN. sqrt of the median power in the highest-frequency ring (0.47-0.50 cycles/px)
                                     of the radial power spectrum; white noise of sigma s gives s. Length 0.05 um.
    psd_corner_dn                    DN. The same in the spectrum's corners (|fx|, |fy| >= 0.4), where the least
                                     structure reaches. Length 0.035 um.
    psd_floor_tile_dn                DN. sqrt of the median over the 256 px tiles of each tile's mean power in that
                                     top ring: a floor that a few tiles full of fine structure cannot lift.
    noise_drift_y_rel_per10um, noise_drift_x_rel_per10um   1 per 10 um. Slope of the solid-interior noise sigma over the
                                     8 drift bands / its mean (beam current or gain changing during the frame).
    noise_drift_y_resid_rel, noise_drift_x_resid_rel       RMS of the band noise about that line / its mean.
  Focus (length = 2 px of the scale used)
    tenengrad                        DN^2, at 25, 50, 100 nm. Mean squared Sobel gradient, gx^2 + gy^2.
    tenengrad_excess                 DN^2, same scales. Tenengrad minus what white noise of the Immerkaer sigma gives
                                     (24 sigma^2); can be negative when the noise is correlated.
    tenengrad_norm                   1/px^2, same scales. Tenengrad / (64 x grey variance): mean squared spatial
                                     frequency, unchanged by black level and contrast.
    focus_lap2_excess                DN^2, 50 nm, length 0.1 um. Variance of the 4-neighbour Laplacian of the 2x2 block
                                     mean inside solid interiors, minus its white-noise part (5 sigma_solid^2): fine
                                     texture inside graphite, which follows focus and detector bandwidth.
    edge_g_ratio                     ratio. Median Gaussian-derivative gradient magnitude on the void outline at
                                     sigma 1.5 px over that at sigma 3 px. A perfect step gives 2, a blurred one less.
    edge_psf_px                      px (1 px = 0.025 um; length about 0.1 um). The edge blur sigma that ratio implies,
                                     sqrt((9 - 2.25 R^2) / (R^2 - 1)), capped at 20: a focus measure that does not
                                     depend on contrast, black level or on how many edges the material has (it does
                                     follow how sharp the void outlines are). Inlens outlines are bright rims, not
                                     steps: the ratio can pass 2 and the sigma then reads 0.
  Astigmatism and scan bandwidth
    grad_x_over_y                    ratio, at 25, 50, 100 nm. Sobel gradient energy along x over that along y.
    grad_diag                        -1..1, same scales. 2 mean(gx gy) / (mean gx^2 + mean gy^2): 0 when both diagonals
                                     carry the same gradient energy, non-zero for an oblique astigmatism.
    psd_hf_x_over_y                  ratio. Power at 0.35-0.50 cycles/px (length 0.06 um) with the wave vector along x
                                     over that along y, 22.5 degree sectors. Below 1 = the fast scan is low-passed.
    psd_hf_d1_over_d2                ratio. The same for the two diagonals (d1: fx and fy of the same sign).
  Scan lines (length 0.025 um = 1 px lag)
    linemean_dy_rms_dn, linemean_dy_max_dn   DN. RMS and largest step between the means of successive scan lines.
    linemean_dy_excess               ratio. sqrt(n x mean squared step of the line means / mean squared difference of
                                     vertically adjacent pixels), n = pixels per line. 1 when pixel differences are
                                     independent along the line; larger when whole lines step together (line-to-line
                                     brightness jitter) or the differences are correlated along the scan.
    linemean_dx_rms_dn, linemean_dx_max_dn, linemean_dx_excess   the same between successive pixel columns.
    linecorr_y_mean, linecorr_y_min, linecorr_y_sd   Pearson r between each scan line and the next: mean, worst pair and
                                     spread over the pairs (a torn or shifted line shows in the minimum).
    linecorr_x_mean, linecorr_x_min, linecorr_x_sd   the same between successive pixel columns.
    resid_rho_x1, resid_rho_y1, resid_rho_x2, resid_rho_y2   lag-1 and lag-2 autocorrelation of the picture minus its
                                     sigma = 2 px blur (mostly noise): white noise gives about -0.05 in both
                                     directions, a slow detector raises the x value. Length 0.025 / 0.05 um.
  Drift
    drift_y_dn_per10um, drift_x_dn_per10um     DN per 10 um. Least-squares slope of the graphite level over 8 bands
                                     stacked along y (length 33.4 um, slow scan: time drift) and 8 bands along x (173.6 um).
                                     Band graphite level = median of the sigma = 2 px blurred picture over the band's
                                     solid interior. (The histogram mode of the anchors' recipe was tried first: where
                                     the graphite peak is broad it jumps between flake populations, band-to-band RMS
                                     4.4 DN against 1.7 DN for the median on one smoke crop, and on a two-peaked
                                     Inlens histogram it is meaningless.)
    drift_y_rel_per10um, drift_x_rel_per10um   the same slope / scale_dn (share of the graphite scale per 10 um).
    drift_y_resid_dn, drift_x_resid_dn         DN. RMS of the band levels about that line (wobble that is not a slope).

Scalars in view `anchored`:
    BSE: noise_g, void_thr_g, bright_thr_g, bright_mode_g, bright_mode_found (crop.anchors, graphite units; the last is
         0/1), void_level_g, bright_level_g (the phase levels above in graphite units; the void level is the "pore
         floor", the strongest acquisition fingerprint in notes/feature_screen.md), focus_lap2_excess_g (graphite units).
    Inlens, SE: noise_rank (Immerkaer sigma of the rank-normalised picture).

Blocks, per detector (view `raw`, same tags):
    hist256            256 values: the grey-code histogram as fractions (keeps the exact comb pattern).
    psd_radial_log10   24 values: log10 mean power (DN^2) in rings of 1/64 cycles/px from 0.125 to 0.5 cycles/px
                       (wavelength 0.2 to 0.05 um): the roll-off into the noise floor.
    psd_hf_angular     8 values: power at 0.35-0.50 cycles/px in 22.5 degree sectors of wave-vector direction
                       (0 = along x, 4 = along y), divided by their mean.
    band_levels_y, band_levels_x   8 values each: (band graphite level - their mean) / scale_dn (the shape of the drift).

Checked on one smoke crop (BSE), because the six synthetic imaging changes contain no drift, line jitter or astigmatism:
    a +1 %/10 um brightness ramp down the frame raised drift_y_rel_per10um by 0.0082 (0.0098 with the phase maps held
        fixed: the maps follow the brightness and take part of the ramp out) and noise_drift_y_rel_per10um by 0.0094;
    a 0.5 DN offset on every scan line took linemean_dy_rms_dn from 0.25 to 0.75 DN (0.75 expected) and
        linemean_dy_excess from 1.4 to 4.1, and left the column statistics, drift, noise and spectrum where they were;
    a 1 px blur along x only took psd_hf_x_over_y from 0.78 to 0.003, grad_x_over_y from 0.88 to 0.40 and resid_rho_x1
        from 0.10 to 0.79 (resid_rho_y1 0.03 to 0.06), with psd_hf_d1_over_d2 and grad_diag unchanged;
    a [1 2 1] / 4 blur along one diagonal took psd_hf_d1_over_d2 from 1.01 to 0.03 and grad_diag from 0.01 to -0.31, with
        the x / y ratios unchanged (0.78 to 0.82, 0.88 to 0.86).
"""
import math

import numpy as np
from scipy import fft as sfft
from scipy import ndimage as ndi

from bank.core import LEAKRISK_DETECTORS, PX_NM, FeatureResult, block_mean
from features._common.harmonise import immerkaer_sigma

FAMILY = "imgqc"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {
    "detectors": ["BSE", "Inlens", "SE"],
    "percentiles": [0.5, 1, 2, 5, 25, 50, 75, 95, 98, 99, 99.5],
    "floor_min_frac": 1e-5,            # a code counts as occupied from 10 ppm of the pixels
    "comb_range_pct": [1, 99],
    "comb_low_ratio": 0.1,
    "rawmode_window_pct": [15, 92],    # as the anchors: the main peak is searched between these pixel percentiles
    "rawmode_smooth_codes": 3,
    "blur_sigma_px": 2,                # the anchors' recipe (features/_common/config.yaml)
    "black_percentile": 0.5,
    "fwhm_bin_dn": 0.25,               # histogram of the blurred solid interior, for the graphite peak width
    "fwhm_smooth_bins": 4,
    "fwhm_window_pct": [10, 90],       # the peak is searched between these percentiles (keeps off a saturation spike)
    "interior_erode_px": 3,            # void and bright interiors
    "solid_margin_px": 4,              # the solid interior keeps this far from every other phase
    "min_px": 1000,                    # a phase interior smaller than this is treated as empty
    "scales": [1, 2, 4],               # block-mean factors for noise and gradients
    "psd_tile": 256,
    "psd_stride": 128,
    "psd_floor_band": [0.47, 0.5],     # cycles/px
    "psd_corner_from": 0.4,
    "psd_hf_band": [0.35, 0.5],
    "psd_rings": 32,
    "psd_rings_from": 8,
    "resid_lags": [1, 2],
    "drift_bands": 8,
    "edge_sigmas_px": [1.5, 3.0],      # Gaussian-derivative scales compared on the void outline
    "edge_psf_cap_px": 20.0,
}

_IMMERKAER = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
_TO_SIGMA = math.sqrt(math.pi / 2) / 6


# ----------------------------------------------------------------------------------------------------
# small tools
# ----------------------------------------------------------------------------------------------------
def _percentiles(hist, q):
    """Percentiles of integer grey codes from their histogram: code k is the bin [k - 0.5, k + 0.5), clipped to 0..255."""
    total = hist.sum()
    if total <= 0:
        return np.zeros(len(q))
    cdf = np.concatenate([[0.0], np.cumsum(hist, dtype=np.float64)]) / total
    return np.clip(np.interp(np.asarray(q, np.float64) / 100.0, cdf, np.arange(257) - 0.5), 0.0, 255.0)


def _peak(smooth, lo, hi):
    """(mode, fwhm) in bins of the tallest point of `smooth` between bins lo..hi. The mode is parabola-refined, the
    half-maximum crossings are interpolated; a side that never falls to half ends at the edge of the histogram."""
    lo, hi = int(max(lo, 0)), int(min(hi, len(smooth) - 1))
    i = lo + int(np.argmax(smooth[lo:hi + 1]))
    top = smooth[i]
    if top <= 0:
        return float(i), 0.0
    shift = 0.0
    if 0 < i < len(smooth) - 1:
        a, b, c = smooth[i - 1], smooth[i], smooth[i + 1]
        if a - 2 * b + c != 0:
            shift = float(np.clip(0.5 * (a - c) / (a - 2 * b + c), -0.5, 0.5))
    half = top / 2
    below = np.flatnonzero(smooth[:i] <= half)
    left = 0.0
    if below.size:
        k = below[-1]
        left = k + (half - smooth[k]) / (smooth[k + 1] - smooth[k])
    below = np.flatnonzero(smooth[i + 1:] <= half)
    right = len(smooth) - 1.0
    if below.size:
        k = i + 1 + below[0]
        right = k - (half - smooth[k]) / (smooth[k - 1] - smooth[k])
    return i + shift, float(right - left)


def _bands(img, solid, axis, cfg, reduce=np.median):
    """`reduce` of img over the solid interior of equal bands stacked along `axis` (0: along y, 1: along x); over the
    whole band where it has fewer than min_px solid pixels. With the blurred picture and the median: the graphite level."""
    n = cfg["drift_bands"]
    size = img.shape[axis] // n
    out = []
    for b in range(n):
        cut = (slice(b * size, (b + 1) * size), slice(None)) if axis == 0 else (slice(None), slice(b * size, (b + 1) * size))
        values = img[cut][solid[cut]]
        out.append(reduce(values if values.size >= cfg["min_px"] else img[cut]))
    return np.array(out, np.float64)


def _slope(levels, extent_um):
    """(slope per 10 um, RMS about the line) of band levels spread evenly over extent_um."""
    x = (np.arange(len(levels)) + 0.5) * extent_um / len(levels)
    slope, intercept = np.polyfit(x, levels, 1)
    return float(slope * 10), float(np.sqrt(np.mean((levels - (slope * x + intercept)) ** 2)))


def _welch(img, size, stride, floor_band):
    """Mean periodogram of Hann-windowed, mean-removed tiles, normalised so that white noise of variance v gives v in
    every bin. -> (power[fy, fx >= 0], fy, fx, radial frequency, every tile's mean power in the floor ring); cycles/px."""
    window = np.outer(np.hanning(size), np.hanning(size))
    norm = (window ** 2).sum()
    fy, fx = sfft.fftfreq(size), sfft.rfftfreq(size)
    fr = np.hypot(fy[:, None], fx[None, :])
    ring = (fr >= floor_band[0]) & (fr <= floor_band[1])
    power = np.zeros((size, size // 2 + 1))
    tile_floor = []
    for y in range(0, img.shape[0] - size + 1, stride):
        t = np.lib.stride_tricks.sliding_window_view(img[y:y + size], size, axis=1)[:, ::stride]
        t = np.ascontiguousarray(t.transpose(1, 0, 2), dtype=np.float64)
        t -= t.mean(axis=(1, 2), keepdims=True)
        t *= window
        f = sfft.rfft2(t, axes=(1, 2), workers=1)
        p = f.real ** 2 + f.imag ** 2
        power += p.sum(axis=0)
        tile_floor.append(p[:, ring].mean(axis=1))
    tile_floor = np.concatenate(tile_floor) / norm
    return power / (len(tile_floor) * norm), fy, fx, fr, tile_floor


def _lines(a):
    """a: (n_lines, n_px). -> (mean of every line, Pearson r between every line and the next, mean squared difference
    between the pixels of every line and the next)."""
    mean = a.mean(axis=1)
    z = a - mean[:, None]
    ss = np.einsum("ij,ij->i", z, z)
    cross = np.einsum("ij,ij->i", z[:-1], z[1:])
    den = np.sqrt(ss[:-1] * ss[1:])
    r = np.divide(cross, den, out=np.zeros_like(cross), where=den > 0)
    return mean, r, (ss[:-1] + ss[1:] - 2 * cross) / a.shape[1] + np.diff(mean) ** 2


def _interiors(crop, cfg):
    """Phase interiors shared by the three detectors: where a grey level and a noise are measured cleanly."""
    e = cfg["interior_erode_px"]
    other = crop.phase("void_hi") | crop.phase("bright_hi") | crop.phase("bright_fixed") | crop.phase("dim")
    inside = {"void": ndi.binary_erosion(crop.phase("void"), iterations=e),
              "solid": ~ndi.binary_dilation(other, iterations=cfg["solid_margin_px"]),
              "bright": ndi.binary_erosion(crop.phase("bright"), iterations=e)}
    solid2 = ndi.binary_erosion(block_mean(inside["solid"], 2) == 1)          # the solid interior at 50 nm
    outline = crop.phase("void") & ~ndi.binary_erosion(crop.phase("void"))    # 1 px wide void outline
    return inside, solid2, outline


# ----------------------------------------------------------------------------------------------------
# one detector
# ----------------------------------------------------------------------------------------------------
def _detector(res, crop, det, inside, solid2, outline, cfg):
    tag = "leakrisk" if det in LEAKRISK_DETECTORS else "imaging"
    px_um = PX_NM / 1000
    raw = crop.view(det, "raw")
    n_y, n_x = raw.shape

    def put(stat, value, length_um=None, scale=1, view="raw"):
        res.scalar(det, view, PX_NM * scale, stat, value, length_um=length_um, tag=tag)

    def block(stat, array, length_um=None):
        res.block(det, "raw", PX_NM, stat, array, length_um=length_um, tag=tag)

    # ---- tone: percentiles, clipping, comb, the main peak of the unblurred histogram
    hist = np.bincount(raw.ravel(), minlength=256).astype(np.float64)
    n = hist.sum()
    codes = np.arange(256.0)
    for q, v in zip(cfg["percentiles"], _percentiles(hist, cfg["percentiles"])):
        put(f"p{q:g}", v)
    median = _percentiles(hist, [50])[0]
    mean = (hist * codes).sum() / n
    put("mean_dn", mean)
    put("std_dn", math.sqrt((hist * (codes - mean) ** 2).sum() / n))
    put("sat0_frac", hist[0] / n)
    put("sat255_frac", hist[255] / n)
    occupied = np.flatnonzero(hist >= cfg["floor_min_frac"] * n)
    put("floor_dn", occupied[0])
    put("floor_frac", hist[occupied[0]] / n)
    put("ceil_dn", occupied[-1])
    put("ceil_frac", hist[occupied[-1]] / n)

    k1, k99 = (int(round(v)) for v in _percentiles(hist, cfg["comb_range_pct"]))
    k1, k99 = max(k1, 1), min(k99, 254)                      # the two end codes hold clipping, not comb
    empty = low = ragged = 0.0
    if k99 - k1 >= 4:
        h = hist[k1:k99 + 1]
        taller = np.maximum(np.concatenate([[0.0], h[:-1]]), np.concatenate([h[1:], [0.0]]))
        empty = float((h == 0).mean())
        low = float((h < cfg["comb_low_ratio"] * taller).mean())
        ragged = float(np.sqrt(np.mean((h[1:-1] - 0.5 * (h[:-2] + h[2:])) ** 2)) / h.mean())
    put("comb_empty_frac", empty)
    put("comb_low_frac", low)
    put("comb_ragged", ragged)
    p = hist[hist > 0] / n
    put("hist_entropy_bits", -(p * np.log2(p)).sum())
    put("hist_max_frac", hist.max() / n)
    block("hist256", hist / n)

    lo, hi = (int(round(v)) for v in _percentiles(hist, cfg["rawmode_window_pct"]))
    body = hist.copy()
    body[0] = body[255] = 0.0
    mode, fwhm = _peak(ndi.gaussian_filter1d(body, cfg["rawmode_smooth_codes"], mode="constant"), lo, hi)
    put("rawmode_dn", mode)
    put("rawmode_fwhm_dn", fwhm)

    # ---- black level, graphite level and its width on the blurred picture
    a = raw.astype(np.float64)
    blur = ndi.gaussian_filter(a, cfg["blur_sigma_px"])
    on_solid = blur[inside["solid"]]                         # the graphite peak alone
    if on_solid.size < cfg["min_px"]:
        on_solid = blur[::2, ::2].ravel()
    if det == "BSE":
        black, graphite = crop.anchors["black"], crop.anchors["graphite"]
    else:
        black, graphite = float(np.percentile(blur[::2, ::2], cfg["black_percentile"])), float(np.median(on_solid))
    scale_dn = max(graphite - black, 1.0)
    bw = cfg["fwhm_bin_dn"]
    fine = ndi.gaussian_filter1d(np.histogram(on_solid, np.arange(0.0, 255.0 + 2 * bw, bw))[0].astype(np.float64),
                                 cfg["fwhm_smooth_bins"], mode="constant")
    put("black_dn", black)
    put("graphite_dn", graphite)
    put("scale_dn", scale_dn)
    lo, hi = np.percentile(on_solid, cfg["fwhm_window_pct"])
    put("graphite_fwhm_dn", _peak(fine, lo / bw, hi / bw)[1] * bw)
    del on_solid

    # ---- noise: Immerkaer at three scales, inside the three phases, and the spectral floor
    sigma = {}
    for s in cfg["scales"]:
        sigma[s] = immerkaer_sigma(crop.view(det, "raw", s))
        put("noise_immerkaer_dn", sigma[s], 2 * s * px_um, scale=s)
    response = np.abs(ndi.convolve(raw.astype(np.float32), _IMMERKAER, mode="reflect"))
    levels, variances, phase_level, phase_sigma = [], [], {}, {}
    for phase in ("void", "solid", "bright"):
        m = inside[phase]
        if int(m.sum()) >= cfg["min_px"]:
            phase_level[phase] = float(_percentiles(np.bincount(raw[m], minlength=256).astype(np.float64), [50])[0])
            phase_sigma[phase] = float(_TO_SIGMA * response[m].mean(dtype=np.float64))
            levels.append(phase_level[phase])
            variances.append(phase_sigma[phase] ** 2)
        else:                                                # an empty phase: the whole picture's values
            phase_level[phase], phase_sigma[phase] = float(median), sigma[1]
        put(f"{phase}_level_dn", phase_level[phase])
        put(f"noise_{phase}_dn", phase_sigma[phase], 2 * px_um)
    gain = 0.0
    if len(levels) >= 2 and max(levels) - min(levels) >= 1.0:
        gain = float(np.polyfit(levels, variances, 1)[0])
    put("noise_gain_dn", gain, 2 * px_um)
    for axis, name, extent_um in ((0, "y", n_y * px_um), (1, "x", n_x * px_um)):
        band_noise = _bands(response, inside["solid"], axis, cfg, lambda v: _TO_SIGMA * v.mean(dtype=np.float64))
        slope, wobble = _slope(band_noise, extent_um)
        typical = float(band_noise.mean())
        put(f"noise_drift_{name}_rel_per10um", slope / typical if typical > 0 else 0.0, extent_um)
        put(f"noise_drift_{name}_resid_rel", wobble / typical if typical > 0 else 0.0, extent_um)
    del response

    power, fy, fx, fr, tile_floor = _welch(a, cfg["psd_tile"], cfg["psd_stride"], cfg["psd_floor_band"])
    lo, hi = cfg["psd_floor_band"]
    put("psd_floor_dn", math.sqrt(np.median(power[(fr >= lo) & (fr <= hi)])), 2 * px_um)
    put("psd_floor_tile_dn", math.sqrt(np.median(tile_floor)), 2 * px_um)
    c = cfg["psd_corner_from"]
    put("psd_corner_dn", math.sqrt(np.median(power[(np.abs(fy)[:, None] >= c) & (fx[None, :] >= c)])), math.sqrt(2) * px_um)
    rings, first = cfg["psd_rings"], cfg["psd_rings_from"]
    ring = np.floor(fr / (0.5 / rings)).astype(int)
    radial = np.array([power[ring == k].mean() for k in range(first, rings)])
    block("psd_radial_log10", np.log10(np.maximum(radial, 1e-12)))
    sector = np.rint(np.mod(np.arctan2(fy[:, None], fx[None, :]), np.pi) / (np.pi / 8)).astype(int) % 8
    lo, hi = cfg["psd_hf_band"]
    band = (fr >= lo) & (fr <= hi)
    angular = np.array([power[band & (sector == k)].mean() for k in range(8)])
    hf_um = px_um / (0.5 * (lo + hi))
    put("psd_hf_x_over_y", angular[0] / angular[4] if angular[4] > 0 else 1.0, hf_um)
    put("psd_hf_d1_over_d2", angular[2] / angular[6] if angular[6] > 0 else 1.0, hf_um)
    block("psd_hf_angular", angular / angular.mean() if angular.mean() > 0 else np.ones(8), hf_um)

    # ---- focus and astigmatism: Sobel gradient energy along x and y at three scales
    for s in cfg["scales"]:
        v = a if s == 1 else crop.view(det, "raw", s).astype(np.float64)
        gx, gy = ndi.sobel(v, axis=1), ndi.sobel(v, axis=0)
        exx, eyy, exy = (float(np.einsum("ij,ij->", p, q)) / v.size for p, q in ((gx, gx), (gy, gy), (gx, gy)))
        length = 2 * s * px_um
        put("tenengrad", exx + eyy, length, scale=s)
        put("tenengrad_excess", exx + eyy - 24 * sigma[s] ** 2, length, scale=s)
        put("tenengrad_norm", (exx + eyy) / (64 * v.var()) if v.var() > 0 else 0.0, length, scale=s)
        put("grad_x_over_y", exx / eyy if eyy > 0 else 1.0, length, scale=s)
        put("grad_diag", 2 * exy / (exx + eyy) if exx + eyy > 0 else 0.0, length, scale=s)
    del gx, gy
    focus = 0.0
    if int(solid2.sum()) >= cfg["min_px"]:
        focus = float(ndi.laplace(crop.view(det, "raw", 2).astype(np.float64))[solid2].var() - 5 * phase_sigma["solid"] ** 2)
    put("focus_lap2_excess", focus, 4 * px_um, scale=2)
    s1, s2 = cfg["edge_sigmas_px"]
    ratio, psf = 1.0, cfg["edge_psf_cap_px"]
    if int(outline.sum()) >= cfg["min_px"]:
        g1 = np.median(ndi.gaussian_gradient_magnitude(a, s1)[outline])
        g2 = np.median(ndi.gaussian_gradient_magnitude(a, s2)[outline])
        ratio = float(g1 / g2) if g2 > 0 else 1.0
        if ratio > 1.0:
            psf = min(math.sqrt(max((s2 ** 2 - ratio ** 2 * s1 ** 2) / (ratio ** 2 - 1), 0.0)), cfg["edge_psf_cap_px"])
    put("edge_g_ratio", ratio, 4 * px_um)
    put("edge_psf_px", psf, 4 * px_um)

    # ---- scan lines: successive scan lines (along y) and successive pixel columns (along x)
    for axis, lines in (("y", a), ("x", np.ascontiguousarray(a.T))):
        line_mean, r, pixel_msd = _lines(lines)
        d = np.diff(line_mean)
        put(f"linemean_d{axis}_rms_dn", np.sqrt(np.mean(d ** 2)), px_um)
        put(f"linemean_d{axis}_max_dn", np.abs(d).max(), px_um)
        put(f"linemean_d{axis}_excess", math.sqrt(lines.shape[1] * np.mean(d ** 2) / pixel_msd.mean()) if pixel_msd.mean() > 0 else 0.0,
            px_um)
        put(f"linecorr_{axis}_mean", r.mean(), px_um)
        put(f"linecorr_{axis}_min", r.min(), px_um)
        put(f"linecorr_{axis}_sd", r.std(), px_um)
    del lines
    resid = a - blur
    energy = float(np.einsum("ij,ij->", resid, resid)) / resid.size
    for lag in cfg["resid_lags"]:
        along_x = float(np.einsum("ij,ij->", resid[:, :-lag], resid[:, lag:])) / resid[:, lag:].size
        along_y = float(np.einsum("ij,ij->", resid[:-lag], resid[lag:])) / resid[lag:].size
        put(f"resid_rho_x{lag}", along_x / energy if energy > 0 else 0.0, lag * px_um)
        put(f"resid_rho_y{lag}", along_y / energy if energy > 0 else 0.0, lag * px_um)
    del resid

    # ---- drift: slope of the graphite level over 8 bands along y (time) and 8 bands along x
    for axis, name, extent_um in ((0, "y", n_y * px_um), (1, "x", n_x * px_um)):
        band_level = _bands(blur, inside["solid"], axis, cfg)
        slope, wobble = _slope(band_level, extent_um)
        put(f"drift_{name}_dn_per10um", slope, extent_um)
        put(f"drift_{name}_rel_per10um", slope / scale_dn, extent_um)
        put(f"drift_{name}_resid_dn", wobble, extent_um)
        block(f"band_levels_{name}", (band_level - band_level.mean()) / scale_dn, extent_um)

    # ---- the same quantities in anchored units
    if det == "BSE":
        anchors = crop.anchors
        for stat, value, length in (("noise_g", anchors["bse_noise_sigma"], 2 * px_um),
                                    ("void_thr_g", anchors["void_threshold"], None),
                                    ("bright_thr_g", anchors["bright_threshold"], None),
                                    ("bright_mode_g", anchors["bright_mode"], None),
                                    ("bright_mode_found", float(anchors["bright_mode_found"]), None),
                                    ("void_level_g", (phase_level["void"] - black) / scale_dn, None),
                                    ("bright_level_g", (phase_level["bright"] - black) / scale_dn, None)):
            put(stat, value, length, view="anchored")
        put("focus_lap2_excess_g", focus / scale_dn ** 2, 4 * px_um, scale=2, view="anchored")
    else:
        rank_sigma = crop.anchors["inlens_noise_sigma"] if det == "Inlens" else immerkaer_sigma(crop.view(det, "anchored"))
        put("noise_rank", rank_sigma, 2 * px_um, view="anchored")

    # ---- the two arrays that live through the whole pass must be what they were. Seen once, on a laptop that had run
    # out of memory: one 16 KB page of `a` read back as zeros mid-run and 22 columns were silently wrong (one scan line
    # 17 DN off). Fail loudly instead: the runner reports the crop version and it can be rerun.
    if not (np.array_equal(a, raw) and np.array_equal(blur, ndi.gaussian_filter(a, cfg["blur_sigma_px"]))):
        raise RuntimeError(f"{det}: a working copy of the picture changed during extraction (memory fault); rerun this crop version")


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    inside, solid2, outline = _interiors(crop, cfg)
    for det in cfg["detectors"]:
        _detector(res, crop, det, inside, solid2, outline, cfg)
    return res
