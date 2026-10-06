"""psd: radial and angular log power spectra of the harmonised BSE and Inlens views at 25 nm per pixel.

How it is computed
    The harmonised view (anchored intensities plus noise up to one fixed level) is cut into 1024 px (25.6 um) tiles:
    12 along x with 50 % overlap and 2 along y (flush with the top and the bottom of the window), 24 in all. Each tile
    has its Hann-weighted mean removed, is multiplied by a 2D Hann window and Fourier transformed; the periodogram is
    |FFT|^2 / sum(window^2), so white noise of variance s^2 reads s^2 in every bin. The 24 periodograms are averaged.
    Saturated pixels are kept (an FFT needs a full tile; they are at most 6e-6 of a crop).
    Intensity unit "u": graphite units (0 = black level, 1 = graphite) for BSE, rank units (0..1) for Inlens.
    Angles are those of the wave vector, measured from +x (columns, in-plane) towards +y (rows, downward,
    through-thickness) and folded to 0..180 degrees. 0 = the image varies along x, 90 = it varies along y (horizontal
    layering puts power at 90). 45 and 135 are different directions and are never merged.

Statistics (per detector; view "harmonised", scale 25 nm)
    rad_logp_<W>nm      26 scalars. log10 of the mean power density in a ring of wavelengths, in u^2 um^2. The rings
                        are tenth-decade bands from 50 nm (Nyquist) to 19.9 um; <W> is the geometric centre in nm,
                        which is also length_um. The harmonised white-noise floor is the same constant in every crop.
    ang_<B>_a<DEG>      3 x 12 scalars. Angular profile in band B: log10 of the mean power in a 15 degree sector
                        (centres 0, 15, ..., 165) after dividing each bin by the ring mean at its wavelength, so the
                        steep radial fall-off does not let the few longest waves decide the answer. Dimensionless
                        (log10 ratio to the isotropic level; 0 = isotropic). Bands: hf 0.05-0.2 um, mid 0.2-2 um,
                        lo 2-10 um (10-20 um is left out: 1024 px tiles hold under 2.6 periods, no angular resolution).
    ang_<B>_c2, _s2     Second angular harmonic of the same whitened power: mean of cos 2a and sin 2a weighted by power.
                        Dimensionless, -1..1. c2 < 0: more variation along y than along x (horizontal layering).
                        s2 != 0: the layering is tilted away from the axes (sign kept, since no flip is ever applied).
    slope_<B>           Exponent p of power ~ frequency^p fitted by least squares to the rad_logp rings of hf, mid and
                        lo (lo here runs to 19.9 um). Dimensionless.
    logvar_fine         log10 of the grey-level variance carried by wavelengths 0.05-0.5 um, in u^2.
    logvar_struct       The same for 0.5-19.9 um ("structural" variance).
    share_0p5_2um, share_2_8um, share_8_20um
                        Share of the structural variance in each wavelength range (they add to 1). Dimensionless.
    centroid_um         Variance-weighted geometric-mean wavelength of the structural range, in um.
  Blocks
    radial_fine (10)    rad_logp for 0.05-0.5 um.          radial_coarse (16)   rad_logp for 0.5-19.9 um.
    angular_hf, angular_mid, angular_lo (12 each)           the ang_<B>_a<DEG> profiles.
  Tiles
    radial_tiles (26, 20)   rad_logp of each 512 px (12.8 um) tile of the grid of core.tiles, the grid glcm_lbp and
                            fbank also use, for the 20 rings from 50 nm to 5.0 um (a 12.8 um tile holds under 2.6
                            periods of anything longer). Same Hann window and units. Fixed tile order, no positions.

Length scales and limits
    length_um is the wavelength (ring centre, or geometric centre of a range). A Hann window blurs the spectrum by
    about +-2 bins, so the four rings above 8 um (under 3.2 periods per tile) overlap heavily and are not independent;
    they also pick up slow brightness drift along the slow-scan (y) axis.

Tags
    imaging   rings centred below 100 nm (2-4 px), everything in band hf, slope_hf and logvar_fine: at these scales the
              signal is the detector noise (topped up to a fixed level, but native noise is not white), the fast-scan
              low-pass (power along x is 0.75-0.88 of power along y at high frequency, set by the session) and focus.
    mixed     every other absolute power, slope, share and centroid, and all Inlens statistics. BSE power in graphite
              units is immune to black level and linear contrast and, above 0.5 um, to blur and noise, but it still
              scales with the bright-phase and void grey levels, which the tone curve of a session sets (bright/graphite
              ratio about 1.7-2.5): gamma 0.8 moved every BSE ring above 0.3 um by 0.08-0.12 dex on the smoke crops.
              Inlens is rank-normalised, so tone changes cancel, but its contrast (charging, edges) depends on how the
              picture was taken, and its 0..1 range is shared between structure and native noise: a 1 px blur raised
              the Inlens power by 0.04-0.06 dex at every wavelength from 0.9 to 18 um.
    material  BSE ang_lo_* (profile, c2, s2) and block angular_lo: ratios of power between directions at 2-10 um, where
              pixel noise, blur and scan low-pass have no weight and any contrast factor cancels. They describe how
              flakes and voids are aligned. On the two smoke crops the six imaging changes moved them by at most
              0.017 (gamma 1.25; blur, noise, contrast and black level by under 0.002), against 0.05-0.21 between the
              crops. Two crops are thin evidence: check the measured imaging sensitivity before trusting the tag.
"""
import functools

