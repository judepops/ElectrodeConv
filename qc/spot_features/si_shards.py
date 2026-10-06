"""si_shards: fractured silicon particles and thin debond gaps around silicon (BSE masks, standard window).

Ledger: si_fragmentation (fragmentation columns) and si_debond_gap (gap columns), both built here in one pass.
    si_shards_fractured_area_frac   share of Si area in fractured parents: >= 3 shards whose gaps close with a 2-px
                                    closing (< ~100 nm) and whose group is compact (convex-hull solidity > 0.8)
    si_shards_parents_per_1000um2   fractured parents per 1000 um2 of section
    si_shards_debond_median_frac    median over Si particles (ECD >= 0.3 um) of the share of the particle's outline
                                    where the next pixel out is pore and solid sits again within 4 px (25-100 nm):
                                    a thin gap between Si and its neighbours, not an open pore
    si_shards_debonded_particle_frac  share of those particles with more than half the outline debonded
Why: calendering cracks Si/SiOx (fresh fracture surface: SEI, contact loss, first-cycle loss); an as-made gap leaves
Si electrically isolated from the start (Muller 2018). The only Batch_1/2 hints so far are Si amount and size.
2D sections, 25 nm pixels: gaps of 1-4 px are near the resolution; relative indices only. Constants fixed before
looking at batch labels.
"""
import math

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import ConvexHull

from preprocessing import preprocess as pp

COLUMNS = ["si_shards_fractured_area_frac", "si_shards_parents_per_1000um2", "si_shards_debond_median_frac",
           "si_shards_debonded_particle_frac"]
LABELS = {"si_shards_fractured_area_frac": "Si area in fractured parent particles",
          "si_shards_parents_per_1000um2": "fractured Si parents per 1000 µm²",
          "si_shards_debond_median_frac": "Si outline with a thin debond gap (median)",
          "si_shards_debonded_particle_frac": "Si particles more than half debonded"}
MIN_PX, CLOSE_IT, MIN_SHARDS, SOLIDITY = 16, 2, 3, 0.8
DEBOND_MIN_PX, GAP_PX = int(math.pi * (0.15 / pp.PIXEL_UM) ** 2), 4
S8 = ndi.generate_binary_structure(2, 2)


def measure(spot, raw):
    void = spot.void
    si = spot.bright & ~void
    lab, n = ndi.label(si, S8)
    if n == 0:
        return {c: math.nan for c in COLUMNS}
    ids = np.arange(1, n + 1)
    area = np.bincount(lab.ravel(), minlength=n + 1)[1:].astype(float)
    keep = area >= MIN_PX
    tot = area[keep].sum()
    # fragmentation: shards whose gaps close with a small closing belong to one parent
    glab, _ = ndi.label(ndi.binary_closing(si, S8, iterations=CLOSE_IT) | si, S8)
    group = ndi.maximum(glab, lab, ids).astype(int)
    frac_area, parents = 0.0, 0
    gids, counts = np.unique(group[keep], return_counts=True)
    for g, c in zip(gids, counts):
        if c < MIN_SHARDS:
            continue
        yy, xx = np.nonzero(glab == g)
        if len(yy) < 10:
            continue
        try:
            hull = ConvexHull(np.c_[yy, xx]).volume
        except Exception:
            continue
        if hull > 0 and len(yy) / hull > SOLIDITY:
            parents += 1
            frac_area += area[keep & (group == g)].sum()
    # debond: outline pixels (first layer outside each particle) that are pore with solid again within GAP_PX
    dist, (iy, ix) = ndi.distance_transform_edt(~si, return_indices=True)
    ring = (dist > 0) & (dist < 1.5)
    owner = lab[iy, ix]
    other_solid = ~void & ~si
    near_solid = ndi.distance_transform_edt(~other_solid) <= GAP_PX
    dark = ndi.gaussian_filter(spot.bse, 1.0) < spot.meta["void_threshold"]   # the void mask fills holes < 16 px
    gap = ring & dark & near_solid
    big = np.flatnonzero(area >= DEBOND_MIN_PX) + 1
    rcount = np.bincount(owner[ring], minlength=n + 1)
    gcount = np.bincount(owner[gap], minlength=n + 1)
    share = gcount[big] / np.maximum(rcount[big], 1)
    area_um2 = void.size * pp.PIXEL_UM ** 2
    return {"si_shards_fractured_area_frac": float(frac_area / tot) if tot else math.nan,
            "si_shards_parents_per_1000um2": parents / area_um2 * 1000,
            "si_shards_debond_median_frac": float(np.median(share)) if len(share) >= 10 else math.nan,
            "si_shards_debonded_particle_frac": float((share > 0.5).mean()) if len(share) >= 10 else math.nan}
