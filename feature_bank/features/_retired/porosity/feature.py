"""porosity_frac: fraction of the BSE image that is pore.

Also provides the shared pore / graphite / bright segmentation (segment_bse, pore_mask) that
bright_phase, pore_size and particle_size reuse. Tuning in config.yaml.

Why it matters: porosity sets how much electrolyte the electrode holds and how fast ions move.
A shift means the pressing or mixing step changed.

Method: blur the BSE image, find two multi-Otsu thresholds on a subsampled copy, apply them at
full resolution. The last sample's result is cached so the segmentation is only done once.
"""
from scipy import ndimage as ndi
from skimage.filters import threshold_multiotsu

from features import feature, load_config

CFG = load_config(__file__)
_cache = {"bse": None, "result": None}


def segment_bse(sample):
    """-> (blurred BSE, pore threshold, bright threshold). Below pore = pore, above bright = bright phase."""
    if sample.bse is not _cache["bse"]:
        blurred = ndi.gaussian_filter(sample.bse, CFG["blur_sigma_px"])
        s = CFG["subsample"]
        low, high = threshold_multiotsu(blurred[::s, ::s], classes=CFG["classes"])
        _cache["bse"], _cache["result"] = sample.bse, (blurred, int(low), int(high))
    return _cache["result"]


def pore_mask(sample):
    """True where the pixel is pore. Same shape as sample.bse."""
    blurred, low, _ = segment_bse(sample)
    return blurred < low


@feature
def porosity_frac(sample):
    return float(pore_mask(sample).mean())
