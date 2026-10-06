"""thin_solid: share of the solid that sits in thin ligaments (flake tips, slivers, thin bridges between pores).

Ledger: ledger/entries/thin_solid.yaml. Image: harmonised BSE masks from features/_common. Columns (fraction of solid):
    thin_solid_frac_0p3, thin_solid_frac_0p5, thin_solid_frac_0p8   ligaments thinner than 0.3 / 0.5 / 0.8 um

Where it comes from: a top-k sparse autoencoder on DINOv2-L patch tokens of the BSE images (analysis/interp/) found
latents that separate Batch_3 from the rest with AUC ~0.99. The cleanest of them (latent 715) fires on thin solid
slivers and acute flake tips poking into pores (interface density 1.18 vs 0.46 /um where it fires). This feature is
the hand-crafted version: distance to the nearest pore, max-filtered over `context_px` to get the half-thickness of
the ligament a pixel belongs to, thresholded. A cheap stand-in for the lower tail of the local-thickness
distribution (Hildebrand & Ruegsegger 1997).

Why it matters: thin solid ligaments are fine fragments and exposed flake edges, so more of them means more
electrolyte-accessible edge surface (SEI growth, first-cycle loss) and weaker, more fragmented particle contacts.
"""
import numpy as np
from scipy import ndimage as ndi

from features import feature, load_config
from features._common.harmonise import PX_UM, harmonised

CFG = load_config(__file__)


@feature
def thin_solid_frac(sample):
    solid = harmonised(sample).solid
    half = ndi.maximum_filter(ndi.distance_transform_edt(solid), CFG["context_px"])
    n = solid.sum()
    return {f"{t:g}".replace(".", "p"): float((solid & (half <= t / 2 / PX_UM)).sum() / n) for t in CFG["thresholds_um"]}
