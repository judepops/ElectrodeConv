"""bright_phase_frac: fraction of the BSE image that is the bright, heavier second phase.

Uses the upper threshold from porosity's segmentation, so pore / graphite / bright is one
consistent split. Also provides bright_mask(sample). No tuning of its own.

Why it matters: the bright phase is an additive (or a contaminant). Its amount is part of the
recipe, so a change here means the formulation changed.
"""
from features import feature
from features._retired.porosity.feature import segment_bse


def bright_mask(sample):
    """True where the pixel is the bright phase. Same shape as sample.bse."""
    blurred, _, high = segment_bse(sample)
    return blurred > high


@feature
def bright_phase_frac(sample):
    return float(bright_mask(sample).mean())
