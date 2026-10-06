"""Steps 3-9 of notes/representation.md: remove position and imaging from the tile embeddings, then run the three
tiers of pair comparisons and the positive control.

    python representation/analyse.py            # prints the report, writes processed/representation/results.json

Reads:   processed/representation/emb/{variant}/{batch}__{site}.npz  (made by representation/embed.py)
Writes:  processed/representation/results.json and site_vectors.csv

Units: every component is divided by the tile-to-tile spread inside a site, and a distance between two sites is the
root-mean-square difference per kept component. Two sites of identical material, 26 independent tiles each, would
sit about sqrt(2/26) = 0.28 apart from position alone.
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut, LeaveOneOut, cross_val_predict
from sklearn.neighbors import NearestNeighbors

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from preprocessing import PROCESSED_DIR   # noqa: E402

EMB = PROCESSED_DIR / "representation" / "emb"
OUT = PROCESSED_DIR / "representation"

# Touching crops of one strip, left to right, found by matching image edges (notes/representation.md).
CHAINS = {2080: ["cfe5vt7s", "r17byphk", "ffwubibz"], 2148: ["f1vzngrs", "epqdaau9"],
          2068: ["vc2whyaq", "x77cy643", "utfgcjfa", "rxax5ozo"], 2060: ["x7u69zsw", "tuy3zymq", "kbdh4tri", "71vgq3fw"],
          1904: ["mgxahqnk", "hawkfj64", "0grcilhi"], 2088: ["9luzk4jm", "hzumfsms"]}
TOUCHING = [(a, b) for chain in CHAINS.values() for a, b in zip(chain, chain[1:])]
# Sites carrying the green edge marker: the first or last crop of their strip.
END_TILES = {"f1vzngrs", "fzrt2k6r", "i9jiqjwl", "ufdvpb81", "vc2whyaq", "x7u69zsw", "xgj4xftb",
             "ffwubibz", "uhdslk0o", "avn74qx1", "0grcilhi", "71vgq3fw", "ptg8lmto"}
N_PCS, KEEP_R, IMAGING_ENERGY = 30, 0.5, 0.90
ACQ_KEYS = ["bse_black_raw", "bse_graphite_raw", "bse_noise_sigma", "inlens_noise_sigma", "bright_mode"]


# ----------------------------------------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------------------------------------
def load(variant):
    """{site: dict of arrays} for one variant folder."""
    out = {}
    for path in sorted((EMB / variant).glob("*.npz")):
        z = np.load(path, allow_pickle=False)
        out[str(z["site"])] = {k: z[k] for k in z.files}
    return out


def tile_matrix(d, main_only=True):
    """Raw 1536-number tile vectors: BSE (class, patch mean) then Inlens (class, patch mean)."""
    x = np.concatenate([d["bse"], d["inlens"]], axis=1)
    return x[~d["is_edge"]] if main_only else x


class Space:
    """Centre, balance the four token blocks, optionally remove the imaging subspace, PCA, keep reliable components,
    scale by within-site tile spread. Fitted on the unchanged sites only; never sees a batch label."""

    def __init__(self, orig, imaging_basis=None):
        sites = list(orig)
        x = np.concatenate([tile_matrix(orig[s]) for s in sites])
        self.mu = x.mean(axis=0)
        xc = x - self.mu
        self.block_scale = np.repeat([np.sqrt((xc[:, i:i + 384] ** 2).mean()) for i in range(0, 1536, 384)], 384)
        self.basis = imaging_basis
        xs = self.pre(x)
        self.pca = PCA(n_components=N_PCS, random_state=0).fit(xs)
        scores = self.pca.transform(xs)
        site_of = np.repeat(np.arange(len(sites)), [int((~orig[s]["is_edge"]).sum()) for s in sites])
        col = np.concatenate([orig[s]["col"][~orig[s]["is_edge"]] for s in sites])
        left = np.array([scores[(site_of == i) & (col <= 5)].mean(axis=0) for i in range(len(sites))])
        right = np.array([scores[(site_of == i) & (col >= 7)].mean(axis=0) for i in range(len(sites))])
        self.split_half_r = np.array([np.corrcoef(left[:, k], right[:, k])[0, 1] for k in range(N_PCS)])
        self.keep = self.split_half_r >= KEEP_R
        centred = scores - np.array([scores[site_of == i].mean(axis=0) for i in range(len(sites))])[site_of]
        self.within_sd = np.sqrt((centred ** 2).sum(axis=0) / (len(scores) - len(sites)))

    def pre(self, x):
        xs = (x - self.mu) / self.block_scale
        return xs if self.basis is None else xs - (xs @ self.basis.T) @ self.basis

    def tiles(self, d, main_only=True):
        """Kept, scaled component scores for every tile of one site version."""
        return (self.pca.transform(self.pre(tile_matrix(d, main_only))) / self.within_sd)[:, self.keep]

    def site(self, d):
        return self.tiles(d).mean(axis=0)


def dist(a, b):
    return float(np.sqrt(((a - b) ** 2).mean()))


# ----------------------------------------------------------------------------------------------------
# statistics
# ----------------------------------------------------------------------------------------------------
def rss(y, design):
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    return float(((y - design @ beta) ** 2).sum()), beta


def within_session_effect(v, session, label, levels):
    """Sum over components of the drop in residual sum of squares when `label` dummies join the session dummies,
    and the label coefficients (rows follow `levels[1:]`, relative to levels[0])."""
    s = pd.get_dummies(session).to_numpy(float)
    lab = np.column_stack([(label == lv).astype(float) for lv in levels[1:]])
    full = np.column_stack([s, lab])
    r0, _ = rss(v, s)
    r1, beta = rss(v, full)
    return r0 - r1, beta[s.shape[1]:]


def exact_within_session_test(v, session, label, levels):
    """Every distinct relabelling of sites inside their own session. Returns (observed, p, null array, coefficients)."""
    observed, coef = within_session_effect(v, session, label, levels)
    groups = [np.flatnonzero(session == s) for s in np.unique(session)]
    options = [sorted(set(itertools.permutations(label[g]))) for g in groups]
    null = []
    for combo in itertools.product(*options):
        lab = label.copy()
        for g, new in zip(groups, combo):
            lab[g] = new
        null.append(within_session_effect(v, session, lab, levels)[0])
    null = np.array(null)
    return observed, float((null >= observed - 1e-12).mean()), null, coef


def session_r2(v, session):
    s = pd.get_dummies(session).to_numpy(float)
    return np.array([1 - rss(v[:, k], s)[0] / ((v[:, k] - v[:, k].mean()) ** 2).sum() for k in range(v.shape[1])])


def loso_r2(v, y, session):
    """Leave-one-session-out R2 of a ridge from site vectors to one descriptor."""
    y = (y - y.mean()) / (y.std() + 1e-12)
    pred = cross_val_predict(RidgeCV(alphas=np.logspace(-2, 3, 12)), v, y, cv=LeaveOneGroupOut(), groups=session)
    return float(1 - ((y - pred) ** 2).sum() / (y ** 2).sum())


def batch_accuracy(v, batch, session):
    """Balanced accuracy of a batch classifier on site vectors under the two schemes the team uses."""
    clf = LogisticRegression(C=1.0, max_iter=5000)
    site_out = cross_val_predict(clf, v, batch, cv=LeaveOneOut())
    sess_out = cross_val_predict(clf, v, batch, cv=LeaveOneGroupOut(), groups=session)
    return float(balanced_accuracy_score(batch, site_out)), float(balanced_accuracy_score(batch, sess_out))


def mnn_shift(tiles_a, content_a, tiles_b, content_b):
    """Mean difference between content-matched tiles: mutual nearest neighbours on (pore, bright, row)."""
    ab = NearestNeighbors(n_neighbors=1).fit(content_b).kneighbors(content_a, return_distance=False)[:, 0]
    ba = NearestNeighbors(n_neighbors=1).fit(content_a).kneighbors(content_b, return_distance=False)[:, 0]
    pairs = [(i, j) for i, j in enumerate(ab) if ba[j] == i]
    if not pairs:
        return np.nan, 0
    i, j = map(np.array, zip(*pairs))
    return float(np.sqrt((((tiles_b[j] - tiles_a[i]).mean(axis=0)) ** 2).mean())), len(pairs)


# ----------------------------------------------------------------------------------------------------
# the run
# ----------------------------------------------------------------------------------------------------
def analyse(orig, perturbed, injected, anchors, use_projection):
    res = {}
    sites = list(orig)
    batch = np.array([str(orig[s]["batch"]) for s in sites])
    session = np.array([int(orig[s]["session"]) for s in sites])
    idx = {s: i for i, s in enumerate(sites)}

    # ---- imaging subspace from the synthetic imaging changes (tile by tile, same tile before and after)
    plain = Space(orig)
    deltas, kinds = [], []
    for variant, group in perturbed.items():
        for s, d in group.items():
            deltas.append(plain.pre(tile_matrix(d)) - plain.pre(tile_matrix(orig[s])))
            kinds += [variant] * len(deltas[-1])
    deltas = np.concatenate(deltas)
    _, sv, vt = np.linalg.svd(deltas, full_matrices=False)
    energy = np.cumsum(sv ** 2) / (sv ** 2).sum()
    k_img = int(np.searchsorted(energy, IMAGING_ENERGY) + 1)
    basis = vt[:k_img]
    res["imaging_subspace"] = dict(n_difference_vectors=len(deltas), dims_for_80pct=int(np.searchsorted(energy, 0.8) + 1),
                                   dims_for_90pct=k_img, dims_for_95pct=int(np.searchsorted(energy, 0.95) + 1))

    sp = Space(orig, basis if use_projection else None)
    v = np.array([sp.site(orig[s]) for s in sites])
    k = v.shape[1]
    res["space"] = dict(projection=use_projection, pcs=N_PCS, kept=int(k),
                        variance_share_of_kept=float(sp.pca.explained_variance_ratio_[sp.keep].sum()),
                        split_half_r_kept=[round(float(r), 2) for r in sp.split_half_r[sp.keep]],
                        session_r2_median=float(np.median(session_r2(v, session))),
                        session_r2_range=[float(session_r2(v, session).min()), float(session_r2(v, session).max())])

    # positional bias: how much of a tile's score its row and column inside the image explain
    t = np.concatenate([sp.tiles(orig[s]) - sp.site(orig[s]) for s in sites])
    rc = np.concatenate([np.column_stack([np.ones((~orig[s]["is_edge"]).sum()), orig[s]["row"][~orig[s]["is_edge"]],
                                          orig[s]["col"][~orig[s]["is_edge"]]]) for s in sites]).astype(float)
    pos_r2 = [1 - rss(t[:, j], rc)[0] / (t[:, j] ** 2).sum() for j in range(k)]
    res["positional_bias_r2"] = dict(median=float(np.median(pos_r2)), max=float(np.max(pos_r2)))

    # ---- pair distances
    pairs = []
    touching = {frozenset(p) for p in TOUCHING}
    for a, b in itertools.combinations(sites, 2):
        kind = ("touching" if frozenset((a, b)) in touching else "same session, not touching") \
            if session[idx[a]] == session[idx[b]] else "different session"
        pairs.append(dict(a=a, b=b, kind=kind, same_batch=batch[idx[a]] == batch[idx[b]], d=dist(v[idx[a]], v[idx[b]])))
    pairs = pd.DataFrame(pairs)
    touch = pairs[pairs.kind == "touching"]
    null_max, null_med = float(touch.d.max()), float(touch.d.median())
    res["pair_distances"] = {f"{kind} / {'same' if sb else 'different'} batch": dict(n=int(len(g)), median=float(g.d.median()),
                             min=float(g.d.min()), max=float(g.d.max()))
                             for (kind, sb), g in pairs.groupby(["kind", "same_batch"])}

    # ---- gate 1: imaging
    b3 = pairs[pairs.a.map(lambda s: batch[idx[s]] == "Batch_3") & pairs.b.map(lambda s: batch[idx[s]] == "Batch_3")]
    moves = {variant: [dist(sp.site(d), v[idx[s]]) for s, d in group.items()] for variant, group in perturbed.items()}
    all_moves = np.concatenate(list(moves.values()))
    res["gate_imaging"] = dict(
        site_shift_by_change={kv: float(np.median(m)) for kv, m in moves.items()},
        median_site_shift=float(np.median(all_moves)), max_site_shift=float(all_moves.max()),
        ratio_to_touching_pairs=float(np.median(all_moves) / null_med),
        ratio_to_batch3_site_distance=float(np.median(all_moves) / b3.d.median()),
        acquisition_predicted_r2={key: loso_r2(v, np.array([json.loads(str(orig[s]["acq"]))[key] for s in sites], float), session)
                                  for key in ACQ_KEYS})

    # ---- tier 1: the control. Cross-batch seams against same-batch seams, exact over which 4 of the 12 are "cross".
    d = touch.d.to_numpy()
    cross = (~touch.same_batch).to_numpy()
    obs = d[cross].mean() - d[~cross].mean()
    null = np.array([d[list(c)].mean() - np.delete(d, list(c)).mean() for c in itertools.combinations(range(len(d)), int(cross.sum()))])
    res["tier1_control"] = dict(cross_batch_seams=[round(float(x), 3) for x in d[cross]], same_batch_seams=[round(float(x), 3) for x in d[~cross]],
                                mean_difference=float(obs), p_two_sided=float((np.abs(null) >= abs(obs) - 1e-12).mean()), arrangements=len(null))

    # ---- tier 2: batch inside mixed sessions, exact permutation
    levels = ["Batch_3", "Batch_1", "Batch_2"]
    t_obs, p, t_null, coef = exact_within_session_test(v, session, batch, levels)
    coef_norm = {lv: float(np.sqrt((coef[i] ** 2).mean())) for i, lv in enumerate(levels[1:])}
    per_session = {}
    for s in np.unique(session):
        here = np.flatnonzero(session == s)
        for x, y in itertools.combinations(sorted(set(batch[here])), 2):
            per_session.setdefault(f"{x} minus {y}", {})[int(s)] = v[here][batch[here] == x].mean(axis=0) - v[here][batch[here] == y].mean(axis=0)
    cosines = {}
    for name, vecs in per_session.items():
        cs = [float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b))) for a, b in itertools.combinations(vecs.values(), 2)]
        cosines[name] = dict(sessions=list(vecs), cosines=[round(c, 2) for c in cs],
                             sizes=[round(float(np.sqrt((x ** 2).mean())), 3) for x in vecs.values()])
    res["tier2_within_session"] = dict(statistic=float(t_obs), p=p, arrangements=len(t_null), null_median=float(np.median(t_null)),
                                       null_95th=float(np.percentile(t_null, 95)), batch_shift_size=coef_norm, direction_agreement=cosines)

    # end-of-strip check inside the Batch_3-only sessions that have both end and interior crops
    sel = np.isin(session, [2060, 1904, 2088])
    is_end = np.array(["end" if s in END_TILES else "interior" for s in sites])
    e_obs, e_p, e_null, e_coef = exact_within_session_test(v[sel], session[sel], is_end[sel], ["interior", "end"])
    b1 = coef[0]
    res["end_of_strip"] = dict(statistic=float(e_obs), p=e_p, arrangements=len(e_null), size=float(np.sqrt((e_coef[0] ** 2).mean())),
                               cosine_with_batch1_shift=float(e_coef[0] @ b1 / (np.linalg.norm(e_coef[0]) * np.linalg.norm(b1))))

    # ---- tier 3: across sessions (confounded)
    acq = np.array([[json.loads(str(orig[s]["acq"]))[key] for key in ACQ_KEYS] for s in sites], float)
    acq = (acq - acq.mean(axis=0)) / acq.std(axis=0)
    top = v[:, :min(k, 8)]
    res["tier3_across_sessions"] = dict(
        chance=1 / 3,
        embedding_leave_site_out=batch_accuracy(top, batch, session)[0], embedding_leave_session_out=batch_accuracy(top, batch, session)[1],
        acquisition_only_leave_site_out=batch_accuracy(acq, batch, session)[0], acquisition_only_leave_session_out=batch_accuracy(acq, batch, session)[1])

    content = {s: np.column_stack([(orig[s]["tile_void"][~orig[s]["is_edge"]] - 0.1) / 0.05, (orig[s]["tile_bright"][~orig[s]["is_edge"]] - 0.06) / 0.05,
                                   orig[s]["row"][~orig[s]["is_edge"]]]) for s in sites}
    tiles = {s: sp.tiles(orig[s]) for s in sites}
    stack = lambda group, src: np.concatenate([src[s] for s in group])   # noqa: E731
    mnn = {}
    for x, y in (("Batch_1", "Batch_3"), ("Batch_2", "Batch_3"), ("Batch_1", "Batch_2")):
        ga, gb = [s for s in sites if batch[idx[s]] == x], [s for s in sites if batch[idx[s]] == y]
        size, n = mnn_shift(stack(ga, tiles), stack(ga, content), stack(gb, tiles), stack(gb, content))
        mnn[f"{x} vs {y}"] = dict(shift=size, matched_tiles=n)
    b3_only = [2060, 1904, 2088, 1612]
    ref = []
    for sa, sb in itertools.combinations(b3_only, 2):
        ga, gb = [s for s in sites if session[idx[s]] == sa], [s for s in sites if session[idx[s]] == sb]
        ref.append(mnn_shift(stack(ga, tiles), stack(ga, content), stack(gb, tiles), stack(gb, content))[0])
    mnn["reference: pairs of Batch_3-only sessions"] = dict(median=float(np.median(ref)), min=float(np.min(ref)), max=float(np.max(ref)))
    res["tier3_content_matched_shift"] = mnn

    # ---- positive control: injected material changes, after the whole pipeline
    partner = {b: a for a, b in TOUCHING} | {a: b for a, b in TOUCHING}
    rows = []
    for variant, group in injected.items():
        for s, dd in group.items():
            raw_delta = (plain.pre(tile_matrix(dd)) - plain.pre(tile_matrix(orig[s]))).mean(axis=0)
            vi = sp.site(dd)
            rows.append(dict(change=variant, site=s, pore_points=100 * (float(dd["site_void"]) - float(orig[s]["site_void"])),
                             bright_points=100 * (float(dd["site_bright"]) - float(orig[s]["site_bright"])),
                             moved=dist(vi, v[idx[s]]), to_partner_before=dist(v[idx[s]], v[idx[partner[s]]]),
                             to_partner_after=dist(vi, v[idx[partner[s]]]),
                             share_inside_imaging=float(((basis @ raw_delta) ** 2).sum() / (raw_delta ** 2).sum())))
    inj = pd.DataFrame(rows)
    if len(inj):
        inj["detected"] = inj.to_partner_after > null_max
        res["positive_control"] = dict(threshold_largest_touching_pair=null_max, by_change={
            c: dict(pore_points=float(g.pore_points.mean()), bright_points=float(g.bright_points.mean()), moved=float(g.moved.mean()),
                    to_partner_after=float(g.to_partner_after.mean()), detected=f"{int(g.detected.sum())}/{len(g)}",
                    share_inside_imaging=float(g.share_inside_imaging.mean())) for c, g in inj.groupby("change")})

    # ---- depth check: the same tests with the crop anchored at the top and at the bottom
    depth = {}
    for name, group in anchors.items():
        if len(group) != len(sites):
            continue
        va = np.array([sp.site(group[s]) for s in sites])
        da = np.array([dist(va[idx[a]], va[idx[b]]) for a, b in zip(touch.a, touch.b)])
        o = da[cross].mean() - da[~cross].mean()
        n1 = np.array([da[list(c)].mean() - np.delete(da, list(c)).mean() for c in itertools.combinations(range(len(da)), int(cross.sum()))])
        depth[name] = dict(tier1_p=float((np.abs(n1) >= abs(o) - 1e-12).mean()), tier2_p=exact_within_session_test(va, session, batch, levels)[1],
                           median_shift_from_centred_crop=float(np.median([dist(va[i], v[i]) for i in range(len(sites))])))
    res["depth_check"] = depth

    table = pd.DataFrame(v, columns=[f"c{j}" for j in range(k)])
    table.insert(0, "site", sites), table.insert(1, "batch", batch), table.insert(2, "session", session)
    table["pore"] = [float(orig[s]["site_void"]) for s in sites]
    table["bright"] = [float(orig[s]["site_bright"]) for s in sites]
    res["component_vs_kpi"] = {kpi: [round(float(np.corrcoef(v[:, j], table[kpi])[0, 1]), 2) for j in range(k)] for kpi in ("pore", "bright")}
    return res, table, inj


def main():
    orig = load("orig")
    perturbed = {p.name: load(p.name) for p in sorted(EMB.iterdir()) if p.name in
                 ("black25", "gamma0.8", "gamma1.25", "contrast0.85", "noise4", "blur1")}
    injected = {p.name: load(p.name) for p in sorted(EMB.iterdir()) if p.name.startswith(("pore_r", "bright_rm"))}
    anchors = {p.name: load(p.name) for p in sorted(EMB.iterdir()) if p.name.startswith("anchor_")}
    print(f"{len(orig)} sites | imaging changes: {sum(map(len, perturbed.values()))} | injected: {sum(map(len, injected.values()))} "
          f"| re-anchored: {sum(map(len, anchors.values()))}")
    results = {}
    for name, use in (("imaging_removed", True), ("imaging_kept", False)):
        res, table, inj = analyse(orig, perturbed, injected, anchors, use)
        results[name] = res
        if use:
            table.to_csv(OUT / "site_vectors.csv", index=False)
            inj.to_csv(OUT / "positive_control.csv", index=False)
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
