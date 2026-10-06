"""One fixed scorecard for any spot-level representation: embeddings, texture statistics, hand-crafted panels.

Written before the embedding sweep's results came in, so that every representation is scored the same way and
the scoring cannot drift towards whatever looks best.

Rows    the 31 training spots (+ the 3 test spots: scored, never trained on inside a CV fold).
Labels  batch folder 1, 2, 3 (7 / 7 / 17). Groups: session = image height (13 values), spot.

Supervised: balanced accuracy (chance 0.33), out of fold
    classifiers (all standardise inside the fold)
        lr        L2 logistic regression, class_weight balanced, C = 0.1 (fast mode) or C picked by an inner
                  leave-one-session-out CV from C_GRID (full mode: nested, no peeking). Fitted on the training fold's
                  PCA scores (all components); for L2 logistic regression that is the same model (the weights lie in
                  the span of the training rows) and 100x faster when D >> n.
        centroid  nearest class centroid, cosine (= "assign the crop to the closest batch cluster")
        knn3      3 nearest neighbours, cosine
        lda       PCA(10) -> LDA with Ledoit-Wolf shrinkage
    validations
        loso      leave one spot out: the blind-test crops so far come from the same large images (they seam onto
                  training spots), so this is the estimate for that test
        losess    leave one session (image height) out: the estimate for crops from large images we have not seen
        mixed     loso calls on the 13 spots of the 5 sessions that hold more than one batch: there the session
                  cannot be the cue, so only what differs inside one image can get these right
        joins     the 4 cross-folder joins (same image, adjacent crops, different batch): both crops of a pair held
                  out together; fraction of the 8 calls that are right (chance 0.33)
Unsupervised: does the representation reproduce Polaron's grouping with no labels at all?
        ari_*     adjusted Rand index of a 3-cluster solution vs the batch labels (k-means and Ward on PCA-10 of the
                  standardised 31 training rows; GMM on PCA-5). 1 = their grouping exactly, 0 = chance.
        ari_sess  the k-means clusters vs session (how much the space is organised by imaging session instead)
Test: the classifier fitted on all 31 spots -> P(batch) for the 3 test spots (their seam neighbours suggest
B1 / B3 / B2, which is not ground truth).

Library use:
    from analysis.embeddings import evalkit as ek
    meta = ek.meta_for(batch, sample_id, height)          # or ek.load_sweep(path) -> (meta, {rep: X})
    row = ek.score(X, meta)                                # fast mode: dict of every metric
    row = ek.score(X, meta, full=True, n_perm=200)         # nested C + permutation p-values
CLI:
    python analysis/embeddings/evalkit.py --sweep processed/emb_sweep --out analysis/embeddings/results/sweep_scores.csv
"""
import argparse
import json
import os
import sys
import warnings
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")      # tiny matrices: threads only add overhead (and parallel workers oversubscribe)
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
SEED = 0
C_FAST = 0.1
C_GRID = (0.001, 0.01, 0.1, 1.0, 10.0)
# the 4 joins that cross batch folders (notes/seam_examples): (left, right) sample ids, same image, adjacent crops
CROSS_JOINS = (("cfe5vt7s", "r17byphk"), ("r17byphk", "ffwubibz"), ("utfgcjfa", "rxax5ozo"), ("f1vzngrs", "epqdaau9"))
SEAM_GUESS = {"3e122cbj": 1, "xrv9xvzb": 3, "fn0mhxef": 2}   # test spots: batch of their seam neighbour (not truth)


# ----------------------------------------------------------------------------------------------------
# data
# ----------------------------------------------------------------------------------------------------
def meta_for(batch, sample_id, height):
    m = pd.DataFrame({"batch": np.asarray(batch).astype(str), "sample_id": np.asarray(sample_id).astype(str),
                      "height": np.asarray(height).astype(int)})
    m["is_test"] = m["batch"] == "Test"
    m["y"] = [int(b[-1]) if b.startswith("Batch_") else 0 for b in m["batch"]]
    m["session"] = m["height"]
    sess = m.loc[~m.is_test].groupby("session")["y"].nunique()
    m["mixed"] = m["session"].map(sess).fillna(0).astype(int).gt(1) & ~m.is_test
    return m


