"""Does the CNN embedding carry the known material features, and is there anything left once they are taken out?

    python cnn/probe_features.py --name supcon/v2/full        # one run (a folder under processed/)
    python cnn/probe_features.py --all                        # every processed/supcon/*/full/embeddings.npz, plus a summary table

Needs cnn/processed/tile_features.csv (cnn/tile_features.py) and processed/<name>/embeddings.npz (cnn/supcon.py).
The FusionNet encoder saw the batch labels, so the "embedding" and "complement" rows here are in-sample for the
encoder; read them as a description of what the embedding holds, and take the honest number from score.json.

Three questions, all at TILE level (806 tiles) with folds by spot or by session, never by tile:
 (1) embedding -> features: out-of-fold ridge from the tile embedding to each tile feature; R2 per feature.
     High R2 = the embedding already encodes that feature. The reverse of what the spot-level residual test tried
     with 31 rows.
 (2) split: features -> embedding, out of fold. KNOWN = the fitted part (the embedding directions the features
     explain); COMPLEMENT = embedding - KNOWN. Both are pooled per spot and scored with evalkit against the batches.
     If COMPLEMENT scores above its permutation null, the embedding sees something the features don't.
 (3) sanity: the same split on a synthetic embedding = features x random map + noise. Its complement must be at
     chance (~0.33); if not, the method itself is making signal.
Galleries: tiles at the two ends of the complement's batch direction, for a materials expert to name.
No batch label is used anywhere except in the final evalkit scoring.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn import evalkit as ek  # noqa: E402
from cnn.common import RUNS_DIR, load_tile, run_dir  # noqa: E402
from cnn.tile_features import FEATURES, OUT as TILE_FEATURES_CSV  # noqa: E402

ALPHAS = np.logspace(-2, 4, 13)
KEYS = ["lr_loso", "lr_losess", "lr_mixed", "lr_joins", "ari_kmeans", "lr_losess_perm_p"]


def ridge_oof(X, Y, groups):
    """Out-of-fold ridge prediction of Y from X, one fold per group, alpha chosen per target inside the fold."""
    from sklearn.linear_model import RidgeCV
    P = np.zeros_like(Y, dtype=float)
    for g in np.unique(groups):
        te = groups == g
        a, b = ek._std(X[~te], X[te])
        mu = Y[~te].mean(0)
        P[te] = RidgeCV(alphas=ALPHAS, alpha_per_target=True).fit(a, Y[~te] - mu).predict(b) + mu
    return P


def r2(Y, P):
    ss = ((Y - Y.mean(0)) ** 2).sum(0)
    return 1 - ((Y - P) ** 2).sum(0) / np.maximum(ss, 1e-12)


def pool(X, spot_key, spots):
    return np.stack([X[spot_key == s].mean(0) for s in spots])


def load_aligned(name):
    z = np.load(run_dir(name) / "embeddings.npz")
    emb = pd.DataFrame({"batch": z["tile_batch"].astype(str), "sample_id": z["tile_sample_id"].astype(str),
                        "row": z["tile_row"].astype(int), "col": z["tile_col"].astype(int)})
    tf = pd.read_csv(TILE_FEATURES_CSV)
    m = emb.merge(tf, on=["batch", "sample_id", "row", "col"], how="left", validate="one_to_one")
    if m[FEATURES].isna().all(1).any():
        raise SystemExit("tile_features.csv does not cover every embedded tile; rerun cnn/tile_features.py")
    F = m[FEATURES].to_numpy(float)
    F = np.where(np.isfinite(F), F, np.nanmean(F, 0))       # tiles with no Si particle: fill size with the mean
    return z["tile_feat"].astype(float), F, m, int(z["epoch"]) if "epoch" in z else -1


def split_known(X, F, groups):
    """Out-of-fold linear map features -> embedding. Returns (KNOWN, COMPLEMENT), both (n_tiles, D)."""
    known = ridge_oof(F, X, groups)
    return known, X - known


def gallery(out, name, scores, ids, n=12):
    """Two rows of BSE thumbnails: the n tiles lowest and the n highest on `scores`."""
    from PIL import Image
    order = np.argsort(scores)
    rows = []
    for sel in (order[:n], order[-n:][::-1]):
        ims = []
        for i in sel:
            t = load_tile(*ids[i])
            ims.append((np.clip(t.bse / 2.6, 0, 1) * 255).astype(np.uint8)[::4, ::4])
        rows.append(np.concatenate(ims, 1))
    Image.fromarray(np.concatenate(rows, 0)).save(out / f"probe_gallery_{name}.png")


def probe(name, n_perm, seed=0):
    out = run_dir(name)
    X, F, m, epoch = load_aligned(name)
    spot_key = (m.batch + "/" + m.sample_id).to_numpy()
    sess = m.session.to_numpy()
    spots = list(dict.fromkeys(spot_key))
    sp = m.drop_duplicates(["batch", "sample_id"]).copy()
    sp = sp.set_index(sp.batch + "/" + sp.sample_id).loc[spots]
    meta = ek.meta_for(sp.batch.to_numpy(), sp.sample_id.to_numpy(), sp.session.to_numpy())
    res = {"name": name, "epoch": epoch, "dim": X.shape[1], "n_tiles": len(X), "n_features": F.shape[1]}

    # (1) embedding -> features, by spot and by session
    for tag, g in (("spot", spot_key), ("session", sess)):
        P = ridge_oof(X, F, g)
        res[f"r2_by_{tag}"] = {f: float(v) for f, v in zip(FEATURES, r2(F, P))}
    print("R2 embedding -> features (leave-one-session-out):",
          {k: round(v, 2) for k, v in sorted(res["r2_by_session"].items(), key=lambda kv: -kv[1])})

    # (2) known / complement split (folds by session: the headline is losess), pooled per spot, scored
    known, comp = split_known(X, F, sess)
    reps = {"embedding": pool(X, spot_key, spots), "tile_features": pool(F, spot_key, spots),
            "known": pool(known, spot_key, spots), "complement": pool(comp, spot_key, spots)}
    res["scores"] = {k: ek.score(v, meta, n_perm=n_perm) for k, v in reps.items()}
    res["complement_share_of_variance"] = float(comp.var(0).sum() / X.var(0).sum())
    for k, r in res["scores"].items():
        print(f"{k:14s}", {kk: round(r.get(kk, float('nan')), 3) for kk in KEYS})

    # (3) sanity on a synthetic embedding that is features + noise
    rng = np.random.default_rng(seed)
    Fs = (F - F.mean(0)) / np.maximum(F.std(0), 1e-8)
    Xsyn = Fs @ rng.normal(size=(F.shape[1], 64)) + rng.normal(size=(len(F), 64))
    _, comp_syn = split_known(Xsyn, F, sess)
    res["synthetic"] = {"embedding": ek.score(pool(Xsyn, spot_key, spots), meta, n_perm=n_perm),
                        "complement": ek.score(pool(comp_syn, spot_key, spots), meta, n_perm=n_perm)}
    print("synthetic complement losess", round(res["synthetic"]["complement"]["lr_losess"], 3),
          "p", res["synthetic"]["complement"].get("lr_losess_perm_p"))

    # galleries along the complement's batch direction (fit on all spots: display only, not a score)
    from sklearn.linear_model import LogisticRegression
    C = reps["complement"]
    mu, sd = C.mean(0), np.maximum(C.std(0), 1e-8)
    clf = LogisticRegression(C=0.1, class_weight="balanced", max_iter=5000).fit((C - mu) / sd, meta.y)
    ids = list(zip(m.batch, m.sample_id, m.row, m.col))
    tile_scores = ((comp - mu) / sd) @ clf.coef_.T
    for k, cls in enumerate(clf.classes_):
        gallery(out, f"B{cls}", tile_scores[:, k], ids)

    (out / "probe.json").write_text(json.dumps(res, indent=1, default=float))
    md = [f"# Feature probe: {name} (epoch {epoch}, {X.shape[1]}-d embedding, {len(X)} tiles, {F.shape[1]} tile features)", "",
          "## (1) Does the embedding carry the known features? Out-of-fold R2, embedding -> feature", "",
          "| feature | R2 by spot | R2 by session |", "|---|---|---|"]
    md += [f"| {f} | {res['r2_by_spot'][f]:.2f} | {res['r2_by_session'][f]:.2f} |" for f in FEATURES]
    md += ["", "## (2) Known part vs complement, pooled per spot. Balanced accuracy, chance 0.33", "",
           f"The complement holds {res['complement_share_of_variance']:.0%} of the embedding's variance.", "",
           "| representation | loso | losess | mixed | joins | ARI | perm p (losess) |", "|---|---|---|---|---|---|---|"]
    for k, r in res["scores"].items():
        md.append(f"| {k} | " + " | ".join(f"{r.get(kk, float('nan')):.2f}" for kk in KEYS[:-1]) + f" | {r.get('lr_losess_perm_p', float('nan')):.3f} |")
    s = res["synthetic"]
    md += ["", "## (3) Sanity: synthetic embedding = features + noise",
           f"embedding losess {s['embedding']['lr_losess']:.2f}, complement losess {s['complement']['lr_losess']:.2f} "
           f"(p {s['complement'].get('lr_losess_perm_p', float('nan')):.3f}). The complement should be near chance.",
           "", "Galleries `probe_gallery_B<k>.png`: top row = tiles least like batch k along the complement direction, bottom row = most like."]
    (out / "probe.md").write_text("\n".join(md) + "\n")
    return res


def summarise(results):
    rows = []
    for r in results:
        row = {"name": r["name"], "epoch": r["epoch"],
               "r2_si_d50": r["r2_by_session"]["si_d50_um"], "r2_si_aspect": r["r2_by_session"]["si_aspect_aw"],
               "r2_chord_x": r["r2_by_session"]["solid_chord_x_um"], "r2_porosity": r["r2_by_session"]["porosity_frac"],
               "r2_mean": float(np.mean(list(r["r2_by_session"].values())))}
        for k in ("embedding", "tile_features", "known", "complement"):
            row[f"{k}_losess"] = r["scores"][k]["lr_losess"]
            row[f"{k}_mixed"] = r["scores"][k]["lr_mixed"]
        row["complement_p"] = r["scores"]["complement"].get("lr_losess_perm_p")
        row["synthetic_complement_losess"] = r["synthetic"]["complement"]["lr_losess"]
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("complement_losess", ascending=False)
    df.to_csv(RUNS_DIR / "probe_summary.csv", index=False)
    md = ["# Feature probe across runs (losess = leave one session out, chance 0.33)", "",
          "| run | mean R2 emb->feat | R2 Si d50 | R2 Si aspect | R2 chord x | emb losess | tile feats losess | known losess | "
          "complement losess | complement p | complement mixed | synthetic complement |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in df.itertuples():
        md.append(f"| {r.name} | {r.r2_mean:.2f} | {r.r2_si_d50:.2f} | {r.r2_si_aspect:.2f} | {r.r2_chord_x:.2f} | {r.embedding_losess:.2f} | "
                  f"{r.tile_features_losess:.2f} | {r.known_losess:.2f} | **{r.complement_losess:.2f}** | {r.complement_p:.3f} | "
                  f"{r.complement_mixed:.2f} | {r.synthetic_complement_losess:.2f} |")
    md += ["", f"K = {len(df)} runs: the best complement in the table is a best-of-{len(df)}. A complement only counts if its "
           "p is small AND the synthetic complement sits near 0.33."]
    (RUNS_DIR / "probe_summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name")
    ap.add_argument("--all", action="store_true", help="every processed/supcon/*/full/ with embeddings.npz")
    ap.add_argument("--n-perm", type=int, default=200)
    ap.add_argument("--summary-only", action="store_true", help="rebuild the summary from existing probe.json files")
    a = ap.parse_args()
    if a.summary_only:
        summarise([json.loads(p.read_text()) for p in sorted(RUNS_DIR.glob("supcon/*/full/probe.json"))])
        return
    if a.all:
        names = sorted(str(p.parent.relative_to(RUNS_DIR)) for p in RUNS_DIR.glob("supcon/*/full/embeddings.npz"))
    elif a.name:
        names = [a.name]
    else:
        raise SystemExit("give --name or --all")
    results = []
    for n in names:
        print(f"\n=== {n}")
        results.append(probe(n, a.n_perm))
    if len(results) > 1:
        summarise(results)


if __name__ == "__main__":
    main()
