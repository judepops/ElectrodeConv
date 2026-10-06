"""Per-tile material features from the tile masks, for probing the CNN embedding.

    python cnn/tile_features.py            # -> cnn/processed/tile_features.csv (one row per tile, 806 rows)

Each number mirrors one of the spot-level hand-crafted feature groups (si_particles, open_porosity, si_fraction,
minkowski_functionals, chord_length, heterogeneity), but is computed on one 512 x 512 tile from its own pore and
Si masks, so there are 806 rows instead of 31. Pixel size 25 nm. Nothing here uses batch labels or acquisition values.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn.common import RUNS_DIR, TILES_CSV, load_tile  # noqa: E402
from preprocessing.preprocess import PIXEL_UM  # noqa: E402

MIN_AREA_PX = 16                     # objects smaller than 4 x 4 px are noise
OUT = RUNS_DIR / "tile_features.csv"

FEATURES = ["porosity_frac", "si_solid_frac", "si_n_per_1000um2", "si_d50_um", "si_d90_um", "si_aspect_aw",
            "si_agglom_d50_um", "interface_density_per_um", "pore_n_per_1000um2", "solid_chord_x_um",
            "solid_chord_y_um", "porosity_block_cv", "si_block_cv"]


def _objects(mask):
    """Label a mask, drop tiny objects. -> labels, areas (px), equivalent diameters (um) for the kept objects."""
    lab, n = ndi.label(mask)
    if n == 0:
        return lab, np.zeros(0), np.zeros(0), np.zeros(0, int)
    areas = np.bincount(lab.ravel())[1:].astype(float)
    keep = areas >= MIN_AREA_PX
    areas = areas[keep]
    return lab, areas, 2 * np.sqrt(areas / np.pi) * PIXEL_UM, np.flatnonzero(keep) + 1


def _wquantile(v, w, q):
    """Weighted quantile (area-weighted size distribution)."""
    if len(v) == 0:
        return np.nan
    o = np.argsort(v)
    cw = np.cumsum(w[o]) / w.sum()
    return float(np.interp(q, cw, v[o]))


def _aspect_aw(lab, ids, areas):
    """Area-weighted mean aspect ratio from each object's second moments (sqrt of the eigenvalue ratio)."""
    if len(ids) == 0:
        return np.nan
    yy, xx = np.indices(lab.shape)
    m = lambda f: np.asarray(ndi.sum(f, lab, ids), float)        # noqa: E731
    n = areas
    my, mx = m(yy) / n, m(xx) / n
    cyy, cxx, cxy = m(yy * yy) / n - my ** 2, m(xx * xx) / n - mx ** 2, m(yy * xx) / n - my * mx
    tr, det = cyy + cxx, cyy * cxx - cxy ** 2
    disc = np.sqrt(np.maximum(tr ** 2 / 4 - det, 0))
    l1, l2 = tr / 2 + disc, np.maximum(tr / 2 - disc, 1e-9)
    return float(np.average(np.minimum(np.sqrt(l1 / l2), 10), weights=n))   # a few 1-px-wide slivers hit 100+


def _chord(solid, axis):
    """Mean solid chord length along an axis: solid pixels / number of solid runs."""
    s = solid if axis == 1 else solid.T
    starts = s[:, 1:] & ~s[:, :-1]
    n_runs = starts.sum() + s[:, 0].sum()
    return float(s.sum() * PIXEL_UM / max(n_runs, 1))


def _block_cv(mask, b=128):
    h, w = mask.shape
    blocks = mask[: h - h % b, : w - w % b].reshape(h // b, b, w // b, b).mean((1, 3))
    return float(blocks.std() / max(blocks.mean(), 1e-9))


def tile_features(tile):
    void, bright = tile.void.astype(bool), tile.bright.astype(bool) & ~tile.void.astype(bool)
    solid = ~void
    area_um2 = void.size * PIXEL_UM ** 2
    lab_b, a_b, d_b, ids_b = _objects(bright)
    lab_p, a_p, d_p, _ = _objects(void)
    agg = ndi.binary_dilation(bright, iterations=8)               # particles within ~0.4 um merge into agglomerates
    _, a_g, d_g, _ = _objects(agg)
    boundary = void ^ ndi.binary_erosion(void)
    return {
        "porosity_frac": float(void.mean()),
        "si_solid_frac": float(bright.sum() / max(solid.sum(), 1)),
        "si_n_per_1000um2": len(a_b) / area_um2 * 1000,
        "si_d50_um": _wquantile(d_b, a_b, 0.5),
        "si_d90_um": _wquantile(d_b, a_b, 0.9),
        "si_aspect_aw": _aspect_aw(lab_b, ids_b, a_b),
        "si_agglom_d50_um": _wquantile(d_g, a_g, 0.5),
        "interface_density_per_um": float(boundary.sum() * PIXEL_UM / area_um2),
        "pore_n_per_1000um2": len(a_p) / area_um2 * 1000,
        "solid_chord_x_um": _chord(solid, 1),
        "solid_chord_y_um": _chord(solid, 0),
        "porosity_block_cv": _block_cv(void),
        "si_block_cv": _block_cv(bright),
    }


def main():
    idx = pd.read_csv(TILES_CSV)
    rows = []
    for i, r in enumerate(idx.itertuples()):
        t = load_tile(r.batch, r.sample_id, int(r.row), int(r.col))
        rows.append({"batch": r.batch, "sample_id": r.sample_id, "session": int(r.session), "row": int(r.row),
                     "col": int(r.col), **tile_features(t)})
        if (i + 1) % 100 == 0:
            print(f"{i + 1}/{len(idx)} tiles", flush=True)
    df = pd.DataFrame(rows)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {df.shape}")
    print(df[FEATURES].describe().T[["mean", "std", "min", "max"]].round(3).to_string())


if __name__ == "__main__":
    main()
