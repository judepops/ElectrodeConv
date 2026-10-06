"""fbank: a Gabor bank, Laplacian-of-Gaussian blobs and Sato ridges on the harmonised views at 25 nm per pixel.

Input and conventions
    The harmonised view (anchored intensities plus noise up to one fixed level), never the smoothed one. Intensity
    unit "u": graphite units (0 = black level, 1 = graphite) for BSE, rank units (0..1) for Inlens.
    Gabor and LoG filters are applied in the Fourier domain: the view is reflect-padded to 1344 x 7000 for a fast FFT,
    its mean is removed, and each filter is one multiplication and one inverse FFT (one response in memory at a time).
    Every statistic is taken over the interior of the window only, at least 3 sigma of the filter from each edge
    (4 sigma for Sato), so neither the padding nor the wrap-around of the FFT reaches it. For the largest filters
    this leaves 68 % (Gabor, 128 px) and 71 % (LoG, 64 px) of the rows. Saturated pixels are kept (at most 6e-6 of a crop).
    Orientations are those of the wave vector, measured from +x (columns, in-plane) towards +y (rows, downward,
    through-thickness): a000 responds to variation along x, a090 to variation along y (horizontal layering).
    The eight orientations are multiples of 22.5 degrees, named a000 a022 a045 a067 a090 a112 a135 a157 (whole degrees,
    rounded down); 45 and 135 are different directions and are never merged.

Gabor (per detector): 6 wavelengths (4, 8, 16, 32, 64, 128 px = 0.1 to 3.2 um) x 8 orientations
    The filters are those of skimage.filters.gabor_kernel(frequency=1/wavelength, theta, bandwidth=1): a complex
    carrier under an isotropic Gaussian of sigma = 0.562 wavelengths, peak gain 1. They are written directly as
    Gaussian transfer functions, which is the same kernel without its 3 sigma spatial cut-off (that cut-off depends
    on theta in skimage and would make the diagonal filters a different shape). On a real patch the mean magnitudes
    match gabor_kernel plus FFT convolution to 4 significant digits (within 0.2 % for the default cut-off).
    gabor_w<W>_a<DEG>_mean   mean magnitude of the complex response, in u. A sine wave of amplitude A reads A/2.
    gabor_w<W>_a<DEG>_std    standard deviation of the magnitude over the interior, in u.
    gabor_w<W>_c2, _s2       second angular harmonic of the eight mean magnitudes: sum(m cos 2a) / sum(m) and the
                             same with sin. Dimensionless. c2 < 0: more energy across the thickness than in-plane;
                             s2 != 0: tilted texture (sign kept).
    length_um is the wavelength.
  Tiles   gabor_tiles (26, 48): mean magnitude of every filter in each 12.8 um tile (fixed order, wavelength-major).

Laplacian of Gaussian (per detector): sigma = 1, 2, 4, 8, 16, 32, 64 px
    Response r = sigma^2 * Laplacian(Gaussian_sigma * view), scale-normalised; r > 0 on dark blobs (voids, cracks),
    r < 0 on bright blobs (bright grains). The filter responds most to blobs of diameter 2 sqrt(2) sigma
    (71 nm to 4.5 um), which is length_um.
    log_s<S>_mabs    mean |r|, in u.
    log_s<S>_std     standard deviation of r, in u.
    log_s<S>_skew    skewness of r, dimensionless: positive when dark blobs dominate, negative when bright ones do.

Sato ridges (Inlens only, unsmoothed harmonised view): skimage.filters.sato, one sigma at a time, sigma = 1, 2, 4, 8 px
    Both polarities come from one skimage Hessian per sigma (sato() would compute it twice); the output is identical
    to sato(view, [sigma], black_ridges=True / False, mode="reflect").
    sato_dark_s<S>_*     black_ridges=True: dark lines on a brighter ground (cracks, gaps between flakes).
    sato_bright_s<S>_*   black_ridges=False: bright lines (charging edges, flake rims, binder filaments).
    _mean, _std, _p99    mean, standard deviation and 99th percentile of the ridge strength, in rank units.
    A line of width 2 sigma responds most (50 to 400 nm), which is length_um.

Tags
    imaging   Gabor at 4 px, LoG at sigma 1 px and Sato at sigma 1 px. At these sizes most of the response is the
              top-up noise itself: against white noise at the harmonised level, the two smoke crops give a noise share
              of 75-85 % of the BSE and 65 % of the Inlens Gabor power at 4 px, and 66-79 % (BSE) and 50 % (Inlens) of
              the LoG variance at sigma 1; Sato at sigma 1 returns a mean of 0.020 on that noise alone, against 0.027
              on the smoke crops. They read noise colour, the fast-scan low-pass and focus, not the electrode.
    mixed     everything else. Larger filters see structure (the noise share falls below 25 % from Gabor 16 px and
              LoG sigma 4 px up), but absolute responses scale with grey-level contrast. A tone curve changes the
              bright-phase and void levels of BSE: gamma 0.8 moved the BSE Gabor means at 16 px and above by about
              10 % on the smoke crops. The rank-normalised Inlens shares its 0..1 range between structure and native
              noise, so less noise means more contrast at every scale: a 1 px blur moved the Inlens Gabor means by
              4-7 % at every wavelength. Below about 500 nm all of them also follow focus.
              c2 and s2 cancel any contrast factor and were the steadiest statistics on the smoke crops. LoG skew
              cancels only a linear factor: gamma 0.8 moved the BSE skew as much as removing half the bright grains.
    Nothing is tagged material.
"""
import numpy as np
import scipy.fft as sfft
from skimage.feature import hessian_matrix, hessian_matrix_eigvals

