"""A worked example, not a real family (files starting with _ are skipped). Copy it to start a new family.

Grey-level moments of the anchored BSE at two scales, and the three void fractions.
"""
import numpy as np

from bank.core import PX_NM, FeatureResult

FAMILY = "_example"
TIER = 1
RUNS_ON = "cpu"
DEFAULT_CFG = {"scales": [1, 4]}


def extract(crop, cfg):
    res = FeatureResult(FAMILY)
    for s in cfg["scales"]:
        img = crop.view("BSE", "anchored", scale=s)
        res.scalar("BSE", "anchored", PX_NM * s, "mean", img.mean(), tag="mixed")
        res.scalar("BSE", "anchored", PX_NM * s, "std", img.std(), length_um=PX_NM * s / 1000, tag="mixed")
    for band in ("lo", "mid", "hi"):
        mask = crop.phase("void" if band == "mid" else f"void_{band}")
        res.scalar("BSE", "phase", PX_NM, f"void_frac_{band}", mask[crop.valid].mean())
    res.block("BSE", "anchored", PX_NM, "histogram", np.histogram(crop.view("BSE", "anchored"), bins=64, range=(-0.5, 3.0))[0] / crop.valid.size)
    return res
