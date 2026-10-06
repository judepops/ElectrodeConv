"""local_thickness: how wide the pores and the solid are, as the area-weighted local thickness.

Columns (all um, a disc diameter):
    pore_lt_d50_um    half of the pore area sits in openings at least this wide
    pore_lt_d90_um    the widest 10 % of the pore area sits in openings at least this wide
    solid_lt_d50_um   the same median for the solid (graphite + Si phase + carbon-binder web)

Image: BSE, through the shared harmonised void mask (features/_common: same crop, black/graphite anchors, noise
matched). The solid is everything that is not void.

What it measures: every pixel of a phase gets the diameter of the largest disc that fits inside the phase and
covers that pixel (local thickness, Hildebrand & Rueegsegger 1997). The distribution of that diameter over the
phase area is a continuous pore-size distribution: no pore has to be cut out as an object, so touching or merged
pores, which make connected-component sizes jump, do not matter.

Why it matters: pore width sets how fast the electrode wets and how much ionic resistance the electrolyte path
has (narrow throats fill last and limit fast charge); solid thickness is the size of the particle/flake stacks
between pores (solid-state diffusion length, packing). A shift points at calendering or the graphite/Si powder.
It replaces pore_size_* (connected-component areas), which mostly counted noise specks (session R2 0.87-0.92).

Method: opening granulometry by Euclidean discs (scipy distance_transform_edt). For a radius R the disc centres
are the pixels further than R from the other phase; the opened set is every pixel within R of a centre (= the
union of all discs of radius R that fit). F(R) = opened area / phase area falls from 1 to 0 as R grows, and the
quantiles are read where F = 0.5 (d50) and F = 0.1 (d90), interpolated between integer radii; diameter = 2R+1 px.
Three things make it fast and change nothing in the result:
    - F is monotone, so only the integer radii a bisection needs are evaluated (about 11 instead of about 60);
    - a disc that fits in one pore can never reach another pore, so each pore is opened in its own small crop;
    - the solid is opened on a 2x downsampled mask (config solid_downsample; a 2x2 block is solid only if all
      four pixels are, so 1-px gaps survive). Against full resolution: |change| <= 0.03 um on 31 spots.
"""
import math

import numpy as np
from scipy import ndimage as ndi

from features import feature, load_config
from features._common.harmonise import PX_UM, harmonised

CFG = load_config(__file__)
EIGHT_CONNECTED = np.ones((3, 3), bool)


def downsample_keep_gaps(mask, factor):
    """factor x factor blocks: True only where every pixel of the block is True (thin gaps of the other phase survive)."""
    h, w = (mask.shape[0] // factor) * factor, (mask.shape[1] // factor) * factor
    return mask[:h, :w].reshape(h // factor, factor, w // factor, factor).all(axis=(1, 3))


class OpeningCurve:
    """F(R) for integer R: the share of the phase covered by Euclidean discs of radius R that fit inside it.

    Each connected object is opened in its own crop (a disc that fits in one object cannot cover another), shrunk
    to the disc centres +- R. Values are cached, since the quantile search asks for some radii twice.
    """

    def __init__(self, mask):
        self.dist = ndi.distance_transform_edt(mask)               # distance of each phase pixel to the other phase
        self.labels, n = ndi.label(mask, structure=EIGHT_CONNECTED)
        self.boxes = ndi.find_objects(self.labels)
        self.peak = ndi.maximum(self.dist, self.labels, index=np.arange(1, n + 1))  # largest disc each object holds
        self.area = np.count_nonzero(mask)
        self.max_radius = int(math.ceil(self.peak.max()))         # no disc centres beyond this radius: F = 0
        self.known = {0: 1.0}                                      # radius 0 = one pixel: covers everything

    def __call__(self, radius):
        if radius not in self.known:
            covered = 0
            for i in np.flatnonzero(self.peak > radius):           # objects too thin for this disc add nothing
                box = self.boxes[i]
                centres = (self.labels[box] == i + 1) & (self.dist[box] > radius)
                rows = np.flatnonzero(centres.any(axis=1))
                cols = np.flatnonzero(centres.any(axis=0))
                centres = centres[max(rows[0] - radius, 0):rows[-1] + radius + 1,
                                  max(cols[0] - radius, 0):cols[-1] + radius + 1]
                covered += np.count_nonzero(ndi.distance_transform_edt(~centres) <= radius)
            self.known[radius] = covered / self.area
        return self.known[radius]


def thickness_quantile_um(curve, area_share_above, px_um):
    """Diameter d (um) such that `area_share_above` of the phase has local thickness >= d.

    Bisection on integer radii for the bracket F(lo) >= share > F(hi), then linear interpolation inside it.
    """
    known = curve.known
    lo = max((r for r, f in known.items() if f >= area_share_above), default=0)
    hi = min((r for r, f in known.items() if f < area_share_above), default=curve.max_radius)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if curve(mid) >= area_share_above:
            lo = mid
        else:
            hi = mid
    f_lo, f_hi = curve(lo), curve(hi)
    radius = lo + (f_lo - area_share_above) / (f_lo - f_hi)
    return (2 * radius + 1) * px_um


def measurable(mask):
    """Local thickness needs both phases in the crop."""
    return mask.any() and not mask.all()


@feature
def pore_lt(sample):
    void = harmonised(sample).void
    if not measurable(void):
        return {"d50_um": math.nan, "d90_um": math.nan}
    curve = OpeningCurve(void)
    return {"d50_um": thickness_quantile_um(curve, 0.5, PX_UM),
            "d90_um": thickness_quantile_um(curve, 0.1, PX_UM)}


@feature
def solid_lt_d50_um(sample):
    factor = CFG["solid_downsample"]
    solid = downsample_keep_gaps(harmonised(sample).solid, factor) if factor > 1 else harmonised(sample).solid
    if not measurable(solid):
        return math.nan
    return thickness_quantile_um(OpeningCurve(solid), 0.5, PX_UM * factor)
