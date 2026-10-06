"""The evaluation harness: learn a small metric over the frozen bank and score it without leaking a source image.

    python -m bank.harness --out results/v1            # 2000 bootstrap resamples, 1000 + 1000 permutations
    python -m bank.harness --out /tmp/h --quick        # 200 resamples, 100 + 100 permutations
    python -m bank.harness --out /tmp/h --skip scat    # without one family; --workers N processes (default 5)

Writes  <out>/harness.json           every number (deterministic: two runs give the same file)
        <out>/results.md             the tables, built only from harness.json
        <out>/oof_predictions.csv    out-of-fold class probabilities of every model under both splits
        <out>/run_info.json          wall time and versions (not part of the deterministic output)

What is fitted, and where (config/primary.yaml holds every number):
  one "fit" = one set of training crops. Per space (family, detector, view, tag) the robust scaler, the PCA (<= 16),
  the RBF bandwidth, the kernel centring and its scale are fitted on the training crops only and applied to all
  crops. ALIGNF weights and the class means use the training labels only. The temperature of an outer fold comes
  from an inner leave-one-source-image-out in which every one of those steps is fitted again without the inner
  validation image. Kernels do not depend on labels, so a fit computes them once and reuses them for the real labels
  and for every permuted labelling.

Splits: LOSO-13 (leave one source image out) and LOCO-nbr (leave one crop out, its touching neighbours dropped from
training). Provenance (source image, neighbours) is used for splits, nulls and the oracle baseline only.

Choices the brief left open (all in config/primary.yaml, all fixed before the full bank is scored):
  - a space is (family, detector, view, tag), so that "not imaging" and "not leakrisk" are exact;
  - a space with only per-tile arrays gets its linear and RBF kernels from the mean over tiles;
  - the MMD kernel uses at most 64 tile slots per crop (the same seeded slots for every crop) and, for tile arrays
    wider than 256, one fixed Gaussian projection that no data went into; tile arrays of a space with the same
    tile count are joined; token grids (wider than 4096) are not loaded at all;
  - after centring, each kernel is scaled to mean training diagonal 1, so weights and the temperature are comparable;
  - the temperature does not change which class is nearest, so it moves log-loss and AUC but not balanced accuracy;
  - Null A and Null B are run on LOSO-13 for models A, B and the acquisition-only baseline. Null B enumerates every
    arrangement when there are no more than the requested number (192 for this data), and samples otherwise;
  - a fold "cannot be learned" when a class has no training crop, or comes from a single training source image
    (the inner LOSO then cannot validate it). Such folds are listed and still scored.

Other files use this module's functions (tests/test_bank_leakage.py): load_config, design_from_bank, make_splits,
fit_jobs, run_fits, fit_fold, compose_kernel, balanced_accuracy_many, null_a_labels, run, write. Keep their signatures.
"""
import os
import sys

if "numpy" not in sys.modules:               # the command line and its worker processes: one BLAS thread per process, so that
    for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(_v, "1")       # --workers is the only parallelism. A process that already uses numpy is left alone.

import argparse                              # noqa: E402
import fnmatch                               # noqa: E402
import itertools                             # noqa: E402
import json                                  # noqa: E402
import time                                  # noqa: E402
import warnings                              # noqa: E402
from dataclasses import dataclass, field     # noqa: E402
from multiprocessing import get_context      # noqa: E402
from pathlib import Path                     # noqa: E402

import numpy as np                           # noqa: E402
import pandas as pd                          # noqa: E402
import yaml                                  # noqa: E402
from scipy.optimize import nnls              # noqa: E402
from sklearn.linear_model import LogisticRegression   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "primary.yaml"
SPLITS = ("loso13", "loco_nbr")


def load_config(path=CONFIG):
    return yaml.safe_load(Path(path).read_text())


# ----------------------------------------------------------------------------------------------------
# the design: what the fits work on (no disk, no provenance in any matrix)
# ----------------------------------------------------------------------------------------------------
@dataclass
class Design:
    crops: list
    classes: list                 # class names, sorted
    y: np.ndarray                 # (n,) class codes
    groups: np.ndarray            # (n,) source image of each crop: splits, nulls and the oracle only
    neighbours: list              # per crop, the indices of its touching neighbours: LOCO-nbr only
    spaces: list                  # dict(key, family, tag, X (n, d), tile_sets [dict(T (N, d), W (n, N))], ...)
    kernels: list                 # dict(name, space, kind, tile_set)
    models: dict                  # name -> dict(kernels [indices], weights "alignf" | "uniform", null bool, role)
    family_spaces: dict           # family -> indices of its non-leakrisk spaces, for the single-family logistic baseline
    notes: list = field(default_factory=list)
    family_candidates: list = field(default_factory=list)   # families the "best single family" baseline may choose (not replaced legacy)

    @property
    def n(self):
        return len(self.crops)

    def family_matrix(self, family):
        return np.concatenate([self.spaces[i]["X"] for i in self.family_spaces[family]], axis=1)

    def family_columns(self, family):
        return int(sum(self.spaces[i]["n_columns"] for i in self.family_spaces[family]))


def _tile_set(tiles, cfg, seed):
    """Stack one tile set: a seeded subset of tile slots per crop, then one fixed Gaussian sketch if it is wide."""
    mm = cfg["kernels"]["mmd"]
    parts, owner = [], []
    for i, t in enumerate(tiles):
        t = np.asarray(t, np.float64)
        if len(t) > mm["max_tiles_per_crop"]:                # the slots depend on the tile count only, never on the crop
            keep = np.sort(np.random.default_rng([seed, 11, len(t)]).choice(len(t), mm["max_tiles_per_crop"], replace=False))
            t = t[keep]
        parts.append(t)
        owner += [i] * len(t)
    T, owner = np.concatenate(parts), np.array(owner)
    if T.shape[1] > mm["sketch_dim"]:                        # data-independent, so it cannot leak a held-out crop
        proj = np.random.default_rng([seed, 12, T.shape[1]]).standard_normal((T.shape[1], mm["sketch_dim"]))
        T = T @ proj / np.sqrt(mm["sketch_dim"])
    W = np.zeros((len(tiles), len(owner)))
    W[owner, np.arange(len(owner))] = 1.0
    return dict(T=T, owner=owner, W=W / W.sum(axis=1, keepdims=True))


