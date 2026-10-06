"""Label-free structure of every feature space (step 10 of the brief). Diagnostics only: nothing here may feed a model.

    python -m bank.labelfree --out results/v1/labelfree                 # P0, every family on disk
    python -m bank.labelfree --out /tmp/lf --families phase,psd --n-perm 200

A space is one family x detector x view x scale x layer (every catalog row with those five values), plus one pooled
space per family (`family|*|*|*|*`, SE left out). For each space, on the crops that are done:

    1. distances   every feature is standardised over the crops, every block (the scalars together, each array) gets
                   the same weight, and the crop x crop Euclidean distance matrix is built (31 x 31 when all are done).
                   Tile arrays enter as their mean over tiles.
    2. clusters    k = 3 by spectral clustering (RBF affinity, bandwidth = the median distance) and by agglomerative
                   clustering (Ward). Each partition is scored by the adjusted Rand index (ARI) against the folder
                   label and against the source image. `ari_source_agglo_k13` cuts the same tree at one cluster per
                   source image, because 3 clusters can never match 13 images.
    3. fixed point the share of crops whose nearest folder centroid is their own folder's. If the folders were cut as
                   clusters in this space, the folder labelling is a fixed point of the k-means step and the share is 1.
                   With many dimensions the share is high for ANY labelling (a crop pulls its own centroid), so read
                   it against its null mean, never alone. `fixed_point_converged` runs the k-means step to the end.
                   `fixed_point_of_spectral` / `_of_agglo` ask the same of the clusters found without any label: the
                   share of crops nearest to their own cluster's centroid (how k-means-like the partition is).
    4. nulls       the same statistics under relabelled crops:
                     image   the three folder names are permuted at random inside each source image (the brief's
                             Null A). It keeps which crops of an image share a label, so it respects the 13 groups.
                     crop    folder labels shuffled over the crops (ignores the groups; shown for comparison).
                     source  source images shuffled over the crops (for the ARI against the source image).
                   p = share of relabellings at least as large. p_max = the same against the largest value over ALL
                   spaces per relabelling (the max-statistic null), which corrects for having looked at every space.
                   p_max_z does it on z = (value - null mean) / null SD, so that spaces with a wide null do not hide
                   the others; for the fixed-point share only p_max_z means anything.

Then marginal means of the statistics by family, detector, view, scale, layer and tag (pooled spaces left out;
leakrisk spaces, i.e. anything from SE, count only in the detector and tag tables).

Unit = crop, groups = the 13 source images. The folder label and the source image are read from meta/crops.csv to
score and to build nulls; they never become a feature, and no output of this file is read by the harness.

Writes <out>/labelfree.json, then <out>/labelfree.md and <out>/labelfree_spaces.csv, both built from that JSON.
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from sklearn.cluster import KMeans

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bank import core   # noqa: E402

K = 3
SPACE_PARTS = ["detector", "view", "scale_nm", "layer"]
SOURCE_STATS = ("ari_source_spectral", "ari_source_agglo", "ari_source_agglo_k13")
# statistics that share one max-statistic null: the largest value over every space AND every statistic of the group
MAX_GROUPS = {"ari_folder": ("ari_folder_spectral", "ari_folder_agglo"), "fixed_point": ("fixed_point",),
              "ari_source": ("ari_source_spectral", "ari_source_agglo"), "ari_source_k13": ("ari_source_agglo_k13",)}
NULLS = {"image": "the three folder names permuted at random inside each source image (respects the 13 groups)",
         "crop": "folder labels shuffled over the crops (ignores the groups)",
         "source": "source images shuffled over the crops"}
MARGINALS = ("family", "detector", "view", "scale_nm", "layer", "tag")
MIN_CROPS = 2 * K               # fewer crops than this cannot be cut into K clusters in any useful way
MAX_TILE_WIDTH = 4096           # wider per-tile arrays are saved token grids: not pooled, as in bank.assemble
MEAN_COLUMNS = ("ari_folder_spectral", "ari_folder_agglo", "ari_source_spectral", "ari_source_agglo", "ari_source_agglo_k13",
                "fixed_point", "fixed_point_excess_image")


# ----------------------------------------------------------------------------------------------------
# loading: one family at a time, so the arrays of one family never sit in memory with those of the others
# ----------------------------------------------------------------------------------------------------
def _from_assemble(name, crops, pert):
    """One family through bank.assemble.load_bank (the harness lane's loader)."""
    from bank import assemble
    bank = assemble.load_bank(perts=(pert,), families=[name])
    if name not in bank.families or tuple(bank.crops) != tuple(crops):
        return None
    fam = bank.families[name]
    done = np.asarray(fam.done.get(pert, np.zeros(len(crops), bool)), bool)
    scalars = pd.DataFrame(index=list(crops))
    if len(fam.scalars) and pert in fam.scalars.index.get_level_values(0):
        scalars = fam.scalars.xs(pert, level=0).reindex(list(crops))
    arrays = {k: np.asarray(v, float) for k, v in fam.blocks.get(pert, {}).items()}
    for k, per_crop in fam.tiles.get(pert, {}).items():
        widths = {t.shape[1] for t in per_crop if t is not None}
        if len(widths) == 1:
            d = widths.pop()
            arrays[k] = np.stack([np.full(d, np.nan) if t is None else t.mean(axis=0, dtype=np.float64) for t in per_crop])
    return dict(catalog=fam.catalog, scalars=scalars, arrays=arrays, done=done)


def _from_core(name, crops, pert):
    """One family through bank.core alone, one crop in memory at a time (when bank/assemble.py is missing or fails)."""
    catalog = core.load_catalog(name).drop_duplicates("name").reset_index(drop=True)
    kind = dict(zip(catalog.name, catalog.kind))
    done = np.array([core.is_done(name, c, pert) for c in crops])
    scalars = pd.DataFrame(index=list(crops))
    table = core.load_scalars(name, perts=(pert,), crops=[c for c, d in zip(crops, done) if d])
    if len(table) and table.shape[1]:
        scalars = table.set_axis([c for _, c in table.index]).reindex(list(crops))
    per = {}
    for i, c in enumerate(crops):
        if done[i]:
            for k, a in core.load_arrays(name, c, pert).items():
                if k in kind and not (kind[k] == "tiles" and a.shape[-1] > MAX_TILE_WIDTH):
                    per.setdefault(k, {})[i] = a.mean(axis=0, dtype=np.float64) if kind[k] == "tiles" else np.asarray(a, float).ravel()
    arrays = {}
    for k, rows in per.items():
        if len({v.size for v in rows.values()}) == 1:
            m = np.full((len(crops), next(iter(rows.values())).size), np.nan)
            for i, v in rows.items():
                m[i] = v
            arrays[k] = m
    return dict(catalog=catalog, scalars=scalars, arrays=arrays, done=done)


def load_families(pert=core.P0, only=None):
    """-> (crop ids, {family: dict(catalog, scalars, arrays, done)}, notes). Rows follow meta/crops.csv."""
    crops = list(core.all_crops())
    names = sorted(p.name for p in core.FEAT_DIR.iterdir() if p.is_dir()) if core.FEAT_DIR.exists() else []
    notes = []
    try:
        from bank import assemble
        names += [n for n in getattr(assemble, "LEGACY_FAMILIES", ()) if n not in names]
        loader = "bank.assemble.load_bank"
    except Exception as e:                                           # not written yet, or half-way through an edit
        assemble = None
        loader = "bank.core"
        notes.append(f"bank.assemble did not import ({type(e).__name__}): families were read with bank.core")
    if only is not None:
        notes += [f"{n}: asked for, but nothing is on disk" for n in only if n not in names]
        names = [n for n in names if n in only]
    out = {}
    for name in names:
        fam = None
        if assemble is not None:
            try:
                fam = _from_assemble(name, crops, pert)
            except Exception as e:
                notes.append(f"{name}: bank.assemble failed ({type(e).__name__}: {e}); read with bank.core")
        if fam is None:
            try:
                fam = _from_core(name, crops, pert)
            except Exception as e:
                notes.append(f"{name}: not readable ({type(e).__name__}: {e})")
                continue
        out[name] = fam
    return crops, out, dict(loader=loader, notes=notes)


# ----------------------------------------------------------------------------------------------------
# spaces and distances
# ----------------------------------------------------------------------------------------------------
def build_spaces(families, min_crops):
    """Cut every family into spaces. -> (spaces, skipped). A space holds the crop positions it covers (`rows`) and its
    blocks (`items`): one matrix of scalars, and one matrix per array, each (len(rows), d)."""
    spaces, skipped = [], []
    min_crops = max(int(min_crops), MIN_CROPS)
    for name in sorted(families):
        fam = families[name]
        cat = fam["catalog"].copy()
        cat["tag"] = np.where(cat.detector.isin(core.LEAKRISK_DETECTORS), "leakrisk", cat.tag)
        cat["layer"] = cat.layer.fillna("").astype(str)
        groups = [(key, part) for key, part in cat.groupby(SPACE_PARTS, sort=True)]
        pooled = cat[cat.tag != "leakrisk"]
        if len(pooled):
            groups.append((("*", "*", "*", "*"), pooled))
        for (det, view, scale, layer), part in groups:
            level = "family" if det == "*" else "space"
            key = "|".join([name, str(det), str(view), str(scale), str(layer) or "-"])
            names = [n for n in part.name[part.kind == "scalar"] if n in fam["scalars"].columns]
            items = [fam["scalars"][names].to_numpy(float)] if names else []
            arrays = [n for n in part.name[part.kind != "scalar"] if n in fam["arrays"]]
            items += [fam["arrays"][n] for n in arrays]
            if not items:
                skipped.append(dict(space=key, reason="nothing readable stored for it (saved token grids are not read)"))
                continue
            usable = fam["done"] & np.all([np.isfinite(m).all(axis=1) for m in items], axis=0)
            if usable.sum() < min_crops:
                skipped.append(dict(space=key, reason=f"{int(usable.sum())} crops done and finite, {min_crops} needed"))
                continue
            tags = part.tag.value_counts().to_dict()
            spaces.append(dict(space=key, level=level, family=name, detector=str(det), view=str(view), scale_nm=str(scale),
                               layer=str(layer) or "-", tag=next(iter(tags)) if len(tags) == 1 else "several",
                               tags={str(k): int(v) for k, v in tags.items()}, n_scalars=len(names), n_arrays=len(arrays),
                               rows=np.flatnonzero(usable), items=[m[usable] for m in items]))
    return spaces, skipped


def distance_matrix(items, balance=True):
    """(D, dimensions kept): Euclidean distances between crops on standardised features.

    Each column is z-scored over the crops; constant columns are dropped. With `balance`, each block is divided by the
    square root of its width, so a 1000-number embedding and 5 scalars in one space count the same."""
    parts, kept = [], 0
    for m in items:
        m = np.asarray(m, float)
        m = m[:, None] if m.ndim == 1 else m
        sd = m.std(axis=0)
        good = sd > 1e-12 * np.maximum(1.0, np.abs(m).max(axis=0))
        if good.any():
            z = (m[:, good] - m[:, good].mean(axis=0)) / sd[good]
            parts.append(z / np.sqrt(z.shape[1]) if balance else z)
            kept += z.shape[1]
    if not parts:
        return None, 0
    z = np.hstack(parts)
    if not balance:
        z = z / np.sqrt(z.shape[1])
    gram = z @ z.T
    sq = np.diag(gram)
    d2 = np.maximum(sq[:, None] + sq[None, :] - 2 * gram, 0.0)
    d2 = (d2 + d2.T) / 2
    np.fill_diagonal(d2, 0.0)
    return np.sqrt(d2), kept


# ----------------------------------------------------------------------------------------------------
# clustering and the statistics, all from the distance matrix
# ----------------------------------------------------------------------------------------------------
def spectral_labels(dist, k=K, seed=0):
    """Ng-Jordan-Weiss spectral clustering on an RBF affinity whose bandwidth is the median distance."""
    n = len(dist)
    sigma = float(np.median(dist[np.triu_indices(n, 1)]))
    if not sigma > 0:
        return np.zeros(n, int)
    affinity = np.exp(-0.5 * (dist / sigma) ** 2)
    np.fill_diagonal(affinity, 0.0)
    degree = affinity.sum(axis=1)
    lap = affinity / np.sqrt(np.outer(degree, degree))
    _, vectors = np.linalg.eigh((lap + lap.T) / 2)
    v = vectors[:, -k:]
    v = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(v)


def agglomerative_labels(dist, k=K, method="ward"):
    tree = linkage(squareform(dist, checks=False), method=method)
    return fcluster(tree, k, criterion="maxclust") - 1


def _onehot(labels, k):
    return np.eye(k)[np.asarray(labels)]


def ari(cluster_onehot, label_onehot):
    """Adjusted Rand index of one partition (n, a) against one or many labellings (..., n, b), both one-hot."""
    table = np.einsum("na,...nb->...ab", cluster_onehot, label_onehot)
    pairs = lambda x: x * (x - 1) / 2   # noqa: E731
    both = pairs(table).sum(axis=(-1, -2))
    a, b = pairs(table.sum(axis=-1)).sum(axis=-1), pairs(table.sum(axis=-2)).sum(axis=-1)
    expected = a * b / pairs(table.sum(axis=(-1, -2)))
    room = (a + b) / 2 - expected
    ok = np.abs(room) > 1e-12
    return np.where(ok, (both - expected) / np.where(ok, room, 1.0), 0.0)


def nearest_centroid(d2, label_onehot):
    """For every crop, the class whose centroid is nearest, from squared distances alone. label_onehot: (..., n, k).

    |x_i - c_k|^2 = mean_j d2(i, j) over the class - half the mean of d2 inside the class."""
    size = label_onehot.sum(axis=-2)[..., None, :]
    to_class = d2 @ label_onehot
    inside = (label_onehot * to_class).sum(axis=-2)[..., None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        d2c = to_class / size - inside / (2 * size ** 2)
    return np.where(size > 0, d2c, np.inf).argmin(axis=-1)


def fixed_point(d2, labels, k=K):
    """Share of crops whose nearest class centroid is their own class's. `labels`: (n,) or (B, n) integers."""
    labels = np.asarray(labels)
    return (nearest_centroid(d2, _onehot(labels, k)) == labels).mean(axis=-1)


def fixed_point_converged(d2, labels, k=K, max_steps=100):
    """Run the k-means step from the labelling until nothing moves; the share of crops still in their first class."""
    now = np.asarray(labels).copy()
    for _ in range(max_steps):
        nxt = nearest_centroid(d2, _onehot(now, k))
        if np.array_equal(nxt, now):
            break
        now = nxt
    return float((now == labels).mean())


def null_labels(y, groups, n_perm, rng):
    """The relabellings, drawn once and shared by every space: {null: (n_perm, n) integer labels}."""
    n_groups = int(groups.max()) + 1
    renaming = np.argsort(rng.random((n_perm, n_groups, K)), axis=-1)       # one permutation of the folder names per source image
    return {"image": renaming[:, groups, y],
            "crop": np.stack([rng.permutation(y) for _ in range(n_perm)]),
            "source": np.stack([rng.permutation(groups) for _ in range(n_perm)])}


# ----------------------------------------------------------------------------------------------------
# the analysis
# ----------------------------------------------------------------------------------------------------
def analyse(spaces, folder, source, n_perm=1000, seed=0, method="ward", balance=True, crop_ids=None):
    """Score every space. `spaces`: dicts with `space`, `rows` (positions into folder / source) and either `items`
    (blocks of features) or `dist` (a ready distance matrix). Returns (rows of numbers, null summary, skipped).
    The cluster strings of a row list its crops in the order of `rows`; `crops_missing_ids` names the others.
    `folders_by_cluster_*` are the counts behind the ARI against the folder: [cluster][folder, in sorted order]."""
    folder, source = np.asarray(folder).astype(str), np.asarray(source).astype(str)
    assert len(set(folder)) == K, f"expected {K} folders, got {sorted(set(folder))}"
    y = np.unique(folder, return_inverse=True)[1]
    g = np.unique(source, return_inverse=True)[1]
    n_groups = int(g.max()) + 1
    null = null_labels(y, g, n_perm, np.random.default_rng(seed))
    rows, skipped, draws = [], [], {}
    for sp in spaces:
        r = np.asarray(sp["rows"])
        if "dist" in sp:
            dist, dims = np.asarray(sp["dist"], float), int(sp.get("n_dims", 0))
        else:
            dist, dims = distance_matrix(sp["items"], balance)
        if len(r) < MIN_CROPS:
            skipped.append(dict(space=sp["space"], reason=f"{len(r)} crops: too few to cut into {K} clusters"))
            continue
        if dist is None or not np.median(dist[np.triu_indices(len(r), 1)]) > 0:
            skipped.append(dict(space=sp["space"], reason="no feature varies between the crops"))
            continue
        d2 = dist ** 2
        parts = {"spectral": spectral_labels(dist, K, seed), "agglo": agglomerative_labels(dist, K, method),
                 "agglo_k13": agglomerative_labels(dist, len(set(g[r])), method)}
        hot = {name: _onehot(lab, int(lab.max()) + 1) for name, lab in parts.items()}
        y_hot, g_hot = _onehot(y[r], K), _onehot(g[r], n_groups)
        row = {k: v for k, v in sp.items() if k not in ("rows", "items", "dist")}
        row.update(n_crops=len(r), n_dims=dims,
                   ari_folder_spectral=float(ari(hot["spectral"], y_hot)), ari_folder_agglo=float(ari(hot["agglo"], y_hot)),
                   ari_source_spectral=float(ari(hot["spectral"], g_hot)), ari_source_agglo=float(ari(hot["agglo"], g_hot)),
                   ari_source_agglo_k13=float(ari(hot["agglo_k13"], g_hot)),
                   fixed_point=float(fixed_point(d2, y[r])), fixed_point_converged=fixed_point_converged(d2, y[r]),
                   fixed_point_of_spectral=float(fixed_point(d2, parts["spectral"])),
                   fixed_point_of_agglo=float(fixed_point(d2, parts["agglo"])),
                   sizes_spectral=np.bincount(parts["spectral"], minlength=K).tolist(),
                   sizes_agglo=np.bincount(parts["agglo"], minlength=K).tolist(),
                   clusters_spectral="".join(str(int(v)) for v in parts["spectral"]),
                   clusters_agglo="".join(str(int(v)) for v in parts["agglo"]),
                   folders_by_cluster_spectral=(hot["spectral"].T @ y_hot).astype(int).tolist(),      # [cluster][folder] counts
                   folders_by_cluster_agglo=(hot["agglo"].T @ y_hot).astype(int).tolist(),
                   crops_missing=int(len(folder) - len(r)))
        if crop_ids is not None and len(r) < len(folder):
            row["crops_missing_ids"] = [c for i, c in enumerate(crop_ids) if i not in set(r.tolist())]
        for kind in ("image", "crop"):
            lab = null[kind][:, r]
            lab_hot = _onehot(lab, K)
            draws.setdefault(("ari_folder_spectral", kind), []).append(ari(hot["spectral"], lab_hot))
            draws.setdefault(("ari_folder_agglo", kind), []).append(ari(hot["agglo"], lab_hot))
            draws.setdefault(("fixed_point", kind), []).append(fixed_point(d2, lab))
        src_hot = _onehot(null["source"][:, r], n_groups)
        for stat, part in zip(SOURCE_STATS, ("spectral", "agglo", "agglo_k13")):
            draws.setdefault((stat, "source"), []).append(ari(hot[part], src_hot))
        rows.append(row)
    summary = {}
    if not rows:
        return rows, summary, skipped
    draws = {key: np.asarray(v, float) for key, v in draws.items()}                    # (spaces, n_perm) each
    centre = {key: v.mean(axis=1) for key, v in draws.items()}
    spread = {key: v.std(axis=1) for key, v in draws.items()}
    zed = {key: (v - centre[key][:, None]) / np.maximum(spread[key][:, None], 1e-9) for key, v in draws.items()}
    for group, stats in MAX_GROUPS.items():
        for kind in (("source",) if group.startswith("ari_source") else ("image", "crop")):
            top = np.max([draws[(s, kind)].max(axis=0) for s in stats], axis=0)          # largest over spaces and statistics
            top_z = np.max([zed[(s, kind)].max(axis=0) for s in stats], axis=0)
            summary[f"{group}__{kind}"] = dict(statistics=list(stats), max_q50=_r(np.quantile(top, 0.5)), max_q95=_r(np.quantile(top, 0.95)),
                                               max_q99=_r(np.quantile(top, 0.99)), max_z_q95=_r(np.quantile(top_z, 0.95)))
            for s in stats:
                for i, row in enumerate(rows):
                    obs = row[s]
                    z = (obs - centre[(s, kind)][i]) / max(spread[(s, kind)][i], 1e-9)
                    row[f"{s}__{kind}_mean"] = float(centre[(s, kind)][i])
                    row[f"{s}__{kind}_sd"] = float(spread[(s, kind)][i])
                    row[f"{s}__{kind}_z"] = float(z)
                    row[f"{s}__{kind}_p"] = float((1 + (draws[(s, kind)][i] >= obs - 1e-12).sum()) / (n_perm + 1))
                    row[f"{s}__{kind}_p_max"] = float((1 + (top >= obs - 1e-12).sum()) / (n_perm + 1))
                    row[f"{s}__{kind}_p_max_z"] = float((1 + (top_z >= z - 1e-9).sum()) / (n_perm + 1))
    for row in rows:
        for kind in ("image", "crop"):
            row[f"fixed_point_excess_{kind}"] = row["fixed_point"] - row[f"fixed_point__{kind}_mean"]
        for k, v in row.items():
            if isinstance(v, float):
                row[k] = _r(v)
    return rows, summary, skipped


def _r(v):
    return round(float(v), 6)


def marginal_means(rows):
    """Mean of each statistic over the spaces sharing one value of a factor. Pooled family spaces are left out;
    leakrisk (SE) spaces count only in the detector and tag tables."""
    every = pd.DataFrame([r for r in rows if r.get("level", "space") == "space"])
    out = {}
    for factor in MARGINALS:
        if factor not in every.columns:
            continue
        frame = every if factor in ("detector", "tag") or "tag" not in every.columns else every[every.tag != "leakrisk"]
        if frame.empty:
            continue
        cols = [c for c in MEAN_COLUMNS if c in frame.columns]
        table = frame.groupby(factor, sort=True)[cols].mean()
        table.insert(0, "n_spaces", frame.groupby(factor, sort=True).size())
        if factor == "scale_nm":                                   # 25, 50, 100, 200: by size, not by spelling
            table = table.loc[sorted(table.index, key=lambda v: (not str(v).isdigit(), int(v) if str(v).isdigit() else 0, str(v)))]
        out[factor] = [dict({factor: str(i), "n_spaces": int(r.n_spaces)}, **{c: _r(r[c]) for c in cols}) for i, r in table.iterrows()]
    return out


def run(pert=core.P0, families=None, n_perm=1000, seed=0, min_crops=20, method="ward", balance=True):
    """Everything, as one JSON-ready dict."""
    table = core.crops_table()
    crops, fams, loading = load_families(pert, families)
    assert list(table.site) == crops
    spaces, skipped = build_spaces(fams, min_crops)
    rows, null, more = analyse(spaces, table.folder.to_numpy(), table.source_image.to_numpy(), n_perm, seed, method, balance, crops)
    done = {name: int(f["done"].sum()) for name, f in sorted(fams.items())}
    return dict(
        what="label-free structure of each feature space; diagnostics only, never a model input",
        pert=pert,
        config=dict(k=K, n_perm=n_perm, seed=seed, min_crops=min_crops, linkage=method, balance_blocks=balance,
                    standardise="z-score over the crops of the space", affinity="RBF, bandwidth = median distance",
                    tiles="mean over tiles", nulls=NULLS, max_groups={k: list(v) for k, v in MAX_GROUPS.items()}),
        crops=dict(n=len(crops), ids=crops, folders=table.folder.value_counts().sort_index().to_dict(),
                   n_source_images=int(table.source_image.nunique())),
        loading=dict(loading, crops_done=done),
        n_spaces=len(rows), spaces=rows, null=null, marginal_means=marginal_means(rows), skipped=skipped + more)


# ----------------------------------------------------------------------------------------------------
# the table, built from the JSON and from nothing else
# ----------------------------------------------------------------------------------------------------
def spaces_frame(result):
    """One row per space with every number in the JSON (the CSV). The cluster strings stay in the JSON: a spreadsheet
    would read "0012..." as a number."""
    return pd.DataFrame([{k: v for k, v in row.items() if not isinstance(v, (dict, list)) and not k.startswith("clusters_")}
                         for row in result["spaces"]])


def _f(v, digits=2):
    return "" if v is None else f"{v:.{digits}f}"


def table(result, top=25):
    """The markdown report. Every number in it is read from `result` (the parsed labelfree.json)."""
    cfg, crops, rows = result["config"], result["crops"], result["spaces"]
    folders = ", ".join(f"{k} {v}" for k, v in crops["folders"].items())
    partial = sum(1 for r in rows if r["crops_missing"])
    lines = ["# Label-free structure of the feature spaces", "",
             "Diagnostics only: nothing in this file may feed a model. Unit = crop, groups = the source images.", "",
             f"- Crops: {crops['n']} ({folders}) from {crops['n_source_images']} source images; crop version {result['pert']}.",
             f"- Spaces scored: {len(rows)} ({sum(1 for r in rows if r['level'] == 'family')} of them pooled per family); "
             f"{partial} on fewer than {crops['n']} crops; skipped: {len(result['skipped'])}.",
             f"- Clusters: k = {cfg['k']}; spectral ({cfg['affinity']}) and agglomerative ({cfg['linkage']}).",
             f"- Nulls: {cfg['n_perm']} relabellings, seed {cfg['seed']}. " + " ".join(f"`{k}` = {v}." for k, v in cfg["nulls"].items()),
             "- p_max = against the largest value over all spaces per relabelling; p_max_z = the same on z-scores.",
             "- The fixed-point share is high for any labelling in a high-dimensional space: read it against its null mean."]
    if not rows:
        lines += ["", "**No space could be scored.** Crops done per family: "
                  + (", ".join(f"{k} {v}" for k, v in result["loading"]["crops_done"].items()) or "none") + "."]
    for key, s in result["null"].items():
        group, kind = key.split("__")
        lines.append(f"- Max-statistic null, {group} under `{kind}`: median {_f(s['max_q50'])}, 95 % {_f(s['max_q95'])}, 99 % {_f(s['max_q99'])}.")
    for note in result["loading"]["notes"]:
        lines.append(f"- Note: {note}")
    if rows:
        head = ("| space | crops | dims | tag | ARI folder (spectral / agglo) | p_max image | p_max crop | ARI source (spectral / agglo / k13) "
                "| p_max source | fixed point (null mean) | fixed point p_max_z image |")
        rule = "|---|---|---|---|---|---|---|---|---|---|---|"

        def line(r):
            return (f"| {r['space'].replace('|', ' / ')} | {r['n_crops']} | {r['n_dims']} | {r['tag']} "
                    f"| {_f(r['ari_folder_spectral'])} / {_f(r['ari_folder_agglo'])} "
                    f"| {_f(r['ari_folder_spectral__image_p_max'], 3)} / {_f(r['ari_folder_agglo__image_p_max'], 3)} "
                    f"| {_f(r['ari_folder_spectral__crop_p_max'], 3)} / {_f(r['ari_folder_agglo__crop_p_max'], 3)} "
                    f"| {_f(r['ari_source_spectral'])} / {_f(r['ari_source_agglo'])} / {_f(r['ari_source_agglo_k13'])} "
                    f"| {_f(r['ari_source_spectral__source_p_max'], 3)} / {_f(r['ari_source_agglo__source_p_max'], 3)} "
                    f"| {_f(r['fixed_point'])} ({_f(r['fixed_point__image_mean'])}) | {_f(r['fixed_point__image_p_max_z'], 3)} |")

        best = lambda r: -max(r["ari_folder_spectral"], r["ari_folder_agglo"])   # noqa: E731
        fine = sorted((r for r in rows if r["level"] == "space"), key=lambda r: (best(r), r["space"]))
        pooled = sorted((r for r in rows if r["level"] == "family"), key=lambda r: (best(r), r["space"]))
        lines += ["", f"## Spaces, by ARI against the folder label (top {min(top, len(fine))} of {len(fine)})", "", head, rule]
        lines += [line(r) for r in fine[:top]]
        if pooled:
            lines += ["", "## One pooled space per family", "", head, rule] + [line(r) for r in pooled]
        for factor, levels in result["marginal_means"].items():
            lines += ["", f"## Mean over spaces, by {factor}", "",
                      f"| {factor} | spaces | ARI folder spectral | ARI folder agglo | ARI source spectral | ARI source agglo | ARI source k13 "
                      "| fixed point | fixed point minus null (image) |", "|---|---|---|---|---|---|---|---|---|"]
            lines += [f"| {lv[factor]} | {lv['n_spaces']} | {_f(lv['ari_folder_spectral'])} | {_f(lv['ari_folder_agglo'])} "
                      f"| {_f(lv['ari_source_spectral'])} | {_f(lv['ari_source_agglo'])} | {_f(lv['ari_source_agglo_k13'])} "
                      f"| {_f(lv['fixed_point'])} | {_f(lv['fixed_point_excess_image'])} |" for lv in levels]
    if result["skipped"]:
        reasons = pd.Series([s["reason"] for s in result["skipped"]]).value_counts()
        lines += ["", "## Skipped", ""] + [f"- {n} space(s): {reason}" for reason, n in reasons.items()]
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", required=True, help="folder for labelfree.json, labelfree.md and labelfree_spaces.csv")
    p.add_argument("--pert", default=core.P0, help="crop version to read (default P0)")
    p.add_argument("--families", default=None, help="comma list; default = every family with output on disk")
    p.add_argument("--n-perm", type=int, default=1000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--min-crops", type=int, default=20, help="a space needs this many finished crops to be scored")
    p.add_argument("--linkage", default="ward", choices=["ward", "average", "complete"])
    p.add_argument("--no-balance", action="store_true", help="plain z-scored Euclidean distance: wide blocks dominate")
    p.add_argument("--top", type=int, default=25, help="rows of the ranked table in labelfree.md (the CSV has all)")
    a = p.parse_args(argv)
    only = [f for f in a.families.split(",") if f] if a.families else None
    result = run(a.pert, only, a.n_perm, a.seed, a.min_crops, a.linkage, not a.no_balance)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "labelfree.json").write_text(json.dumps(result, indent=1, sort_keys=False) + "\n")
    saved = json.loads((out / "labelfree.json").read_text())             # the table is built from the file, not from memory
    (out / "labelfree.md").write_text(table(saved, a.top))
    spaces_frame(saved).to_csv(out / "labelfree_spaces.csv", index=False)
    print(table(saved, a.top))
    print(f"wrote {out / 'labelfree.json'}, labelfree.md and labelfree_spaces.csv")


if __name__ == "__main__":
    main()
