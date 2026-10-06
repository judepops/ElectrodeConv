"""open_porosity: how much of the cross-section is open void (black in BSE), with its error bar.

    porosity_open_frac        void area / crop area, from the shared harmonised void mask (h.void)
    porosity_open_ci95_frac   half-width of the 95 % sampling interval of that fraction for one image
    porosity_fixed060_frac    sensitivity recipe: anchored, blurred BSE < 0.6 graphite units, same cleanup
    porosity_void_threshold   the per-image Otsu void threshold actually used, in graphite units (diagnostic)

Image: BSE only, harmonised by features/_common (same central crop of every spot, black level 0 and graphite 1,
noise topped up to one level). Unit: area fraction (0-1); the threshold is in graphite units.

Why it matters: the electrolyte lives in the pores. Less porosity means longer, narrower ion paths (effective
diffusivity ~ porosity^alpha, Bruggeman), poorer rate capability and a higher lithium-plating risk at fast charge;
more porosity means lower energy density and poorer particle contact. A shift points at calendering pressure,
coat weight or slurry solids. Read it as a RELATIVE index: a 2D section shows 8-15 % open void where the real
electrode is plausibly 25-35 % porous, because pores seen through to the material behind them (pore-back) and the
sub-resolution pores in the carbon-binder web read as solid.

The error bar is sampling error only (two-point correlation of the void mask, the ImageRep idea): one image of
~5800 um2 is a small sample of a heterogeneous material. Site-to-site and session variation come on top.
"""
import math

from features import feature, load_config
from features._common.harmonise import CFG as COMMON_CFG
from features._common.harmonise import drop_small, fill_small_holes, fraction_se, harmonised

CFG = load_config(__file__)


@feature
def porosity_open_frac(sample):
    """The decision KPI: share of the crop in the shared void mask."""
    return float(harmonised(sample).void.mean())


@feature
def porosity_open_ci95_frac(sample):
    """95 % half-width of porosity_open_frac from the void mask's two-point correlation (one image)."""
    se, _ = fraction_se(harmonised(sample).void)
    return CFG["ci_z"] * se if math.isfinite(se) else math.nan


@feature
def porosity_fixed060_frac(sample):
    """Same void definition with a fixed threshold instead of the per-image Otsu one (sensitivity check)."""
    h = harmonised(sample)
    min_px = COMMON_CFG["segmentation"]["min_void_px"]          # the cleanup h.void uses
    void = drop_small(h.bse_blur < CFG["fixed_threshold"], min_px)
    void = fill_small_holes(void, min_px)
    return float(void.mean())


@feature
def porosity_void_threshold(sample):
    """The Otsu pore/graphite split of this image, in graphite units (clamped to 0.5-0.75 in _common)."""
    return float(harmonised(sample).acq["void_threshold"])