from bank.core import PX_NM, FeatureResult

FAMILY = "fbank"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {
    "detectors": ["BSE", "Inlens"],
    "view": "harmonised",
    "fft_shape": [1344, 7000],                    # the 1336 x 6944 window padded to sizes with small prime factors
    "gabor_wavelengths_px": [4, 8, 16, 32, 64, 128],
    "gabor_orientations": 8,                      # 0, 22.5, ..., 157.5 degrees
    "gabor_bandwidth_octaves": 1.0,               # as skimage.filters.gabor_kernel: sigma = 0.562 wavelengths
    "log_sigmas_px": [1, 2, 4, 8, 16, 32, 64],
    "margin_sigmas": 3.0,                         # Gabor and LoG statistics stay this far from the window edge
    "sato_detector": "Inlens",
    "sato_sigmas_px": [1, 2, 4, 8],
    "sato_margin_sigmas": 4.0,
    "sato_percentile": 99,
    "tile_px": 512,                               # 12.8 um
    "imaging": {"gabor_wavelengths_px": [4], "log_sigmas_px": [1], "sato_sigmas_px": [1]},   # noise-bound sizes, tagged imaging
}


def _gabor_sigma(wavelength, bandwidth):
    """Envelope sigma in px for a bandwidth in octaves: the formula of skimage.filters.gabor_kernel."""
    return wavelength / np.pi * np.sqrt(np.log(2) / 2) * (2.0 ** bandwidth + 1) / (2.0 ** bandwidth - 1)


def _spectrum(img, shape):
    """complex64 FFT of the reflect-padded view with its mean removed."""
    pad = np.pad(img, ((0, shape[0] - img.shape[0]), (0, shape[1] - img.shape[1])), mode="reflect")
    spec = sfft.fft2(pad.astype(np.float32, copy=False))
    spec[0, 0] = 0
    return spec


def _sato_both(img, sigma):
    """skimage.filters.sato(img, [sigma], mode="reflect") for black_ridges=True and for False, from one Hessian.

    sato() is sigma^2 times the positive part of the leading Hessian eigenvalue of the image (dark ridges) or of its
    negative (bright ridges), with the Hessian from these two skimage calls. Doing it here halves the cost.
    """
    eig = hessian_matrix_eigvals(hessian_matrix(img, sigma, mode="reflect", cval=0, use_gaussian_derivatives=True))   # decreasing
    return sigma ** 2 * np.maximum(eig[0], 0), sigma ** 2 * np.maximum(-eig[-1], 0)


