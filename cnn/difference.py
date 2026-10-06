"""What is the difference between two embeddings made of? Read an embedding difference through the named features.

    python cnn/difference.py --name v2                 # -> processed/supcon/v2/difference.json
    python cnn/difference.py --name v2 --pair 4ih2ggld,0grcilhi

A linear read-out from the tile embedding to each of the 13 tile features is fitted on all training tiles (ridge,
standardised both sides). Any difference vector d between two spot embeddings (or two batch means) then maps to a
predicted difference in every feature, in units of that feature's spot-to-spot SD: "Batch_1 minus Batch_3 reads as
+1.2 SD Si agglomerate size, -0.8 SD porosity". The share of |d|^2 that lies in the span of the feature directions is
the part the features can name; the rest is what the embedding knows that the features do not. Reported for every
batch against Batch_3, every test spot against Batch_3, and any pair you ask for.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LOSSLARP_MASKS", "harmonise")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.linear_model import RidgeCV  # noqa: E402

from cnn.common import RUNS_DIR  # noqa: E402
from cnn.tile_features import FEATURES  # noqa: E402

SDIR = RUNS_DIR / "supcon"


def readout(z, tf):
    """Ridge X_tiles(std) -> F_tiles(std). -> (mu, sd of X; f_mu, f_sd; B (D x 13))."""
    key = pd.DataFrame({"sample_id": z["tile_sample_id"], "row": z["tile_row"], "col": z["tile_col"]})
    F = key.merge(tf, on=["sample_id", "row", "col"], how="left")[FEATURES].to_numpy(float)
    F = np.where(np.isfinite(F), F, np.nanmean(F, 0))
    X = z["tile_feat"].astype(float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-8] = 1.0
    f_mu, f_sd = F.mean(0), F.std(0)
    f_sd[f_sd < 1e-8] = 1.0
    m = RidgeCV(alphas=np.logspace(0, 4, 9)).fit((X - mu) / sd, (F - f_mu) / f_sd)
    r2 = m.score((X - mu) / sd, (F - f_mu) / f_sd)
    return mu, sd, f_mu, f_sd, m.coef_.T, r2


def explain_diff(d, sd, B, spot_sd_units):
    """d: raw embedding difference. -> per-feature predicted difference (feature SD units of the tile table,
    rescaled to spot SD), and the share of |d|^2 inside the feature span."""
    ds = d / sd
    Q, _ = np.linalg.qr(B)                       # orthonormal basis of the feature directions
    inside = Q @ (Q.T @ ds)
    share = float((inside @ inside) / max(ds @ ds, 1e-12))
    pred = ds @ B                                # predicted feature change in tile-SD units
    return {f: float(v * s) for f, v, s in zip(FEATURES, pred, spot_sd_units)}, share


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="v2")
    ap.add_argument("--run-dir", default=None, help="folder with embeddings.npz (default processed/supcon/<name>/full)")
    ap.add_argument("--pair", default="", help="sample_id_a,sample_id_b (a minus b)")
    a = ap.parse_args()
    rd = Path(a.run_dir) if a.run_dir else SDIR / a.name / "full"
    z = np.load(rd / "embeddings.npz")
    tf = pd.read_csv(RUNS_DIR / "tile_features.csv")
    mu, sd, f_mu, f_sd, B, r2 = readout(z, tf)
    spots = pd.read_csv(REPO / "qc" / "processed" / "features_table.csv")
    b3 = spots[spots.batch == "Batch_3"]
    spot_sd = (b3[FEATURES].std(ddof=1) / pd.Series(f_sd, index=FEATURES)).to_numpy()   # tile-SD -> Batch_3 spot-SD units
    site = {str(s): z["site_feat"][i].astype(float) for i, s in enumerate(z["sample_id"])}
    batch_of = {str(s): str(b) for s, b in zip(z["sample_id"], z["batch"])}
    means = {b: np.mean([v for s, v in site.items() if batch_of[s] == b], 0) for b in ("Batch_1", "Batch_2", "Batch_3")}
    out = {"name": a.name, "readout_r2_tiles": float(r2), "features": FEATURES, "units": "Batch_3 spot-to-spot SD of the feature",
           "pairs": []}

    def add(label, a_vec, b_vec, kind):
        feats, share = explain_diff(a_vec - b_vec, sd, B, spot_sd)
        top = sorted(feats.items(), key=lambda kv: -abs(kv[1]))
        out["pairs"].append({"label": label, "kind": kind, "features": feats, "share_named": share,
                             "distance": float(np.linalg.norm((a_vec - b_vec) / sd))})
        print(f"{label:38s} named share {share:.2f}  " + ", ".join(f"{f} {v:+.2f}" for f, v in top[:4]), flush=True)

    for b in ("Batch_1", "Batch_2"):
        add(f"{b} minus Batch_3 (means)", means[b], means["Batch_3"], "batch")
    add("Batch_1 minus Batch_2 (means)", means["Batch_1"], means["Batch_2"], "batch")
    if "test_site_feat" in z:
        for s, v in zip(z["test_sample_id"], z["test_site_feat"]):
            add(f"test {s} minus Batch_3", v.astype(float), means["Batch_3"], "test")
    if a.pair:
        x, y_ = a.pair.split(",")
        add(f"{x} minus {y_}", site[x], site[y_], "spots")
    (rd / "difference.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {rd / 'difference.json'} (feature read-out R2 on tiles {r2:.2f})")


if __name__ == "__main__":
    main()
