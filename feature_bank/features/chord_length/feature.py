"""chord_length: mean chord (intercept) length of the solid and the pore phase, in-plane (x) and through-plane (y).

Columns: solid_chord_x_um, solid_chord_y_um, solid_chord_hv_ratio. pore_chord_x_um and pore_chord_y_um are still
computed by pore_chord() but are not features.csv columns since the team audit (2026-10-03); see the comment on it.
Image: BSE, through the shared harmonised void mask (features/_common). Unit: um (the ratio has none).

A chord is an unbroken run of one phase along an image row (x, in the electrode plane) or column (y, very likely
through the thickness: flakes lie horizontally). The mean is number-weighted: the average run length.

Why it matters: the through-plane solid chord is the typical solid distance between two pores across the thickness,
the closest image stand-in for graphite flake thickness / particle size (D50 is the first item on an anode
certificate of analysis). Longer solid chords mean longer solid-state diffusion paths; shorter ones mean finer
graphite, more surface and more SEI. The x/y ratio is the in-plane elongation of the solid skeleton (calendering
and flake alignment), which sets how much harder ions move through the thickness than along it.

Method: run lengths along every row and column of the crop. The crop border cuts some chords; the estimator in
config.yaml handles that: V_V / N_L with N_L = P_L / 2 (default) or minus-sampling with Miles-Lantuejoul weights.
Both are unbiased.
"""
import math

import numpy as np

from features import feature, load_config
from features._common.harmonise import PX_UM, harmonised

CFG = load_config(__file__)


def complete_chords(mask, axis):
    """Lengths (px) of the runs of True that touch neither end of their line, and the line length (px).

    axis=1: runs along rows (x). axis=0: runs along columns (y).
    """
    lines = mask if axis == 1 else mask.T
    n = lines.shape[1]
    padded = np.zeros((lines.shape[0], n + 2), np.int8)
    padded[:, 1:-1] = lines
    step = np.diff(padded, axis=1)                       # +1 where a run starts, -1 just after it ends
    starts, ends = np.flatnonzero(step == 1), np.flatnonzero(step == -1)
    lengths = ends - starts                              # same line, so the flat-index difference is the length
    first, after = starts % (n + 1), ends % (n + 1)      # column of the first pixel, column after the last one
    inside = (first > 0) & (after < n)                   # minus-sampling: drop runs cut by the line ends
    return lengths[inside], n


def mean_chord_um(mask, axis):
    """Number-weighted mean chord length of the True phase along one axis (um); nan if too few chords."""
    lengths, n = complete_chords(mask, axis)
    if len(lengths) < CFG["min_chords"]:
        return math.nan
    if CFG["estimator"] == "minus_sampling":
        # a chord of L px fits fully inside a line of n px at n - L - 1 positions: weight by the inverse
        weights = 1.0 / (n - lengths - 1)
        return float((weights * lengths).sum() / weights.sum()) * PX_UM
    if CFG["estimator"] != "vv_nl":
        raise ValueError(f"chord_length: unknown estimator {CFG['estimator']!r} (vv_nl or minus_sampling)")
    # V_V / N_L with N_L = P_L / 2: all phase pixels on the lines / half the phase boundaries crossed inside the
    # lines (chord starts + chord ends). Counting both ends, not starts only, gives both phases the same N_L, so
    # solid_chord / pore_chord = (1 - phi) / phi exactly, and it cancels which phase each line begins and ends in.
    lines = mask if axis == 1 else mask.T
    crossings = np.count_nonzero(lines[:, 1:] != lines[:, :-1])
    return float(lines.sum() / (crossings / 2)) * PX_UM


@feature
def solid_chord(sample):
    solid = harmonised(sample).solid
    x_um, y_um = mean_chord_um(solid, axis=1), mean_chord_um(solid, axis=0)
    return {"x_um": x_um, "y_um": y_um, "hv_ratio": x_um / y_um}


# Not a features.csv column (team audit, 2026-10-03): an identity: phi / N_L, fixed by porosity and the solid chord.
def pore_chord(sample):
    void = harmonised(sample).void
    return {"x_um": mean_chord_um(void, axis=1), "y_um": mean_chord_um(void, axis=0)}