def build_design(crops, labels, groups, neighbours, spaces, cfg, complete_families=None):
    """Spaces (bank.assemble.Space, or anything with key/family/tag/X/tile_sets) -> Design.

    neighbours: {crop: right-hand touching crop}; made symmetric here.
    """
    crops = list(crops)
    classes = sorted(set(labels))
    y = np.array([classes.index(v) for v in labels])
    at = {c: i for i, c in enumerate(crops)}
    nbr = [set() for _ in crops]
    for a, b in (neighbours or {}).items():
        if a in at and b in at:
            nbr[at[a]].add(at[b])
            nbr[at[b]].add(at[a])
    seed = int(cfg["seed"])
    sp, kernels, notes = [], [], []
    for s in spaces:
        X = np.asarray(s.X, np.float64)
        if X.shape[0] != len(crops) or not np.isfinite(X).all():
            notes.append(f"space {s.key} skipped: wrong number of rows or not finite")
            continue
        tsets = [_tile_set(ts["tiles"], cfg, seed) for ts in getattr(s, "tile_sets", [])]
        si = len(sp)
        sp.append(dict(key=s.key, family=s.family, tag=s.tag, detector=getattr(s, "detector", ""), view=getattr(s, "view", ""),
                       X=X, tile_sets=tsets, legacy=bool(getattr(s, "legacy", False)), pooled=bool(getattr(s, "pooled", False)),
                       n_columns=int(X.shape[1]), tile_dims=[int(ts["tiles"][0].shape[1]) for ts in getattr(s, "tile_sets", [])]))
        for kind in cfg["kernels"]["kinds"]:
            if kind in ("linear", "rbf"):
                kernels.append(dict(name=f"{s.key}::{kind}", space=si, kind=kind, tile_set=None))
            elif kind == "mmd":
                for j in range(len(tsets)):
                    kernels.append(dict(name=f"{s.key}::mmd" + (f"@{j}" if len(tsets) > 1 else ""), space=si, kind="mmd", tile_set=j))
    families_here = sorted({s["family"] for s in sp})
    complete = set(families_here if complete_families is None else complete_families)

    def replaced(family):
        prefixes = cfg.get("legacy", {}).get(family, {}).get("replaced_by", [])
        return any(f.startswith(p) for f in complete if f != family for p in prefixes)

    def pool(keep):
        return [k for k, kn in enumerate(kernels) if keep(sp[kn["space"]])]

    acq_family = cfg["acquisition"]["family"] if cfg["acquisition"]["family"] in families_here else cfg["acquisition"]["fallback"]
    models = {}
    for name, m in cfg["models"].items():
        ks = pool(lambda s, m=m: s["tag"] not in m["exclude_tags"] and not replaced(s["family"])
                  and not any(fnmatch.fnmatch(s["key"], pat) for pat in m.get("exclude_spaces", [])))
        models[name] = dict(kernels=ks, weights=m["weights"], null=name in cfg["statistics"]["null_models"], role="model")
        models[f"uniform_{name}"] = dict(kernels=ks, weights="uniform", null=False, role="baseline")
        if cfg.get("sensitivity", {}).get("alignf_cross_image"):
            models[f"cross_{name}"] = dict(kernels=ks, weights="alignf_cross", null=False, role="sensitivity")
    models["acquisition"] = dict(kernels=pool(lambda s: s["family"] == acq_family and s["tag"] != "leakrisk"), weights="alignf",
                                 null="acquisition" in cfg["statistics"]["null_models"], role="baseline", family=acq_family)
    models["dinov2s_legacy"] = dict(kernels=pool(lambda s: s["family"] == "legacy_dinov2s"), weights="alignf", null=False, role="baseline")
    for name in [k for k, m in models.items() if not m["kernels"]]:
        notes.append(f"model {name} has no kernels in this bank and is not scored")
        del models[name]
    family_spaces = {}
    for f in families_here:
        mine = [i for i, s in enumerate(sp) if s["family"] == f and s["tag"] != "leakrisk"]
        if mine:
            family_spaces[f] = mine
    return Design(crops, classes, y, np.asarray(groups).astype(str), nbr, sp, kernels, models, family_spaces, notes,
                  [f for f in family_spaces if not replaced(f)])


def design_from_bank(cfg, bank=None, skip=()):
    """The design of the bank on disk (P0). meta/analysis_only.csv is read for the touching neighbours only.

    skip: families to leave out of everything (as if they were not on disk).
    """
    from bank import core
    from bank.assemble import load_bank
    bank = load_bank() if bank is None else bank
    table = pd.read_csv(core.META_DIR / "analysis_only.csv")
    neighbours = {r.site: r.right_neighbour for r in table.itertuples() if isinstance(r.right_neighbour, str)}
    complete = [f for f in bank.complete_families() if not bank.families[f].legacy and f not in skip]
    design = build_design(bank.crops, bank.y, bank.groups, neighbours, [s for s in bank.spaces() if s.family not in skip], cfg, complete)
    if skip:
        design.notes.append("left out on the command line: " + ", ".join(sorted(skip)))
    return design, bank


# ----------------------------------------------------------------------------------------------------
# splits
# ----------------------------------------------------------------------------------------------------
def make_splits(groups, neighbours):
    """{"loso13": folds, "loco_nbr": folds}; a fold = dict(name, test, train, inner=[dict(val, train)]), indices as sorted tuples."""
    n = len(groups)
    everything = range(n)

    def with_inner(name, test, train):
        inner = []
        for g in sorted(set(groups[list(train)])):
            val = tuple(i for i in train if groups[i] == g)
            rest = tuple(i for i in train if groups[i] != g)
            if val and rest:
                inner.append(dict(val=val, train=rest))
        return dict(name=name, test=tuple(test), train=tuple(train), inner=inner)

    loso = [with_inner(g, [i for i in everything if groups[i] == g], [i for i in everything if groups[i] != g])
            for g in sorted(set(groups))]
    loco = [with_inner(i, [i], [j for j in everything if j != i and j not in neighbours[i]]) for i in everything]
    return {"loso13": loso, "loco_nbr": loco}


def fit_jobs(splits):
    """Every distinct training set, with "all" where the permuted labellings are needed (LOSO-13) and "real" elsewhere."""
    jobs = {}
    for name, folds in splits.items():
        mode = "all" if name == "loso13" else "real"
        for fold in folds:
            for train in [fold["train"]] + [inner["train"] for inner in fold["inner"]]:
                if jobs.get(train) != "all":
                    jobs[train] = mode
    return jobs


def fold_report(fold, y, groups, crops, classes):
    """What a fold can and cannot learn, from the real labels."""
    tr, te = list(fold["train"]), list(fold["test"])
    counts = [int((y[tr] == c).sum()) for c in range(len(classes))]
    images = [len(set(groups[tr][y[tr] == c])) for c in range(len(classes))]
    reasons = []
    for c, name in enumerate(classes):
        if counts[c] == 0:
            reasons.append(f"{name} has no training crop" + (" but is in the test fold" if (y[te] == c).any() else ""))
        elif images[c] < 2:
            reasons.append(f"{name} comes from one source image in training, so the inner LOSO cannot validate it")
    return dict(fold=str(fold["name"]) if not isinstance(fold["name"], (int, np.integer)) else crops[fold["name"]],
                test=[crops[i] for i in te], test_classes=sorted({classes[c] for c in y[te]}), n_train=len(tr),
                train_crops=dict(zip(classes, counts)), train_images=dict(zip(classes, images)),
                unlearnable=bool(reasons), reasons=reasons)