def load_sweep(path, aggs=("mean", "meanstd")):
    """processed/emb_sweep/<backbone>.npz -> (meta, {rep name: X (n, D)}). Rep = backbone|mode|chan|s<k>|token|agg."""
    z = np.load(path)
    bb = Path(path).stem
    meta = meta_for(z["batch"], z["sample_id"], z["height"])
    reps = {}
    for k in z.files:
        if not (k.startswith("site|") and k.endswith("|mean")):
            continue
        base = k[len("site|"):-len("|mean")]
        if "mean" in aggs:
            reps[f"{bb}|{base}|mean"] = z[k]
        sd = f"site|{base}|std"
        if "meanstd" in aggs and sd in z.files:
            reps[f"{bb}|{base}|meanstd"] = np.hstack([z[k], z[sd]])
    return meta, reps


def acquisition_reference(meta):
    """The imaging-only reference: black level, contrast and the SE detector name (processed/acquisition.csv).
    Image height is never used. Test spots get NaN (not in the CSV)."""
    acq = pd.read_csv(ROOT / "processed" / "acquisition.csv")
    cols = ["acq_bse_black_level", "acq_bse_contrast", "acq_se_named_SE"]
    m = meta[["sample_id"]].merge(acq[["sample_id"] + cols], on="sample_id", how="left")
    return m[cols].to_numpy(float)


# ----------------------------------------------------------------------------------------------------
# classifiers (numpy where it is cheap; everything is fitted on the training fold only)
# ----------------------------------------------------------------------------------------------------
def _std(Xtr, Xte):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd < 1e-8] = 1.0
    return (Xtr - mu) / sd, (Xte - mu) / sd


def _unit(X):
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


def _pca_scores(Xtr, Xte, k=None):
    """PCA scores through the n x n Gram matrix (n spots << D dimensions: exact and fast)."""
    mu = Xtr.mean(0)
    A, B = Xtr - mu, Xte - mu
    w, U = np.linalg.eigh(A @ A.T)
    order = np.argsort(w)[::-1]
    w, U = w[order], U[:, order]
    keep = w > max(w[0], 0) * 1e-10 if w.size else np.zeros(0, bool)
    U, s = U[:, keep], np.sqrt(w[keep])
    if k:
        U, s = U[:, :k], s[:k]
    return U * s, (B @ A.T @ U) / s


def _proba_lr(Xtr, ytr, Xte, C):
    from sklearn.linear_model import LogisticRegression
    Ptr, Pte = _pca_scores(Xtr, Xte)
    clf = LogisticRegression(C=C, class_weight="balanced", max_iter=5000).fit(Ptr, ytr)
    P = np.zeros((len(Xte), 3))
    P[:, clf.classes_ - 1] = clf.predict_proba(Pte)
    return P


def _proba_centroid(Xtr, ytr, Xte):
    A, B = _unit(Xtr), _unit(Xte)
    S = np.full((len(Xte), 3), -np.inf)
    for c in np.unique(ytr):
        S[:, c - 1] = B @ _unit(A[ytr == c].mean(0, keepdims=True))[0]
    E = np.exp(10 * (S - S.max(1, keepdims=True)))
    return E / E.sum(1, keepdims=True)


def _proba_knn(Xtr, ytr, Xte, k=3):
    S = _unit(Xte) @ _unit(Xtr).T
    P = np.zeros((len(Xte), 3))
    for i, row in enumerate(S):
        for j in np.argsort(-row)[:k]:
            P[i, ytr[j] - 1] += 1.0 / k
    return P


def _proba_lda(Xtr, ytr, Xte):
    from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
    Ptr, Pte = _pca_scores(Xtr, Xte, k=min(10, len(Xtr) - 2))
    clf = LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto").fit(Ptr, ytr)
    P = np.zeros((len(Xte), 3))
    P[:, clf.classes_ - 1] = clf.predict_proba(Pte)
    return P


def _bacc(y, pred):
    classes = np.unique(y)
    return float(np.mean([(pred[y == c] == c).mean() for c in classes]))


def _inner_C(Xtr, ytr, gtr):
    """C for lr by leave-one-session-out inside the training fold (balanced accuracy; ties -> smaller C)."""
    best, best_s = C_GRID[0], -1.0
    groups = np.unique(gtr)
    for C in C_GRID:
        pred = np.zeros(len(ytr), int)
        for g in groups:
            te = gtr == g
            if len(np.unique(ytr[~te])) < 2:
                pred[te] = 3
                continue
            a, b = _std(Xtr[~te], Xtr[te])
            pred[te] = _proba_lr(a, ytr[~te], b, C).argmax(1) + 1
        s = _bacc(ytr, pred)
        if s > best_s + 1e-9:
            best, best_s = C, s
    return best


