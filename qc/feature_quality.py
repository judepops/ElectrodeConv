"""How good is each hand-crafted feature? Measured, not assumed.

    python qc/feature_quality.py            # -> qc/processed/feature_quality.{csv,json}

Per feature (the 13 tile features and the chord ratio), from the tile table and the two spot tables:
  session_r2       share of spot-to-spot variance explained by the imaging session (one-way R2; 13 sessions on 31
                   spots, so about 0.40 is what noise alone gives)
  split_half_r     reliability: correlation across spots between the mean over the left half of a spot's tiles and the
                   mean over the right half
  mask_agreement   correlation across spots between the feature from the BSE-threshold masks and from the seg3 masks:
                   how much the number depends on the segmentation recipe
  losess, perm_p   single-feature balanced accuracy for the batch, leave one session out (evalkit), and its permutation
                   p: descriptive only, never a gate
  trust            high / medium / low from the measurement gates alone (reliability and mask agreement; batch
                   separation never enters, so the trust cannot be tuned to the answer)
Gates: high = split_half_r >= 0.5 and mask_agreement >= 0.7 and session_r2 < 0.8; medium = split_half_r >= 0.35 and
mask_agreement >= 0.5; low otherwise. qc/impacts.py reads the trust from here when the file exists.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LOSSLARP_MASKS", "harmonise")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cnn import evalkit as ek  # noqa: E402
from cnn.tile_features import FEATURES  # noqa: E402
from preprocessing.preprocess import PROCESSED_NAME  # noqa: E402

COLS = FEATURES + ["solid_chord_hv_ratio"]
OUT_DIR = ROOT / "qc" / PROCESSED_NAME
GATES = {"high": {"split_half_r": 0.5, "mask_agreement": 0.7, "session_r2_max": 0.8}, "medium": {"split_half_r": 0.35, "mask_agreement": 0.5}}


def with_ratio(df):
    df = df.copy()
    df["solid_chord_hv_ratio"] = df["solid_chord_x_um"] / df["solid_chord_y_um"]
    return df


def session_r2(x, sess):
    tot = ((x - x.mean()) ** 2).sum()
    within = sum(((x[sess == s] - x[sess == s].mean()) ** 2).sum() for s in np.unique(sess))
    return float(1 - within / tot) if tot > 0 else float("nan")


def corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 2 else float("nan")


def trust_of(r):
    g = GATES["high"]
    if r["split_half_r"] >= g["split_half_r"] and r["mask_agreement"] >= g["mask_agreement"] and r["session_r2"] < g["session_r2_max"]:
        return "high"
    g = GATES["medium"]
    if r["split_half_r"] >= g["split_half_r"] and r["mask_agreement"] >= g["mask_agreement"]:
        return "medium"
    return "low"


def main(n_perm=100):
    tiles = with_ratio(pd.read_csv(ROOT / "cnn" / "processed" / "tile_features.csv"))
    spots = pd.read_csv(ROOT / "qc" / "processed" / "features_table.csv")
    spots = spots[spots.batch != "Test"].sort_values(["batch", "sample_id"]).reset_index(drop=True)
    seg3_path = ROOT / "qc" / "processed_seg3" / "features_table.csv"
    seg3 = pd.read_csv(seg3_path) if seg3_path.exists() else None
    if seg3 is not None:
        seg3 = seg3[seg3.batch != "Test"].set_index("sample_id").loc[spots.sample_id]
    half = tiles.col < tiles.col.max() / 2
    left = tiles[half].groupby("sample_id")[COLS].mean().loc[spots.sample_id]
    right = tiles[~half].groupby("sample_id")[COLS].mean().loc[spots.sample_id]
    meta = ek.meta_for(spots.batch, spots.sample_id, spots.session)
    sess = spots.session.to_numpy()
    rows = []
    for f in COLS:
        x = spots[f].to_numpy(float)
        sc = ek.score(x[:, None], meta, clfs=("lr",), n_perm=n_perm)
        r = {"feature": f, "session_r2": session_r2(x, sess), "split_half_r": corr(left[f], right[f]),
             "mask_agreement": corr(x, seg3[f]) if seg3 is not None else float("nan"),
             "losess": sc["lr_losess"], "perm_p": sc["lr_losess_perm_p"], "mixed": sc["lr_mixed"],
             "b3_mean": float(x[spots.batch == "Batch_3"].mean()), "b3_sd": float(x[spots.batch == "Batch_3"].std(ddof=1))}
        r["trust"] = trust_of(r)
        rows.append(r)
        print(f"{f:26s} session R2 {r['session_r2']:.2f}  split-half r {r['split_half_r']:.2f}  mask agreement {r['mask_agreement']:.2f}  "
              f"losess {r['losess']:.2f} (p {r['perm_p']:.2f})  -> {r['trust']}", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT_DIR / "feature_quality.csv", index=False)
    (OUT_DIR / "feature_quality.json").write_text(json.dumps({"gates": GATES, "n_perm": n_perm, "seg3_available": seg3 is not None,
                                                              "features": {r["feature"]: r for r in rows}}, indent=1, default=float))
    print(f"wrote {OUT_DIR / 'feature_quality.csv'} and .json; trust: " + ", ".join(f"{r['feature']} {r['trust']}" for r in rows))


if __name__ == "__main__":
    main()
