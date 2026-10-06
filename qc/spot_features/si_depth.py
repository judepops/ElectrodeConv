"""si_depth: silicon (bright-phase) share of the solid and Si particle size against depth from the bottom edge (BSE, full height).

Ledger: si_depth (adarsh). Bands of 11.2 um counted up from the bottom edge (read as the current-collector side, as in
qc/depth_profile.py; only epqdaau9 shows the Cu band), on rows CROP_TOP .. H - CROP_BOTTOM with the standard recipe.
    si_depth_b0_solid_frac          bright / solid area in the bottom 11.2 um band (fraction)
    si_depth_b1_solid_frac          the same, 11.2-22.4 um above the bottom
    si_depth_rel_slope_per_10um     least-squares change of the Si share per 10 um TOWARDS the bottom, divided by the
                                    spot's own mean Si share (fraction of mean per 10 um; > 0: Si-rich near the
                                    collector). Relative, so a spot with more Si overall does not read as steeper.
    si_depth_b0_d50_um              area-weighted median ECD of Si particles (bright objects >= 16 px, assigned to a band
                                    by centroid) in the bottom band (um; 2D sections, relative only)
    si_depth_b1_d50_um              the same, 11.2-22.4 um above the bottom
    si_depth_d50_slope_per_10um     least-squares change of that d50 per 10 um towards the bottom (um per 10 um)
Why: during drying, particles that settle faster than the drying front sinks pile up near the current collector
(sedimentation-dominated drying, Baburoglu et al. 2025). Stokes settling goes with density contrast x size^2; Si/SiOx
(2.2-2.3 g/cm3) is barely denser than graphite (2.2), so a Si gradient would come mostly from coarse Si or Si
agglomerates (the d50 columns), or from a slow-drying, low-viscosity slurry. More Si at the collector concentrates
swelling at the interface (delamination risk) and leaves the top Si-poor. Bands with < 10 Si particles give nan d50.
"""
import math

import numpy as np
from scipy import ndimage as ndi

from preprocessing import preprocess as pp

COLUMNS = ["si_depth_b0_solid_frac", "si_depth_b1_solid_frac", "si_depth_rel_slope_per_10um",
           "si_depth_b0_d50_um", "si_depth_b1_d50_um", "si_depth_d50_slope_per_10um"]
LABELS = {"si_depth_b0_solid_frac": "Si share of the solid, bottom 11 µm",
          "si_depth_b1_solid_frac": "Si share of the solid, 11–22 µm up",
          "si_depth_rel_slope_per_10um": "Si share gradient towards the collector (rel.)",
          "si_depth_b0_d50_um": "Si particle d50, bottom 11 µm",
          "si_depth_b1_d50_um": "Si particle d50, 11–22 µm up",
          "si_depth_d50_slope_per_10um": "Si d50 gradient towards the collector"}
BAND_PX, MIN_AREA_PX, MIN_PARTICLES = 448, 16, 10      # 11.2 um bands and object floor as qc/depth_profile / cnn


def _wquantile(v, w, q):
    o = np.argsort(v)
    return float(np.interp(q, np.cumsum(w[o]) / w.sum(), v[o]))


def _slope(x, y):
    ok = np.isfinite(y)
    return float(-np.polyfit(x[ok], y[ok], 1)[0]) if ok.sum() >= 3 else math.nan   # minus: towards the bottom


def measure(spot, raw):
    H, W = raw.bse.shape
    full = pp.preprocess(raw, box=(pp.CROP_TOP, H - pp.CROP_BOTTOM, pp.CROP_SIDE, W - pp.CROP_SIDE))
    solid = ~full.void
    si = full.bright & solid
    n = si.shape[0]
    band = (n - 1 - np.arange(n)) // BAND_PX                       # 0 = bottom
    lab, k = ndi.label(si, ndi.generate_binary_structure(2, 2))
    ids = np.arange(1, k + 1)
    area = np.asarray(ndi.sum(si, lab, ids), float) if k else np.zeros(0)
    cy = np.asarray([c[0] for c in ndi.center_of_mass(si, lab, ids)], float) if k else np.zeros(0)
    keep = area >= MIN_AREA_PX
    area, pband = area[keep], band[np.clip(np.round(cy[keep]).astype(int), 0, n - 1)]
    ecd = 2 * np.sqrt(area / np.pi) * pp.PIXEL_UM
    share, d50, depth = [], [], []
    for b in range(band.max() + 1):
        rows = band == b
        if rows.sum() < BAND_PX // 2:
            continue
        s = solid[rows].sum()
        share.append(si[rows].sum() / s if s else math.nan)
        m = pband == b
        d50.append(_wquantile(ecd[m], area[m], 0.5) if m.sum() >= MIN_PARTICLES else math.nan)
        depth.append((b + 0.5) * BAND_PX * pp.PIXEL_UM / 10)
    share, d50, depth = np.array(share), np.array(d50), np.array(depth)
    if len(depth) < 2:
        return {c: math.nan for c in COLUMNS}
    mean_share = float(si.sum() / max(solid.sum(), 1))
    return {"si_depth_b0_solid_frac": float(share[0]), "si_depth_b1_solid_frac": float(share[1]),
            "si_depth_rel_slope_per_10um": _slope(depth, share) / mean_share if mean_share > 0 else math.nan,
            "si_depth_b0_d50_um": float(d50[0]), "si_depth_b1_d50_um": float(d50[1]),
            "si_depth_d50_slope_per_10um": _slope(depth, d50)}