def fit_predict(clf, Xtr, ytr, Xte, gtr=None, full=False):
    a, b = _std(Xtr, Xte)
    if clf == "lr":
        C = _inner_C(Xtr, ytr, gtr) if full else C_FAST
        return _proba_lr(a, ytr, b, C)
    if clf == "centroid":
        return _proba_centroid(a, ytr, b)
    if clf == "knn3":
        return _proba_knn(a, ytr, b)
    if clf == "lda":
        return _proba_lda(a, ytr, b)
    raise ValueError(clf)


def oof(X, y, groups, clf, sess=None, full=False):
    """Out-of-fold P(batch) with one fold per value of `groups`."""
    P = np.zeros((len(y), 3))
    for g in np.unique(groups):
        te = groups == g
        P[te] = fit_predict(clf, X[~te], y[~te], X[te], None if sess is None else sess[~te], full)
    return P


def joins_oof(X, y, sid, clf, sess, full=False):
    """Both crops of each cross-folder join held out together -> (n right, n calls)."""
    right = n = 0
    for a, b in CROSS_JOINS:
        te = np.isin(sid, [a, b])
        if te.sum() != 2:
            continue
        P = fit_predict(clf, X[~te], y[~te], X[te], sess[~te], full)
        right += int(((P.argmax(1) + 1) == y[te]).sum())
        n += 2
    return right, n


# ----------------------------------------------------------------------------------------------------
# unsupervised
# ----------------------------------------------------------------------------------------------------
def unsup(X, y, sess):
    from sklearn.cluster import AgglomerativeClustering, KMeans
    from sklearn.metrics import adjusted_rand_score as ari
    from sklearn.mixture import GaussianMixture
    Z, _ = _std(X, X)
    P10, _ = _pca_scores(Z, Z, k=10)
    P5 = P10[:, :5]
    km = KMeans(3, n_init=20, random_state=SEED).fit_predict(P10)
    ward = AgglomerativeClustering(3, linkage="ward").fit_predict(P10)
    try:
        gmm = GaussianMixture(3, covariance_type="diag", n_init=5, random_state=SEED).fit(P5).predict(P5)
        a_gmm = ari(y, gmm)
    except Exception:   # noqa: BLE001
        a_gmm = np.nan
    return {"ari_kmeans": ari(y, km), "ari_ward": ari(y, ward), "ari_gmm": a_gmm, "ari_sess": ari(sess, km)}


# ----------------------------------------------------------------------------------------------------
# the scorecard
# ----------------------------------------------------------------------------------------------------
CLFS = ("lr", "centroid", "knn3", "lda")


def score(X, meta, full=False, n_perm=0, clfs=CLFS, test=True):
    """X: (n, D) rows aligned with meta (training + optional test rows). -> flat dict of metrics."""
    X = np.asarray(X, float)
    tr = ~meta.is_test.to_numpy()
    Xt, y = X[tr], meta.y.to_numpy()[tr]
    if not np.isfinite(Xt).all():
        col_mean = np.nanmean(Xt, 0)
        Xt = np.where(np.isfinite(Xt), Xt, col_mean)
    sess, sid = meta.session.to_numpy()[tr], meta.sample_id.to_numpy()[tr]
    mixed = meta.mixed.to_numpy()[tr]
    out = {"dim": X.shape[1]}
    for clf in clfs:
        P_loso = oof(Xt, y, np.arange(len(y)), clf, sess, full)
        P_sess = oof(Xt, y, sess, clf, sess, full)
        p_loso, p_sess = P_loso.argmax(1) + 1, P_sess.argmax(1) + 1
        out[f"{clf}_loso"] = _bacc(y, p_loso)
        out[f"{clf}_losess"] = _bacc(y, p_sess)
        out[f"{clf}_mixed"] = _bacc(y[mixed], p_loso[mixed])
        r, n = joins_oof(Xt, y, sid, clf, sess, full)
        out[f"{clf}_joins"] = r / n if n else np.nan
        out[f"{clf}_losess_logloss"] = float(-np.mean(np.log(np.clip(P_sess[np.arange(len(y)), y - 1], 1e-6, 1))))
    out.update(unsup(Xt, y, sess))
    if test and meta.is_test.any():
        Xte = X[~tr]
        clf = "lr"
        P = fit_predict(clf, Xt, y, Xte, sess, full)
        for i, s in enumerate(meta.sample_id[~tr]):
            out[f"test_{s}"] = int(P[i].argmax() + 1)
            out[f"test_{s}_p"] = json.dumps(np.round(P[i], 3).tolist())
        guess = np.array([SEAM_GUESS.get(s, 0) for s in meta.sample_id[~tr]])
        out["test_agree_seam"] = int(((P.argmax(1) + 1) == guess).sum())
    if n_perm:
        rng = np.random.default_rng(SEED)
        null = {"loso": [], "losess": []}
        for _ in range(n_perm):
            yp = rng.permutation(y)
            null["loso"].append(_bacc(yp, oof(Xt, yp, np.arange(len(y)), "lr", sess, False).argmax(1) + 1))
            null["losess"].append(_bacc(yp, oof(Xt, yp, sess, "lr", sess, False).argmax(1) + 1))
        for k in ("loso", "losess"):
            obs = out[f"lr_{k}"]
            out[f"lr_{k}_perm_p"] = (1 + np.sum(np.array(null[k]) >= obs - 1e-12)) / (1 + n_perm)
    return out