import numpy as np
import scipy.fft as sfft

from bank.core import PX_NM, FeatureResult, tiles

FAMILY = "psd"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {
    "detectors": ["BSE", "Inlens"],
    "view": "harmonised",
    "tile_px": 1024,                      # 25.6 um
    "stride_x_px": 512,                   # 50 % overlap along x
    "bands_per_decade": 10,               # ring edges at 2 px * 10^(i/10): 0.05, 0.063, ..., 0.5, ..., 5.0, ..., 19.9 um
    "n_bands": 26,
    "n_sectors": 12,                      # 15 degrees each, centred on 0, 15, ..., 165
    "imaging_below_um": 0.1,              # rings centred below this are tagged imaging
    "fine_below_um": 0.5,                 # radial_fine / radial_coarse and logvar_fine / logvar_struct split here
    "angular_bands_um": {"hf": [0.05, 0.2], "mid": [0.2, 2.0], "lo": [2.0, 10.0]},
    "slope_bands_um": {"hf": [0.05, 0.2], "mid": [0.2, 2.0], "lo": [2.0, 20.0]},
    "share_bands_um": {"share_0p5_2um": [0.5, 2.0], "share_2_8um": [2.0, 8.0], "share_8_20um": [8.0, 20.0]},
    "set_tile_px": 512,                   # radial_tiles: the 12.8 um grid of core.tiles ...
    "set_tile_bands": 20,                 # ... and the rings such a tile resolves (50 nm to 5.0 um)
}
TINY = 1e-30


