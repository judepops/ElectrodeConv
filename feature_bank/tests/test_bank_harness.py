"""The evaluation harness (bank/harness.py) and the assembler (bank/assemble.py).

    pytest tests/test_bank_harness.py -q

What is checked: no source image is ever in train and test; nothing from a held-out image (features or labels) reaches
a fitted step; shuffled labels score near one third; two runs give the same JSON; leakrisk and imaging spaces stay out
of the models they must stay out of; a partial bank loads and is reported. The harness tests run on a small synthetic
bank laid over the real crop table (meta/crops.csv), so they need no feature files.
"""
import copy
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from bank import assemble, core, harness

CFG = harness.load_config()


def _table():
    crops = core.crops_table()
    meta = pd.read_csv(core.META_DIR / "analysis_only.csv")
    neighbours = {r.site: r.right_neighbour for r in meta.itertuples() if isinstance(r.right_neighbour, str)}
    return list(crops.site), crops.folder.to_numpy(str), crops.source_image.to_numpy(str), neighbours


def _space(family, det, view, tag, X, tiles=None):
    tile_sets = [dict(names=[f"{family}|{det}|{view}|25|t"], tiles=tiles)] if tiles is not None else []
    return SimpleNamespace(key=f"{family}|{det}|{view}|{tag}", family=family, detector=det, view=view, tag=tag, X=X,
                           tile_sets=tile_sets, legacy=False, pooled=False)


def synthetic_design(seed=0, signal=2.5, image_effect=1.0, cfg=CFG):
    """A bank with a real class signal, a source-image effect, an imaging-only family and a leaking leakrisk space."""
    crops, labels, groups, neighbours = _table()
    rng = np.random.default_rng(seed)
    classes = sorted(set(labels))
    y = np.array([classes.index(v) for v in labels])
    images = sorted(set(groups))
    g = np.array([images.index(v) for v in groups])
    n = len(crops)

    def block(d, s, e):
        centres, shifts = rng.standard_normal((len(classes), d)), rng.standard_normal((len(images), d))
        return s * centres[y] + e * shifts[g] + rng.standard_normal((n, d))

    tile_base = block(10, signal, image_effect)
    tiles = [tile_base[i] + 0.5 * rng.standard_normal((6, 10)) for i in range(n)]
    spaces = [_space("syn_mat", "BSE", "anchored", "material", block(12, signal, image_effect)),
              _space("syn_mix", "Inlens", "harmonised", "mixed", block(40, signal / 2, image_effect), tiles),
              _space("syn_acq", "BSE", "raw", "imaging", block(3, 0.0, 3.0)),
              _space("syn_leak", "SE", "raw", "leakrisk", np.eye(len(classes))[y] + 0.01 * rng.standard_normal((n, len(classes))))]
    cfg = copy.deepcopy(cfg)
    cfg["acquisition"] = dict(family="syn_acq", fallback="syn_acq")
    cfg["sensitivity"] = dict(alignf_cross_image=True)                 # so the leakage tests cover the optional rows too
    return harness.build_design(crops, labels, groups, neighbours, spaces, cfg), cfg


@pytest.fixture(scope="module")
def syn():
    return synthetic_design()


def _loso(design, cfg, Y):
    """LOSO-13 only: fits, then out-of-fold probabilities and temperatures per kernel model."""
    folds = harness.make_splits(design.groups, design.neighbours)["loso13"]
    jobs = harness.fit_jobs({"loso13": folds})
    results = harness.run_fits(design, Y, cfg, jobs)
    out = {}
    for name, model in design.models.items():
        out[name] = harness.compose_kernel(design, folds, results, name, Y if model["null"] else Y[:1], cfg)
    return folds, results, out