def _tile_means(arr, size, margin):
    """Mean of every size x size tile (the order of core.tiles), over the part of it inside the interior."""
    h, w = arr.shape
    out = []
    for y in range(0, h - size + 1, size):
        for x in range(0, w - size + 1, size):
            part = arr[max(y, margin):min(y + size, h - margin), max(x, margin):min(x + size, w - margin)]
            out.append(part.mean(dtype=np.float64))
    return out


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    view, imaging = cfg["view"], cfg["imaging"]
    px_um = PX_NM / 1000.0
    hp, wp = cfg["fft_shape"]
    fy = sfft.fftfreq(hp)                                                 # cycles per px along y (rows)
    fx = sfft.fftfreq(wp)
    n_orient = cfg["gabor_orientations"]
    two_pi2 = 2 * np.pi ** 2

    for det in cfg["detectors"]:
        img = crop.view(det, view)
        h, w = img.shape
        if h > hp or w > wp:
            raise ValueError(f"fft_shape {cfg['fft_shape']} is smaller than the window {img.shape}")
        spec = _spectrum(img, (hp, wp))

        # ---- Gabor: magnitude of the response to a Gaussian window on the wave vector (cos a, sin a) / wavelength
        tile_cols = []
        for lam in cfg["gabor_wavelengths_px"]:
            sigma = _gabor_sigma(lam, cfg["gabor_bandwidth_octaves"])
            margin = int(np.ceil(cfg["margin_sigmas"] * sigma))
            length = lam * px_um
            tag = "imaging" if lam in imaging["gabor_wavelengths_px"] else "mixed"
            means = []
            for k in range(n_orient):
                theta = np.pi * k / n_orient
                gy = np.exp(-two_pi2 * sigma ** 2 * (fy - np.sin(theta) / lam) ** 2).astype(np.float32)
                gx = np.exp(-two_pi2 * sigma ** 2 * (fx - np.cos(theta) / lam) ** 2).astype(np.float32)
                band = spec * gy[:, None]
                band *= gx[None, :]
                mag = np.abs(sfft.ifft2(band, overwrite_x=True))[:h, :w]
                inner = mag[margin:h - margin, margin:w - margin]
                name = f"gabor_w{lam}_a{int(180 * k / n_orient):03d}"
                means.append(inner.mean(dtype=np.float64))
                res.scalar(det, view, PX_NM, f"{name}_mean", means[-1], length_um=length, tag=tag)
                res.scalar(det, view, PX_NM, f"{name}_std", inner.std(dtype=np.float64), length_um=length, tag=tag)
                tile_cols.append(_tile_means(mag, cfg["tile_px"], margin))
            means = np.array(means)
            angles = np.pi * np.arange(n_orient) / n_orient
            res.scalar(det, view, PX_NM, f"gabor_w{lam}_c2", (means * np.cos(2 * angles)).sum() / means.sum(), length_um=length, tag=tag)
            res.scalar(det, view, PX_NM, f"gabor_w{lam}_s2", (means * np.sin(2 * angles)).sum() / means.sum(), length_um=length, tag=tag)
        waves = cfg["gabor_wavelengths_px"]
        res.tile_block(det, view, PX_NM, "gabor_tiles", np.array(tile_cols).T, length_um=float(np.sqrt(waves[0] * waves[-1])) * px_um, tag="mixed")

        # ---- Laplacian of Gaussian, scale-normalised: transfer function -(2 pi sigma f)^2 exp(-2 pi^2 sigma^2 f^2)
        half = spec[:, :wp // 2 + 1]                                      # the half-plane a real inverse FFT needs
        f2 = (fy[:, None] ** 2 + fx[None, :wp // 2 + 1] ** 2).astype(np.float32)
        for s in cfg["log_sigmas_px"]:
            margin = int(np.ceil(cfg["margin_sigmas"] * s))
            length = 2 * np.sqrt(2) * s * px_um
            tag = "imaging" if s in imaging["log_sigmas_px"] else "mixed"
            transfer = (-2 * two_pi2 * s ** 2) * f2 * np.exp(-two_pi2 * s ** 2 * f2)
            resp = sfft.irfft2(half * transfer.astype(np.float32), s=(hp, wp), overwrite_x=True)
            inner = resp[margin:h - margin, margin:w - margin].astype(np.float64)
            mean, std = inner.mean(), inner.std()
            res.scalar(det, view, PX_NM, f"log_s{s}_mabs", np.abs(inner).mean(), length_um=length, tag=tag)
            res.scalar(det, view, PX_NM, f"log_s{s}_std", std, length_um=length, tag=tag)
            res.scalar(det, view, PX_NM, f"log_s{s}_skew", ((inner - mean) ** 3).mean() / std ** 3 if std > 0 else 0.0,
                       length_um=length, tag=tag)
        del spec, half

    # ---- Sato ridges on the unsmoothed harmonised Inlens
    det = cfg["sato_detector"]
    img = crop.view(det, view)
    h, w = img.shape
    for s in cfg["sato_sigmas_px"]:
        margin = int(np.ceil(cfg["sato_margin_sigmas"] * s))
        length = 2 * s * px_um
        tag = "imaging" if s in imaging["sato_sigmas_px"] else "mixed"
        for kind, ridge in zip(("dark", "bright"), _sato_both(img, s)):
            ridge = ridge[margin:h - margin, margin:w - margin]
            res.scalar(det, view, PX_NM, f"sato_{kind}_s{s}_mean", ridge.mean(dtype=np.float64), length_um=length, tag=tag)
            res.scalar(det, view, PX_NM, f"sato_{kind}_s{s}_std", ridge.std(dtype=np.float64), length_um=length, tag=tag)
            res.scalar(det, view, PX_NM, f"sato_{kind}_s{s}_p{cfg['sato_percentile']}", np.percentile(ridge, cfg["sato_percentile"]),
                       length_um=length, tag=tag)
    return res
