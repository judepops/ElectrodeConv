"""Phase geometry of the BSE phase maps: how much of each phase there is, how much boundary and how many objects it
has, how far it stays correlated along x and along y, and how long the straight runs through it are.

x is in-plane, y is through-thickness: every directional statistic is reported per axis and never pooled. Lengths
are in um (1 px = 25 nm). All statistics are measured on the Crop's phase maps (blur sigma 2 px = 50 nm, objects under
16 px removed, so nothing below about 0.1 um counts) except the Minkowski curves, which threshold the smoothed BSE.
`_lo` / `_mid` / `_hi` is the Crop's threshold band (void +-0.05 g, bright -+0.15 g; _lo is the smaller phase); for
the solid phase it is the band of the void map it is the complement of.

Scalars, phase|BSE|phase|25|...
  void_frac_{lo,mid,hi}, bright_frac_{lo,mid,hi}    area fraction on valid pixels, 0..1. No length. material:
        counted on the phase maps, whose thresholds follow the image's own grey anchors.
  dim_frac, bright_fixed_frac    area fraction of the dim-grey band (1.15-1.45 g) and of the fixed 1.45 g bright mask.
        mixed: both are cut at fixed grey levels, which move with gamma and with the bright-to-graphite grey ratio
        (on the smoke crops gamma 0.8 moves dim_frac by 46 % and bright_fixed_frac by 18 %).
  {void,bright}_perim_per_um_{lo,mid,hi}    boundary length per unit window area, um^-1 (skimage perimeter_crofton,
        4 directions, with the part that lies on the window frame removed). Probes 0.1 um upward. material.
  {void,bright}_euler_per_um2_{lo,mid,hi}   Euler number (objects minus holes, 8-connected, skimage euler_number)
        per um2 of window. Objects cut by the frame count as whole objects. Probes 0.1 um upward. material.
  s2_{void,bright}_{x,y}_len_e_um_{lo,mid,hi}    lag where the normalised two-point correlation falls to 1/e, um
        (10 if it never does within 10 um). Typically 0.5-1.5 um. material.
  s2_{void,bright}_{x,y}_len_int_um_mid          integral of the normalised correlation up to its first zero, um.
  s2_{void,bright}_len_e_x_over_y_{lo,mid,hi}, s2_{void,bright}_len_int_x_over_y_mid    x / y ratio of the two
        lengths above (above 1 = longer in-plane). material.
  chord_{void,solid,bright}_{x,y}_{mean,median,p10,p90,lmean}_um_mid    chord lengths in um: number-weighted mean,
        median, 10th and 90th percentile, and the length-weighted mean (the mean chord through a random point of the
        phase). Voids about 0.5 um, bright grains about 1 um, solid about 5 um. material.
  chord_{void,solid,bright}_{x,y}_mean_um_{lo,hi}        the mean chord at the other two thresholds.
  chord_{void,solid,bright}_mean_x_over_y_{lo,mid,hi}, chord_..._median_x_over_y_mid    x / y ratios. material.

Scalars, phase|BSE|smoothed|100|...   (read off the Minkowski curves at 100 nm pixels; mixed, see the curves)
  mink_{area,perim,euler}_t0.60    area fraction, boundary density (um^-1) and Euler density (um^-2) of the set
        brighter than 0.60 g: the solid against the void at one fixed grey level.
  mink_{area,perim,euler}_t1.47    the same for the set brighter than 1.47 g: bright grains at one fixed grey level.

Blocks
  phase|BSE|smoothed|100|mink_area_t64, phase|BSE|smoothed|{100,200}|mink_{perim,euler}_t64    Minkowski curves:
        for each of 64 fixed thresholds t = 0.39, 0.42, ... 2.28 graphite units, the set {smoothed BSE >= t} gives
        area fraction, boundary density (um^-1) and Euler density (um^-2). The smoothed BSE (blur 62 nm) is
        block-averaged to 100 and to 200 nm pixels first, and that pixel size is the length the curve probes; the
        area curve hardly depends on it and is stored once. mixed: thresholds are fixed grey levels, so gamma, blur
        and noise move the curves; below about 0.5 g they follow the grey level inside voids and above about 1.7 g
        the grey level of the bright phase, and both differ between microscope sessions.
  phase|BSE|phase|25|s2norm_{void,bright}_{x,y}    two-point correlation along one axis, normalised:
        (S2(r) - f^2) / (f - f^2), where S2(r) is the chance that two pixels r apart are both in the phase and f its
        area fraction. 1 at r = 0, 0 when uncorrelated. 39 geometrically spaced lags from 25 nm to 10 um
        (DEFAULT_CFG gives the rule; lag 0 is left out because it is always 1). S2 is the FFT autocorrelation of
        every line, zero-padded, divided by the number of pixel pairs. S2 itself is f^2 + (f - f^2) times this
        curve. material.
  phase|BSE|phase|25|chord_{void,solid,bright}_{x,y}_q19    chord length in um at the 5 %, 10 %, ... 95 % points of
        the number-weighted chord distribution. material.

Tile array (for set kernels; one line per 668 px = 16.7 um tile, 2 x 10 tiles, tile order carries no meaning)
  phase|BSE|phase|25|tiles668_geometry    6 columns: void area fraction, void boundary density (um^-1), void Euler
        density (um^-2), then the same three for the bright phase, all on the mid maps and on all pixels of the
        tile. Objects cut by a tile edge count as whole objects, so the Euler densities run higher than the
        whole-window ones. Probes how unevenly the phases are spread over 17 um. material.

Chords come from porespy.filters.apply_chords and porespy.metrics.chord_length_distribution. Conventions checked on a
small synthetic image with porespy 3.1.1: axis=1 draws chords along x and axis=0 along y; spacing=1 uses every second
line; trim_edges drops every chord that touches the window edge (they are cut short); spacing=0 must not be used,
because chord_counts then merges chords of neighbouring lines; with bins=None a chord of n px lands in the bin centred
on n + 0.5; the returned `cdf` runs from 1 down to 0. So the bins here are one pixel wide and centred on whole pixels,
and the mean and percentiles are computed from `relfreq` (percentiles interpolate inside the one-pixel bin).

An empty phase gives 0 for fractions, densities, lengths and curves, and 1 for every x / y ratio.
"""
import warnings