# ----------------------------------------------------------------------------------------------------
# splits
# ----------------------------------------------------------------------------------------------------
def test_no_source_image_in_train_and_test(syn):
    design, _ = syn
    groups, n = design.groups, design.n
    splits = harness.make_splits(groups, design.neighbours)
    assert len(splits["loso13"]) == 13 and len(splits["loco_nbr"]) == n
    assert sorted(i for f in splits["loso13"] for i in f["test"]) == list(range(n))            # every crop tested once
    assert sorted(i for f in splits["loco_nbr"] for i in f["test"]) == list(range(n))
    for fold in splits["loso13"]:
        assert not set(groups[list(fold["train"])]) & set(groups[list(fold["test"])])
        assert set(fold["train"]) | set(fold["test"]) == set(range(n))
        assert len(fold["inner"]) == 12
    assert any(design.neighbours)                                                               # the 12 joins were read
    for fold in splits["loco_nbr"]:
        (i,) = fold["test"]
        assert i not in fold["train"] and not design.neighbours[i] & set(fold["train"])
        assert set(fold["train"]) == set(range(n)) - {i} - design.neighbours[i]
    for folds in splits.values():
        for fold in folds:
            for inner in fold["inner"]:                                                         # the inner LOSO is group-disjoint too
                assert not set(groups[list(inner["train"])]) & set(groups[list(inner["val"])])
                assert set(inner["train"]) | set(inner["val"]) == set(fold["train"])
                assert not set(inner["train"]) & set(fold["test"])
    # every fit that scores a crop was trained without it
    jobs = harness.fit_jobs(splits)
    results = harness.run_fits(design, design.y[None], CFG, {k: "real" for k in list(jobs)[:3]})
    for train, res in results.items():
        assert not set(res["eval"]) & set(train) and set(res["eval"]) | set(train) == set(range(n))


def test_neighbours_are_symmetric_and_same_image(syn):
    design, _ = syn
    pairs = [(i, j) for i, s in enumerate(design.neighbours) for j in s]
    assert len(pairs) == 2 * 12                                                                  # 12 joins, both directions
    for i, j in pairs:
        assert i in design.neighbours[j] and design.groups[i] == design.groups[j]


# ----------------------------------------------------------------------------------------------------
# leakage
# ----------------------------------------------------------------------------------------------------
def _same(a, b):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return np.array_equal(np.asarray(a), np.asarray(b))


def _scramble(design, rows, seed=1):
    """A copy of the design in which the features and tiles of `rows` are replaced by large random numbers."""
    d = copy.deepcopy(design)
    rng = np.random.default_rng(seed)
    for s in d.spaces:
        s["X"][rows] = 50.0 * rng.standard_normal((len(rows), s["X"].shape[1]))
        for ts in s["tile_sets"]:
            hit = np.isin(ts["owner"], rows)
            ts["T"][hit] = 50.0 * rng.standard_normal((int(hit.sum()), ts["T"].shape[1]))
    return d


@pytest.mark.parametrize("image", ["img04", "img07", "img10"])
def test_held_out_features_reach_no_fitted_step(syn, image):
    """Scaler, PCA, bandwidth, centring, kernel scale, ALIGNF weights: identical whatever the held-out image contains."""
    design, cfg = syn
    held = np.flatnonzero(design.groups == image)
    train = tuple(np.flatnonzero(design.groups != image))
    Y = design.y[None]
    a = harness.fit_fold(design, train, Y, cfg, with_state=True)
    b = harness.fit_fold(_scramble(design, held), train, Y, cfg, with_state=True)
    assert a["state"] and _same(a["state"], b["state"])                                          # every fitted number
    tr = np.array(train)
    assert np.array_equal(a["K"][:, tr][:, :, tr], b["K"][:, tr][:, :, tr])                      # the training kernels
    assert _same(a["weights"], b["weights"])
    assert not np.array_equal(a["K"], b["K"])                                                    # (the scramble did change the test rows)
    if len(held) > 1:                                                                            # test crops are transformed one by one
        c = harness.fit_fold(_scramble(design, held[:1]), train, Y, cfg)
        for name in a["dist"]:
            assert np.array_equal(a["dist"][name][:, 1:], c["dist"][name][:, 1:])
            assert not np.array_equal(a["dist"][name][:, :1], c["dist"][name][:, :1])
        for fam in a["logit"]:
            assert np.array_equal(a["logit"][fam][1:], c["logit"][fam][1:])