# ----------------------------------------------------------------------------------------------------
# one fit: everything below sees the training rows only when it estimates anything
# ----------------------------------------------------------------------------------------------------
def _quartiles(A):
    """25th, 50th and 75th percentile of each column (linear interpolation, as np.percentile; one sort instead of three partitions)."""
    S = np.sort(A, axis=0)
    out = []
    for q in (0.25, 0.5, 0.75):
        pos = q * (len(S) - 1)
        lo = int(np.floor(pos))
        hi = min(lo + 1, len(S) - 1)
        out.append(S[lo] + (S[hi] - S[lo]) * (pos - lo))
    return out


def _scale_pca(X, tr, q_max, clip):
    """Robust scale and PCA fitted on rows `tr`, applied to every row. Returns (scores (n, q), state) or (None, None)."""
    A = X[tr]
    q25, med, q75 = _quartiles(A)
    scale = (q75 - q25) / 1.349
    tiny = 1e-9 * np.maximum(1.0, np.abs(med))
    scale = np.where(scale > tiny, scale, A.std(axis=0))
    keep = scale > tiny
    if not keep.any():
        return None, None
    Z = np.clip((X[:, keep] - med[keep]) / scale[keep], -clip, clip)
    mu = Z[tr].mean(axis=0)
    Z = Z - mu
    A = Z[tr]
    if A.shape[1] > A.shape[0]:                              # more columns than rows: eigenvectors of the Gram matrix
        w, U = np.linalg.eigh(A @ A.T)
        w, U = np.clip(w[::-1], 0, None), U[:, ::-1]
        q = min(q_max, int((w > 1e-12 * w[0]).sum())) if w[0] > 0 else 0
        comps = (U[:, :q].T @ A) / np.sqrt(w[:q])[:, None] if q else None
    else:
        w, V = np.linalg.eigh(A.T @ A)
        w, V = np.clip(w[::-1], 0, None), V[:, ::-1]
        q = min(q_max, int((w > 1e-12 * w[0]).sum())) if w[0] > 0 else 0
        comps = V[:, :q].T if q else None
    if comps is None:
        return None, None
    return Z @ comps.T, dict(median=med, scale=scale, keep=keep, mean=mu, components=comps)


def _sqdist(S):
    g = S @ S.T
    d = np.diag(g)
    return np.clip(d[:, None] + d[None, :] - 2.0 * g, 0.0, None)


def _median_distance(D2):
    d = np.sqrt(D2[np.triu_indices(len(D2), 1)])
    med = float(np.median(d)) if len(d) else 0.0
    return med if med > 1e-12 else 1.0


def _finish(K, tr):
    """Cosine-normalise, centre on the training mean, scale to mean training diagonal 1. Returns (K, ok, state)."""
    d = np.sqrt(np.clip(np.diag(K), 0.0, None))
    ok = d > 1e-12
    d = np.where(ok, d, 1.0)
    K = K / d[:, None] / d[None, :]
    K[~ok] = 0.0
    K[:, ~ok] = 0.0
    col = K[:, tr].mean(axis=1)
    tot = float(K[np.ix_(tr, tr)].mean())
    K = K - col[:, None] - col[None, :] + tot
    trace = float(np.diag(K)[tr].mean())
    if not np.isfinite(trace) or trace <= 1e-10:
        return np.zeros_like(K), False, None
    return K / trace, True, dict(train_column_mean=col[tr], train_mean=tot, trace=trace)


def fit_kernels(design, tr, cfg, with_state=False):
    """Every kernel of the design, fitted on the crops `tr`: (M, n, n) array, valid flags and (optionally) the fitted state."""
    kc = cfg["kernels"]
    n, M = design.n, len(design.kernels)
    K, valid, state = np.zeros((M, n, n)), np.zeros(M, bool), {}
    in_train = np.zeros(n, bool)
    in_train[tr] = True
    for si, s in enumerate(design.spaces):
        mine = [(k, kn) for k, kn in enumerate(design.kernels) if kn["space"] == si]
        S, st = _scale_pca(s["X"], tr, kc["pca_max_components"], kc["scale_clip"]) if any(kn["kind"] != "mmd" for _, kn in mine) else (None, None)
        for k, kn in mine:
            fitted = {}
            if kn["kind"] == "mmd":
                ts = s["tile_sets"][kn["tile_set"]]
                rows = np.flatnonzero(in_train[ts["owner"]])                      # the tiles of the training crops
                St, st_t = _scale_pca(ts["T"], rows, kc["pca_max_components"], kc["scale_clip"])
                if St is None:
                    continue
                D2 = _sqdist(St)
                m = kc["mmd"]["bandwidth_tiles"]
                sub = rows if len(rows) <= m else rows[np.sort(np.random.default_rng([int(cfg["seed"]), 13, len(rows)]).choice(len(rows), m, replace=False))]
                sigma = _median_distance(D2[np.ix_(sub, sub)])
                raw = ts["W"] @ np.exp(-D2 / (2.0 * sigma ** 2)) @ ts["W"].T      # mean over tile pairs: the MMD set kernel
                fitted = dict(st_t, sigma=sigma)
            elif S is None:
                continue
            elif kn["kind"] == "linear":
                raw, fitted = S @ S.T, dict(st)
            else:
                D2 = _sqdist(S)
                sigma = _median_distance(D2[np.ix_(tr, tr)])
                raw, fitted = np.exp(-D2 / (2.0 * sigma ** 2)), dict(st, sigma=sigma)
            K[k], valid[k], fin = _finish(raw, tr)
            if with_state and valid[k]:
                state[kn["name"]] = dict(fitted, **fin)
    return (K, valid, state) if with_state else (K, valid)


def _nnls_fallback(G, a, sweeps=500):
    """Coordinate descent for min v'Gv - 2a'v, v >= 0 (used only if scipy's nnls gives up)."""
    v = np.zeros(len(a))
    for _ in range(sweeps):
        for k in range(len(a)):
            if G[k, k] > 0:
                v[k] = max(0.0, v[k] + (a[k] - G[k] @ v) / G[k, k])
    return v


def alignf(G, a):
    """ALIGNF weights for each row of `a`: argmin_{v >= 0} v'Gv - 2a'v, scaled to sum 1.

    G[k, l] = <K_k, K_l> of the centred training kernels, a[r, k] = <K_k, target kernel of labelling r>.
    Returns (weights (R, m), fallback (R,)): fallback is True where no kernel aligned and equal weights were used.
    """
    R, m = a.shape
    mu, fallback = np.full((R, m), 1.0 / m), np.zeros(R, bool)
    if m == 1:
        fallback[:] = a[:, 0] <= 0
        return mu, fallback
    w, U = np.linalg.eigh(G)
    keep = w > 1e-10 * max(w[-1], 1e-300)
    root = np.sqrt(w[keep])
    A = root[:, None] * U[:, keep].T                          # A'A = G
    B = (U[:, keep] / root).T                                 # b = B a gives A'b = a
    for r in range(R):
        v = None
        if (a[r] > 0).any():
            try:
                v = nnls(A, B @ a[r])[0]
            except RuntimeError:
                v = _nnls_fallback(G, a[r])
        if v is None or not np.isfinite(v).all() or v.sum() <= 1e-12:
            fallback[r] = True
        else:
            mu[r] = v / v.sum()
    return mu, fallback