import numpy as np
import porespy as ps
from scipy import fft as sfft
from skimage import measure

from bank.core import PX_NM, FeatureResult, tiles

FAMILY = "phase"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {
    "mink_scales": [4, 8],               # block-mean factors of the smoothed BSE for the Minkowski curves
    "mink_scalar_scale": 4,              # the scale that also gives the area curve and the summary scalars
    "mink_t0_g": 0.39, "mink_step_g": 0.03, "mink_n": 64,   # thresholds t0, t0 + step, ... in graphite units
    "mink_void_t": 0.60, "mink_bright_t": 1.47,             # the two thresholds reported as scalars
    "s2_max_lag_px": 400,                # 10 um
    "s2_lag_points": 48,                 # lags = the distinct rounded values of geomspace(1, max_lag, points)
    "chord_spacing": 1,                  # porespy: every second line. Never 0 (see the module docstring)
    "chord_quantiles": 19,               # the block holds the k / (n + 1) quantiles, k = 1..n
    "tile_px": 668,                      # half the window height: 2 x 10 tiles of 16.7 um
}
PX_UM = PX_NM / 1000.0
BANDS = ("lo", "mid", "hi")
# nominal lengths (um) each group of statistics probes, for the catalog
LEN_MAP = 0.1
LEN_S2 = {"void": 0.7, "bright": 1.5}
LEN_CHORD = {"void": 0.5, "solid": 5.0, "bright": 1.0}


def _map(crop, phase, band):
    """The phase map at one threshold band. solid is everything that is not void."""
    if phase == "solid":
        return ~_map(crop, "void", band)
    return crop.phase(phase if band == "mid" else f"{phase}_{band}")


def _ratio(a, b):
    return float(a / b) if a > 0 and b > 0 else 1.0


# ----------------------------------------------------------------------------------------------------
# Minkowski functionals
# ----------------------------------------------------------------------------------------------------
def _frame(shape):
    """What perimeter_crofton reports for a set that fills the window: the window frame itself."""
    return measure.perimeter_crofton(np.ones(shape, bool), 4)


def _perimeter_px(mask, frame):
    """Boundary length inside the window, in pixels. perimeter_crofton pads with background, so a set and its
    complement each count their share of the frame; adding both and removing the frame leaves twice the boundary."""
    both = measure.perimeter_crofton(mask, 4) + measure.perimeter_crofton(~mask, 4)
    return max(float(both - frame) / 2.0, 0.0)


def _minkowski(mask, frame, px_um):
    """(boundary length per area in um^-1, Euler number per um2) of one binary map."""
    area_um2 = mask.size * px_um ** 2
    return _perimeter_px(mask, frame) * px_um / area_um2, float(measure.euler_number(mask, connectivity=2)) / area_um2


def _minkowski_curves(img, thresholds, px_um):
    frame = _frame(img.shape)
    out = np.zeros((3, len(thresholds)))
    for i, t in enumerate(thresholds):
        above = img >= t
        out[0, i] = above.mean()
        out[1, i], out[2, i] = _minkowski(above, frame, px_um)
    return out


