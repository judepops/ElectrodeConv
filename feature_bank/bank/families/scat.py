"""Wavelet scattering (Mallat) of BSE and Inlens: a fixed, physics-style texture descriptor with no trained weights.

`kymatio.torch.Scattering2D` (kymatio 0.3.0, Morlet wavelets, L = 8 orientations, orders 0 to 2) on tiles of the
25 nm views: J = 4 on 256 px tiles (6.4 um) and J = 5 on 512 px tiles (12.8 um). Tiles cover the whole crop
(6 x 28 tiles of 256 px, 3 x 14 of 512 px, evenly spaced origins, neighbours overlapping by 8 to 100 px; fixed
order, positions never used). No mirror, no rotation, no rescale.

NEEDS kymatio 0.3.0, which is deliberately NOT in the local .venv (it requires scipy < 1.17; see
cloud/requirements-gpu.txt). It is imported inside the functions, so this file imports anywhere, but `extract`
raises ImportError where kymatio is missing. Device: cuda, then mps, then cpu (BANK_EMB_DEVICE forces one), always
float32. The Apple GPU agrees with the CPU to 2e-6 of a coefficient and is about 8 times faster than 2 CPU threads;
keep one device per feature directory all the same, because the gain-free ratios are small differences of logs.

What the paths are
    order 0   the tile low-passed over 2^J px (0.4 um for J = 4, 0.8 um for J = 5): local mean intensity.
    order 1   |tile * wavelet(j1, angle)| low-passed: how much oscillation of wavelength 2.6 * 2^j1 px there is
              along one direction. j1 = 0..J-1, so about 65, 130, 260, 515 nm and (J = 5) 1.03 um.
    order 2   ||tile * wavelet(j1, a1)| * wavelet(j2, a2)| low-passed, j2 > j1: how the envelope of the fine
              oscillation is itself modulated at the coarser wavelength (clustering, intermittency of texture).
    Angles are those of the wave vector, measured from the in-plane (x) axis and read off each filter's Fourier
    peak at run time: a0 = intensity varies along x (in-plane), a90 = it varies along y (through-thickness).
    Units: BSE in graphite units (graphite = 1), Inlens in rank units (0..1). Order 1 and 2 scale with contrast,
    which is why everything is reported as a logarithm (natural log, cfg["eps"] added first).

Blocks, per detector (BSE, Inlens), view (harmonised, anchored) and J; paths in kymatio's order (the low-pass,
then order 1 by j1 and angle, then order 2 by j1, angle 1, j2, angle 2): 417 numbers for J = 4, 681 for J = 5.
    J<J>_logmean   log of each path's mean over positions and tiles: the angle-resolved texture spectrum.
    J<J>_logstd    log of each path's standard deviation over positions and tiles: how patchy that texture is
                   between 0.4 um (J = 4) or 0.8 um (J = 5) windows.
Tile arrays:
    J<J>_logmean_tiles   (n_tiles, 417 or 681): log of each path's mean within one tile, for set kernels.
Scalars, per detector, view and J (length = the wavelength of j1, or of j2 for order 2):
    J<J>_o0_logmean                log mean of the low-pass: mean intensity of the view.
    J<J>_o1_j<j>_logmean           log of the order-1 mean over all angles: texture energy at that wavelength.
    J<J>_o1_j<j>_logstd            log of the standard deviation, over positions and tiles, of the angle-averaged
                                   order-1 map: patchiness of that texture.
    J<J>_o1_j<j>_a<deg>_rel        log(order 1 at one angle) - log(mean over angles): the angular profile, free of
                                   gain. deg = 0, 22.5, ..., 157.5.
    J<J>_o1_j<j>_logratio_a0_a90   log(order 1 at 0 deg) - log(order 1 at 90 deg): in-plane against
                                   through-thickness oscillation. Negative when layering is horizontal.
    J<J>_o2_j<j1>_j<j2>_lognorm    log(mean order 2 over angles) - log(mean order 1 at j1): order 2 normalised by
                                   its parent, free of gain; high when the fine texture comes in clumps of size j2.

Tag: everything is `mixed`. The finest wavelengths (67 to 133 nm) sit where noise and focus live, so they describe
the acquisition as much as the material; the harmonised view (every crop topped up to one noise level) is the one
to trust below 500 nm, the anchored view is kept for comparison. Coarser paths and the gain-free ratios should be
closer to material, but that is for the perturbation runs to show, not for this file to claim.
"""
import numpy as np