def nested_select(reps, meta, clf="centroid", by="losess", outer="losess"):
    """Selection-aware estimate: in each outer fold, pick the representation with the best inner score on the
    training spots only, then call the held-out spots with it. Returns (balanced accuracy, picks per fold).
    This is the honest number for "the best of N representations" (the max over N is optimistic)."""
    tr = ~meta.is_test.to_numpy()
    y, sess = meta.y.to_numpy()[tr], meta.session.to_numpy()[tr]
    names = list(reps)
    Xs = [np.asarray(reps[n], float)[tr] for n in names]
    groups = sess if outer == "losess" else np.arange(len(y))
    pred = np.zeros(len(y), int)
    picks = []
    for g in np.unique(groups):
        te = groups == g
        inner_g = sess[~te] if by == "losess" else np.arange((~te).sum())
        best, best_s = 0, -1.0
        for i, X in enumerate(Xs):
            s = _bacc(y[~te], oof(X[~te], y[~te], inner_g, clf).argmax(1) + 1)
            if s > best_s:
                best, best_s = i, s
        picks.append(names[best])
        pred[te] = fit_predict(clf, Xs[best][~te], y[~te], Xs[best][te]).argmax(1) + 1
    return _bacc(y, pred), picks


# ----------------------------------------------------------------------------------------------------
# CLI: score every representation of a sweep folder (fast mode), in parallel
# ----------------------------------------------------------------------------------------------------
def _score_one(args):
    name, X, meta = args
    try:
        return {"rep": name, **score(X, meta, clfs=("lr", "centroid", "knn3"))}
    except Exception as e:   # noqa: BLE001
        return {"rep": name, "error": f"{type(e).__name__}: {e}"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sweep", default=str(ROOT / "processed" / "emb_sweep"))
    ap.add_argument("--out", default=str(ROOT / "analysis" / "embeddings" / "results" / "sweep_scores.csv"))
    ap.add_argument("--backbones", default="", help="comma list (default: every .npz in --sweep)")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    from concurrent.futures import ProcessPoolExecutor
    files = sorted(Path(a.sweep).glob("*.npz"))
    if a.backbones:
        keep = set(a.backbones.split(","))
        files = [f for f in files if f.stem in keep]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=["rep"])
    rows = [done]
    for f in files:
        meta, reps = load_sweep(f)
        todo = [(n, X, meta) for n, X in reps.items() if n not in set(done["rep"])]
        if not todo:
            continue
        with ProcessPoolExecutor(a.jobs) as ex:
            res = pd.DataFrame(list(ex.map(_score_one, todo, chunksize=4)))
        rows.append(res)
        print(f"{f.stem}: {len(res)} reps, best lr_losess {res['lr_losess'].max():.2f}, best lr_loso "
              f"{res['lr_loso'].max():.2f}, best ari_kmeans {res['ari_kmeans'].max():.2f}", flush=True)
        pd.concat(rows, ignore_index=True).to_csv(out, index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    main()
