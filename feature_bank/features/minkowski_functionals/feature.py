"""minkowski_functionals: interface length and connectivity of the pore phase, per unit area.

Columns:
    interface_density_per_um     L_A, pore/solid boundary length per area (um of boundary per um2 = 1/um)
    interface_density_resid_z    L_A against what Batch_3 shows at the same porosity, in B3 residual SDs (trained)
    pore_n_per_1000um2           resolvable pores: 8-connected void objects >= 64 px (0.04 um2) per 1000 um2
    euler_density_per_1000um2    [not a features.csv column since the team audit, 2026-10-03; see the comment on the function] Euler characteristic density: those pores minus solid islands >= 64 px inside them

Image: BSE, through the shared harmonised void mask (features/_common: same crop, anchors, noise matched).

What it measures: in 2D a phase has three Minkowski functionals, area (porosity, column porosity_open_frac of
open_porosity), boundary length and Euler characteristic (number of objects minus number of holes). L_A comes
from counting boundary crossings along every row and column: P_L = crossings per um of test line, and for an
isotropic section L_A = (pi/2) P_L, averaged over x and y: L_A = (pi/4) (P_Lx + P_Ly). In 3D, for isotropic
structure, the surface area per volume is S_V = (4/pi) L_A.

Why it matters: L_A is the macro (> 50 nm) part of the electrode/electrolyte interface, where the SEI forms on the
first cycle: more surface means more first-cycle lithium loss (lower ICE). At equal porosity, more boundary means a
finer, more divided pore network; the residual removes the porosity part. The pore count says how finely the pore
space is split into separate gaps (incoming batches are lower than Batch_3 in all four within-session contrasts,
about -1.2 B3-SD, but p = 0.17 and one image is a noisy estimate). Caution: in 2D the pores are isolated and the
solid percolates, so the Euler characteristic is almost exactly the pore count, and any count is sensitive to noise
and blur (hence the shared noise matching and the 64 px floor).

interface_density_resid_z is trained: train() stores (porosity, L_A) of every baseline spot in
models/minkowski_functionals.npz; the feature fits L_A = a + b * porosity on the baseline spots (leaving the scored
spot out if it is one of them) and returns its residual divided by the residual SD of that fit. The model also
stores the hash of the shared harmonisation recipe it was trained on; after any change to features/_common the
feature refuses the stale model (NaN plus a "retrain" message) instead of scoring against old baseline values.
    python features/run_features.py --train
"""
import math

import numpy as np
from scipy import ndimage as ndi

from features import feature, load_config
from features._common import harmonise as _harmonise
from features._common.harmonise import PX_UM, harmonised
from preprocessing import MODELS_DIR

CFG = load_config(__file__)
MODEL_FILE = MODELS_DIR / "minkowski_functionals.npz"
RECIPE = getattr(_harmonise, "_RECIPE_HASH", "")   # hash of features/_common/harmonise.py + config.yaml
_counts_cache = {"h": None, "value": None}


def interface_density(void):
    """L_A in 1/um: (pi/4) * (crossings per um along rows + crossings per um along columns)."""
    h, w = void.shape
    per_um_x = np.count_nonzero(void[:, 1:] != void[:, :-1]) / (h * (w - 1) * PX_UM)
    per_um_y = np.count_nonzero(void[1:, :] != void[:-1, :]) / ((h - 1) * w * PX_UM)
    return math.pi / 4 * (per_um_x + per_um_y)


def object_counts(void):
    """-> (pores, enclosed solid islands), both >= CFG['min_object_px'].

    Pores are 8-connected and the solid 4-connected (the dual pair the 2D Euler number needs). Pores cut by the
    crop edge count (same crop size for every spot); a solid piece touching the edge is not known to be an island.
    """
    min_px = CFG["min_object_px"]
    pore_labels, _ = ndi.label(void, structure=np.ones((3, 3), bool))
    pores = int((np.bincount(pore_labels.ravel())[1:] >= min_px).sum())
    solid_labels, _ = ndi.label(~void)                            # default structure = 4-connected
    sizes = np.bincount(solid_labels.ravel())
    edge = np.unique(np.concatenate([solid_labels[0], solid_labels[-1], solid_labels[:, 0], solid_labels[:, -1]]))
    sizes[edge] = 0                                               # also drops label 0 (void)
    islands = int((sizes[1:] >= min_px).sum())
    return pores, islands


def counts_of(h):
    """object_counts of this harmonised spot, cached (two columns use it)."""
    if _counts_cache["h"] is not h:
        _counts_cache["h"], _counts_cache["value"] = h, object_counts(h.void)
    return _counts_cache["value"]


def sample_key(sample):
    return f"{sample.batch}/{sample.sample_id}"


def train(baseline_samples):
    """Save every baseline spot's porosity and L_A, with its id, to models/."""
    keys, porosity, l_a = [], [], []
    for s in baseline_samples:
        void = harmonised(s).void
        keys.append(sample_key(s))
        porosity.append(void.mean())
        l_a.append(interface_density(void))
    MODEL_FILE.parent.mkdir(exist_ok=True)
    np.savez(MODEL_FILE, keys=np.array(keys), porosity=np.array(porosity), interface_density=np.array(l_a),
             recipe=np.array(RECIPE))
    slope, intercept = np.polyfit(porosity, l_a, 1)
    print(f"  saved {MODEL_FILE.name}: {len(keys)} baseline spots, L_A = {intercept:.3f} + {slope:.3f} * porosity"
          f" (harmonisation recipe {RECIPE or '?'})")


@feature
def interface_density_per_um(sample):
    return interface_density(harmonised(sample).void)


@feature
def interface_density_resid_z(sample):
    if not MODEL_FILE.exists():
        raise FileNotFoundError(f"{MODEL_FILE} is missing. Run:  python features/run_features.py --train")
    with np.load(MODEL_FILE) as model:
        trained_on = str(model["recipe"]) if "recipe" in model.files else "unknown"
        if trained_on != RECIPE:                                  # baseline values from another void recipe
            raise RuntimeError(f"{MODEL_FILE.name} was trained on harmonisation recipe {trained_on}, the current "
                               f"one is {RECIPE}. Run:  python features/run_features.py --train")
        others = model["keys"] != sample_key(sample)              # leave this spot out if it is a baseline spot
        x, y = model["porosity"][others], model["interface_density"][others]
    if len(x) < CFG["min_baseline_spots"]:
        return math.nan
    slope, intercept = np.polyfit(x, y, 1)
    resid_sd = math.sqrt(np.sum((y - (intercept + slope * x)) ** 2) / (len(x) - 2))
    void = harmonised(sample).void
    return float((interface_density(void) - (intercept + slope * void.mean())) / resid_sd)


@feature
def pore_n_per_1000um2(sample):
    h = harmonised(sample)
    pores, _ = counts_of(h)
    return pores / h.area_um2 * 1000


# Not a features.csv column (team audit, 2026-10-03): r 0.99 with pore_n_per_1000um2 (solid islands are ~3 % of the count).
def euler_density_per_1000um2(sample):
    h = harmonised(sample)
    pores, islands = counts_of(h)
    return (pores - islands) / h.area_um2 * 1000