from bank.core import PX_NM, FeatureResult
from bank.families._emb_common import cover_tiles, pick_device

FAMILY = "scat"
TIER = 1
RUNS_ON = "gpu"
DEFAULT_CFG = {"detectors": ["BSE", "Inlens"], "views": ["harmonised", "anchored"], "L": 8, "max_order": 2, "eps": 1e-8,
               "banks": [{"J": 4, "tile_px": 256}, {"J": 5, "tile_px": 512}], "batch": {"cuda": 64, "mps": 16, "cpu": 8}}
TAG = "mixed"
_BANKS = {}


def _scattering_class():
    try:
        from kymatio.torch import Scattering2D
    except ModuleNotFoundError as e:
        if e.name != "kymatio":
            raise
        raise ImportError("scat needs kymatio 0.3.0 (cloud/requirements-gpu.txt). It is not in the local .venv on purpose: "
                          "it requires scipy < 1.17.") from e
    except ImportError:
        # scipy >= 1.17 dropped a function that kymatio's 3D module imports at package level. The 2D transform does
        # not use it, so take the 2D class directly.
        from kymatio.scattering2d.frontend.torch_frontend import ScatteringTorch2D as Scattering2D
    return Scattering2D


def _bank(J, tile_px, cfg):
    """The scattering transform for one (J, tile size), with the angle and wavelength of every wavelet. Built once."""
    key = (J, tile_px, cfg["L"], cfg["max_order"])
    if key not in _BANKS:
        S = _scattering_class()(J=J, shape=(tile_px, tile_px), L=cfg["L"], max_order=cfg["max_order"], out_type="list")
        wavelets = {}
        for psi in S.psi:                                   # the Fourier peak of each wavelet gives its wave vector
            f = np.abs(np.asarray(psi["levels"][0])).squeeze()
            iy, ix = np.unravel_index(int(np.argmax(f)), f.shape)
            fy, fx = np.fft.fftfreq(f.shape[0])[iy], np.fft.fftfreq(f.shape[1])[ix]
            step = 180.0 / cfg["L"]
            angle = (np.rint(np.degrees(np.arctan2(fy, fx)) / step) * step) % 180.0
            wavelets[int(psi["j"]), int(psi["theta"])] = (float(angle), float(1.0 / np.hypot(fy, fx)))
        _BANKS[key] = (S.to(pick_device()), wavelets)
    return _BANKS[key]


def warmup(cfg):
    for b in cfg["banks"]:
        _bank(b["J"], b["tile_px"], cfg)