def _logistic(X, tr, ev, y_tr, n_classes, cfg):
    """L2 logistic regression on the in-fold robust scale + PCA of one family. Returns (n_eval, C) probabilities."""
    kc, lc = cfg["kernels"], cfg["baselines"]["single_family"]
    P = np.zeros((len(ev), n_classes))
    present = np.unique(y_tr)
    S, _ = _scale_pca(X, tr, kc["pca_max_components"], kc["scale_clip"])
    if S is None or len(present) < 2:
        P[:, present] = 1.0 / len(present)
        return P
    S = S / np.sqrt((S[tr] ** 2).sum(axis=1).mean())           # total training variance 1, so C means the same everywhere
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lr = LogisticRegression(C=float(lc["C"]), class_weight=lc["class_weight"], max_iter=5000, tol=1e-8).fit(S[tr], y_tr)
    P[:, lr.classes_] = lr.predict_proba(S[ev])
    return P


def fit_fold(design, train, Y, cfg, with_state=False):
    """Fit everything on the crops `train` and score every other crop.

    Y: (R, n) label codes; row 0 is the real labelling, the rest are permuted ones (null models only).
    Returns dict(eval, dist {model: (R or 1, n_eval, C) squared distances to the class means},
                 weights {model: (m,) for the real labels}, fallback {model: (R or 1,)}, logit {family: (n_eval, C)}).
    """
    n, C = design.n, len(design.classes)
    tr = np.asarray(train)
    in_train = np.zeros(n, bool)
    in_train[tr] = True
    ev = np.flatnonzero(~in_train)
    out = fit_kernels(design, tr, cfg, with_state)
    K, valid = out[0], out[1]
    res = dict(eval=ev, dist={}, weights={}, fallback={}, logit={})
    if with_state:
        res["state"], res["K"] = out[2], K
    for name, model in design.models.items():
        idx = [k for k in model["kernels"] if valid[k]]
        Ym = Y if model["null"] else Y[:1]
        R = len(Ym)
        onehot = (Ym[:, tr, None] == np.arange(C)).astype(float)                    # (R, n_train, C)
        counts = onehot.sum(axis=1)
        Yb = onehot / np.where(counts > 0, counts, 1.0)[:, None, :]                 # each class column sums to 1
        full = np.zeros(len(model["kernels"]))
        if not idx:                                                                 # no usable kernel: every class equally far
            res["dist"][name], res["weights"][name], res["fallback"][name] = np.zeros((R, len(ev), C)), full, np.ones(R, bool)
            continue
        Km = K[idx]
        if model["weights"] in ("alignf", "alignf_cross"):
            KTT = Km[:, tr][:, :, tr]
            target = np.einsum("ric,rjc->rij", Yb, Yb)                              # class-balanced target kernel
            if model["weights"] == "alignf_cross":                                  # sensitivity: only pairs of crops from different
                target = target - target.mean(axis=1, keepdims=True) - target.mean(axis=2, keepdims=True) + target.mean(axis=(1, 2), keepdims=True)
                cross_image = design.groups[tr][:, None] != design.groups[tr][None, :]    # training source images count
                KTT, target = KTT * cross_image, target * cross_image
            V = KTT.reshape(len(idx), -1)
            mu, fb = alignf(V @ V.T, target.reshape(R, -1) @ V.T)
        else:
            mu, fb = np.full((R, len(idx)), 1.0 / len(idx)), np.zeros(R, bool)
        Kc = (mu @ Km.reshape(len(idx), -1)).reshape(R, n, n)                       # combined kernel of each labelling
        kxx = Kc[:, ev, ev]
        cross = np.einsum("ret,rtc->rec", Kc[:, ev][:, :, tr], Yb)
        within = np.einsum("rtc,rts,rsc->rc", Yb, Kc[:, tr][:, :, tr], Yb)
        D = kxx[:, :, None] - 2.0 * cross + within[:, None, :]
        res["dist"][name] = np.where((counts == 0)[:, None, :], np.inf, D)          # a class with no training crop is never chosen
        full[[model["kernels"].index(k) for k in idx]] = mu[0]
        res["weights"][name], res["fallback"][name] = full, fb
    for fam in design.family_spaces:
        res["logit"][fam] = _logistic(design.family_matrix(fam), tr, ev, Y[0, tr], C, cfg)
    return res


_W = {}


def _init_worker(design, Y, cfg):
    _W.update(design=design, Y=Y, cfg=cfg)


def _job(job):
    train, mode = job
    return train, fit_fold(_W["design"], train, _W["Y"] if mode == "all" else _W["Y"][:1], _W["cfg"])


def run_fits(design, Y, cfg, jobs, workers=1, log=None):
    """{training set: fit result} for every job, in one process or in a spawn pool (the results do not depend on which)."""
    items = sorted(jobs.items())
    results, t0 = {}, time.time()
    if workers > 1 and len(items) > 1:
        with get_context("spawn").Pool(workers, initializer=_init_worker, initargs=(design, Y, cfg)) as pool:
            for i, (train, res) in enumerate(pool.imap(_job, items, chunksize=1), 1):
                results[train] = res
                if log and i % 50 == 0:
                    log(f"  fits {i}/{len(items)}  {time.time() - t0:.0f} s")
    else:
        from threadpoolctl import threadpool_limits
        _init_worker(design, Y, cfg)
        with threadpool_limits(limits=1):                    # one thread where the BLAS allows it (Accelerate ignores this)
            for i, item in enumerate(items, 1):
                results[item[0]] = _job(item)[1]
                if log and i % 50 == 0:
                    log(f"  fits {i}/{len(items)}  {time.time() - t0:.0f} s")
    return results


# ----------------------------------------------------------------------------------------------------
# labels under the two nulls
# ----------------------------------------------------------------------------------------------------
def null_a_labels(y, groups, n_classes, n_perm, rng):
    """Per source image, one random permutation of the class names: keeps which crops of an image agree."""
    out = np.empty((n_perm, len(y)), int)
    for r in range(n_perm):
        for g in sorted(set(groups)):
            idx = groups == g
            out[r, idx] = rng.permutation(n_classes)[y[idx]]
    return out


def null_b_labels(y, groups, n_perm, rng):
    """Labels shuffled between the crops of each mixed source image; single-batch images keep theirs.

    Returns (labellings, exact): every distinct arrangement (the real one included) when there are at most n_perm.
    """
    mixed = [g for g in sorted(set(groups)) if len(set(y[groups == g])) > 1]
    arrangements = [sorted(set(itertools.permutations(y[groups == g].tolist()))) for g in mixed]
    total = int(np.prod([len(a) for a in arrangements])) if mixed else 1
    if total <= n_perm:
        out = np.tile(y, (total, 1))
        for r, combo in enumerate(itertools.product(*arrangements)):
            for g, labels in zip(mixed, combo):
                out[r, groups == g] = labels
        return out, True
    out = np.tile(y, (n_perm, 1))
    for r in range(n_perm):
        for g in mixed:
            idx = np.flatnonzero(groups == g)
            out[r, idx] = y[rng.permutation(idx)]
    return out, False