def test_held_out_labels_reach_no_fitted_step(syn):
    """Changing the labels of the held-out image changes nothing about its own predictions or its temperature."""
    design, cfg = syn
    y = design.y
    for image in ("img04", "img12"):
        held = np.flatnonzero(design.groups == image)
        y2 = y.copy()
        y2[held] = (y[held] + 1) % len(design.classes)
        folds, res1, out1 = _loso(design, cfg, y[None])
        _, res2, out2 = _loso(design, cfg, y2[None])
        f = [fold["name"] for fold in folds].index(image)
        for name in design.models:
            (P1, t1), (P2, t2) = out1[name], out2[name]
            assert np.array_equal(P1[0, held], P2[0, held]) and t1[0, f] == t2[0, f]
            assert np.array_equal(res1[folds[f]["train"]]["weights"][name], res2[folds[f]["train"]]["weights"][name])
        assert any(not np.array_equal(out1[m][0], out2[m][0]) for m in design.models)            # other folds did see the change


def test_held_out_features_do_not_move_weights_or_temperature(syn):
    design, cfg = syn
    image = "img05"
    held = np.flatnonzero(design.groups == image)
    folds, res1, out1 = _loso(design, cfg, design.y[None])
    _, res2, out2 = _loso(_scramble(design, held), cfg, design.y[None])
    f = [fold["name"] for fold in folds].index(image)
    for name in design.models:
        assert out1[name][1][0, f] == out2[name][1][0, f]                                        # temperature of that fold
        assert np.array_equal(res1[folds[f]["train"]]["weights"][name], res2[folds[f]["train"]]["weights"][name])


def test_leakrisk_and_imaging_stay_out(syn):
    design, _ = syn
    tag_of = lambda k: design.spaces[design.kernels[k]["space"]]["tag"]                          # noqa: E731
    assert {tag_of(k) for k in design.models["A"]["kernels"]} == {"material", "mixed", "imaging"}
    assert {tag_of(k) for k in design.models["B"]["kernels"]} == {"material", "mixed"}
    assert {tag_of(k) for k in design.models["acquisition"]["kernels"]} == {"imaging"}
    for model in design.models.values():
        assert all(tag_of(k) != "leakrisk" for k in model["kernels"])
    assert "syn_leak" not in design.family_spaces
    assert any(k["kind"] == "mmd" for k in design.kernels)
    assert {"A", "B", "uniform_A", "uniform_B", "cross_A", "cross_B", "acquisition"} <= set(design.models)
    plain = harness.build_design(design.crops, [design.classes[c] for c in design.y], design.groups, {}, [], CFG)
    assert not plain.models                                             # nothing to score, nothing invented
    assert sorted(design.family_candidates) == sorted(design.family_spaces)
    cfg = copy.deepcopy(CFG)                                            # a replaced legacy family leaves the models and the candidates
    cfg["legacy"] = {"syn_acq": {"replaced_by": ["syn_ma"]}}
    spaces = [SimpleNamespace(key=s["key"], family=s["family"], tag=s["tag"], X=s["X"], tile_sets=[]) for s in design.spaces]
    old = harness.build_design(design.crops, [design.classes[c] for c in design.y], design.groups, {}, spaces, cfg)
    assert "syn_acq" in old.family_spaces and "syn_acq" not in old.family_candidates
    assert "syn_acq" not in {old.spaces[old.kernels[k]["space"]]["family"] for k in old.models["A"]["kernels"]}
    cfg = copy.deepcopy(CFG)                                            # the Phase 2 hook: spaces listed by key or pattern leave a model
    cfg["models"]["B"]["exclude_spaces"] = ["syn_mix|*"]
    cut = harness.build_design(design.crops, [design.classes[c] for c in design.y], design.groups, {}, spaces, cfg)
    assert {cut.spaces[cut.kernels[k]["space"]]["family"] for k in cut.models["B"]["kernels"]} == {"syn_mat"}
    assert "syn_mix" in {cut.spaces[cut.kernels[k]["space"]]["family"] for k in cut.models["A"]["kernels"]}


