"""Where the batches sit: a 2-D PCA of the spot embeddings of V1, V2 and V1 + V2, for the team page.

    python cnn/pca_plot.py                                         # -> dashboard/site/pca.js (section "Embedding map")
    python cnn/pca_plot.py --v1 v_k7_con02 --v2 supcon/v2/full     # the same from run folders under cnn/processed/

Reads   models/v1 and models/v2: embeddings.npz of each (and V1's test_embeddings.npz, V2's test_* arrays)
Needs only numpy. No checkpoint, no retraining, a second or two.

Per view, the spot embeddings are standardised feature by feature and scaled by 1 / sqrt(dimensions), exactly as
cnn/compare.py feeds them to the classifier, so V1 (1536 numbers) and V2 (512) weigh the same in V1 + V2. PCA is
fitted on the 31 training spots; the tiles and the test spots are projected onto the same two axes.

How to read it. PCA shows the two directions with the most spread, which need not be the directions that separate
the batches: batches can overlap here and still be separable in the other dimensions, and the reverse. And V2's
full model was trained on these 31 labels, so any separation in the V2 and V1 + V2 views is partly in-sample; only
V1 never saw a label.
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

from cnn.common import RUNS_DIR  # noqa: E402

OUT = REPO / "dashboard" / "site" / "pca.js"


def load(run):
    d = REPO / run if (REPO / run / "embeddings.npz").exists() else RUNS_DIR / run   # models/v1 (tracked) or a run folder
    z = np.load(d / "embeddings.npz")
    order = np.argsort(z["sample_id"].astype(str))
    r = {"site": z["site_feat"][order].astype(float), "ids": z["sample_id"][order].astype(str),
         "batch": z["batch"][order].astype(str), "session": z["session"][order].astype(int),
         "tile": z["tile_feat"].astype(float), "tile_ids": z["tile_sample_id"].astype(str),
         "tile_key": [f"{s}_{r_}_{c}" for s, r_, c in zip(z["tile_sample_id"].astype(str), z["tile_row"], z["tile_col"])] if "tile_row" in z.files else None,
         "test": None, "test_ids": None}
    if "test_site_feat" in z.files:                                   # supcon.py stores the test spots in the same file
        ids = z["test_sample_id"] if "test_sample_id" in z.files else np.unique(z["test_tile_sample_id"])
        r["test"], r["test_ids"] = z["test_site_feat"].astype(float), np.asarray(ids).astype(str)
    elif (d / "test_embeddings.npz").exists():                        # predict.py writes them next to it
        t = np.load(d / "test_embeddings.npz")
        r["test"], r["test_ids"] = t["site_feat"].astype(float), t["sample_id"].astype(str)
    if r["test"] is not None:
        o = np.argsort(r["test_ids"])
        r["test"], r["test_ids"] = r["test"][o], r["test_ids"][o]
    return r


def std(Xtr, X):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd < 1e-8] = 1.0
    return (X - mu) / sd / np.sqrt(Xtr.shape[1])


def view(label, note, runs, weights=None):
    """One PCA view from one or more runs (blocks side by side). weights: one factor per block (default 1)."""
    a = runs[0]
    assert all((r["ids"] == a["ids"]).all() for r in runs), "the runs do not hold the same spots"
    weights = weights or [1.0] * len(runs)
    runs = [{**r, "site": r["site"], "_w": w} for r, w in zip(runs, weights)]
    X = np.hstack([r["_w"] * std(r["site"], r["site"]) for r in runs])
    mean = X.mean(0)
    U, S, Vt = np.linalg.svd(X - mean, full_matrices=False)
    P = Vt[:2].T
    xy = (X - mean) @ P
    var = (S ** 2 / (S ** 2).sum())[:2]
    out = {"label": label, "note": note, "dims": int(X.shape[1]), "var": [round(float(v), 3) for v in var],
           "spots": [{"id": i, "batch": b, "session": int(s), "x": round(float(x), 4), "y": round(float(y), 4)}
                     for i, b, s, (x, y) in zip(a["ids"], a["batch"], a["session"], xy)], "tiles": [], "test": []}
    keys = [r["tile_key"] for r in runs]
    if all(k is not None for k in keys) and all(set(k) == set(keys[0]) for k in keys):      # the same tiles in every run
        idx = [{k: j for j, k in enumerate(ks)} for ks in keys]
        T = np.hstack([r["_w"] * std(r["site"], r["tile"][[ix[k] for k in keys[0]]]) for r, ix in zip(runs, idx)])
        txy = (T - mean) @ P
        bof = dict(zip(a["ids"], a["batch"]))
        out["tiles"] = [[round(float(x), 3), round(float(y), 3), int(bof[s][-1])] for (x, y), s in zip(txy, a["tile_ids"])]
    if all(r["test"] is not None for r in runs) and all((r["test_ids"] == a["test_ids"]).all() for r in runs):
        t = (np.hstack([r["_w"] * std(r["site"], r["test"]) for r in runs]) - mean) @ P
        out["test"] = [{"id": i, "x": round(float(x), 4), "y": round(float(y), 4)} for i, (x, y) in zip(a["test_ids"], t)]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--v1", default="models/v1", help="label-free model: a tracked folder (models/v1) or a run under cnn/processed/")
    ap.add_argument("--v2", default="models/v2,models/v2s1,models/v2s2,models/v2_noseg", help="batch-supervised model(s), comma-separated members ('' to skip)")
    a = ap.parse_args()
    v1 = load(a.v1)
    views = [view("V1 (label-free)", "Never saw a batch label, so this picture is not fitted to the batches.", [v1])]
    seeds = [load(r) for r in a.v2.split(",") if r]
    if seeds:
        views.append(view("V2 (trained on the batch labels)", "Trained on these 31 labels: separation here is partly in-sample.", [seeds[0]]))
        label = "V1 + V2 side by side" if len(seeds) == 1 else f"V1 + V2, {len(seeds)}-member ensemble (the final model)"
        # V1 and the V2 seeds together weigh the same: each of n seeds is scaled by 1 / sqrt(n)
        views.append(view(label, "The V2 half was trained on these 31 labels: separation here is partly in-sample.",
                          [v1] + seeds, [1.0] + [1 / np.sqrt(len(seeds))] * len(seeds)))
    data = {"runs": {"v1": a.v1, "v2": a.v2}, "n_spots": len(v1["ids"]), "n_tiles": int(len(v1["tile"])), "views": views}
    # what the embedding's batch axes are made of: the literature features of cnn/interpret_features.py (V1, out of fold)
    interp = REPO / "cnn" / "results" / "interpret_v1_local.json"
    if interp.exists():
        d = json.loads(interp.read_text())
        data["interpret"] = {"tag": d["tag"], "n_features": len(d["features"]), "axes": [
            {"id": ax, "what": d["axes"][ax]["what"], "check": d["axes"][ax]["check"],
             "top": [{"feature": c["feature"], "entry": (d["ledger"].get(c["feature"]) or {}).get("entry"),
                      "rho": round(c["rho"], 2), "q": round(c["q"], 3), "rho_session": None if c.get("rho_session") is None else round(c["rho_session"], 2)}
                     for c in sorted(d["correlations"][ax], key=lambda c: -abs(c["rho"]))[:6]]}
            for ax in ("B3_score", "B2_vs_B1") if ax in d["axes"]]}
        # the last link: what the papers say more of each of those features does (literature/evidence.json)
        try:
            import yaml
            terms = yaml.safe_load((REPO / "literature" / "evidence_terms.yaml").read_text())
            ev = {(q["concept"], q["outcome"]): q for q in json.loads((REPO / "literature" / "evidence.json").read_text())["pairs"]}
            names = {"capacity": "energy storage", "charge_speed": "charging speed", "lifespan": "lifespan",
                     "first_charge_loss": "first-charge loss", "swelling": "swelling", "uniformity": "uniformity"}
            good = {"capacity": 1, "charge_speed": 1, "lifespan": 1, "first_charge_loss": -1, "swelling": -1, "uniformity": 1}
            for ax in data["interpret"]["axes"]:
                for t in ax["top"]:
                    c = next((c for c in terms["concepts"] if t["feature"] in c["features"]), None)
                    t["outcomes"] = []
                    if c is None:
                        continue
                    flip = -1 if t["feature"] in c.get("inverse", []) else 1
                    for o in names:
                        q = ev.get((c["id"], o))
                        if q and q["consensus"] in ("more", "less"):
                            more = (1 if q["consensus"] == "more" else -1) * flip > 0
                            t["outcomes"].append({"label": names[o], "more": bool(more), "good": bool((1 if more else -1) * good[o] > 0), "n": q["n_papers"]})
        except Exception as e:                       # the map still works without the literature join
            print("literature join skipped:", e)
    OUT.write_text("window.PCA = " + json.dumps(data, separators=(",", ":")) + ";\n")
    for v in views:
        print(f"{v['label']:<34} {v['dims']:>5} numbers per spot | first two axes hold {100 * sum(v['var']):.0f} % of the spread | "
              f"{len(v['tiles'])} tiles, {len(v['test'])} test spots")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