@functools.lru_cache(maxsize=4)
def _plan(n, bands_per_decade, n_bands, n_sectors):
    """Which ring and which sector every bin of an n x n half-plane FFT belongs to (the same for every crop)."""
    ky = np.fft.fftfreq(n, 1.0 / n)                       # integer wavenumbers along y (rows)
    kx = np.arange(n // 2 + 1, dtype=np.float64)          # the half-plane kept by rfft2
    kk = np.hypot(ky[:, None], kx[None, :])
    kk[0, 0] = 1.0                                        # placeholder: the mean is dropped just below
    ring = np.floor(bands_per_decade * np.log10(n / (2.0 * kk)) + 1e-9).astype(np.int64)   # wavelength / 2 px, tenth-decades
    ring[0, 0] = -1
    keep = (ring >= 0) & (ring < n_bands)                 # drops the corners beyond Nyquist and waves longer than the last ring
    theta = np.arctan2(ky[:, None], kx[None, :]) % np.pi  # wave-vector angle from +x towards +y (down), folded to [0, pi)
    width = np.pi / n_sectors
    sector = np.floor((theta + width / 2) / width).astype(np.int64) % n_sectors
    weight = np.full(kk.shape, 2.0)                       # a bin stands for itself and its conjugate ...
    weight[:, 0] = weight[:, -1] = 1.0                    # ... except in the two columns that hold both
    plan = dict(keep=keep, ring=ring[keep], sector=sector[keep], weight=weight[keep],
                cos2=np.cos(2 * theta[keep]), sin2=np.sin(2 * theta[keep]))
    plan["ring_weight"] = np.bincount(plan["ring"], plan["weight"], n_bands)
    if not (plan["ring_weight"] > 0).all():
        raise ValueError(f"a {n} px tile leaves a wavelength ring without any bin")
    hann = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)
    plan["window"] = np.outer(hann, hann)
    return plan


def _tile_origins(shape, n, stride_x):
    """Top-left corners of the tiles: two rows flush with the top and bottom, columns centred in the window."""
    ys = sorted({0, shape[0] - n})
    n_x = (shape[1] - n) // stride_x + 1
    off = ((shape[1] - n) - (n_x - 1) * stride_x) // 2
    return [(y, off + j * stride_x) for y in ys for j in range(n_x)]


def _welch(stack, plan, n_bands):
    """Mean periodogram over a sequence of square tiles (kept bins only) and the ring means of every single tile."""
    window = plan["window"]
    norm = (window ** 2).sum()
    total, per_tile = 0.0, []
    for tile in stack:
        tile = tile.astype(np.float64)
        tile = (tile - (tile * window).sum() / window.sum()) * window
        spec = sfft.rfft2(tile)
        power = (spec.real ** 2 + spec.imag ** 2)[plan["keep"]] / norm
        total = total + power
        per_tile.append(np.bincount(plan["ring"], plan["weight"] * power, n_bands) / plan["ring_weight"])
    return total / len(per_tile), np.array(per_tile)