# ----------------------------------------------------------------------------------------------------
# putting folds together
# ----------------------------------------------------------------------------------------------------
def _softmax(logits):
    logits = logits - logits.max(axis=-1, keepdims=True)
    e = np.exp(logits)
    return e / e.sum(axis=-1, keepdims=True)


def _floor(P, floor):
    P = np.clip(P, floor, 1.0)
    return P / P.sum(axis=-1, keepdims=True)


def _rows(res, table, rows, R):
    """Rows `rows` (crop indices) of one fit's (R_fit, n_eval, C) table, for the first R labellings."""
    pos = np.searchsorted(res["eval"], rows)
    assert np.array_equal(res["eval"][pos], rows), "a fold asked a fit for a crop it was trained on"
    return table[:R, pos]


def choose_tau(D, y, grid, floor):
    """Per labelling, the temperature with the lowest log-loss on the inner out-of-fold distances D (R, m, C)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        P = _softmax(-D[:, None, :, :] / grid[None, :, None, None])                 # (R, G, m, C)
    pt = np.take_along_axis(P, np.broadcast_to(y[:, None, :, None], P.shape[:3] + (1,)), axis=-1)[..., 0]
    loss = -np.log(np.clip(pt, floor, 1.0)).mean(axis=-1)                           # (R, G)
    return grid[np.argmin(loss, axis=1)]


def tau_grid(cfg):
    g = cfg["classifier"]["temperature"]["grid"]
    return np.logspace(g["log10_min"], g["log10_max"], int(g["n"]))


def compose_kernel(design, folds, results, model, Y, cfg):
    """Out-of-fold probabilities (R, n, C) and temperatures (R, n_folds) of one kernel model, for the labellings Y."""
    R, n, C = len(Y), design.n, len(design.classes)
    floor, grid = float(cfg["classifier"]["prob_floor"]), tau_grid(cfg)
    P, taus = np.full((R, n, C), np.nan), np.zeros((R, len(folds)))
    for f, fold in enumerate(folds):
        outer = results[fold["train"]]
        D_out = _rows(outer, outer["dist"][model], np.array(fold["test"]), R)
        if fold["inner"]:
            D_in = np.concatenate([_rows(results[i["train"]], results[i["train"]]["dist"][model], np.array(i["val"]), R)
                                   for i in fold["inner"]], axis=1)
            rows = np.concatenate([i["val"] for i in fold["inner"]])
            tau = choose_tau(D_in, Y[:, rows], grid, floor)
        else:
            tau = np.full(R, float(cfg["classifier"]["temperature"]["default"]))
        taus[:, f] = tau
        with np.errstate(invalid="ignore", divide="ignore"):
            P[:, fold["test"]] = _floor(_softmax(-D_out / tau[:, None, None]), floor)
    return P, taus


def compose_logistic(design, folds, results, y, cfg):
    """Out-of-fold probabilities of each single family, and of the family chosen per fold by the inner LOSO."""
    n, C = design.n, len(design.classes)
    floor = float(cfg["classifier"]["prob_floor"])
    fams = sorted(design.family_spaces)
    cands = [f for f in fams if f in design.family_candidates] or fams
    single = {f: np.full((n, C), np.nan) for f in fams}
    best, chosen = np.full((n, C), np.nan), []
    for fold in folds:
        outer, test = results[fold["train"]], np.array(fold["test"])
        for f in fams:
            single[f][test] = _floor(_rows(outer, outer["logit"][f][None], test, 1)[0], floor)
        if not fams:
            continue
        score = {}
        if fold["inner"]:
            rows = np.concatenate([i["val"] for i in fold["inner"]])
            for f in cands:
                Pin = _floor(np.concatenate([_rows(results[i["train"]], results[i["train"]]["logit"][f][None], np.array(i["val"]), 1)[0]
                                             for i in fold["inner"]]), floor)
                m = metrics(Pin, y[rows], C)
                score[f] = (-m["ba"], m["logloss"], f)
        pick = min(score.values())[2] if score else cands[0]
        chosen.append(pick)
        best[test] = single[pick][test]
    return single, best, chosen


def majority_probs(design, folds, y):
    P = np.full((design.n, len(design.classes)), np.nan)
    for fold in folds:
        P[list(fold["test"])] = np.bincount(y[list(fold["train"])], minlength=len(design.classes)) / len(fold["train"])
    return P


def oracle_probs(design, folds, y, pseudo):
    """Provenance oracle: the labels of the training crops that share the test crop's source image (LOCO-nbr only)."""
    C = len(design.classes)
    P = np.full((design.n, C), np.nan)
    for fold in folds:
        tr = np.array(fold["train"])
        prior = np.bincount(y[tr], minlength=C) / len(tr)
        for i in fold["test"]:
            same = tr[design.groups[tr] == design.groups[i]]
            P[i] = (np.bincount(y[same], minlength=C) + pseudo * prior) / (len(same) + pseudo)
    return P


