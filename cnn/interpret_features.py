"""What is an embedding's batch signal made of? Correlate every literature feature with the embedding's own axes.

    python cnn/interpret_features.py --run k7_local                      # a label-free run: cnn/<processed>/<run>/embeddings.npz
    python cnn/interpret_features.py --run supcon/r3a                    # a supervised run: per-fold encoders, out of fold
    python cnn/interpret_features.py --run v_k7_con02 --run supcon/v2    # V1 + V2 side by side (each block standardised)
    python cnn/interpret_features.py --npz ../losslarp/processed/emb/dv2l_s2_full_BSE.npz --tag dinov2l_full
-> cnn/results/interpret_<tag>.json and .md (small, committed), every number written by this file.

The embedding is reduced to a few per-spot axes, each scored out of fold so labels never leak into the axis:
    B3_score     logit P(Batch_3) of a logistic regression on the spot embedding, every spot scored by a model that
                 never saw its imaging session (label-free runs) or by the fold encoder that never saw it (supcon runs)
    B2_vs_B1     the same for Batch_2 against Batch_1, fitted on those 14 spots only
    PC1..PC3     principal axes of the standardised spot embeddings (label-free; for supcon runs the full model)
Every literature column of qc/<processed>/features_table.csv (the ledger's built features: tile features, depth
profile, plug-ins) is then compared with every axis, spot = unit (31 spots):
    rho          Spearman across spots; p from 2,000 permutations; q = Benjamini-Hochberg over the columns of one axis
    rho_session  the same after removing each imaging session's mean from both (sessions with >= 2 spots): does the
                 link hold where the microscope cannot be the cue?
    rho_batch    after removing each batch's mean from both: does the feature track the axis beyond the label itself?
    r2_embed     out-of-fold R2 of the feature from the embedding (ridge, leave one session out) and its permutation p:
                 does the embedding encode this feature at all?
and per axis, how much of it the named features explain together: out-of-fold ridge R2 of the axis from all
columns (leave one session out) against 200 shuffles, and per feature family. What is left over is what the
embedding knows that the literature features do not name.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("LOSSLARP_MASKS", "harmonise")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "ledger"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import rankdata  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.linear_model import LogisticRegression, RidgeCV  # noqa: E402

from cnn.common import RUNS_DIR  # noqa: E402
from qc.features_table import COLUMNS, OUT as TABLE  # noqa: E402

warnings.filterwarnings("ignore")
RESULTS = REPO / "cnn" / "results"
ALPHAS = np.logspace(-1, 5, 13)
C_LR = 0.1                                                    # evalkit's fast-mode logistic regression


# ---- embeddings --------------------------------------------------------------------------------------------
def _site(z):
    return z["site_feat"] if "site_feat" in z.files else z["emb"]


def load_run(spec):
    """-> {"X": {sid: vec} (label-free / full model), "folds": [({sid: vec}, heldout ids)] or None}."""
    root = RUNS_DIR / spec
    if (root / "embeddings.npz").exists():
        z = np.load(root / "embeddings.npz")
        return {"X": dict(zip(map(str, z["sample_id"]), _site(z).astype(float))), "folds": None}
    folds = sorted(root.glob("fold*/embeddings.npz"))
    if folds:
        fs = []
        for p in folds:
            z = np.load(p)
            fs.append((dict(zip(map(str, z["sample_id"]), _site(z).astype(float))), set(map(str, z["heldout"]))))
        full = root / "full" / "embeddings.npz"
        X = dict(zip(map(str, np.load(full)["sample_id"]), _site(np.load(full)).astype(float))) if full.exists() else fs[0][0]
        return {"X": X, "folds": fs}
    raise FileNotFoundError(f"no embeddings.npz under {root} (nor fold*/)")


def load_npz(path):
    z = np.load(path, allow_pickle=True)
    return {"X": dict(zip(map(str, z["sample_id"]), _site(z).astype(float))), "folds": None}


def stack(blocks, ids):
    """Standardise each block over the training spots and put them side by side (equal weight per block)."""
    out = []
    for X in blocks:
        A = np.stack([X[s] for s in ids])
        sd = A.std(0)
        sd[sd < 1e-8] = 1
        out.append((A - A.mean(0)) / sd / np.sqrt(A.shape[1]))
    return np.hstack(out)


# ---- out-of-fold axes ----------------------------------------------------------------------------------------
def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _lr(Xtr, ytr, Xte):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd < 1e-8] = 1
    m = LogisticRegression(C=C_LR, class_weight="balanced", max_iter=5000).fit((Xtr - mu) / sd, ytr)
    return m.predict_proba((Xte - mu) / sd)[:, 1]


def axes(runs, ids, y, sess):
    """B3_score and B2_vs_B1 out of fold, PC1..3 of the (full-model) embedding. -> DataFrame (index = ids)."""
    n = len(ids)
    s3, s21 = np.full(n, np.nan), np.full(n, np.nan)
    b12 = np.isin(y, (1, 2))
    if all(r["folds"] is None for r in runs):
        X = stack([r["X"] for r in runs], ids)
        for g in np.unique(sess):                     # leave one imaging session out
            te = sess == g
            s3[te] = _logit(_lr(X[~te], (y[~te] == 3).astype(int), X[te]))
            tr12 = ~te & b12
            if te[b12].any() and len(np.unique(y[tr12])) == 2:
                s21[te & b12] = _logit(_lr(X[tr12], (y[tr12] == 2).astype(int), X[te & b12]))
    else:                                             # supervised: the fold encoder that never saw the spot
        nf = {len(r["folds"]) for r in runs if r["folds"]}
        if len(nf) != 1 or any(r["folds"] is None for r in runs):
            raise ValueError("side-by-side runs must all be per-fold (supcon) runs with the same folds, or all label-free")
        for k in range(nf.pop()):
            held = runs[0]["folds"][k][1]
            X = stack([r["folds"][k][0] for r in runs], ids)
            te = np.isin(ids, list(held))
            s3[te] = _logit(_lr(X[~te], (y[~te] == 3).astype(int), X[te]))
            tr12 = ~te & b12
            if (te & b12).any():
                s21[te & b12] = _logit(_lr(X[tr12], (y[tr12] == 2).astype(int), X[te & b12]))
    Xf = stack([r["X"] for r in runs], ids)
    pcs = PCA(3).fit(Xf)
    P = pcs.transform(Xf)
    df = pd.DataFrame({"B3_score": s3, "B2_vs_B1": s21, "PC1": P[:, 0], "PC2": P[:, 1], "PC3": P[:, 2]}, index=ids)
    return df, [float(v) for v in pcs.explained_variance_ratio_], Xf


# ---- statistics ----------------------------------------------------------------------------------------------
def _spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 6 or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
        return np.nan, ok
    return float(np.corrcoef(rankdata(a[ok]), rankdata(b[ok]))[0, 1]), ok


def _demean(v, g):
    out = v.astype(float).copy()
    for k in np.unique(g):
        m = g == k
        out[m] = v[m] - np.nanmean(v[m])
    return out


def _bh(p):
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    if ok.any():
        pp = p[ok]
        o = np.argsort(pp)
        r = pp[o] * len(pp) / np.arange(1, len(pp) + 1)
        qq = np.empty_like(pp)
        qq[o] = np.minimum.accumulate(r[::-1])[::-1].clip(max=1)
        q[ok] = qq
    return q


def correlations(ax, F, y, sess, rng, n_perm):
    multi = pd.Series(sess).map(pd.Series(sess).value_counts()).to_numpy() >= 2
    rows = []
    for c in F.columns:
        f = F[c].to_numpy(float)
        rho, ok = _spearman(ax, f)
        if not np.isfinite(rho):
            rows.append({"feature": c, "rho": None})
            continue
        ra, rf = rankdata(ax[ok]), rankdata(f[ok])
        null = np.array([np.corrcoef(ra, rng.permutation(rf))[0, 1] for _ in range(n_perm)])
        rs, _ = _spearman(_demean(ax, sess)[multi], _demean(f, sess)[multi])
        rb, _ = _spearman(_demean(ax, y), _demean(f, y))
        rows.append({"feature": c, "rho": rho, "p": float((1 + (np.abs(null) >= abs(rho)).sum()) / (n_perm + 1)),
                     "rho_session": rs, "rho_batch": rb, "n": int(ok.sum())})
    q = _bh([r.get("p", np.nan) for r in rows])
    for r, qq in zip(rows, q):
        r["q"] = None if not np.isfinite(qq) else float(qq)
    return rows


def _loso_r2(X, t, sess):
    pred = np.full(len(t), np.nan)
    for g in np.unique(sess):
        te = sess == g
        mu, sd = X[~te].mean(0), X[~te].std(0)
        sd[sd < 1e-8] = 1
        m = RidgeCV(alphas=ALPHAS).fit((X[~te] - mu) / sd, t[~te])
        pred[te] = m.predict((X[te] - mu) / sd)
    return float(1 - np.sum((t - pred) ** 2) / np.sum((t - t.mean()) ** 2))


def _loso_r2_topk(S, t, sess, k):
    """Nested: inside each fold pick the k columns most rank-correlated with the axis on the training spots, ridge."""
    pred = np.full(len(t), np.nan)
    for g in np.unique(sess):
        te = sess == g
        rt = rankdata(t[~te])
        cor = np.array([abs(np.corrcoef(rt, rankdata(S[~te, j]))[0, 1]) if np.std(S[~te, j]) > 0 else 0 for j in range(S.shape[1])])
        idx = np.argsort(-np.nan_to_num(cor))[:k]
        X = S[:, idx]
        mu, sd = X[~te].mean(0), X[~te].std(0)
        sd[sd < 1e-8] = 1
        pred[te] = RidgeCV(alphas=ALPHAS).fit((X[~te] - mu) / sd, t[~te]).predict((X[te] - mu) / sd)
    return float(1 - np.sum((t - pred) ** 2) / np.sum((t - t.mean()) ** 2))


def explained(ax, F, groups, sess, rng, n_perm, k=3):
    """Out-of-fold R2 of the axis from the named features: the best k chosen inside each fold (the honest summary
    with 31 spots), all of them, and each family, each against a shuffle null."""
    ok = np.isfinite(ax)
    t, S, s = ax[ok], F.to_numpy(float)[ok], sess[ok]
    S = np.where(np.isfinite(S), S, np.nanmedian(S, 0))
    r2 = _loso_r2_topk(S, t, s, k)
    null = [_loso_r2_topk(S, rng.permutation(t), s, k) for _ in range(n_perm)]
    out = {f"top{k}": {"r2": r2, "p": float((1 + sum(n >= r2 for n in null)) / (n_perm + 1)), "n_features": k,
                       "null95": float(np.quantile(null, 0.95))}}
    for name, cols in {"all": list(F.columns), **groups}.items():
        idx = [F.columns.get_loc(c) for c in cols if c in F.columns]
        if not idx:
            continue
        r2 = _loso_r2(S[:, idx], t, s)
        null = [_loso_r2(S[:, idx], rng.permutation(t), s) for _ in range(n_perm)]
        out[name] = {"r2": r2, "p": float((1 + sum(n >= r2 for n in null)) / (n_perm + 1)), "n_features": len(idx),
                     "null95": float(np.quantile(null, 0.95))}
    return out


def encodes(Xf, F, sess, rng, n_perm):
    """Does the embedding carry each feature? Out-of-fold ridge R2 (leave one session out) + permutation p."""
    out = {}
    for c in F.columns:
        f = F[c].to_numpy(float)
        ok = np.isfinite(f)
        if ok.sum() < 20 or np.std(f[ok]) == 0:
            continue
        r2 = _loso_r2(Xf[ok], f[ok], sess[ok])
        null = [_loso_r2(Xf[ok], rng.permutation(f[ok]), sess[ok]) for _ in range(n_perm)]
        out[c] = {"r2": r2, "p": float((1 + sum(n >= r2 for n in null)) / (n_perm + 1))}
    return out


# ---- ledger link ---------------------------------------------------------------------------------------------
def ledger_map():
    try:
        import ledger as L
        out = {}
        for _, e in L.load_entries():
            for c in e.get("columns") or []:
                out[c] = {"entry": e["id"], "name": e.get("name"), "module": e.get("implemented_in"), "n_refs": len(e.get("refs") or []),
                          "why": " ".join(str(e.get("battery_relevance") or "").split())[:240]}
        return out
    except Exception as ex:                           # the ledger is optional context, never a reason to fail
        print(f"(ledger not read: {ex})")
        return {}


def family_of(c, led):
    m = (led.get(c) or {}).get("module") or ""
    return "plug-ins" if "spot_features" in m else "depth profile" if "depth_profile" in m else "tile features"


# ---- report --------------------------------------------------------------------------------------------------
def write_md(res, path):
    fmt = lambda v, d=2: "–" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{d}f}"  # noqa: E731
    L = [f"# What is `{res['tag']}` made of? Literature features against the embedding's axes", "",
         f"Generated by `python cnn/interpret_features.py {res['cmd']}`. Masks: {res['masks']}. {res['n_spots']} spots, "
         f"embedding dimension {res['dim']}, {len(res['features'])} literature columns. Spot = unit.", "",
         "| axis | what it is | out-of-fold check | best 3 named features, chosen in-fold (OOF R2, p) | all named features (OOF R2) |", "|---|---|---|---|---|"]
    for a, info in res["axes"].items():
        ex = res["explained"].get(a, {})
        t3, al = ex.get("top3", {}), ex.get("all", {})
        L.append(f"| {a} | {info['what']} | {info.get('check', '')} | {fmt(t3.get('r2'))} (p {fmt(t3.get('p'), 3)}) | {fmt(al.get('r2'))} |")
    for a in res["axes"]:
        rows = sorted([r for r in res["correlations"][a] if r.get("rho") is not None], key=lambda r: r["p"])[:10]
        fam = res["explained"].get(a, {})
        L += ["", f"## {a}", "", "Families (all their columns, OOF): " + ", ".join(f"{k} R2 {fmt(v['r2'])} (p {fmt(v['p'], 3)})" for k, v in fam.items() if k not in ("all", "top3")), "",
              "| literature column | ledger entry | rho | p | q | rho inside sessions | rho inside batches | embedding encodes it (R2, p) |",
              "|---|---|---|---|---|---|---|---|"]
        for r in rows:
            e, enc = res["ledger"].get(r["feature"], {}), res["encodes"].get(r["feature"], {})
            L.append(f"| `{r['feature']}` | {e.get('entry', '–')} | {fmt(r['rho'])} | {fmt(r['p'], 3)} | {fmt(r['q'], 3)} | "
                     f"{fmt(r['rho_session'])} | {fmt(r['rho_batch'])} | {fmt(enc.get('r2'))} ({fmt(enc.get('p'), 3)}) |")
    L += ["", "Read: q < 0.1 survives testing every column of one axis; a link that keeps its sign inside sessions is not",
          "the microscope; one that keeps it inside batches tracks the embedding beyond the label. 'Explained' is what the",
          "named features can say about the axis together; 1 - R2 is what the embedding knows that they do not name."]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", default=[], help="cnn/<processed>/<run> (repeat for side by side)")
    ap.add_argument("--npz", action="append", default=[], help="any .npz with sample_id + site_feat or emb")
    ap.add_argument("--tag", default="")
    ap.add_argument("--n-perm", type=int, default=2000)
    ap.add_argument("--n-perm-r2", type=int, default=50, help="shuffles for the R2 nulls (slower: one ridge per fold)")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if not a.run and not a.npz:
        ap.error("give --run and/or --npz")
    runs = [load_run(r) for r in a.run] + [load_npz(p) for p in a.npz]
    tag = a.tag or "+".join([r.replace("/", "_") for r in a.run] + [Path(p).stem for p in a.npz])
    rng = np.random.default_rng(a.seed)

    table = pd.read_csv(TABLE)
    table = table[table.batch.str.startswith("Batch_")]
    ids = [s for s in table.sample_id if all(s in r["X"] for r in runs)]
    table = table.set_index("sample_id").loc[ids]
    y = table.batch.str[-1].astype(int).to_numpy()
    sess = table.session.to_numpy()
    cols = [c for c in COLUMNS if c in table.columns and table[c].notna().sum() >= 25]
    F = table[cols].astype(float)
    led = ledger_map()
    groups = {}
    for c in cols:
        groups.setdefault(family_of(c, led), []).append(c)

    AX, var_ratio, Xf = axes(runs, np.array(ids), y, sess)
    supervised = any(r["folds"] for r in runs)
    what = {"B3_score": ("logit P(Batch_3) from the embedding", "fold encoder never saw the spot" if supervised else "leave one session out"),
            "B2_vs_B1": ("logit P(Batch_2) against Batch_1, 14 spots", "fold encoder never saw the spot" if supervised else "leave one session out"),
            **{f"PC{i + 1}": (f"principal axis {i + 1} ({100 * v:.0f} % of variance)", "label-free" + (" (full model)" if supervised else ""))
               for i, v in enumerate(var_ratio)}}
    res = {"tag": tag, "cmd": " ".join(sys.argv[1:]), "masks": os.environ["LOSSLARP_MASKS"], "n_spots": len(ids),
           "dim": int(Xf.shape[1]), "features": cols, "families": groups, "ledger": {c: led[c] for c in cols if c in led},
           "axes": {}, "correlations": {}, "explained": {},
           "spots": [{"sample_id": s, "batch": int(b), "session": int(g), **{k: (None if not np.isfinite(v) else float(v)) for k, v in AX.loc[s].items()}}
                     for s, b, g in zip(ids, y, sess)]}
    for k in AX.columns:
        ax = AX[k].to_numpy(float)
        info = {"what": what[k][0], "check": what[k][1]}
        if k in ("B3_score", "B2_vs_B1"):
            m = np.isfinite(ax)
            yy = (y[m] == 3) if k == "B3_score" else (y[m] == 2)
            from sklearn.metrics import roc_auc_score
            info["auc"] = float(roc_auc_score(yy, ax[m])) if len(np.unique(yy)) == 2 else None
            info["check"] += f", AUC {info['auc']:.2f}" if info["auc"] is not None else ""
        res["axes"][k] = info
        res["correlations"][k] = correlations(ax, F, y, sess, rng, a.n_perm)
        res["explained"][k] = explained(ax, F, groups, sess, rng, a.n_perm_r2)
        ex = res["explained"][k]
        print(f"{k:9s} {info['check']:40s} explained by the best 3 named features (chosen in-fold): OOF R2 {ex['top3']['r2']:+.2f} "
              f"(p {ex['top3']['p']:.3f}); all {len(cols)}: {ex['all']['r2']:+.2f}", flush=True)
    res["encodes"] = encodes(Xf, F, sess, rng, a.n_perm_r2)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"interpret_{tag}.json"
    out.write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    write_md(res, out.with_suffix(".md"))
    for k in ("B3_score", "B2_vs_B1", "PC1"):
        top = sorted([r for r in res["correlations"][k] if r.get("rho") is not None], key=lambda r: r["p"])[:5]
        print(f"  {k}: " + "; ".join(f"{r['feature']} rho {r['rho']:+.2f} (q {r['q']:.2f}, in-session {r['rho_session']:+.2f})" for r in top))
    print(f"wrote {out.relative_to(REPO)} and .md")


if __name__ == "__main__":
    main()