def _rings_in(centres, lo, hi):
    """Indices of the rings whose centre wavelength lies in [lo, hi) um."""
    return np.flatnonzero((centres >= lo) & (centres < hi))


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    n, n_bands, n_sectors = cfg["tile_px"], cfg["n_bands"], cfg["n_sectors"]
    px_um = PX_NM / 1000.0
    plan = _plan(n, cfg["bands_per_decade"], n_bands, n_sectors)
    set_bands = cfg["set_tile_bands"]
    set_plan = _plan(cfg["set_tile_px"], cfg["bands_per_decade"], set_bands, n_sectors)
    edges = 2 * px_um * 10 ** (np.arange(n_bands + 1) / cfg["bands_per_decade"])      # um
    centres = np.sqrt(edges[:-1] * edges[1:])
    fine = centres < cfg["fine_below_um"]
    sector_deg = np.arange(n_sectors) * 180 // n_sectors

    for det in cfg["detectors"]:
        view = cfg["view"]
        mixed = "mixed"
        img = crop.view(det, view)
        power, _ = _welch([img[y:y + n, x:x + n] for y, x in _tile_origins(img.shape, n, cfg["stride_x_px"])], plan, n_bands)
        ring_mean = np.bincount(plan["ring"], plan["weight"] * power, n_bands) / plan["ring_weight"]
        rad = np.log10(np.maximum(ring_mean, TINY) * px_um ** 2)                    # u^2 um^2

        for b in range(n_bands):
            tag = "imaging" if centres[b] < cfg["imaging_below_um"] else mixed
            res.scalar(det, view, PX_NM, f"rad_logp_{int(round(centres[b] * 1000)):05d}nm", rad[b], length_um=centres[b], tag=tag)
        res.block(det, view, PX_NM, "radial_fine", rad[fine], length_um=np.sqrt(edges[0] * cfg["fine_below_um"]), tag=mixed)
        res.block(det, view, PX_NM, "radial_coarse", rad[~fine], length_um=np.sqrt(cfg["fine_below_um"] * edges[-1]), tag=mixed)
        _, per_tile = _welch(tiles(img, cfg["set_tile_px"]), set_plan, set_bands)
        res.tile_block(det, view, PX_NM, "radial_tiles", np.log10(np.maximum(per_tile, TINY) * px_um ** 2),
                       length_um=np.sqrt(edges[0] * edges[set_bands]), tag=mixed)

        # angular profiles of the radially whitened spectrum
        white = plan["weight"] * power / ring_mean[plan["ring"]]
        for band, (lo, hi) in cfg["angular_bands_um"].items():
            inside = np.isin(plan["ring"], _rings_in(centres, lo, hi))
            mass = np.bincount(plan["sector"][inside], white[inside], n_sectors)
            count = np.bincount(plan["sector"][inside], plan["weight"][inside], n_sectors)
            if not (count > 0).all():
                raise ValueError(f"angular band {band}: a sector holds no bin")
            profile = np.log10(np.maximum(mass / count, TINY))
            length = float(np.sqrt(lo * hi))
            tag = "imaging" if band == "hf" else "material" if (band == "lo" and det == "BSE") else mixed
            for s in range(n_sectors):
                res.scalar(det, view, PX_NM, f"ang_{band}_a{sector_deg[s]:03d}", profile[s], length_um=length, tag=tag)
            res.scalar(det, view, PX_NM, f"ang_{band}_c2", (white[inside] * plan["cos2"][inside]).sum() / white[inside].sum(),
                       length_um=length, tag=tag)
            res.scalar(det, view, PX_NM, f"ang_{band}_s2", (white[inside] * plan["sin2"][inside]).sum() / white[inside].sum(),
                       length_um=length, tag=tag)
            res.block(det, view, PX_NM, f"angular_{band}", profile, length_um=length, tag=tag)

        # spectral slopes
        for band, (lo, hi) in cfg["slope_bands_um"].items():
            idx = _rings_in(centres, lo, hi)
            slope = np.polyfit(-np.log10(centres[idx]), rad[idx], 1)[0]             # against log10 frequency
            res.scalar(det, view, PX_NM, f"slope_{band}", slope, length_um=float(np.sqrt(lo * min(hi, edges[-1]))),
                       tag="imaging" if band == "hf" else mixed)

        # how the variance is shared between wavelengths
        variance = ring_mean * plan["ring_weight"] / n ** 2                         # u^2 per ring; white noise s^2 sums to s^2
        struct = variance[~fine].sum()
        res.scalar(det, view, PX_NM, "logvar_fine", np.log10(max(variance[fine].sum(), TINY)),
                   length_um=np.sqrt(edges[0] * cfg["fine_below_um"]), tag="imaging")
        res.scalar(det, view, PX_NM, "logvar_struct", np.log10(max(struct, TINY)),
                   length_um=np.sqrt(cfg["fine_below_um"] * edges[-1]), tag=mixed)
        for stat, (lo, hi) in cfg["share_bands_um"].items():
            res.scalar(det, view, PX_NM, stat, variance[_rings_in(centres, lo, hi)].sum() / max(struct, TINY),
                       length_um=float(np.sqrt(lo * hi)), tag=mixed)
        centroid = 10 ** ((variance[~fine] * np.log10(centres[~fine])).sum() / max(struct, TINY))
        res.scalar(det, view, PX_NM, "centroid_um", centroid, length_um=np.sqrt(cfg["fine_below_um"] * edges[-1]), tag=mixed)
    return res