def _paths(S, tiles, cfg):
    """tiles (n, T, T) -> per-path coefficients as (n, K, h, w) float64 on the CPU, and the (j, theta) of each path."""
    import torch
    device = next(S.buffers()).device
    step = int(cfg["batch"].get(device.type, 8))
    coef, meta = [], None
    with torch.inference_mode():
        for i in range(0, len(tiles), step):
            out = S(torch.from_numpy(np.ascontiguousarray(tiles[i:i + step], dtype=np.float32)).to(device))
            coef.append(torch.stack([o["coef"] for o in out], 1).cpu().numpy().astype(np.float64))   # mps has no float64
            meta = [(tuple(int(v) for v in o["j"]), tuple(int(v) for v in o["theta"])) for o in out]
    return np.concatenate(coef), meta


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    eps, L = cfg["eps"], cfg["L"]

    def log(v):
        return np.log(np.maximum(v, 0.0) + eps)

    for bank in cfg["banks"]:
        J, tile_px = bank["J"], bank["tile_px"]
        S, wavelets = _bank(J, tile_px, cfg)
        for view in cfg["views"]:
            for det in cfg["detectors"]:
                tiles = cover_tiles(np.asarray(crop.view(det, view), np.float32), tile_px)
                c, meta = _paths(S, tiles, cfg)                         # (n, K, h, w)
                expected = 1 + J * L + (L * L * J * (J - 1)) // 2 if cfg["max_order"] == 2 else 1 + J * L
                if c.shape[1] != expected or meta[0] != ((), ()):
                    raise RuntimeError(f"scat: {c.shape[1]} paths, expected {expected}: not the kymatio 0.3.0 layout")
                window_um = (2 ** J) * PX_NM / 1000.0                   # the low-pass window every path is averaged over
                path_mean = c.mean(axis=(0, 2, 3))
                res.block(det, view, PX_NM, f"J{J}_logmean", log(path_mean), length_um=window_um, layer=f"scat.J{J}", tag=TAG)
                res.block(det, view, PX_NM, f"J{J}_logstd", log(c.std(axis=(0, 2, 3))), length_um=window_um, layer=f"scat.J{J}", tag=TAG)
                res.tile_block(det, view, PX_NM, f"J{J}_logmean_tiles", log(c.mean(axis=(2, 3))), length_um=window_um,
                               layer=f"scat.J{J}", tag=TAG)
                res.scalar(det, view, PX_NM, f"J{J}_o0_logmean", log(path_mean[0]), length_um=window_um, layer=f"scat.J{J}.o0", tag=TAG)
                first = {(jt[0], th[0]): k for k, (jt, th) in enumerate(meta) if len(jt) == 1}   # (j1, theta1) -> path number
                o1_mean = {}
                for j in range(J):
                    ks = [first[j, t] for t in range(L)]
                    wavelength_um = float(np.mean([wavelets[j, t][1] for t in range(L)])) * PX_NM / 1000.0
                    layer = f"scat.J{J}.o1.j{j}"
                    o1_mean[j] = path_mean[ks].mean()
                    res.scalar(det, view, PX_NM, f"J{J}_o1_j{j}_logmean", log(o1_mean[j]), length_um=wavelength_um, layer=layer, tag=TAG)
                    res.scalar(det, view, PX_NM, f"J{J}_o1_j{j}_logstd", log(c[:, ks].mean(axis=1).std()), length_um=wavelength_um,
                               layer=layer, tag=TAG)
                    by_angle = {wavelets[j, t][0]: path_mean[first[j, t]] for t in range(L)}
                    if len(by_angle) != L or 0.0 not in by_angle or 90.0 not in by_angle:
                        raise RuntimeError(f"scat: wavelet angles {sorted(by_angle)} are not {L} distinct directions with 0 and 90")
                    for angle in sorted(by_angle):
                        res.scalar(det, view, PX_NM, f"J{J}_o1_j{j}_a{angle:g}_rel", log(by_angle[angle]) - log(o1_mean[j]),
                                   length_um=wavelength_um, layer=layer, tag=TAG)
                    res.scalar(det, view, PX_NM, f"J{J}_o1_j{j}_logratio_a0_a90", log(by_angle[0.0]) - log(by_angle[90.0]),
                               length_um=wavelength_um, layer=layer, tag=TAG)
                second = {}
                for k, (jt, _) in enumerate(meta):
                    if len(jt) == 2:
                        second.setdefault(jt, []).append(k)
                for (j1, j2), ks in sorted(second.items()):
                    wavelength_um = float(np.mean([wavelets[j2, t][1] for t in range(L)])) * PX_NM / 1000.0
                    res.scalar(det, view, PX_NM, f"J{J}_o2_j{j1}_j{j2}_lognorm", log(path_mean[ks].mean()) - log(o1_mean[j1]),
                               length_um=wavelength_um, layer=f"scat.J{J}.o2.j{j1}.j{j2}", tag=TAG)
    return res