# ----------------------------------------------------------------------------------------------------
# the numbers
# ----------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def syn_run(syn):
    design, cfg = syn
    return harness.run(design, cfg, n_boot=60, n_null_a=40, n_null_b=10)


def test_real_signal_is_found_and_shuffled_labels_are_chance(syn_run):
    res, oof = syn_run
    for model in ("A", "B"):
        row = res["results"]["loso13"][model]
        assert row["ba"] > 0.6                                                                   # the planted signal is found
        assert abs(row["null_a"]["mean"] - 1 / 3) < 0.15 and row["null_a"]["p"] < 0.1            # relabelled images: one third
        assert row["ba_ci"][0] <= row["ba"] <= row["ba_ci"][1]
        assert np.array(row["confusion"]).sum() == res["meta"]["n_crops"]
    acq = res["results"]["loso13"]["acquisition"]                                                # imaging only carries no class signal here
    assert abs(acq["null_a"]["mean"] - 1 / 3) < 0.15 and acq["ba"] < 0.6
    assert abs(res["results"]["loso13"]["majority"]["ba"] - 1 / 3) < 1e-9
    assert "provenance_oracle" in res["results"]["loco_nbr"] and "provenance_oracle" not in res["results"]["loso13"]
    assert res["results"]["loso13"]["A"]["delta_ba_vs_acquisition"]["delta"] == pytest.approx(
        res["results"]["loso13"]["A"]["ba"] - acq["ba"], abs=1e-9)
    assert res["blind_model"]["chosen"] in ("A", "B")
    assert set(oof.split) == {"loso13", "loco_nbr"} and oof.groupby(["split", "model"]).crop.nunique().eq(31).all()
    assert np.allclose(oof[[f"p_{c}" for c in res["meta"]["classes"]]].sum(axis=1), 1.0)


def test_fully_shuffled_labels_give_one_third(syn):
    """Labels shuffled across all crops (not only renamed per image): balanced accuracy 0.33 +- 0.15 on average."""
    design, cfg = syn
    rng = np.random.default_rng(5)
    Y = np.stack([design.y] + [rng.permutation(design.y) for _ in range(30)])
    design = copy.deepcopy(design)
    for m in design.models.values():
        m["null"] = True
    _, _, out = _loso(design, cfg, Y)
    for name in ("A", "B", "uniform_A"):
        ba = harness.balanced_accuracy_many(out[name][0], Y)
        assert abs(ba[1:].mean() - 1 / 3) < 0.15, (name, ba[1:].mean())


