"""One row per spot of material features, for the verdict and the battery sliders.

    python qc/features_table.py          # -> qc/processed/features_table.csv (31 training spots + 3 test spots)

Training spots: the mean of the 13 per-tile features (cnn/tile_features.py) over the spot's 26 tiles.
Test spots (the Polaron release, one unlabeled spot per batch): preprocessed and tiled here, in memory, with the same
recipe; their tiles are saved under cnn/processed/test_tiles/Test/<id>/ so predict.py and explain.py can embed them.
tiles.csv of the training set is never touched (it defines the training folds).
Also writes cnn/processed/test_tiles/tile_features_test.csv (per tile, same columns as tile_features.csv).
"""
from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cnn.common import RUNS_DIR  # noqa: E402
from cnn.tile_features import FEATURES, OUT as TILE_FEATURES_CSV, tile_features  # noqa: E402
from preprocessing import preprocess as pp  # noqa: E402

TEST_DIR = Path(os.environ.get("LOSSLARP_TEST_DIR", Path.home() / "Downloads" / "Hackathon-Polaron-test"))
TEST_IDS = ("3e122cbj", "fn0mhxef", "xrv9xvzb")
TEST_TILES_DIR = RUNS_DIR / "test_tiles"
TEST_TILE_FEATURES_CSV = TEST_TILES_DIR / "tile_features_test.csv"
OUT_DIR = ROOT / "qc" / pp.PROCESSED_NAME
OUT = OUT_DIR / "features_table.csv"
DEPTH_CSV = OUT_DIR / "depth_profile.csv"      # qc/depth_profile.py: spot-level, from the full image height
DEPTH_COLUMNS = ["thin_solid_frac", "depth_porosity_b0_frac", "depth_interface_b0_per_um",
                 "depth_interface_b1_per_um", "depth_interface_slope_per_10um"]
from qc.spot_features import OUT_DIR as PLUGIN_DIR, columns as plugin_columns  # noqa: E402
PLUGIN_COLUMNS = plugin_columns()                # qc/spot_features/<id>.py: {id: [columns]}
COLUMNS = FEATURES + ["solid_chord_hv_ratio"] + DEPTH_COLUMNS + [c for cs in PLUGIN_COLUMNS.values() for c in cs]


def test_tiles(sid, force=False):
    """Preprocess + tile one test spot (batch label "Test"); cache the tiles on disk. -> (tiles, spot meta)."""
    raw = pp.load_spot(TEST_DIR, sid)
    raw = dataclasses.replace(raw, batch="Test")
    spot = pp.preprocess(raw)
    if force or not (TEST_TILES_DIR / "Test" / sid).exists():
        pp.save_tiles(spot, out_dir=TEST_TILES_DIR)
    return pp.tiles_of(spot), spot.meta


def test_tile_features(force=False) -> pd.DataFrame:
    rows = []
    for sid in TEST_IDS:
        tiles, meta = test_tiles(sid, force)
        for t in tiles:
            rows.append({"batch": "Test", "sample_id": sid, "session": int(meta["raw_height"]), "row": t.row,
                         "col": t.col, **tile_features(t)})
        print(f"test spot {sid}: {len(tiles)} tiles, height {meta['raw_height']}, Si peak found {meta.get('bright_peak_found')}")
    df = pd.DataFrame(rows)
    TEST_TILES_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TEST_TILE_FEATURES_CSV, index=False)
    return df


def spot_table(tile_df: pd.DataFrame) -> pd.DataFrame:
    """Mean of the tile features per spot, plus the chord ratio."""
    g = tile_df.groupby(["batch", "sample_id", "session"], as_index=False)[FEATURES].mean()
    g["solid_chord_hv_ratio"] = g["solid_chord_x_um"] / g["solid_chord_y_um"]
    g["n_tiles"] = tile_df.groupby(["batch", "sample_id", "session"]).size().to_numpy()
    return g


def main():
    train = pd.read_csv(TILE_FEATURES_CSV)
    parts = [spot_table(train)]
    if TEST_DIR.exists():
        parts.append(spot_table(test_tile_features()))
    else:
        print(f"no test spots at {TEST_DIR} (set LOSSLARP_TEST_DIR): training spots only")
    table = pd.concat(parts, ignore_index=True)
    if DEPTH_CSV.exists():
        table = table.merge(pd.read_csv(DEPTH_CSV)[["batch", "sample_id"] + DEPTH_COLUMNS], on=["batch", "sample_id"], how="left")
    else:
        print(f"no {DEPTH_CSV} (run qc/depth_profile.py): the depth / thin-solid columns are left empty")
        table = table.assign(**{c: float("nan") for c in DEPTH_COLUMNS})
    for plugin, cols in PLUGIN_COLUMNS.items():
        csv = PLUGIN_DIR / f"{plugin}.csv"
        if csv.exists():
            table = table.merge(pd.read_csv(csv)[["batch", "sample_id"] + cols], on=["batch", "sample_id"], how="left")
        else:
            print(f"no {csv.name} (run python qc/spot_features/run.py {plugin}): its columns are left empty")
            table = table.assign(**{c: float("nan") for c in cols})
    table = table.sort_values(["batch", "sample_id"]).reset_index(drop=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {table.shape}, batches {table.batch.value_counts().to_dict()}")
    print(table.groupby("batch")[["porosity_frac", "si_solid_frac", "si_d50_um", "solid_chord_x_um"]].median().round(3).to_string())


if __name__ == "__main__":
    main()
