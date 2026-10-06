"""Thin solid and depth profiles per spot, from the FULL image height (the tiles keep only a central window).

    python qc/depth_profile.py              # -> qc/processed/depth_profile.csv (31 training spots + the test spots if present)
    python qc/depth_profile.py --workers 4

Same recipe as preprocessing/preprocess.py (anchor, noise top-up, segmentation), on rows CROP_TOP .. H - CROP_BOTTOM
instead of the central 1336 rows. Bands of 11.2 um are counted up from the bottom edge, which we read as the
current-collector side (only epqdaau9 shows the Cu band itself; ask Polaron). Columns:
    thin_solid_frac                 share of the solid in ligaments thinner than 0.5 um, on the standard central window
    depth_porosity_b0_frac          porosity of the bottom 11.2 um band
    depth_interface_b0_per_um       pore/solid interface per area, bottom band
    depth_interface_b1_per_um       the same, 11.2-22.4 um above the bottom
    depth_interface_slope_per_10um  least-squares change of interface density per 10 um TOWARDS the bottom (> 0: more
                                    interface near the current collector)

Where they come from (old repo, ledger entries thin_solid and binder_depth_profile): a sparse autoencoder on DINOv2-L
BSE patch tokens found latents that separate Batch_3 from the rest; the cleanest fires on thin solid slivers and flake
tips (thin_solid is its hand-crafted version). Profiling that direction with depth showed Batch_1 and Batch_2 get
denser towards the bottom edge while Batch_3 stays flat. thin_solid: distance to the nearest pore, max-filtered over
9 px to the half-thickness of the ligament a pixel belongs to (a cheap stand-in for local thickness, Hildebrand &
Ruegsegger 1997). Nothing here uses batch labels; constants are the old repo's, frozen before this port.
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from preprocessing import preprocess as pp  # noqa: E402
from qc.features_table import DEPTH_COLUMNS, DEPTH_CSV, TEST_DIR, TEST_IDS  # noqa: E402

BAND_PX = 448                          # 11.2 um bands, as the old repo's features/depth_profile
THIN_UM = 0.5                          # thin-solid threshold (full ligament thickness)
CONTEXT_PX = 9                         # max-filter window: distance to pore -> ligament half-thickness


def spot_row(batch_dir, sample_id, batch):
    raw = dataclasses.replace(pp.load_spot(batch_dir, sample_id), batch=batch)
    H, W = raw.bse.shape
    top, bottom = pp.CROP_TOP, H - pp.CROP_BOTTOM
    void = pp.preprocess(raw, box=(top, bottom, pp.CROP_SIDE, W - pp.CROP_SIDE)).void
    solid = ~void
    half = ndi.maximum_filter(ndi.distance_transform_edt(solid), CONTEXT_PX)
    thin = solid & (half <= THIN_UM / 2 / pp.PIXEL_UM)
    edge = void ^ ndi.binary_erosion(void)
    r0, r1, _, _ = pp.crop_box(H, W)
    win = slice(r0 - top, r1 - top)                              # the tiles' central window, in this array
    n = void.shape[0]
    band = (n - 1 - np.arange(n)) // BAND_PX                     # 0 = bottom
    por, inter, depth = [], [], []
    for b in range(band.max() + 1):
        rows = band == b
        if rows.sum() < BAND_PX // 2:
            continue
        por.append(void[rows].mean())
        inter.append(edge[rows].mean() / pp.PIXEL_UM)
        depth.append((b + 0.5) * BAND_PX * pp.PIXEL_UM / 10)
    slope = float(-np.polyfit(depth, inter, 1)[0]) if len(depth) >= 2 else np.nan
    return {"batch": batch, "sample_id": sample_id, "session": H,
            "thin_solid_frac": float(thin[win].sum() / max(solid[win].sum(), 1)),
            "depth_porosity_b0_frac": float(por[0]), "depth_interface_b0_per_um": float(inter[0]),
            "depth_interface_b1_per_um": float(inter[1]) if len(inter) > 1 else np.nan,
            "depth_interface_slope_per_10um": slope, "n_bands": len(depth)}


def _job(args):
    return spot_row(*args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    jobs = [(pp.DATA_DIR / b, s, b) for b, s in pp.list_spots()]
    if TEST_DIR.exists():
        jobs += [(TEST_DIR, s, "Test") for s in TEST_IDS]
    else:
        print(f"no test spots at {TEST_DIR} (set LOSSLARP_TEST_DIR): training spots only")
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(_job, jobs):
            rows.append(r)
            print(f"{r['batch']:8s} {r['sample_id']:9s} " + " ".join(f"{r[c]:.4f}" for c in DEPTH_COLUMNS), flush=True)
    df = pd.DataFrame(rows).sort_values(["batch", "sample_id"]).reset_index(drop=True)
    DEPTH_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DEPTH_CSV, index=False)
    print(f"wrote {DEPTH_CSV}: {df.shape}")
    print(df.groupby("batch")[DEPTH_COLUMNS].mean().round(4).to_string())


if __name__ == "__main__":
    main()
