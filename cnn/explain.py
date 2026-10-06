"""Why did the network call that batch? Interpretability of the embedding, in the material's own vocabulary.

    python cnn/explain.py --run supcon/v2/full --subset   # -> processed/supcon/v2/full/explain.json + explain_img/ (ablations on 9 spots)
    python cnn/explain.py --run supcon/v2/full --all      # ablations and perturbations on every spot (slow on a laptop)

For every spot (31 training + 3 test), with the batch direction of the logistic regression used by predict.py:
 1. Decomposition. The embedding splits into the part a linear map from the 13 tile features reproduces ("known")
    and the rest ("complement"). The spot's score along its called batch's direction is the sum of the two, so
    "share known" says how much of the call is named features; and because the known part is linear in the
    features, each feature gets a signed contribution ("Si d50 +1.3 SD pushed towards Batch_1 by 0.4").
 2. Where in the image: every tile's score along that direction (a rows x cols grid, 2 x 13 for the fixed tiles),
    the three strongest tiles as BSE thumbnails with their predicted material map (the preprocessing masks when the
    run had no decoder).
 3. Nearest neighbours: the five most similar training spots (cosine), overall and from other imaging sessions.
For the subset (test spots + 2 per batch) or all spots:
 4. Material ablations: blank the Si particles, blank the pores, or blank a random graphite region of the same
    shape (control), re-embed, and see how far the batch probabilities move.
 5. Imaging perturbations: BSE offset +-0.05 graphite units, gain x0.9 / x1.1, extra noise sigma 0.1 (all beyond the
    training augmentation), re-embed: does the call move when the microscope changes?
Writes explain.json incrementally (safe to interrupt and rerun).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi

os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
import torch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn import evalkit as ek  # noqa: E402
from cnn.common import DETECTORS, load_tile, pick_device, run_dir  # noqa: E402
from cnn.predict import embed_tiles, embed_x, load_net, tiles_to_x  # noqa: E402
from cnn.tile_features import FEATURES, OUT as TILE_FEATURES_CSV  # noqa: E402
from preprocessing.preprocess import load_tiles  # noqa: E402
from qc.features_table import OUT as TABLE, TEST_IDS, TEST_TILE_FEATURES_CSV, TEST_TILES_DIR  # noqa: E402
from qc.verdict import clean  # noqa: E402

ALPHAS = np.logspace(-2, 4, 13)
MAP_COLOURS = np.array([[40, 120, 255], [150, 150, 150], [224, 164, 0]], np.uint8)   # pore, graphite, Si
ABLATIONS = ("si_removed", "pores_removed", "control")
PERTURBATIONS = {"bse_offset_-0.05": ("offset", -0.05), "bse_offset_+0.05": ("offset", 0.05),
                 "gain_x0.9": ("gain", 0.9), "gain_x1.1": ("gain", 1.1), "noise_0.1": ("noise", 0.1)}


# ----------------------------------------------------------------------------------------------------
# the batch direction in embedding space
# ----------------------------------------------------------------------------------------------------
def lr_direction(X, y, C=0.1):
    """Logistic regression as evalkit fits it (PCA scores through the Gram matrix), mapped back to the
    standardised embedding space: scores = ((X - mu) / sd) @ W + b. Returns mu, sd, W (D x 3), b, classes."""
    from sklearn.linear_model import LogisticRegression
    mu, sd = X.mean(0), X.std(0)
    sd[sd < 1e-8] = 1.0
    A = (X - mu) / sd
    w, U = np.linalg.eigh(A @ A.T)
    order = np.argsort(w)[::-1]
    w, U = w[order], U[:, order]
    keep = w > w[0] * 1e-10
    U, s = U[:, keep], np.sqrt(w[keep])
    P = U * s
    clf = LogisticRegression(C=C, class_weight="balanced", max_iter=5000).fit(P, y)
    M = A.T @ U / s                                  # maps a standardised row to its PCA scores
    W, b = M @ clf.coef_.T, clf.intercept_
    assert np.allclose(A @ W + b, clf.decision_function(P), atol=1e-6), "direction does not reproduce the classifier"
    return mu, sd, W, b, [int(c) for c in clf.classes_]


def ridge_known(F, X):
    """Linear map tile features -> embedding, fitted on all training tiles (display, not a score).
    Returns (f_mu, f_sd, B, c): known = ((F - f_mu) / f_sd) @ B + c."""
    from sklearn.linear_model import RidgeCV
    f_mu, f_sd = F.mean(0), F.std(0)
    f_sd[f_sd < 1e-8] = 1.0
    Fs = (F - f_mu) / f_sd
    m = RidgeCV(alphas=ALPHAS).fit(Fs, X)
    return f_mu, f_sd, m.coef_.T, m.intercept_


def softmax_rows(S):
    e = np.exp(S - S.max(1, keepdims=True))
    return e / e.sum(1, keepdims=True)


# ----------------------------------------------------------------------------------------------------
# images
# ----------------------------------------------------------------------------------------------------
def bse_png(t, path):
    Image.fromarray((np.clip(t.bse / 2.6, 0, 1) * 255).astype(np.uint8)[::4, ::4]).save(path)


@torch.no_grad()
def map_png(net, device, t, path):
    o = net(tiles_to_x([t]).to(device))
    if "seg" in o:
        m = o["seg"].argmax(1)[0].cpu().numpy()
    else:                                   # contrastive-only run (no decoder): show the preprocessing masks instead
        from cnn.common import material_map
        m = material_map(t)
    Image.fromarray(MAP_COLOURS[m][::4, ::4]).save(path)
    return [float((m == k).mean()) for k in range(3)]


# ----------------------------------------------------------------------------------------------------
# ablations and perturbations
# ----------------------------------------------------------------------------------------------------
def fill(t, mask, rng):
    """Replace the masked pixels of every plane by graphite-like pixels: per-plane median + the graphite pixels'
    own noise. Graphite = not pore, not Si, eroded 3 px away from mask edges; the mask is dilated 2 px first."""
    void, bright = t.void.astype(bool), t.bright.astype(bool)
    graphite = ndi.binary_erosion(~void & ~bright, iterations=3)
    if graphite.sum() < 100:
        graphite = ~void & ~bright
    m = ndi.binary_dilation(mask, iterations=2)
    planes = {}
    for d in DETECTORS:
        a = getattr(t, d).copy()
        g = a[graphite]
        a[m] = np.median(g) + g.std() * rng.standard_normal(int(m.sum()))
        planes[d] = a
    return planes, m


def ablate(t, mode, rng):
    void, bright = t.void.astype(bool), t.bright.astype(bool) & ~t.void.astype(bool)
    if mode == "si_removed":
        planes, _ = fill(t, bright, rng)
        return dataclasses.replace(t, **planes, bright=np.zeros_like(bright))
    if mode == "pores_removed":
        planes, _ = fill(t, void, rng)
        return dataclasses.replace(t, **planes, void=np.zeros_like(void))
    # control: the Si mask moved to a random place inside the graphite, same shapes, same area
    graphite = ~void & ~bright
    dy, dx = rng.integers(64, 448, 2)
    moved = np.roll(np.roll(bright, int(dy), 0), int(dx), 1) & graphite
    planes, _ = fill(t, moved, rng)
    return dataclasses.replace(t, **planes)


def perturb(x, kind, v, rng):
    x = x.clone()
    if kind == "offset":
        x[:, 0] += v                                 # BSE only (graphite units)
    elif kind == "gain":
        x *= v
    else:
        x += v * torch.randn(x.shape, generator=rng)
    return x


# ----------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="supcon/v2/full", help="folder under processed/")
    ap.add_argument("--subset", action="store_true", help="ablations/perturbations on the test spots + 2 per batch")
    ap.add_argument("--all", action="store_true", help="ablations/perturbations on every spot")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()
    out = run_dir(a.run)
    img_dir = out / "explain_img"
    img_dir.mkdir(exist_ok=True)
    device = pick_device(a.device)
    net, _ = load_net(a.run, device)
    rng = np.random.default_rng(a.seed)
    trng = torch.Generator().manual_seed(a.seed)

    z = np.load(out / "embeddings.npz")
    zt = np.load(out / "test_embeddings.npz")
    pred = json.loads((out / "predictions.json").read_text())
    X = z["site_feat"].astype(float)
    meta = ek.meta_for(z["batch"], z["sample_id"], z["session"])
    y, sess = meta.y.to_numpy(), meta.session.to_numpy()
    keys = [f"{b}/{s}" for b, s in zip(meta.batch, meta.sample_id)]
    mu, sd, W, b, classes = lr_direction(X, y)
    S_all = ((X - mu) / sd) @ W + b

    # known / complement from the tile features (training tiles)
    tf = pd.read_csv(TILE_FEATURES_CSV)
    emb = pd.DataFrame({"batch": z["tile_batch"].astype(str), "sample_id": z["tile_sample_id"].astype(str),
                        "row": z["tile_row"].astype(int), "col": z["tile_col"].astype(int)})
    m = emb.merge(tf, on=["batch", "sample_id", "row", "col"], how="left", validate="one_to_one")
    F = m[FEATURES].to_numpy(float)
    F = np.where(np.isfinite(F), F, np.nanmean(F, 0))
    Xt = z["tile_feat"].astype(float)
    f_mu, f_sd, B, c = ridge_known(F, Xt)
    table = pd.read_csv(TABLE)
    base = table[table.batch == "Batch_3"]
    b3_mu, b3_sd = base[FEATURES].mean().to_numpy(), base[FEATURES].std(ddof=1).to_numpy()
    # per-feature weight along each class direction: contribution_j = Fs_j * ((B_j / sd) . w)
    G = (B / sd) @ W                                  # (13, 3)
    # complement centre over the training spots (so the "share" does not depend on the constant of the known part)
    spot_F =np.stack([F[(m.batch == bb) & (m.sample_id == ss)].mean(0) for bb, ss in zip(meta.batch, meta.sample_id)])
    known_site = ((spot_F - f_mu) / f_sd) @ B + c
    comp_site = X - known_site
    comp_centre = (comp_site / sd) @ W
    comp_mean = comp_centre.mean(0)

    # test spots
    tft = pd.read_csv(TEST_TILE_FEATURES_CSV)
    Xte = zt["site_feat"].astype(float)
    S_te = ((Xte - mu) / sd) @ W + b
    te_rows = {r["sample_id"]: r for r in pred["test"]}

    # standardised cosine for neighbours
    Z = (X - mu) / sd
    Zu = Z / np.linalg.norm(Z, axis=1, keepdims=True)

    def neighbours(zrow, own_key, own_sess, k=5):
        u = zrow / np.linalg.norm(zrow)
        sim = Zu @ u
        order = [i for i in np.argsort(-sim) if keys[i] != own_key]
        mk = lambda i: {"key": keys[i], "batch": int(y[i]), "session": int(sess[i]), "cos": float(sim[i])}  # noqa: E731
        return {"all": [mk(i) for i in order[:k]], "other_sessions": [mk(i) for i in order if sess[i] != own_sess][:k]}

    def tile_rows(spot_key, batch, sid):
        if batch == "Test":
            sel = zt["tile_sample_id"].astype(str) == sid
            feats, rows, cols = zt["tile_feat"][sel].astype(float), zt["tile_row"][sel], zt["tile_col"][sel]
            ft = tft[tft.sample_id == sid]
        else:
            sel = (emb.batch == batch) & (emb.sample_id == sid)
            feats, rows, cols = Xt[sel.to_numpy()], emb.row[sel].to_numpy(), emb.col[sel].to_numpy()
            ft = m[sel]
        return feats, rows.astype(int), cols.astype(int), ft

    def load(batch, sid, r, cc):
        if batch != "Test":
            return load_tile(batch, sid, r, cc)
        return next(t for t in load_tiles("Test", sid, out_dir=TEST_TILES_DIR) if t.row == r and t.col == cc)

    def all_tiles(batch, sid):
        if batch == "Test":
            return load_tiles("Test", sid, out_dir=TEST_TILES_DIR)
        rows = emb[(emb.batch == batch) & (emb.sample_id == sid)]
        return [load_tile(batch, sid, int(r), int(cc)) for r, cc in zip(rows.row, rows.col)]

    results = json.loads((out / "explain.json").read_text()) if (out / "explain.json").exists() else {}
    results.setdefault("spots", {})
    results.update({"run": a.run, "classes": classes, "features": FEATURES,
                    "feature_direction_weight": {f: [float(v) for v in G[j]] for j, f in enumerate(FEATURES)}})

    spots = [(str(bb), str(ss), int(hh), int(yy), int(pred_row["call_losess"]), S_all[i], X[i], spot_F[i], comp_centre[i])
             for i, (bb, ss, hh, yy, pred_row) in enumerate(zip(meta.batch, meta.sample_id, sess, y, pred["spots"]))]
    for j, sid in enumerate(TEST_IDS):
        fsp = tft[tft.sample_id == sid][FEATURES].to_numpy(float)
        fsp = np.where(np.isfinite(fsp), fsp, np.nanmean(F, 0)).mean(0)
        ks = ((fsp - f_mu) / f_sd) @ B + c
        spots.append(("Test", sid, int(te_rows[sid]["session"]), 0, int(te_rows[sid]["call"]), S_te[j], Xte[j], fsp,
                      ((Xte[j] - ks) / sd) @ W))
    if a.all:
        subset = {f"{bb}/{ss}" for bb, ss, *_ in spots}
    else:
        subset = {f"Test/{s}" for s in TEST_IDS}
        if a.subset:
            for bb in ("Batch_1", "Batch_2", "Batch_3"):
                subset |= {f"{bb}/{ss}" for _, ss, *_ in [s for s in spots if s[0] == bb][:2]}

    for bb, sid, hh, yy, call, S, x, fsp, cc in spots:
        key = f"{bb}/{sid}"
        print(f"\n{key}: call Batch_{call}" + (f" (true {yy})" if yy else ""), flush=True)
        ci = classes.index(call)
        wdir = W[:, ci]
        # 1. decomposition along the called class direction
        fs = (fsp - f_mu) / f_sd
        contrib = fs * G[:, ci]
        s_known = float(contrib.sum())                      # centred known score (constant k0 left out)
        s_comp = float(cc[ci] - comp_mean[ci])
        share = abs(s_known) / max(abs(s_known) + abs(s_comp), 1e-12)
        feats_out = sorted([{"feature": f, "contribution": float(contrib[j]), "value": float(fsp[j]),
                             "delta_b3_sd": float((fsp[j] - b3_mu[j]) / b3_sd[j]), "z_all": float(fs[j])}
                            for j, f in enumerate(FEATURES)], key=lambda d: -abs(d["contribution"]))
        xs = (x - mu) / sd
        assert abs(float(xs @ wdir + b[ci]) - float(S[ci])) < 1e-6
        # 2. tile heat grid
        feats, rows, cols, _ = tile_rows(key, bb, sid)
        tscore = ((feats - mu) / sd) @ wdir + b[ci]
        assert abs(tscore.mean() - float(S[ci])) < 1e-3 * max(1, abs(float(S[ci]))), "tile scores do not average to the spot score"
        grid = np.full((rows.max() + 1, cols.max() + 1), np.nan)
        grid[rows, cols] = tscore
        top = []
        for i in np.argsort(-tscore)[:3]:
            t = load(bb, sid, int(rows[i]), int(cols[i]))
            stem = f"{sid}_r{rows[i]}c{cols[i]:02d}"
            bse_png(t, img_dir / f"{stem}_bse.png")
            fr = map_png(net, device, t, img_dir / f"{stem}_map.png")
            top.append({"row": int(rows[i]), "col": int(cols[i]), "score": float(tscore[i]), "bse": f"{stem}_bse.png",
                        "map": f"{stem}_map.png", "map_fractions": fr})
        rec = {"batch": bb, "sample_id": sid, "session": hh, "y": yy, "call": call, "scores": [float(v) for v in S],
               "p_insample": [float(v) for v in softmax_rows(S[None])[0]],
               "decomposition": {"share_known": share, "s_known": s_known, "s_complement": s_comp, "features": feats_out},
               "heat": {"grid": grid.tolist(), "top": top, "min": float(np.nanmin(grid)), "max": float(np.nanmax(grid))},
               "neighbours": neighbours(xs, key, hh)}
        print(f"  share of the call explained by named features {share:.0%}; top: "
              + ", ".join(f"{d['feature']} {d['contribution']:+.2f} ({d['delta_b3_sd']:+.1f} SD vs B3)" for d in feats_out[:3]), flush=True)
        # 4-5. ablations and perturbations on the subset
        if key in subset:
            tiles = all_tiles(bb, sid)
            x0 = tiles_to_x(tiles)
            base_feat = embed_tiles(net, device, tiles, a.batch).mean(0)
            p0 = ek.fit_predict("lr", X, y, base_feat[None])[0]
            s0 = float(((base_feat - mu) / sd) @ wdir + b[ci])
            rec["ablation"], rec["perturbation"] = {"base_p": [float(v) for v in p0], "base_score": s0}, {"base_p": [float(v) for v in p0]}
            for mode in ABLATIONS:
                at = [ablate(t, mode, rng) for t in tiles]
                f1 = embed_tiles(net, device, at, a.batch).mean(0)
                p1 = ek.fit_predict("lr", X, y, f1[None])[0]
                s1 = float(((f1 - mu) / sd) @ wdir + b[ci])
                rec["ablation"][mode] = {"p": [float(v) for v in p1], "dp": [float(v) for v in p1 - p0], "dscore": s1 - s0,
                                         "call": int(p1.argmax() + 1)}
                print(f"  ablation {mode:14s} P -> {np.round(p1, 2).tolist()}  score {s1 - s0:+.2f}", flush=True)
            for name, (kind, v) in PERTURBATIONS.items():
                f1 =embed_x(net, device, perturb(x0, kind, v, trng), a.batch).mean(0)
                p1 = ek.fit_predict("lr", X, y, f1[None])[0]
                rec["perturbation"][name] = {"p": [float(v) for v in p1], "dp": [float(v) for v in p1 - p0], "call": int(p1.argmax() + 1)}
                print(f"  perturb  {name:16s} P -> {np.round(p1, 2).tolist()}", flush=True)
        elif key in results["spots"] and "ablation" in results["spots"][key]:
            rec["ablation"], rec["perturbation"] = results["spots"][key]["ablation"], results["spots"][key]["perturbation"]
        results["spots"][key] = rec
        (out / "explain.json").write_text(json.dumps(clean(results), indent=1))
    print(f"\nwrote {out / 'explain.json'} ({len(results['spots'])} spots; ablations on {len(subset)})")


if __name__ == "__main__":
    main()