# ----------------------------------------------------------------------------------------------------
# two-point correlation
# ----------------------------------------------------------------------------------------------------
def _s2(mask, axis, max_lag):
    """S2 at lags 0..max_lag px along one axis: FFT autocorrelation of every line, summed, over the pair count."""
    m = mask.astype(np.float64)
    n, lines = m.shape[axis], m.shape[1 - axis]
    nfft = sfft.next_fast_len(n + max_lag, real=True)
    f = sfft.rfft(m, n=nfft, axis=axis)
    power = (f.real ** 2 + f.imag ** 2).sum(axis=1 - axis)
    lag = np.arange(max_lag + 1)
    return sfft.irfft(power, n=nfft)[:max_lag + 1] / ((n - lag) * lines)


def _normalised(s2, f):
    """(S2 - f^2) / (f - f^2) for a phase of area fraction f; zeros when the phase is absent or fills the window."""
    if not 0.0 < f < 1.0:
        return np.zeros_like(s2)
    return (s2 - f * f) / (f - f * f)


def _corr_lengths(acf):
    """(1/e length, integral length up to the first zero) in um from a normalised curve sampled every pixel."""
    if not acf.any():
        return 0.0, 0.0
    below = np.flatnonzero(acf < np.exp(-1.0))
    if len(below):
        i = int(below[0])
        len_e = i - 1 + (acf[i - 1] - np.exp(-1.0)) / (acf[i - 1] - acf[i])
    else:
        len_e = len(acf) - 1
    zero = np.flatnonzero(acf <= 0.0)
    stop = int(zero[0]) if len(zero) else len(acf) - 1
    part = np.clip(acf[:stop + 1], 0.0, None)
    return float(len_e * PX_UM), float((part.sum() - 0.5 * (part[0] + part[-1])) * PX_UM)


# ----------------------------------------------------------------------------------------------------
# chords
# ----------------------------------------------------------------------------------------------------
CHORD_STATS = ("mean", "median", "p10", "p90", "lmean")


def _quantiles(edges, mass, q):
    """Quantiles q (ascending) of a binned distribution, interpolating inside the bin that holds each."""
    cum = np.cumsum(mass)
    k = np.minimum(np.searchsorted(cum, q, side="left"), len(mass) - 1)
    before = np.where(k > 0, cum[k - 1], 0.0)
    inside = np.divide(q - before, mass[k], out=np.full(len(k), 0.5), where=mass[k] > 0)
    return edges[k] + np.clip(inside, 0.0, 1.0) * (edges[k + 1] - edges[k])


