"""Baselines for the batch test, scored exactly like the CNN versions (evalkit, leave one session out, logistic
regression), each with its uncertainty.

    LOSSLARP_MASKS=harmonise python cnn/baselines.py [--n-perm 200]   # -> dashboard/data/baselines.json

Rows: the permutation null (what shuffled labels score), imaging cues only (the session fingerprints the
preprocessing is meant to remove: the bar any material model must clear), the 13 hand-crafted tile features averaged
per spot (BSE-threshold masks, and seg3 masks when that table exists), plain pixel statistics of the fair tiles, an
untrained k7 encoder (what training adds), and the V1 embedding for reference. Every row: balanced accuracy
(losess, loso, mixed, joins), permutation p, 90 % session-bootstrap interval, per-class recall with Wilson
intervals, and the three test-spot calls where the representation exists for them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("LOSSLARP_MASKS", "harmonise")
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402  (before evalkit, which caps BLAS threads)
from scipy import ndimage as ndi  # noqa: E402
from scipy.stats import kurtosis, skew  # noqa: E402

from cnn import evalkit as ek  # noqa: E402
from cnn import uncertainty as U  # noqa: E402
from cnn.common import DETECTORS, RUNS_DIR, TILES_CSV, load_tile, pick_device  # noqa: E402
from cnn.tile_features import FEATURES  # noqa: E402
from qc.features_table import TEST_IDS  # noqa: E402

OUT = REPO / "dashboard" / "data" / "baselines.json"
ACQ_COLS = ["bse_black_level", "bse_contrast", "bse_noise_sigma", "inlens_noise_sigma"]   # raw-image session cues (never model inputs)


def spot_meta():
    t = pd.read_csv(TILES_CSV).drop_duplicates(["batch", "sample_id"]).sort_values(["batch", "sample_id"]).reset_index(drop=True)
    return t, ek.meta_for(t.batch, t.sample_id, t.session)


def score_row(name, uses, X, meta, n_perm, Xte=None, null=False, seed=0):
    X = np.asarray(X, float)
    y, sess = meta.y.to_numpy(), meta.session.to_numpy()
    r = ek.score(X, meta, clfs=("lr",), n_perm=n_perm)
    P = ek.oof(X, y, sess, "lr", sess)
    call = P.argmax(1) + 1
    row = {"name": name, "uses": uses, "n_dims": int(X.shape[1]), "lr_losess": r["lr_losess"], "lr_loso": r["lr_loso"],
           "lr_mixed": r["lr_mixed"], "lr_joins": r["lr_joins"], "perm_p": r["lr_losess_perm_p"],
           "ci90": U.session_bootstrap(y, call, sess), "recall": U.recall_table(y, call), "calls": [int(c) for c in call]}
    if Xte is not None:
        Pt = ek.fit_predict("lr", X, y, np.asarray(Xte, float))
        row["test"] = [{"sample_id": s, "call": int(p.argmax() + 1), "p": [float(v) for v in p]} for s, p in zip(TEST_IDS, Pt)]
    if null:
        rng = np.random.default_rng(seed)
        vals = []
        for _ in range(n_perm):
            yp = rng.permutation(y)
            vals.append(U.bacc(yp, ek.oof(X, yp, sess, "lr", sess).argmax(1) + 1))
        row["null"] = {"mean": float(np.mean(vals)), "q95": float(np.quantile(vals, 0.95)), "max": float(np.max(vals)), "n": n_perm}
    print(f"{name:45s} losess {row['lr_losess']:.2f} [{row['ci90']['lo']:.2f}, {row['ci90']['hi']:.2f}] p {row['perm_p']:.3f} "
          f"mixed {row['lr_mixed']:.2f} joins {row['lr_joins']:.2f}" + (f"  null mean {row['null']['mean']:.2f} q95 {row['null']['q95']:.2f}" if null else ""),
          flush=True)
    return row


def features_rows(spots, n_perm):
    """The 13 tile features averaged per spot, from qc/<processed>/features_table.csv (train + test rows)."""
    rows = []
    for label, folder in (("BSE-threshold masks", "processed"), ("seg3 masks", "processed_seg3")):
        f = REPO / "qc" / folder / "features_table.csv"
        if not f.exists():
            print(f"no {f}: skipping the {label} feature row")
            continue
        t = pd.read_csv(f)
        tr = t[t.batch != "Test"].set_index("sample_id").loc[spots.sample_id]
        te = t[t.batch == "Test"].set_index("sample_id").loc[list(TEST_IDS)]
        _, meta = spot_meta()
        rows.append(score_row(f"hand-crafted features ({len(FEATURES)}, {label})",
                              f"the {len(FEATURES)} material features per tile (porosity, Si share and size, interfaces, chords, heterogeneity), mean per spot",
                              tr[FEATURES].to_numpy(), meta, n_perm, te[FEATURES].to_numpy(), null=(folder == "processed")))
    return rows


def pixel_stats(spots):
    """Per spot: mean over its tiles of 7 plain numbers per detector plane (mean, SD, skew, kurtosis, p1, p99, gradient energy)."""
    t = pd.read_csv(TILES_CSV)
    out = []
    for r in spots.itertuples():
        g = t[(t.batch == r.batch) & (t.sample_id == r.sample_id)]
        vals = []
        for tr in g.itertuples():
            tile = load_tile(r.batch, r.sample_id, int(tr.row), int(tr.col))
            v = []
            for d in DETECTORS:
                a = getattr(tile, d).astype(np.float32)
                gy, gx = np.gradient(a[::2, ::2])
                v += [a.mean(), a.std(), skew(a.ravel()[::7]), kurtosis(a.ravel()[::7]), np.percentile(a, 1), np.percentile(a, 99),
                      float(np.sqrt(gx ** 2 + gy ** 2).mean())]
            vals.append(v)
        out.append(np.mean(vals, 0))
    return np.array(out)


def untrained_embedding(spots, batch=2):
    """An untrained k7 encoder (seed 0) run over every tile; mean per spot. What the training adds."""
    from torch.utils.data import DataLoader
    from cnn.data import TileDataset, collate, tile_index
    from cnn.supcon import FusionNet
    torch.manual_seed(0)
    device = pick_device()
    net = FusionNet("k7", with_decoder=False).to(device).eval()
    dl = DataLoader(TileDataset(tile_index(), augment=False), batch, shuffle=False, collate_fn=collate)
    feats, ids = [], []
    with torch.no_grad():
        for x, _, info in dl:
            o = net(x.to(device), seg=False)
            feats.append(o["feat"].float().cpu().numpy())
            ids += [(i["batch"], i["sample_id"]) for i in info]
    F = np.concatenate(feats)
    ids = np.array(ids)
    return np.stack([F[(ids[:, 0] == r.batch) & (ids[:, 1] == r.sample_id)].mean(0) for r in spots.itertuples()])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-perm", type=int, default=200)
    ap.add_argument("--skip", default="", help="comma list of rows to skip: untrained,pixels,features,imaging,v1")
    a = ap.parse_args()
    skip = set(a.skip.split(",")) - {""}
    spots, meta = spot_meta()
    rows = []
    if "features" not in skip:
        rows += features_rows(spots, a.n_perm)
    if "imaging" not in skip:
        rows.append(score_row("imaging cues only", "black level, contrast, BSE noise, Inlens noise of the raw image (never model inputs; the bar)",
                              spots[ACQ_COLS].to_numpy(float), meta, a.n_perm))
    if "pixels" not in skip:
        rows.append(score_row("pixel statistics", "7 plain numbers per detector plane of the fair tiles (mean, SD, skew, kurtosis, p1, p99, gradient energy), mean per spot",
                              pixel_stats(spots), meta, a.n_perm))
    if "untrained" not in skip:
        rows.append(score_row("untrained k7 encoder", "the same encoder architecture with random weights, mean+SD pooled, mean per spot",
                              untrained_embedding(spots), meta, a.n_perm))
    if "v1" not in skip:
        z = RUNS_DIR / "versions" / "V1" / "embeddings.npz"
        if z.exists():
            e = np.load(z)
            assert list(e["sample_id"]) == list(spots.sample_id), "embedding order differs from tiles.csv"
            rows.append(score_row("V1 CNN embedding", "the trained k7 encoder (fixed tiles, material map + light contrastive), last.pt", e["site_feat"], meta, a.n_perm))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists() and skip:                          # partial run: keep the rows that were not recomputed, in the standard order
        old = {r["name"]: r for r in json.loads(OUT.read_text())["rows"]}
        new = {r["name"]: r for r in rows}
        order = [n for n in old if n not in new] + list(new)
        rows = [new.get(n, old.get(n)) for n in order]
        rows.sort(key=lambda r: (r["name"].startswith("V1"), r["name"] in ("imaging cues only", "pixel statistics", "untrained k7 encoder"), r["name"]))
    OUT.write_text(json.dumps({"built": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "chance": 1 / 3, "n_perm": a.n_perm,
                               "n_spots": int(len(spots)), "n_sessions": int(meta.session.nunique()), "rows": rows}, indent=1, default=float))
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
