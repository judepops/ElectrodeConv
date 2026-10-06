"""two_point_correlation: how far apart two points can be and still "see" the same phase, along x and y.

Columns: s2_void_corrlen_x_um, s2_void_corrlen_y_um, s2_bright_corrlen_x_um, s2_bright_corrlen_y_um (um),
s2_void_integral_range_um2, s2_bright_integral_range_um2 (um2).
Image: BSE, through the shared harmonised masks (features/_common): void, solid (= not void), bright (Si-like phase).

S2(r) is the probability that two points a distance r apart both lie in the phase (Torquato). It starts at the area
fraction phi (r = 0) and decays to phi^2 (independent points). The normalised version f(r) = (S2 - phi^2)/(phi - phi^2)
runs from 1 to 0; the correlation length is the r where f falls to 1/e. Along x (in the electrode plane) and y
(very likely through the thickness) separately, because calendering flattens pores and flakes.

Why it matters: a size and spacing scale per phase that needs no particle splitting (the most segmentation-robust size
descriptor we have), its x/y anisotropy (calendering), and the integral range: the area over which the phase is
correlated, which sets how precisely one image measures the phase fraction (ImageRep idea; used for error bars).

Note: with two phases, solid = not void has exactly the same normalised S2 as void (the covariance of 1 - m equals
that of m), so the s2_solid columns repeat s2_void up to border effects. s2_solid() is kept but is not a features.csv
column since the team audit (2026-10-03).

Method: per axis, the autocorrelation of every row (or column) by zero-padded FFT, summed over lines and divided by
the number of overlapping pixel pairs at each lag (no wrap-around). Linear interpolation at 1/e.
"""
import math

import numpy as np
import scipy.fft as sfft

from features import feature, load_config
from features._common.harmonise import PX_UM, fraction_se, harmonised

CFG = load_config(__file__)


def s2_profile(mask, axis, max_lag_px):
    """S2(r) for r = 0..max_lag_px pixels along one axis (axis=1: rows, x; axis=0: columns, y)."""
    m = mask.astype(np.float64)
    n = m.shape[axis]
    max_lag_px = min(max_lag_px, n - 1)
    nfft = sfft.next_fast_len(n + max_lag_px)        # padding >= n + lag: circular wrap never reaches real pixels
    spectrum = sfft.rfft(m, n=nfft, axis=axis)
    autocorr = sfft.irfft(spectrum * np.conj(spectrum), n=nfft, axis=axis)
    autocorr = autocorr[:, :max_lag_px + 1].sum(axis=0) if axis == 1 else autocorr[:max_lag_px + 1].sum(axis=1)
    pairs = m.shape[1 - axis] * (n - np.arange(max_lag_px + 1))   # pixel pairs that overlap at each lag
    return autocorr / pairs


def correlation_length_um(mask, axis):
    """r (um) where (S2 - phi^2) / (phi - phi^2) first falls to 1/e along one axis; nan if not measurable."""
    phi = float(mask.mean())
    if not CFG["min_phase_frac"] <= phi <= 1 - CFG["min_phase_frac"]:
        return math.nan
    s2 = s2_profile(mask, axis, int(round(CFG["max_lag_um"] / PX_UM)))
    f = (s2 - phi ** 2) / (phi - phi ** 2)
    below = np.flatnonzero(f < math.exp(-1))
    if len(below) == 0:
        return math.nan
    i = below[0]                                     # f[i-1] >= 1/e > f[i]: interpolate between the two lags
    return float((i - 1) + (f[i - 1] - math.exp(-1)) / (f[i - 1] - f[i])) * PX_UM


def _corrlens(mask):
    return {"corrlen_x_um": correlation_length_um(mask, axis=1), "corrlen_y_um": correlation_length_um(mask, axis=0)}


@feature
def s2_void(sample):
    void = harmonised(sample).void
    return {**_corrlens(void), "integral_range_um2": fraction_se(void)[1]}


# Not a features.csv column (team audit, 2026-10-03): duplicates s2_void by the two-phase identity (r 0.997 / 0.970).
def s2_solid(sample):
    return _corrlens(harmonised(sample).solid)


@feature
def s2_bright(sample):
    bright = harmonised(sample).bright
    return {**_corrlens(bright), "integral_range_um2": fraction_se(bright)[1]}