def _chords(mask, axis, cfg):
    """porespy chords of one map along one axis -> ({stat: um}, chord length in um at the block's quantiles)."""
    spacing = int(cfg["chord_spacing"])
    if spacing < 1:
        raise ValueError("chord_spacing must be 1 or more: porespy merges touching chords when it is 0")
    n_q = int(cfg["chord_quantiles"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                      # porespy 3.1.1 reads a skimage property by its old name
        chords = ps.filters.apply_chords(mask, spacing=spacing, axis=axis, trim_edges=True)
        if not chords.any():
            return dict.fromkeys(CHORD_STATS, 0.0), np.zeros(n_q)
        edges = (np.arange(1, mask.shape[axis] + 2) - 0.5) * PX_UM        # one-pixel bins centred on 1, 2, ... px
        cld = ps.metrics.chord_length_distribution(chords, bins=edges, voxel_size=PX_UM, normalization="count")
    mass = np.asarray(cld.relfreq, np.float64)
    mass = mass / mass.sum()
    length = np.asarray(cld.bin_centers, np.float64)
    mean = float(mass @ length)
    p10, median, p90 = _quantiles(edges, mass, np.array([0.1, 0.5, 0.9]))
    stats = dict(mean=mean, median=float(median), p10=float(p10), p90=float(p90), lmean=float(mass @ length ** 2) / mean)
    return stats, _quantiles(edges, mass, np.arange(1, n_q + 1) / (n_q + 1.0))


# ----------------------------------------------------------------------------------------------------
def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    valid = crop.valid

    def frac(mask):
        return float(mask[valid].mean()) if valid.any() else 0.0

    # --- area fractions -------------------------------------------------------------------------------
    for phase in ("void", "bright"):
        for band in BANDS:
            res.scalar("BSE", "phase", PX_NM, f"{phase}_frac_{band}", frac(_map(crop, phase, band)))
    res.scalar("BSE", "phase", PX_NM, "dim_frac", frac(crop.phase("dim")), tag="mixed")
    res.scalar("BSE", "phase", PX_NM, "bright_fixed_frac", frac(crop.phase("bright_fixed")), tag="mixed")

    # --- boundary and Euler density of the phase maps ---------------------------------------------------
    frame = _frame(crop.shape)
    for phase in ("void", "bright"):
        for band in BANDS:
            perim, euler = _minkowski(_map(crop, phase, band), frame, PX_UM)
            res.scalar("BSE", "phase", PX_NM, f"{phase}_perim_per_um_{band}", perim, length_um=LEN_MAP)
            res.scalar("BSE", "phase", PX_NM, f"{phase}_euler_per_um2_{band}", euler, length_um=LEN_MAP)

    # --- Minkowski curves over fixed grey thresholds -----------------------------------------------------
    thresholds = cfg["mink_t0_g"] + cfg["mink_step_g"] * np.arange(cfg["mink_n"])
    for s in cfg["mink_scales"]:
        px_um = PX_UM * s
        curves = dict(zip(("area", "perim", "euler"), _minkowski_curves(crop.view("BSE", "smoothed", s), thresholds, px_um)))
        main = s == cfg["mink_scalar_scale"]
        for stat in (("area", "perim", "euler") if main else ("perim", "euler")):
            res.block("BSE", "smoothed", PX_NM * s, f"mink_{stat}_t{len(thresholds)}", curves[stat], length_um=px_um, tag="mixed")
        if main:
            for t in (cfg["mink_void_t"], cfg["mink_bright_t"]):
                i = int(np.argmin(np.abs(thresholds - t)))
                for stat in ("area", "perim", "euler"):
                    res.scalar("BSE", "smoothed", PX_NM * s, f"mink_{stat}_t{t:.2f}", curves[stat][i], length_um=px_um, tag="mixed")

    # --- two-point correlation along x and along y --------------------------------------------------------
    max_lag = int(cfg["s2_max_lag_px"])
    lags = np.unique(np.round(np.geomspace(1, max_lag, cfg["s2_lag_points"])).astype(int))
    for phase in ("void", "bright"):
        for band in BANDS:
            lengths = {}
            mask = _map(crop, phase, band)
            fraction = float(mask.mean())
            for axis, name in ((1, "x"), (0, "y")):
                acf = _normalised(_s2(mask, axis, max_lag), fraction)
                lengths[name] = _corr_lengths(acf)
                res.scalar("BSE", "phase", PX_NM, f"s2_{phase}_{name}_len_e_um_{band}", lengths[name][0], length_um=LEN_S2[phase])
                if band == "mid":
                    res.scalar("BSE", "phase", PX_NM, f"s2_{phase}_{name}_len_int_um_mid", lengths[name][1], length_um=LEN_S2[phase])
                    res.block("BSE", "phase", PX_NM, f"s2norm_{phase}_{name}", acf[lags], length_um=max_lag * PX_UM)
            res.scalar("BSE", "phase", PX_NM, f"s2_{phase}_len_e_x_over_y_{band}", _ratio(lengths["x"][0], lengths["y"][0]),
                       length_um=LEN_S2[phase])
            if band == "mid":
                res.scalar("BSE", "phase", PX_NM, f"s2_{phase}_len_int_x_over_y_mid", _ratio(lengths["x"][1], lengths["y"][1]),
                           length_um=LEN_S2[phase])

    # --- chord lengths along x and along y ------------------------------------------------------------------
    n_q = int(cfg["chord_quantiles"])
    for phase in ("void", "solid", "bright"):
        for band in BANDS:
            stats = {}
            for axis, name in ((1, "x"), (0, "y")):
                stats[name], quantiles = _chords(_map(crop, phase, band), axis, cfg)
                for stat in (CHORD_STATS if band == "mid" else ("mean",)):
                    res.scalar("BSE", "phase", PX_NM, f"chord_{phase}_{name}_{stat}_um_{band}", stats[name][stat],
                               length_um=LEN_CHORD[phase])
                if band == "mid":
                    res.block("BSE", "phase", PX_NM, f"chord_{phase}_{name}_q{n_q}", quantiles, length_um=LEN_CHORD[phase])
            for stat in (("mean", "median") if band == "mid" else ("mean",)):
                res.scalar("BSE", "phase", PX_NM, f"chord_{phase}_{stat}_x_over_y_{band}",
                           _ratio(stats["x"][stat], stats["y"][stat]), length_um=LEN_CHORD[phase])

    # --- fraction, boundary and Euler density per tile, for set kernels -------------------------------------
    size = int(cfg["tile_px"])
    tile_frame = _frame((size, size))
    columns = []
    for phase in ("void", "bright"):
        stack = tiles(crop.phase(phase), size)
        geometry = np.array([_minkowski(t, tile_frame, PX_UM) for t in stack])
        columns += [stack.mean(axis=(1, 2)), geometry[:, 0], geometry[:, 1]]
    res.tile_block("BSE", "phase", PX_NM, f"tiles{size}_geometry", np.stack(columns, axis=1), length_um=size * PX_UM)
    return res