# ----------------------------------------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------------------------------------
def _weighted(P, y, W, C):
    """Balanced accuracy, macro one-vs-rest AUC and log-loss for each row of crop weights W (B, n)."""
    pred = P.argmax(axis=1)
    correct = (pred == y).astype(float)
    recalls, aucs = [], []
    with np.errstate(invalid="ignore", divide="ignore"):
        for c in range(C):
            pos, neg = y == c, y != c
            recalls.append((W[:, pos] @ correct[pos]) / W[:, pos].sum(axis=1))
            H = (P[pos, c][:, None] > P[neg, c][None, :]) + 0.5 * (P[pos, c][:, None] == P[neg, c][None, :])
            aucs.append(np.einsum("bi,ij,bj->b", W[:, pos], H, W[:, neg]) / (W[:, pos].sum(axis=1) * W[:, neg].sum(axis=1)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ba, auc = np.nanmean(recalls, axis=0), np.nanmean(aucs, axis=0)
        loss = (W @ -np.log(P[np.arange(len(y)), y])) / W.sum(axis=1)
    return ba, auc, loss


def metrics(P, y, C):
    ba, auc, loss = _weighted(P, y, np.ones((1, len(y))), C)
    pred = P.argmax(axis=1)
    conf = np.zeros((C, C), int)
    np.add.at(conf, (y, pred), 1)
    return dict(ba=float(ba[0]), auc=float(auc[0]), logloss=float(loss[0]), n_correct=int((pred == y).sum()), confusion=conf.tolist())


def balanced_accuracy_many(P, Y):
    """Balanced accuracy of each labelling r: P (R, n, C) against Y (R, n); classes absent from a labelling are skipped."""
    pred = P.argmax(axis=2)
    C = P.shape[2]
    onehot = Y[:, :, None] == np.arange(C)
    hit = ((pred == Y)[:, :, None] & onehot).sum(axis=1)
    tot = onehot.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        rec = np.where(tot > 0, hit / tot, np.nan)
    return np.nanmean(rec, axis=1)


def bootstrap_weights(groups, n_boot, rng):
    """Crop multiplicities (n_boot, n) of resampling whole source images with replacement."""
    uniq = sorted(set(groups))
    draws = rng.integers(0, len(uniq), size=(n_boot, len(uniq)))
    mult = np.zeros((n_boot, len(uniq)))
    np.add.at(mult, (np.arange(n_boot)[:, None], draws), 1.0)
    return mult[:, [uniq.index(g) for g in groups]]


def _ci(x):
    return [float(v) for v in np.nanpercentile(x, [2.5, 97.5])] if len(x) else [np.nan, np.nan]


def score(P, y, C, W):
    """Point estimates and image-bootstrap intervals; also returns the balanced accuracy of every resample (for paired differences)."""
    out = metrics(P, y, C)
    ba, auc, loss = _weighted(P, y, W, C)
    out.update(ba_ci=_ci(ba), auc_ci=_ci(auc), logloss_ci=_ci(loss))
    return out, ba


def paired_delta(ba_boot, ref_boot, ba, ref):
    d = ba_boot - ref_boot
    return dict(delta=float(ba - ref), ci=_ci(d), share_of_resamples_at_or_below_0=float(np.mean(d <= 0)) if len(d) else np.nan)


# ----------------------------------------------------------------------------------------------------
# the run
# ----------------------------------------------------------------------------------------------------
def run(design, cfg, n_boot=None, n_null_a=None, n_null_b=None, workers=1, log=None):
    """Score every model and baseline under both splits. Returns (results dict, out-of-fold table)."""
    st = cfg["statistics"]
    n_boot = st["bootstrap"]["resamples"] if n_boot is None else n_boot
    n_null_a = st["null_a"]["permutations"] if n_null_a is None else n_null_a
    n_null_b = st["null_b"]["permutations"] if n_null_b is None else n_null_b
    seed, y, groups, C = int(cfg["seed"]), design.y, design.groups, len(design.classes)
    splits = make_splits(groups, design.neighbours)
    ya = null_a_labels(y, groups, C, n_null_a, np.random.default_rng([seed, 1]))
    yb, exact_b = null_b_labels(y, groups, n_null_b, np.random.default_rng([seed, 2])) if n_null_b else (np.empty((0, len(y)), int), False)
    Y = np.concatenate([y[None], ya, yb])
    sl_a, sl_b = slice(1, 1 + len(ya)), slice(1 + len(ya), len(Y))
    jobs = fit_jobs(splits)
    if log:
        log(f"{design.n} crops, {len(design.spaces)} spaces, {len(design.kernels)} kernels, {len(design.models)} kernel models, "
            f"{len(design.family_spaces)} families; {len(jobs)} fits ({sum(m == 'all' for m in jobs.values())} with {len(Y)} labellings)")
    results = run_fits(design, Y, cfg, jobs, workers, log)
    W = bootstrap_weights(list(groups), n_boot, np.random.default_rng([seed, 3]))
    mixed_images = [g for g in sorted(set(groups)) if len(set(y[groups == g])) > 1]
    in_mixed = np.isin(groups, mixed_images)
    kernel_names = [k["name"] for k in design.kernels]
    out = dict(
        meta=dict(n_crops=design.n, classes=design.classes, class_counts=np.bincount(y, minlength=C).tolist(),
                  n_source_images=len(set(groups)), mixed_source_images=mixed_images, n_bootstrap=n_boot, n_null_a=len(ya),
                  n_null_b=len(yb), null_b_exact=bool(exact_b), seed=seed, n_fits=len(jobs), notes=design.notes),
        config=cfg,
        spaces=[{k: s[k] for k in ("key", "family", "detector", "view", "tag", "n_columns", "tile_dims", "pooled", "legacy")} for s in design.spaces],
        kernels=kernel_names,
        models={name: dict(role=m["role"], weights=m["weights"], n_kernels=len(m["kernels"]),
                           spaces=sorted({design.spaces[design.kernels[k]["space"]]["key"] for k in m["kernels"]}),
                           n_columns=int(sum(design.spaces[s]["n_columns"] for s in {design.kernels[k]["space"] for k in m["kernels"]})),
                           **({"family": m["family"]} if "family" in m else {})) for name, m in design.models.items()},
        families={f: dict(n_columns=design.family_columns(f)) for f in sorted(design.family_spaces)},
        splits={}, results={})
    oof = []
    for split in SPLITS:
        folds = splits[split]
        reports = [fold_report(f, y, groups, design.crops, design.classes) for f in folds]
        out["splits"][split] = dict(n_folds=len(folds), unlearnable=[r for r in reports if r["unlearnable"]], folds=reports)
        fold_of = np.empty(design.n, object)
        for f, r in zip(folds, reports):
            fold_of[list(f["test"])] = r["fold"]
        rows, boots, probs = {}, {}, {}
        for name, model in design.models.items():
            use_null = split == "loso13" and model["null"]
            P, taus = compose_kernel(design, folds, results, name, Y if use_null else Y[:1], cfg)
            row, boots[name] = score(P[0], y, C, W)
            wts = np.array([results[f["train"]]["weights"][name] for f in folds])
            fam_of = [design.spaces[design.kernels[k]["space"]]["family"] for k in model["kernels"]]
            by_fam = {fm: wts[:, [j for j, v in enumerate(fam_of) if v == fm]].sum(axis=1) for fm in sorted(set(fam_of))}
            row.update(kind="kernel_ncm", weights=model["weights"], tau=taus[0].tolist(),
                       alignf_fallback_folds=int(sum(bool(results[f["train"]]["fallback"][name][0]) for f in folds)),
                       kernel_weights={kernel_names[k]: dict(mean=float(wts[:, j].mean()), sd=float(wts[:, j].std()))
                                       for j, k in enumerate(model["kernels"])},
                       family_weights={fm: dict(mean=float(v.mean()), sd=float(v.std())) for fm, v in by_fam.items()})
            if use_null:
                ba_all = balanced_accuracy_many(P, Y)
                obs, na, nb = ba_all[0], ba_all[sl_a], ba_all[sl_b]
                if len(na):
                    row["null_a"] = dict(n=len(na), p=float((1 + (na >= obs - 1e-12).sum()) / (1 + len(na))), mean=float(na.mean()),
                                         sd=float(na.std()), q95=float(np.percentile(na, 95)), ba=na.tolist())
                if len(nb):
                    acc = ((P.argmax(axis=2) == Y) & in_mixed).sum(axis=1) / max(int(in_mixed.sum()), 1)
                    am = acc[sl_b]
                    p = (lambda null, o: float((null >= o - 1e-12).mean()) if exact_b else float((1 + (null >= o - 1e-12).sum()) / (1 + len(null))))
                    row["null_b"] = dict(n=len(nb), exact=bool(exact_b), p=p(nb, obs), mean=float(nb.mean()), sd=float(nb.std()),
                                         q95=float(np.percentile(nb, 95)), mixed_accuracy=float(acc[0]), p_mixed_accuracy=p(am, acc[0]),
                                         mixed_accuracy_null_mean=float(am.mean()), ba=nb.tolist())
            rows[name], probs[name] = row, (P[0], taus[0])
        single, best, chosen = compose_logistic(design, folds, results, y, cfg)
        for f, P in single.items():
            rows[f"family:{f}"], boots[f"family:{f}"] = score(P, y, C, W)
            rows[f"family:{f}"].update(kind="l2_logistic", n_columns=design.family_columns(f))
            probs[f"family:{f}"] = (P, None)
        if single:
            rows["best_single_family"], boots["best_single_family"] = score(best, y, C, W)
            rows["best_single_family"].update(kind="l2_logistic", chosen={f: chosen.count(f) for f in sorted(set(chosen))},
                                              candidates=sorted(design.family_candidates))
            probs["best_single_family"] = (best, None)
        Pm = _floor(majority_probs(design, folds, y), float(cfg["classifier"]["prob_floor"]))
        rows["majority"], boots["majority"] = score(Pm, y, C, W)
        rows["majority"]["kind"] = "prior"
        probs["majority"] = (Pm, None)
        if split == "loco_nbr":
            Po = _floor(oracle_probs(design, folds, y, float(cfg["baselines"]["provenance_oracle"]["pseudo_count"])),
                        float(cfg["classifier"]["prob_floor"]))
            rows["provenance_oracle"], boots["provenance_oracle"] = score(Po, y, C, W)
            rows["provenance_oracle"]["kind"] = "oracle"
            probs["provenance_oracle"] = (Po, None)
        if "acquisition" in rows:
            for name in rows:
                if name != "acquisition":
                    rows[name]["delta_ba_vs_acquisition"] = paired_delta(boots[name], boots["acquisition"], rows[name]["ba"], rows["acquisition"]["ba"])
        out["results"][split] = rows
        for name, (P, taus) in probs.items():
            tau_of = {r["fold"]: t for r, t in zip(reports, taus)} if taus is not None else {}
            for i, crop in enumerate(design.crops):
                oof.append(dict(split=split, model=name, crop=crop, label=design.classes[y[i]], source_image=groups[i], fold=fold_of[i],
                                **{f"p_{c}": P[i, j] for j, c in enumerate(design.classes)}, pred=design.classes[int(P[i].argmax())],
                                correct=bool(P[i].argmax() == y[i]), tau=tau_of.get(fold_of[i], np.nan)))
    out["blind_model"] = blind_rule(out, cfg)
    return _clean(out), pd.DataFrame(oof)


def blind_rule(out, cfg):
    """config/primary.yaml blind_model: the higher balanced accuracy of A and B, B when within the margin."""
    bm = cfg["blind_model"]
    split = "loco_nbr" if bm["blind_crops_share_source_images"] else bm["split"]
    rows = out["results"][split]
    if "A" not in rows or "B" not in rows:
        only = [m for m in ("A", "B") if m in rows]
        return dict(split=split, chosen=only[0] if only else None, reason="only one of A and B could be scored")
    a, b = rows["A"], rows["B"]
    gap = abs(a["n_correct"] - b["n_correct"])
    if gap <= bm["tie_margin_crops"]:
        chosen, reason = bm["tie_winner"], f"A and B differ by {gap} correctly classified crop(s), within the margin of {bm['tie_margin_crops']}"
    else:
        chosen = "A" if a["ba"] > b["ba"] else "B"
        reason = f"higher balanced accuracy ({gap} crops apart)"
    return dict(split=split, chosen=chosen, reason=reason, ba_A=a["ba"], ba_B=b["ba"], n_correct_A=a["n_correct"], n_correct_B=b["n_correct"])


def _clean(x):
    """JSON-ready: plain types, floats rounded to 10 significant digits (below 1e-12 in size: 0), NaN as null."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return _clean(x.tolist())
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else 0.0 if abs(x) < 1e-12 else float(f"{float(x):.10g}")
    return x


# ----------------------------------------------------------------------------------------------------
# the report: built from the JSON and nothing else
# ----------------------------------------------------------------------------------------------------
def _cell(text):
    """A name with | in it, safe inside a Markdown table."""
    return "`" + str(text).replace("|", "\\|") + "`"


def _fmt(v, ci=None, digits=3):
    if v is None:
        return "–"
    s = f"{v:.{digits}f}"
    return s + (f" [{ci[0]:.{digits}f}, {ci[1]:.{digits}f}]" if ci and ci[0] is not None else "")


def render(res):
    """results.md from the harness JSON."""
    meta, loso, loco = res["meta"], res["results"]["loso13"], res["results"]["loco_nbr"]
    order = [m for m in ("A", "B") if m in loso] + [m for m in ("majority", "acquisition", "best_single_family", "uniform_A", "uniform_B",
                                                              "dinov2s_legacy", "provenance_oracle", "cross_A", "cross_B") if m in loso or m in loco]
    order += sorted(m for m in loso if m.startswith("family:"))
    label = {"A": "**Model A** (all non-leakrisk spaces)", "B": "**Model B** (no imaging, no leakrisk)", "majority": "majority class",
             "acquisition": f"acquisition only ({res['models'].get('acquisition', {}).get('family', '?')})",
             "best_single_family": "best single family (inner-chosen)", "uniform_A": "uniform kernel sum, A's kernels",
             "uniform_B": "uniform kernel sum, B's kernels", "dinov2s_legacy": "old DINOv2-S", "provenance_oracle": "provenance oracle (LOCO-nbr only)",
             "cross_A": "sensitivity: A with cross-image ALIGNF", "cross_B": "sensitivity: B with cross-image ALIGNF"}
    L = ["# Harness results", "",
         f"{meta['n_crops']} crops ({', '.join(f'{c} {n}' for c, n in zip(meta['classes'], meta['class_counts']))}), "
         f"{meta['n_source_images']} source images. Chance balanced accuracy = {1 / len(meta['classes']):.3f}. "
         f"Intervals: {meta['n_bootstrap']} bootstrap resamples of source images (percentile 95 %). "
         f"Null A: {meta['n_null_a']} per-image relabellings. Null B: {meta['n_null_b']} "
         f"{'arrangements (exact)' if meta['null_b_exact'] else 'shuffles'} inside the mixed images. Both nulls refit the weights and the temperature.", "",
         "| Row | Columns | LOSO-13 BA [95 % CI] | ΔBA vs acquisition [95 % CI] | Macro AUC | Log-loss | Null A p | Null B p | LOCO-nbr BA [95 % CI] |",
         "|---|---|---|---|---|---|---|---|---|"]
    for m in order:
        a, b = loso.get(m), loco.get(m)
        cols = res["models"][m]["n_columns"] if m in res["models"] else (res["families"][m[7:]]["n_columns"] if m.startswith("family:") else "–")
        d = (a or {}).get("delta_ba_vs_acquisition")
        L.append(f"| {label.get(m, 'single family: ' + m[7:] if m.startswith('family:') else m)} | {cols} | "
                 f"{_fmt(a['ba'], a['ba_ci']) if a else '–'} | {_fmt(d['delta'], d['ci']) if d else '–'} | {_fmt(a['auc']) if a else '–'} | "
                 f"{_fmt(a['logloss']) if a else '–'} | {_fmt(a['null_a']['p']) if a and 'null_a' in a else '–'} | "
                 f"{_fmt(a['null_b']['p']) if a and 'null_b' in a else '–'} | {_fmt(b['ba'], b['ba_ci']) if b else '–'} |")
    L += ["", "Kernel rows use the kernel nearest-class-mean classifier; single-family rows use L2 logistic regression on the in-fold PCA.",
          "ΔBA is paired: the same image resamples are used for the row and for the acquisition-only baseline.", ""]
    bm = res["blind_model"]
    L += ["## Blind-test model", "", f"Rule (config/primary.yaml), read on {bm['split']}: **{bm['chosen']}**. {bm['reason']}."
          + (f" A: {bm['n_correct_A']} crops correct (BA {bm['ba_A']:.3f}); B: {bm['n_correct_B']} (BA {bm['ba_B']:.3f})." if "ba_A" in bm else ""), ""]
    for m in ("A", "B", "acquisition"):
        if m in loso:
            r = loso[m]
            L += [f"## {m}: nulls and confusion (LOSO-13)", "", f"- Balanced accuracy {r['ba']:.3f}; {r['n_correct']} of {meta['n_crops']} crops correct."]
            if "null_a" in r:
                L.append(f"- Null A: mean {r['null_a']['mean']:.3f}, SD {r['null_a']['sd']:.3f}, 95th percentile {r['null_a']['q95']:.3f}, p = {r['null_a']['p']:.3f}.")
            if "null_b" in r:
                nb = r["null_b"]
                L.append(f"- Null B: mean {nb['mean']:.3f}, 95th percentile {nb['q95']:.3f}, p = {nb['p']:.3f}; accuracy on the mixed-image crops "
                         f"{nb['mixed_accuracy']:.3f} against a null mean of {nb['mixed_accuracy_null_mean']:.3f}, p = {nb['p_mixed_accuracy']:.3f}.")
            L += ["", "| true \\ predicted | " + " | ".join(meta["classes"]) + " |", "|---|" + "---|" * len(meta["classes"])]
            L += [f"| {c} | " + " | ".join(str(v) for v in row) + " |" for c, row in zip(meta["classes"], r["confusion"])]
            L.append("")
    for m in ("A", "B"):
        if m in loso:
            L += [f"## {m}: ALIGNF weights over the LOSO-13 folds", "", "| Family | Weight, mean ± SD |", "|---|---|"]
            L += [f"| {f} | {w['mean']:.3f} ± {w['sd']:.3f} |" for f, w in sorted(loso[m]["family_weights"].items(), key=lambda kv: -kv[1]["mean"])]
            top = sorted(loso[m]["kernel_weights"].items(), key=lambda kv: -kv[1]["mean"])[:12]
            L += ["", "| Kernel (top 12) | Weight, mean ± SD |", "|---|---|"] + [f"| {_cell(k)} | {w['mean']:.3f} ± {w['sd']:.3f} |" for k, w in top if w["mean"] > 0]
            L.append("")
    L += ["## Folds that cannot be learned", ""]
    for split in SPLITS:
        bad = res["splits"][split]["unlearnable"]
        L.append(f"- {split}: {len(bad)} of {res['splits'][split]['n_folds']} folds." + "".join(f"\n  - {b['fold']}: {'; '.join(b['reasons'])}" for b in bad))
    L += ["", "## What was scored", "", f"{len(res['spaces'])} spaces, {len(res['kernels'])} kernels.", "", "| Space | Tag | Columns | Tile arrays (width) |", "|---|---|---|---|"]
    L += [f"| {_cell(s['key'])} | {s['tag']} | {s['n_columns']}{' (tile means)' if s['pooled'] else ''} | {', '.join(map(str, s['tile_dims'])) or '–'} |" for s in res["spaces"]]
    if res.get("bank"):
        fams = res["bank"]["families"]
        L += ["", "## Bank on disk", "", "| Family | Crops done | In the harness |", "|---|---|---|"]
        L += [f"| {f} | {v['n_done']}/{v['n_expected']} | {'yes' if v['complete'] else 'no (incomplete)'} |" for f, v in fams.items()]
        if res["bank"]["missing"]:
            L += ["", "Gaps:", ""] + [f"- {k.replace('|', '/')} ({v['n']})" for k, v in res["bank"]["missing"].items()]
    if meta["notes"]:
        L += ["", "Notes: " + "; ".join(meta["notes"]) + "."]
    return "\n".join(L) + "\n"


def write(out_dir, res, oof, info=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "harness.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    (out_dir / "results.md").write_text(render(json.loads((out_dir / "harness.json").read_text())))     # from the file, nothing else
    oof.to_csv(out_dir / "oof_predictions.csv", index=False, float_format="%.10g")
    if info is not None:
        (out_dir / "run_info.json").write_text(json.dumps(info, indent=1) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="directory for harness.json, results.md and oof_predictions.csv")
    p.add_argument("--quick", action="store_true", help="100 permutations per null and 200 bootstrap resamples")
    p.add_argument("--workers", type=int, default=5, help="processes, one BLAS thread each (default 5)")
    p.add_argument("--config", default=str(CONFIG))
    p.add_argument("--skip", default="", help="comma list of families to leave out (for example one that is half written)")
    a = p.parse_args(argv)
    cfg = load_config(a.config)
    q = cfg["statistics"]["quick"] if a.quick else {}
    t0 = time.time()
    design, bank = design_from_bank(cfg, skip=tuple(f for f in a.skip.split(",") if f))
    res, oof = run(design, cfg, q.get("bootstrap"), q.get("null_a"), q.get("null_b"), workers=max(1, a.workers), log=print)
    res["bank"] = _clean(bank.summary())
    res["meta"]["quick"] = bool(a.quick)
    import scipy
    import sklearn
    info = dict(seconds=round(time.time() - t0, 1), finished=time.strftime("%Y-%m-%dT%H:%M:%S"), workers=a.workers, argv=sys.argv[1:],
                numpy=np.__version__, scipy=scipy.__version__, sklearn=sklearn.__version__, python=sys.version.split()[0])
    write(a.out, res, oof, info)
    print(render(res).split("## What was scored")[0])
    print(f"wrote {a.out}/harness.json, results.md, oof_predictions.csv in {info['seconds']} s")


if __name__ == "__main__":
    main()