def test_two_runs_give_identical_json(syn, syn_run, tmp_path):
    design, cfg = syn
    res1, oof1 = syn_run
    res2, oof2 = harness.run(design, cfg, n_boot=60, n_null_a=40, n_null_b=10)
    assert json.dumps(res1, sort_keys=True) == json.dumps(res2, sort_keys=True)
    harness.write(tmp_path / "a", res1, oof1)
    harness.write(tmp_path / "b", res2, oof2)
    for name in ("harness.json", "results.md", "oof_predictions.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    # results.md is built from the JSON and nothing else
    assert harness.render(json.loads((tmp_path / "a" / "harness.json").read_text())) == (tmp_path / "a" / "results.md").read_text()


def test_worker_processes_give_the_same_json(syn, syn_run):
    design, cfg = syn
    res, _ = harness.run(design, cfg, n_boot=60, n_null_a=40, n_null_b=10, workers=2)
    assert json.dumps(res, sort_keys=True) == json.dumps(syn_run[0], sort_keys=True)


def test_runs_without_resamples_or_permutations(syn, syn_run):
    """No bootstrap, no nulls: the point estimates are the same and the report still renders."""
    design, cfg = syn
    res, _ = harness.run(design, cfg, n_boot=0, n_null_a=0, n_null_b=0)
    for split in ("loso13", "loco_nbr"):
        for model in ("A", "B", "acquisition", "majority"):
            assert res["results"][split][model]["ba"] == syn_run[0]["results"][split][model]["ba"]
            assert res["results"][split][model]["confusion"] == syn_run[0]["results"][split][model]["confusion"]
    assert "null_a" not in res["results"]["loso13"]["A"] and res["results"]["loso13"]["A"]["ba_ci"] == [None, None]
    assert "LOSO-13" in harness.render(res)


def test_null_labellings():
    crops, labels, groups, _ = _table()
    classes = sorted(set(labels))
    y = np.array([classes.index(v) for v in labels])
    ya = harness.null_a_labels(y, groups, 3, 50, np.random.default_rng(0))
    for g in set(groups):                                              # Null A renames classes inside an image, nothing more
        idx = groups == g
        for row in ya:
            assert len(set(zip(y[idx], row[idx]))) == len(set(y[idx])) == len(set(row[idx]))
    assert len({tuple(r) for r in ya}) > 40
    yb, exact = harness.null_b_labels(y, groups, 1000, np.random.default_rng(0))
    pure = np.array([len(set(y[groups == g])) == 1 for g in groups])
    assert exact and len(yb) == 192 and len({tuple(r) for r in yb}) == 192     # 2 x 6 x 2 x 2 x 4 arrangements, the real one included
    assert (yb[:, pure] == y[pure]).all() and any((r == y).all() for r in yb)
    for g in set(groups):
        assert all(sorted(r[groups == g]) == sorted(y[groups == g]) for r in yb)
    yb2, exact2 = harness.null_b_labels(y, groups, 100, np.random.default_rng(0))
    assert not exact2 and len(yb2) == 100 and (yb2[:, pure] == y[pure]).all()


def test_alignf_and_metrics():
    rng = np.random.default_rng(0)
    V = np.linalg.qr(rng.standard_normal((40, 5)))[0].T               # five orthonormal "kernels"
    mu, fb = harness.alignf(V @ V.T, np.array([[0.0, 2.0, 0.0, 1.0, -3.0], [-1.0, -1.0, -1.0, -1.0, -1.0]]))
    assert np.allclose(mu[0], [0, 2 / 3, 0, 1 / 3, 0]) and not fb[0]  # weights follow the positive alignments
    assert fb[1] and np.allclose(mu[1], 0.2)                          # nothing aligned: equal weights, flagged
    V = rng.standard_normal((12, 30))                                 # correlated kernels: the weights maximise the alignment
    G, a = V @ V.T, V @ rng.standard_normal(30)
    mu, _ = harness.alignf(G, a[None])
    align = lambda w: (w @ a) / np.sqrt(w @ G @ w)                    # noqa: E731
    assert all(align(mu[0]) >= align(w) - 1e-9 for w in rng.dirichlet(np.ones(12) * 0.3, 3000))
    v = harness._nnls_fallback(G, a)                                  # the spare solver finds the same optimum
    assert np.allclose(v / v.sum(), mu[0], atol=1e-6)
    P = np.array([[0.8, 0.1, 0.1], [0.2, 0.7, 0.1], [0.6, 0.3, 0.1], [0.1, 0.1, 0.8]])
    m = harness.metrics(P, np.array([0, 1, 1, 2]), 3)
    assert m["ba"] == pytest.approx((1 + 0.5 + 1) / 3) and m["n_correct"] == 3
    assert m["confusion"] == [[1, 0, 0], [1, 1, 0], [0, 0, 1]]
    from sklearn.metrics import balanced_accuracy_score, log_loss, roc_auc_score
    y = rng.integers(0, 3, 60)
    P = rng.dirichlet(np.ones(3), 60)
    m = harness.metrics(P, y, 3)
    assert m["ba"] == pytest.approx(balanced_accuracy_score(y, P.argmax(1)))
    assert m["auc"] == pytest.approx(roc_auc_score(y, P, multi_class="ovr", average="macro"))
    assert m["logloss"] == pytest.approx(log_loss(y, P, labels=[0, 1, 2]))
    W = harness.bootstrap_weights(list("aabbbcdd"), 500, np.random.default_rng(0))
    assert W.shape == (500, 8) and (W[:, 0] == W[:, 1]).all() and (W[:, 2] == W[:, 4]).all()    # whole images move together
    assert (W.sum(axis=1) > 0).all() and W[:, [0, 2, 5, 6]].sum(axis=1).tolist() == [4.0] * 500  # 4 images drawn each time


# ----------------------------------------------------------------------------------------------------
# the assembler
# ----------------------------------------------------------------------------------------------------
def _fake_result(i):
    rng = np.random.default_rng(i)
    res = core.FeatureResult("fake")
    res.scalar("BSE", "anchored", 25, "mean", rng.normal(), tag="material")
    res.scalar("BSE", "anchored", 25, "noise_floor", rng.normal(), tag="imaging")
    res.scalar("SE", "raw", 25, "mean", rng.normal(), tag="leakrisk")
    res.block("Inlens", "harmonised", 50, "spectrum", rng.normal(size=(4, 2)), tag="mixed")
    res.tile_block("Inlens", "harmonised", 50, "tiles_a", rng.normal(size=(5, 3)), tag="mixed")
    res.tile_block("Inlens", "harmonised", 50, "tiles_b", rng.normal(size=(5, 2)), tag="mixed")
    res.tile_block("Inlens", "harmonised", 50, "token_grid", rng.normal(size=(2, 5000)), tag="mixed")     # too wide for a kernel
    return res


def test_assemble_tolerates_a_partial_bank(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "FEAT_DIR", tmp_path / "feat")
    monkeypatch.setattr(core, "STATUS_LOG", tmp_path / "_status.jsonl")
    crops = core.all_crops()
    for i, c in enumerate(crops[:2]):
        core.save_result(_fake_result(i), c)
    bank = assemble.load_bank(families=["fake", "nothing_here"])
    table = core.crops_table()
    assert bank.crops == tuple(table.site) and list(bank.y) == list(table.folder) and list(bank.groups) == list(table.source_image)
    fam = bank.families["fake"]
    assert not fam.complete() and fam.done["P0"].sum() == 2 and len(fam.scalars) == 2
    assert fam.blocks["P0"]["fake|Inlens|harmonised|50|spectrum"].shape == (31, 8)
    assert sum(t is not None for t in fam.tiles["P0"]["fake|Inlens|harmonised|50|tiles_a"]) == 2
    gaps = {(m["family"], m["what"]) for m in bank.missing}
    assert ("nothing_here", "no output on disk") in gaps and sum(m["family"] == "fake" and m["what"] == "not done" for m in bank.missing) == 29
    assert bank.spaces() == []                                          # an incomplete family is not scored
    assert "fake|Inlens|harmonised|50|token_grid" not in fam.tiles["P0"]         # the wide token grid stays on disk
    assert any("token_grid" in m["what"] and "5000 wide" in m["what"] for m in bank.missing)
    for i, c in enumerate(crops[2:], 2):
        core.save_result(_fake_result(i), c)
    bank = assemble.load_bank(families=["fake"])
    spaces = {s.key: s for s in bank.spaces()}
    assert set(spaces) == {"fake|BSE|anchored|material", "fake|BSE|anchored|imaging", "fake|SE|raw|leakrisk", "fake|Inlens|harmonised|mixed"}
    mixed = spaces["fake|Inlens|harmonised|mixed"]
    assert mixed.X.shape == (31, 8) and len(mixed.tile_sets) == 1 and mixed.tile_sets[0]["tiles"][0].shape == (5, 5)
    assert all(np.isfinite(s.X).all() and s.X.shape[0] == 31 for s in spaces.values())
    design = harness.build_design(bank.crops, bank.y, bank.groups, {}, bank.spaces(), CFG)
    assert all(design.spaces[design.kernels[k]["space"]]["tag"] != "leakrisk" for m in design.models.values() for k in m["kernels"])


def test_legacy_families_on_the_real_bank():
    """The two legacy families, if this machine has them: 26 non-edge tiles of 768 numbers, five imaging anchors."""
    bank = assemble.load_bank(families=[assemble.LEGACY_EMB, assemble.LEGACY_ACQ])
    if not (bank.families[assemble.LEGACY_EMB].complete() and bank.families[assemble.LEGACY_ACQ].complete()):
        pytest.skip("legacy embeddings or crop views are not on this machine")
    spaces = {s.key: s for s in bank.spaces()}
    assert set(spaces) == {"legacy_acq|BSE|raw|imaging", "legacy_acq|Inlens|raw|imaging",
                           "legacy_dinov2s|BSE|harmonised|mixed", "legacy_dinov2s|Inlens|harmonised|mixed"}
    emb = spaces["legacy_dinov2s|BSE|harmonised|mixed"]
    assert emb.pooled and emb.X.shape == (31, 768) and all(t.shape == (26, 768) for t in emb.tile_sets[0]["tiles"])
    assert spaces["legacy_acq|BSE|raw|imaging"].X.shape == (31, 4)
    assert not any(core.forbidden_tokens(n) for fam in bank.families.values() for n in fam.catalog.name)
    anchors = core.load_crop(core.SMOKE_CROPS[0]).anchors                                        # the fast reader agrees with the Crop
    assert assemble.crop_anchors(core.SMOKE_CROPS[0]) == anchors


# ----------------------------------------------------------------------------------------------------
# the pieces against independent implementations
# ----------------------------------------------------------------------------------------------------
def test_scale_pca_and_centring_match_sklearn():
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import KernelCenterer, RobustScaler
    rng = np.random.default_rng(0)
    for n, d in ((24, 6), (24, 60)):                                   # fewer and more columns than rows
        X = rng.standard_normal((n, d)) * rng.uniform(0.1, 5, d) + rng.uniform(-3, 3, d)
        tr = np.arange(18)
        S, st = harness._scale_pca(X, tr, 16, 1e9)                     # no clipping, so sklearn can follow
        Z = RobustScaler().fit(X[tr]).transform(X) * 1.349
        S2 = PCA(S.shape[1]).fit(Z[tr]).transform(Z)
        assert S.shape[1] == min(16, d, len(tr) - 1) and np.allclose(S @ S.T, S2 @ S2.T)
        # fitted on the training rows only: other rows can be anything
        X2 = X.copy()
        X2[18:] = 1e3
        assert _same(st, harness._scale_pca(X2, tr, 16, 1e9)[1])
        K = np.exp(-harness._sqdist(S) / 7.0)
        mine, ok, fin = harness._finish(K.copy(), tr)
        ref = KernelCenterer().fit(K[np.ix_(tr, tr)]).transform(K[:, tr])
        assert ok and np.allclose(mine[:, tr] * fin["trace"], ref)
        assert np.diag(mine)[tr].mean() == pytest.approx(1.0)
    S, _ = harness._scale_pca(np.c_[np.ones(10), np.arange(10.0)], np.arange(10), 16, 10.0)   # a constant column is dropped
    assert S.shape == (10, 1)
    assert harness._scale_pca(np.ones((10, 3)), np.arange(10), 16, 10.0) == (None, None)


def test_mmd_kernel_is_the_mean_over_tile_pairs(syn):
    design, cfg = syn
    k = next(i for i, kn in enumerate(design.kernels) if kn["kind"] == "mmd")
    space = design.spaces[design.kernels[k]["space"]]
    ts = space["tile_sets"][0]
    tr = np.flatnonzero(design.groups != "img01")
    res = harness.fit_fold(design, tuple(tr), design.y[None], cfg, with_state=True)
    st = res["state"][design.kernels[k]["name"]]
    Z = np.clip((ts["T"][:, st["keep"]] - st["median"][st["keep"]]) / st["scale"][st["keep"]], -10, 10) - st["mean"]
    S = Z @ st["components"].T
    n = design.n
    raw = np.zeros((n, n))
    for a in range(n):
        for b in range(n):
            A, B = S[ts["owner"] == a], S[ts["owner"] == b]
            raw[a, b] = np.mean([np.exp(-((u - v) ** 2).sum() / (2 * st["sigma"] ** 2)) for u in A for v in B])
    ref, ok, _ = harness._finish(raw, tr)
    assert ok and np.allclose(res["K"][k], ref)
    train_tiles = S[np.isin(ts["owner"], tr)]                          # the bandwidth is the median distance between training tiles
    d = np.sqrt(((train_tiles[:, None] - train_tiles[None]) ** 2).sum(-1))[np.triu_indices(len(train_tiles), 1)]
    assert st["sigma"] == pytest.approx(np.median(d))


def _plain_fold(design, cfg, train, test, y, kernels, groups):
    """One fold written the slow, obvious way: weights, class means, inner LOSO for the temperature, probabilities."""
    C = len(design.classes)

    def distances(tr, rows):
        K, valid = harness.fit_kernels(design, np.array(tr), cfg)
        idx = [k for k in kernels if valid[k]]
        H = np.eye(len(tr)) - 1.0 / len(tr)
        Yb = np.stack([(y[tr] == c) / max((y[tr] == c).sum(), 1) for c in range(C)], axis=1)
        target = H @ (Yb @ Yb.T) @ H
        G = np.array([[(K[a][np.ix_(tr, tr)] * K[b][np.ix_(tr, tr)]).sum() for b in idx] for a in idx])
        a = np.array([(K[k][np.ix_(tr, tr)] * target).sum() for k in idx])
        mu, _ = harness.alignf(G, a[None])
        Kc = sum(w * K[k] for w, k in zip(mu[0], idx))
        D = np.zeros((len(rows), C))
        for j, x in enumerate(rows):
            for c in range(C):
                members = [i for i in tr if y[i] == c]
                D[j, c] = Kc[x, x] - 2 * np.mean([Kc[x, i] for i in members]) + np.mean([[Kc[i, k] for k in members] for i in members])
        return D

    inner_D, inner_y = [], []
    for g in sorted(set(groups[list(train)])):
        val = [i for i in train if groups[i] == g]
        rest = [i for i in train if groups[i] != g]
        inner_D.append(distances(rest, val))
        inner_y += list(y[val])
    inner_D, inner_y = np.concatenate(inner_D), np.array(inner_y)
    losses = []
    for tau in harness.tau_grid(cfg):
        P = np.exp(-inner_D / tau - (-inner_D / tau).max(axis=1, keepdims=True))
        P /= P.sum(axis=1, keepdims=True)
        losses.append(-np.log(np.clip(P[np.arange(len(inner_y)), inner_y], 1e-6, 1)).mean())
    tau = harness.tau_grid(cfg)[int(np.argmin(losses))]
    D = distances(list(train), list(test))
    P = np.exp(-D / tau - (-D / tau).max(axis=1, keepdims=True))
    P = np.clip(P / P.sum(axis=1, keepdims=True), 1e-6, 1)
    return P / P.sum(axis=1, keepdims=True), tau


def test_out_of_fold_probabilities_match_a_plain_nested_loop(syn, syn_run):
    """The fold bookkeeping (which fit scores which crop, which inner fits choose the temperature) against a slow rewrite."""
    design, cfg = syn
    res, oof = syn_run
    splits = harness.make_splits(design.groups, design.neighbours)
    cols = [f"p_{c}" for c in design.classes]
    for split, picks in (("loso13", (3, 6)), ("loco_nbr", (7, 20))):
        for f in picks:
            fold = splits[split][f]
            for model in ("A", "B"):
                P, tau = _plain_fold(design, cfg, fold["train"], fold["test"], design.y, design.models[model]["kernels"], design.groups)
                got = oof[(oof.split == split) & (oof.model == model)].set_index("crop").loc[[design.crops[i] for i in fold["test"]]]
                assert np.allclose(got[cols].to_numpy(), P, atol=1e-9), (split, f, model)
                assert np.allclose(got.tau.to_numpy(), tau)
                assert res["results"][split][model]["tau"][f] == pytest.approx(tau)
