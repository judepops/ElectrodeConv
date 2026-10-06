"""V1 vs V2 vs V1+2 on the same folds, and what each embedding knows about the material.

    python cnn/compare.py --v2 v2 --v12 r2a           # -> cnn/results/compare.json + compare.md

Models (all scored on the same 5 folds by spot, the folds supcon.py trains on):
  V1         the label-free encoder (cnn/processed/v_k7_con02): never saw a label, so one encoder serves every fold
  V2         batch-supervised encoder, retrained per fold (cnn/processed/supcon/<v2>/foldNN)
  V1+2 cat   V1 and V2 embeddings side by side, each block standardised and weighted equally
  V1+2 tune  the V1 encoder fine-tuned with batch supervision (supcon.py --init, spot-level), retrained per fold
Each: balanced accuracy of out-of-fold calls (same logistic regression for all), 90 % session-bootstrap interval,
per-class recall, paired difference vs V1.

Is it learning the material? Three checks per embedding, each against a control:
  1. Feature read-out: out-of-fold R2 of each of the 13 tile features from the tile embedding (ridge; tiles of a
     held-out spot never in the fit). Controls: the same encoder architecture with random weights (what the image
     statistics alone give), and a shuffled null (features of whole spots permuted).
  2. Batch direction in feature terms: the share of (Batch_1 mean - Batch_3 mean) and (Batch_2 - Batch_3) that lies
     in the span of the feature read-out directions. A random direction gives about 13 / dimension.
  3. Session leak: nearest neighbour in the same imaging session vs chance (cnn/predict.session_leak).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LOSSLARP_MASKS", "harmonise")
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402  (before evalkit)
from sklearn.linear_model import LogisticRegression, Ridge  # noqa: E402

from cnn import uncertainty as U  # noqa: E402
from cnn.common import RUNS_DIR  # noqa: E402
from cnn.data import make_folds, tile_index  # noqa: E402
from cnn.predict import session_leak  # noqa: E402
from cnn.tile_features import FEATURES  # noqa: E402

OUT = REPO / "cnn" / "results"
N_FOLDS = 5
BMAP = {"Batch_1": 1, "Batch_2": 2, "Batch_3": 3}


def load(path):
    z = np.load(path)
    order = np.argsort(z["sample_id"])
    tiles = pd.DataFrame({"sample_id": z["tile_sample_id"].astype(str), "row": z["tile_row"], "col": z["tile_col"]})
    return {"site": z["site_feat"][order].astype(float), "ids": z["sample_id"][order].astype(str),
            "batch": z["batch"][order].astype(str), "session": z["session"][order].astype(int),
            "tile": z["tile_feat"].astype(float), "tiles": tiles}


def std_block(Xtr, Xte):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd < 1e-8] = 1.0
    return (Xtr - mu) / sd / np.sqrt(Xtr.shape[1]), (Xte - mu) / sd / np.sqrt(Xtr.shape[1])


def lr_calls(blocks_tr, blocks_te, ytr):
    """Same classifier for every model: blocks standardised and weighted equally, L2 logistic regression."""
    parts = [std_block(a, b) for a, b in zip(blocks_tr, blocks_te)]
    Xtr, Xte = np.hstack([p[0] for p in parts]), np.hstack([p[1] for p in parts])
    clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000).fit(Xtr * 10, ytr)
    return clf.predict(Xte * 10)


def tile_features_aligned(tiles, tf):
    F = tiles.merge(tf, on=["sample_id", "row", "col"], how="left")[FEATURES].to_numpy(float)
    return F


def feature_r2(Xt, F, spot_of_tile, folds, shuffle_seed=None):
    """Out-of-fold R2 per feature, ridge from tile embedding to tile features; folds by spot."""
    F = F.copy()
    if shuffle_seed is not None:                       # null: give each spot the features of another spot
        spots = np.unique(spot_of_tile)
        perm = dict(zip(spots, np.random.default_rng(shuffle_seed).permutation(spots)))
        means = {s: np.nanmean(F[spot_of_tile == s], 0) for s in spots}
        F = np.stack([means[perm[s]] for s in spot_of_tile])
    pred = np.full_like(F, np.nan)
    for tr_ids, te_ids in folds:
        tr, te = np.isin(spot_of_tile, tr_ids), np.isin(spot_of_tile, te_ids)
        mu, sd = Xt[tr].mean(0), Xt[tr].std(0)
        sd[sd < 1e-8] = 1.0
        for j in range(F.shape[1]):
            ok = tr & np.isfinite(F[:, j])
            if ok.sum() < 20:
                continue
            m = Ridge(alpha=Xt.shape[1] * 1.0).fit((Xt[ok] - mu) / sd, F[ok, j])
            pred[te, j] = m.predict((Xt[te] - mu) / sd)
    out = {}
    for j, f in enumerate(FEATURES):
        ok = np.isfinite(F[:, j]) & np.isfinite(pred[:, j])
        y_ = F[ok, j]
        out[f] = float(1 - ((y_ - pred[ok, j]) ** 2).sum() / ((y_ - y_.mean()) ** 2).sum()) if ok.sum() > 20 else float("nan")
    return out


def named_share(site, batch, Xt, F):
    """Share of each batch-mean difference that lies in the span of the feature read-out directions."""
    mu, sd = Xt.mean(0), Xt.std(0)
    sd[sd < 1e-8] = 1.0
    ok = np.all(np.isfinite(F), 1)
    Fz = (F[ok] - F[ok].mean(0)) / (F[ok].std(0) + 1e-12)
    B = Ridge(alpha=Xt.shape[1] * 1.0).fit((Xt[ok] - mu) / sd, Fz).coef_.T       # D x 13
    Q, _ = np.linalg.qr(B)
    res = {}
    for b in ("Batch_1", "Batch_2"):
        d = (site[batch == b].mean(0) - site[batch == "Batch_3"].mean(0)) / sd
        inside = Q @ (Q.T @ d)
        res[f"{b} - Batch_3"] = float(inside @ inside / max(d @ d, 1e-12))
    res["random_direction"] = float(B.shape[1] / B.shape[0])
    return res


def untrained_tile_embedding(idx):
    """Random-weight FusionNet (seed 0) over every tile: the control for the feature read-out."""
    cache = RUNS_DIR / "untrained_fusion_tiles.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        return z["tile"], pd.DataFrame({"sample_id": z["sid"], "row": z["row"], "col": z["col"]})
    from cnn.common import pick_device
    from cnn.supcon import FusionNet, embed_all
    torch.manual_seed(0)
    device = pick_device()
    net = FusionNet("k7", with_decoder=False).to(device)
    feat, infos = embed_all(net, device, idx, batch=2)
    tiles = pd.DataFrame({"sample_id": [i["sample_id"] for i in infos], "row": [i["row"] for i in infos], "col": [i["col"] for i in infos]})
    np.savez(cache, tile=feat, sid=tiles.sample_id.to_numpy().astype(str), row=tiles.row.to_numpy(), col=tiles.col.to_numpy())
    return feat, tiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v1", default="v_k7_con02")
    ap.add_argument("--v2", default="v2")
    ap.add_argument("--v12", default="r2a")
    ap.add_argument("--n-null", type=int, default=10)
    ap.add_argument("--extra", default="", help="comma list of supcon runs to concatenate with V1 (each its own row), and 'all' = V1 + every one")
    ap.add_argument("--skip-material", action="store_true")
    ap.add_argument("--ensemble", default="", help="comma list of V2 seed runs: V1 + each, probabilities averaged (one row)")
    a = ap.parse_args()
    idx = tile_index()
    folds = make_folds(idx, by="sample_id", n_folds=N_FOLDS, seed=0)
    tf = pd.read_csv(RUNS_DIR / "tile_features.csv")
    v1 = load(RUNS_DIR / a.v1 / "embeddings.npz")
    ids, batch, sess = v1["ids"], v1["batch"], v1["session"]
    y = np.array([BMAP[b] for b in batch])
    mixed = np.array([len(set(y[sess == s])) > 1 for s in sess])

    def fold_runs(name):
        runs = [load(RUNS_DIR / "supcon" / name / f"fold{k:02d}" / "embeddings.npz") for k in range(N_FOLDS)]
        for r in runs:
            assert list(r["ids"]) == list(ids)
        return runs

    v2runs, v12runs = fold_runs(a.v2), fold_runs(a.v12)
    models = {
        "V1 (label-free)": lambda k: [v1["site"]],
        "V2 (batch-supervised)": lambda k: [v2runs[k]["site"]],
        "V1+2 concatenated": lambda k: [v1["site"], v2runs[k]["site"]],
        "V1+2 fine-tuned (V1 encoder + batch supervision)": lambda k: [v12runs[k]["site"]],
    }
    extras = [e for e in a.extra.split(",") if e]
    xruns = {e: fold_runs(e) for e in extras}
    for e in extras:
        models[f"V1 + {e} concatenated"] = (lambda e_: lambda k: [v1["site"], xruns[e_][k]["site"]])(e)
    if len(extras) > 1:
        models["V1 + " + " + ".join(extras) + " concatenated"] = lambda k: [v1["site"]] + [xruns[e][k]["site"] for e in extras]
    ens = [e for e in a.ensemble.split(",") if e]
    eruns = {e: fold_runs(e) for e in ens}
    res = {"folds": "5 by spot (cnn/data.make_folds seed 0)", "models": {}}
    calls_v1 = None
    if ens:
        models[f"V1 + V2 seed ensemble ({len(ens)} seeds, probabilities averaged)"] = "ensemble"
    for name, blocks in models.items():
        pred = np.zeros_like(y)
        for k, (tr_ids, te_ids) in enumerate(folds):
            tr, te = np.isin(ids, tr_ids), np.isin(ids, te_ids)
            if blocks == "ensemble":
                from cnn.classify import lr_proba
                P = np.mean([lr_proba([v1["site"][tr], eruns[e][k]["site"][tr]], [v1["site"][te], eruns[e][k]["site"][te]], y[tr]) for e in ens], 0)
                pred[te] = P.argmax(1) + 1
                continue
            bl = blocks(k)
            pred[te] = lr_calls([b[tr] for b in bl], [b[te] for b in bl], y[tr])
        r = {"bacc": U.bacc(y, pred), "ci90": U.session_bootstrap(y, pred, sess), "recall": U.recall_table(y, pred),
             "mixed_bacc": U.bacc(y[mixed], pred[mixed]), "calls": pred.tolist()}
        if calls_v1 is None:
            calls_v1 = pred
        else:
            r["delta_vs_v1"] = U.paired_delta(y, pred, calls_v1, sess)
            r["moved"] = U.gained_lost(y, pred, calls_v1, ids, sess, mixed)
        res["models"][name] = r
        d = r.get("delta_vs_v1")
        print(f"{name:50s} bacc {r['bacc']:.2f} [{r['ci90']['lo']:.2f}, {r['ci90']['hi']:.2f}]  recall "
              f"{[round(q['recall'], 2) for q in r['recall']]}  mixed {r['mixed_bacc']:.2f}" +
              (f"  delta {d['delta']:+.2f} [{d['lo']:+.2f}, {d['hi']:+.2f}] P(>0) {d['p_gt0']:.2f}" if d else ""), flush=True)

    if a.skip_material:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "compare_extra.json").write_text(json.dumps(res, indent=1, default=float))
        return
    # material checks: tile embeddings of the full models (V2 / V1+2: the encoder trained on all spots) + controls
    full = {"V1 (label-free)": v1, "V2 (batch-supervised)": load(RUNS_DIR / "supcon" / a.v2 / "full" / "embeddings.npz"),
            "V1+2 fine-tuned (V1 encoder + batch supervision)": load(RUNS_DIR / "supcon" / a.v12 / "full" / "embeddings.npz")}
    ut, ut_tiles = untrained_tile_embedding(idx)
    full["untrained encoder (control)"] = {"tile": ut, "tiles": ut_tiles, "site": None}
    res["material"] = {}
    for name, m in full.items():
        spot_of_tile = m["tiles"].sample_id.to_numpy()
        F = tile_features_aligned(m["tiles"], tf)
        r2 = feature_r2(m["tile"], F, spot_of_tile, folds)
        entry = {"feature_r2": r2, "mean_r2": float(np.nanmean(list(r2.values())))}
        if name.startswith("V1 (") or name.startswith("untrained"):
            nulls = [np.nanmean(list(feature_r2(m["tile"], F, spot_of_tile, folds, shuffle_seed=s).values())) for s in range(a.n_null)]
            entry["null_mean_r2"] = {"mean": float(np.mean(nulls)), "max": float(np.max(nulls)), "n": a.n_null}
        if m["site"] is not None:
            entry["batch_direction_named_share"] = named_share(m["site"], m["batch"], m["tile"], F)
            entry["session_leak"] = session_leak(m["site"], m["session"])
        res["material"][name] = entry
        ns = entry.get("batch_direction_named_share", {})
        print(f"{name:50s} mean feature R2 {entry['mean_r2']:.2f}" +
              (f" (shuffled null {entry['null_mean_r2']['mean']:.2f}, max {entry['null_mean_r2']['max']:.2f})" if "null_mean_r2" in entry else "") +
              (f"  named share B1-B3 {ns['Batch_1 - Batch_3']:.2f}, B2-B3 {ns['Batch_2 - Batch_3']:.2f} (random {ns['random_direction']:.3f})" if ns else "") +
              (f"  leak {entry['session_leak']['nn_same_session_rate']:.2f} vs {entry['session_leak']['nn_chance']:.2f} (p {entry['session_leak']['nn_perm_p']:.3f})" if "session_leak" in entry else ""),
              flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "compare.json").write_text(json.dumps(res, indent=1, default=float))
    md = ["# V1 vs V2 vs V1+2 (same 5 folds by spot; balanced accuracy, chance 0.33; 90 % session-bootstrap intervals)", "",
          "| model | balanced accuracy [90 %] | recall B1 / B2 / B3 | mixed sessions | delta vs V1 [90 %] |", "|---|---|---|---|---|"]
    for name, r in res["models"].items():
        d = r.get("delta_vs_v1")
        md.append(f"| {name} | {r['bacc']:.2f} [{r['ci90']['lo']:.2f}, {r['ci90']['hi']:.2f}] | " + " / ".join(f"{q['recall']:.2f}" for q in r["recall"]) +
                  f" | {r['mixed_bacc']:.2f} | " + (f"{d['delta']:+.2f} [{d['lo']:+.2f}, {d['hi']:+.2f}]" if d else "reference") + " |")
    md += ["", "## Does the embedding know the material?", "",
           "| embedding | mean out-of-fold feature R2 | " + " | ".join(FEATURES) + " |", "|---|---|" + "---|" * len(FEATURES)]
    for name, e in res["material"].items():
        md.append(f"| {name} | {e['mean_r2']:.2f} | " + " | ".join(f"{e['feature_r2'][f]:.2f}" for f in FEATURES) + " |")
    (OUT / "compare.md").write_text("\n".join(md) + "\n")
    print(f"wrote {OUT / 'compare.json'} and compare.md")


if __name__ == "__main__":
    main()
