"""Leakage guards for the feature bank: nothing a model can see may carry provenance.

    pytest tests/test_bank_leakage.py -q                     # everything that can run locally
    pytest tests/test_bank_leakage.py -q -k "not family"     # the guards that run no family (about 3 minutes)
    pytest tests/test_bank_leakage.py -q -k phase            # the tests of one family
    pytest tests/test_bank_leakage.py -q --gpu               # also the GPU families (set BANK_EMB_PROFILE as for the stored runs)
    pytest tests/test_bank_leakage.py -q -rs                 # also print why a test was skipped

The guards, in the order of the brief (step 11):

    names         no provenance word in any stored column, block or tile-array name; no stored column that copies
                  the image height or width
    padding       the same window inside an image of height 1612, 2060 or 2316 gives the same Crop (exactly); inside
                  a narrower image it does not, a known gap that is bounded here and recorded in CONTRACT_REQUESTS.md
    renaming      the same pixels under another file name, folder and crop id give the same Crop and the same features
    edges         random values in the 8 outer columns change nothing
    splits        no source image on both sides of a harness split, inner folds included; held-out crops reach no
                  fitted step; SE / leakrisk spaces reach no model                       (needs bank/harness.py)
    shuffling     shuffled labels give balanced accuracy 0.33 +/- 0.15                   (needs bank/harness.py)
    lifted black  crops x7u69zsw, kbdh4tri, tuy3zymq and 71vgq3fw keep their material features when the black level moves
    determinism   a Crop, a family, the harness and the label-free report come out the same twice

A test that needs something another lane has not written or run yet is skipped with the reason (-rs prints it); it
never passes silently. Provenance (meta/, file names) is read here to check the bank, never to make a feature.
"""
import functools
import importlib
import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bank import core, families

ROOT = Path(__file__).resolve().parents[1]
H = core.H                                           # features/_common/harmonise.py: crop_box lives there
DETS = core.DETECTORS + core.LEAKRISK_DETECTORS
HEIGHTS = (1612, 2060, 2316)                         # the shortest image, the lifted-black image, the tallest image
LIFTED = ("x7u69zsw", "kbdh4tri", "tuy3zymq", "71vgq3fw")     # black level lifted by the microscope: imaging, not material
LIFTED_SMOKE = "kbdh4tri"
NAME = re.compile(r"^[a-z0-9_]+\|(BSE|Inlens|BSExInlens|SE)\|[a-z0-9_]+\|\d+\|[A-Za-z0-9_.+-]+$")
MIN_SPREAD_CROPS = 10                                # crops needed before a between-crop spread means anything
ROBUST, FRAGILE = 0.25, 1.0                          # the brief's imaging-sensitivity bands, in robust SDs between crops
CHANCE, CHANCE_BAND = 1 / 3, 0.15


# ----------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=2)
def _raw(crop_id):
    """The three raw images of one crop (2D uint8, read-only)."""
    folder = core.crops_table().set_index("site").folder[crop_id]
    return {d: core.load_grey(core.raw_path(folder, crop_id, d)) for d in DETS}


def _differences(got, want):
    """Every way two Crops differ. Empty = the same pixels, anchors, phase maps and noise."""
    out = [f"raw {d}" for d in DETS if not np.array_equal(got.raw[d], want.raw[d])]
    out += [f"anchor {k}: {got.anchors.get(k)!r} != {want.anchors.get(k)!r}"
            for k in sorted(set(got.anchors) | set(want.anchors)) if got.anchors.get(k) != want.anchors.get(k)]
    for k in sorted(set(got.masks) | set(want.masks)):
        if k not in got.masks or k not in want.masks:
            out.append(f"mask {k}: missing on one side")
        elif not np.array_equal(got.masks[k], want.masks[k]):
            out.append(f"mask {k}: {int((got.masks[k] != want.masks[k]).sum())} px differ")
    out += [f"view {d} harmonised" for d in core.DETECTORS
            if not np.array_equal(got.view(d, "harmonised"), want.view(d, "harmonised"))]
    got._cache.clear()                                   # 150 MB of views per Crop: the laptop is shared
    want._cache.clear()
    return out


def _fresh(crop):
    """The same Crop with an empty view cache, so one family's views never reach the next one."""
    return core.Crop(crop.raw, crop.anchors, crop.masks, crop.pert, crop._id)


def _families(runs_on):
    """Families by where they run. One that fails to import counts as CPU, so its own test fails and nobody else's."""
    out = []
    for f in families.family_names():
        try:
            kind = families.load(f).RUNS_ON
        except Exception:
            kind = "cpu"
        if kind == runs_on:
            out.append(f)
    return out


def _stored_families():
    return sorted(p.name for p in core.FEAT_DIR.iterdir() if p.is_dir()) if core.FEAT_DIR.exists() else []


def _gpu_ok(name, request):
    try:
        gpu = families.load(name).RUNS_ON == "gpu"
    except Exception:
        gpu = False
    return not gpu or request.config.getoption("--gpu")


def _provenance_parts(name):
    """Name parts that would give provenance away: core's forbidden tokens, plus their plural and numbered forms
    (rows, cols, batch1, fold3), which core.forbidden_tokens does not see."""
    bad = set(core.forbidden_tokens(name))
    for token in re.split(r"[^a-z0-9]+", name.lower()):
        stem = token.rstrip("0123456789")
        for form in (stem, stem[:-1] if stem.endswith("s") else stem, stem[:-2] if stem.endswith("es") else stem):
            if form in core.FORBIDDEN_TOKENS and token not in core.FORBIDDEN_TOKENS and not token.isdigit():
                bad.add(token)
    return bad


def _stored_names():
    """({name: (family, where it was first seen)}, [finished files that cannot be read]) for every column, block and tile
    array of every finished crop version under processed/bank/feat. Only the file headers are read."""
    import pyarrow.parquet as pq
    names, unreadable = {}, []
    for family in _stored_families():
        folder = core.FEAT_DIR / family
        if (folder / "catalog.parquet").exists():
            try:
                for n in pd.read_parquet(folder / "catalog.parquet").name:
                    names.setdefault(str(n), (family, "catalog"))
            except Exception:                              # another lane is replacing it right now: the files below still count
                pass
        for f in sorted(folder.glob("*/*.parquet")) + sorted(folder.glob("*/*.npz")):
            if f.name.startswith(".") or not f.with_suffix(".done").exists():      # a job is writing it: not in the bank yet
                continue
            try:
                if f.suffix == ".parquet":
                    found = [n for n in pq.read_schema(f).names if not n.startswith("__index_level_")]
                else:
                    with np.load(f) as z:
                        found = list(z.files)
            except Exception as e:
                unreadable.append(f"{f.relative_to(core.FEAT_DIR)} ({type(e).__name__})")
                continue
            for n in found:
                names.setdefault(str(n), (family, str(f.relative_to(core.FEAT_DIR))))
    return names, unreadable


def _robust_sd(values):
    """Per-column robust spread between crops: 1.4826 MAD, or the SD where the MAD is zero."""
    values = np.asarray(values, float)
    mad = 1.4826 * np.median(np.abs(values - np.median(values, axis=0)), axis=0)
    return np.where(mad > 0, mad, values.std(axis=0))


# ----------------------------------------------------------------------------------------------------
# names: no provenance word in anything stored
# ----------------------------------------------------------------------------------------------------
def test_provenance_words_are_caught():
    """The name check has teeth: every provenance word is refused in every position, also plural or numbered."""
    for word in sorted(core.FORBIDDEN_TOKENS):
        for name in (f"fam|BSE|raw|25|{word}", f"fam|BSE|raw|25|mean_{word}", f"fam|BSE|raw|25|{word.upper()}_x",
                     f"fam|BSE|{word}|25|mean", f"fam|BSE|raw|25|p50.{word}"):
            assert core.forbidden_tokens(name), name
            assert _provenance_parts(name), name
    for name in ("fam|BSE|raw|25|tile_rows", "fam|BSE|raw|25|cols_mean", "fam|BSE|raw|25|batch2_dist", "fam|BSE|raw|25|fold3",
                 "fam|BSE|raw|25|n_images", "fam|BSE|raw|25|heights"):
        assert _provenance_parts(name), name
    for name in ("phase|BSE|phase|25|void_frac_mid", "glcm_lbp|Inlens|harmonised|50|contrast_d4_a90", "psd|BSE|anchored|100|slope_x",
                 "emb_x|BSE|anchored|200|cls_b11", "orient|Inlens|harmonised|25|coherence_p50", "fbank|BSE|harmonised|25|gabor_l8_t3"):
        assert not _provenance_parts(name), name


def test_no_forbidden_name_is_stored():
    names, unreadable = _stored_names()
    if not names and not unreadable:
        pytest.skip("no family has stored anything under processed/bank/feat yet")
    problems = [f"{f}: marked done but not readable, so its names cannot be checked" for f in unreadable]
    for name, (family, where) in sorted(names.items()):
        bad = _provenance_parts(name)
        if bad:
            problems.append(f"{name} ({where}): provenance word(s) {sorted(bad)}")
        if not NAME.match(name) or not name.startswith(family + "|"):
            problems.append(f"{name} ({where}): not {family}|det|view|scale_nm|stat")
    for family in _stored_families():
        try:
            cat = core.load_catalog(family)
        except Exception:
            continue
        for row in cat.itertuples():
            if row.tag not in core.TAGS:
                problems.append(f"{row.name}: tag {row.tag!r}")
            if row.detector in core.LEAKRISK_DETECTORS and row.tag != "leakrisk":
                problems.append(f"{row.name}: from {row.detector} but tagged {row.tag!r}, not leakrisk")
            if _provenance_parts(str(row.layer)) or _provenance_parts(str(row.view)):
                problems.append(f"{row.name}: provenance word in layer {row.layer!r} or view {row.view!r}")
    assert not problems, f"{len(problems)} stored name(s) break the rules:\n  " + "\n  ".join(problems[:25])


def test_no_stored_column_copies_provenance():
    """Whatever a column is called, its values must come from pixels. Two fingerprints of provenance are refused:
    a column that is a monotonic function of the image height or width, and a material or mixed column that is
    exactly equal for all crops of a source image while differing between images (pixels of different crops never
    agree to the last digit; a file tag, a size or a name does)."""
    meta = pd.read_csv(core.META_DIR / "analysis_only.csv").set_index("site")
    problems, checked = [], 0
    for family in _stored_families():
        try:
            table, catalog = core.load_scalars(family), core.load_catalog(family)
        except Exception:
            continue
        if len(table) < MIN_SPREAD_CROPS or table.shape[1] == 0:
            continue
        table = table.set_axis([crop for _, crop in table.index]).astype(float)
        table = table.loc[:, table.nunique() > 1]
        checked += table.shape[1]
        for what in ("height_px", "width_px"):
            rho = table.rank().corrwith(meta.loc[table.index, what].rank())
            problems += [f"{c}: Spearman {r:+.3f} with the image {what[:-3]}" for c, r in rho.items() if abs(r) > 0.98]
        image = meta.loc[table.index, "source_image"]
        several = image.map(image.value_counts()) > 1                      # crops whose source image has another stored crop
        if image[several].nunique() >= 5:
            tag = dict(zip(catalog.name, catalog.tag))
            levels = table[several].groupby(image[several]).nunique()      # distinct values per image, per column
            first = table[several].groupby(image[several]).first()
            for c in table.columns:
                if tag.get(c) in ("material", "mixed") and (levels[c] == 1).all() and first[c].nunique() >= 5:
                    problems.append(f"{c}: identical for all crops of every source image and different between images")
    if not checked:
        pytest.skip(f"no family has P0 scalars for {MIN_SPREAD_CROPS} crops yet (only the smoke crops are run locally)")
    assert not problems, "\n  ".join(problems[:25])


# ----------------------------------------------------------------------------------------------------
# padding, edges, determinism: what reaches a Crop
# ----------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module", params=core.SMOKE_CROPS)
def smoke(request):
    """(crop id, the three raw images, the stored Crop)."""
    return request.param, _raw(request.param), core.load_crop(request.param)


def _in_height(img, height, rng):
    """The window rows of `img` put where crop_box looks for them in an image `height` px high; noise everywhere else."""
    r0, r1, _, _ = H.crop_box(*img.shape)
    q0, q1, _, _ = H.crop_box(height, img.shape[1])
    assert q1 - q0 == r1 - r0 == core.WINDOW[0]
    out = rng.integers(0, 256, (height, img.shape[1]), dtype=np.uint8)
    out[q0:q1] = img[r0:r1]
    return out


@pytest.mark.parametrize("height", HEIGHTS)
def test_image_height_does_not_reach_a_crop(smoke, height):
    """The image height marks the source image (18 of 31 crops have a height unique to one folder). Put the same
    window in an image of another height, with noise in every row outside it: the Crop must not change at all."""
    crop_id, raw, stored = smoke
    rng = np.random.default_rng(height)
    padded = {d: _in_height(img, height, rng) for d, img in raw.items()}
    assert all(img.shape[0] == height for img in padded.values())
    again = core.make_crop(padded["BSE"], padded["Inlens"], padded["SE"])
    assert again.shape == core.WINDOW
    found = _differences(again, stored)
    assert not found, (f"{crop_id} in a {height} px image differs from the stored Crop: {found[:6]} "
                       "-> bank.core.make_crop depends on the image height (record it in bank/CONTRACT_REQUESTS.md)")


def test_outer_columns_do_not_reach_a_crop(smoke):
    """The 8 trimmed columns each side carry the green end-of-strip marker in 13 crops: they never reach a Crop."""
    crop_id, raw, stored = smoke
    rng = np.random.default_rng(8)
    noisy = {d: img.copy() for d, img in raw.items()}
    for img in noisy.values():
        img[:, :8] = rng.integers(0, 256, (img.shape[0], 8))
        img[:, -8:] = rng.integers(0, 256, (img.shape[0], 8))
    assert not np.array_equal(noisy["BSE"], raw["BSE"])
    found = _differences(core.make_crop(noisy["BSE"], noisy["Inlens"], noisy["SE"]), stored)
    assert not found, f"{crop_id}: the outer 8 columns reach the Crop: {found[:6]}"


@pytest.mark.parametrize("width", (6996, 6960))
def test_image_width_does_not_reach_a_crop(smoke, width):
    """Contract version 2: anchors, noise and phase maps are made on exactly the columns a Crop holds, so the same
    window inside a narrower image (the data holds widths 7000, 6996 and 6960) gives an identical Crop.
    (Version 1 handed the whole image to harmonise, so up to 20 columns each side took part: see CONTRACT_REQUESTS.md.)"""
    crop_id, raw, stored = smoke
    full = raw["BSE"].shape[1]
    if full <= width:
        pytest.skip(f"{crop_id} is only {full} px wide")
    cut = (full - width) // 2
    narrow = {d: np.ascontiguousarray(img[:, cut:full - cut]) for d, img in raw.items()}
    again = core.make_crop(narrow["BSE"], narrow["Inlens"], narrow["SE"])
    assert all(np.array_equal(again.raw[d], stored.raw[d]) for d in DETS), "not the same window: the test is wrong"
    found = _differences(again, stored)
    assert not found, f"{crop_id}: the image width reaches the Crop: {found[:6]}"


def test_make_crop_is_deterministic(smoke):
    """A Crop made now equals the one stored by another process, noise top-up included, whatever id it is given."""
    crop_id, raw, stored = smoke
    again = core.make_crop(raw["BSE"], raw["Inlens"], raw["SE"], crop_id="another-id")
    found = _differences(again, stored)
    assert not found, f"{crop_id}: {found[:6]}"
    assert again.anchors["seed"] == stored.anchors["seed"]            # the noise seed comes from the pixels alone


# ----------------------------------------------------------------------------------------------------
# renaming: the same pixels under another file name, folder and id
# ----------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def renamed(tmp_path_factory):
    """The first smoke crop's files under another folder, id and SE/ETD spelling, made into a Crop by the same code
    as every stored crop (core.build_views + core.load_crop). Returns (true id, the renamed Crop)."""
    crop_id = core.SMOKE_CROPS[0]
    folder = core.crops_table().set_index("site").folder[crop_id]
    tmp = tmp_path_factory.mktemp("renamed")
    new_id, new_folder = "zz0zz0zz", "Batch_9"
    (tmp / "data" / new_folder).mkdir(parents=True)
    for det in DETS:
        src = core.raw_path(folder, crop_id, det)
        spelled = {"ETD": "SE", "SE": "ETD"}.get(src.stem.split("_")[-1], det)      # the SE/ETD spelling marks one source image
        dst = tmp / "data" / new_folder / f"img_{new_id}_{spelled}.tif"
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)
    table = pd.DataFrame({"site": [new_id], "folder": [new_folder], "source_image": ["img99"]})
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys.modules[core.raw_path.__module__], "DATA_DIR", tmp / "data")
        patch.setattr(core, "crops_table", lambda: table)
        patch.setattr(core, "VIEWS_DIR", tmp / "views")
        core.build_views(new_id)
        crop = core.load_crop(new_id, build=False)
    shutil.rmtree(tmp, ignore_errors=True)
    return crop_id, crop


def test_renamed_files_give_the_same_crop(renamed):
    crop_id, crop = renamed
    assert crop._id != crop_id                                         # it really went in under another name
    found = _differences(crop, core.load_crop(crop_id))
    assert not found, f"{crop_id} under another file name, folder and id: {found[:6]}"


def _feature_differences(res, scalars, arrays):
    """How a FeatureResult differs from stored (or freshly made) scalars and arrays; the tolerances of the contract test."""
    if set(res.scalars) != set(scalars.index):
        return [f"the column sets differ ({len(set(res.scalars) ^ set(scalars.index))} names)"]
    got = np.array([res.scalars[k] for k in scalars.index], float)
    bad = ~np.isclose(got, scalars.to_numpy(float), rtol=1e-6, atol=1e-9)
    out = [f"{int(bad.sum())} of {bad.size} scalars differ, e.g. {list(scalars.index[bad][:5])}"] if bad.any() else []
    for k, v in {**res.blocks, **res.tiles}.items():
        if k not in arrays or v.shape != arrays[k].shape or not np.allclose(v, arrays[k], rtol=1e-4, atol=1e-5):
            out.append(f"array {k} differs")
    return out


def _check_renamed(name, renamed, against_stored=True):
    """The family on the renamed crop against the stored run of the true name (one run). If they differ, the family
    is run on the true name too: only a difference between those two runs is a name effect (or a family that does
    not repeat). Stored results older than the family file are the contract test's finding, and only warned about."""
    crop_id, crop = renamed
    module = families.load(name)
    res = module.extract(_fresh(crop), dict(module.DEFAULT_CFG))
    core.validate(res)
    stale = None
    if against_stored and core.is_done(name, crop_id):
        stale = _feature_differences(res, core.load_scalars(name, crops=[crop_id]).iloc[0], core.load_arrays(name, crop_id))
        if not stale:
            return
    ref = module.extract(core.load_crop(crop_id), dict(module.DEFAULT_CFG))
    found = _feature_differences(res, pd.Series(ref.scalars, dtype=float), {**ref.blocks, **ref.tiles})
    assert not found, f"{name} on {crop_id}: the renamed crop and the true name give different output: {found[:6]}"
    if stale:
        import warnings
        warnings.warn(f"{name}: the stored run of {crop_id} differs from a run made now ({stale[0]}); the family file changed "
                      f"or the run came from another device. Rerun it with --force.")


@pytest.mark.parametrize("name", _families("cpu"))
def test_cpu_family_output_ignores_names(name, renamed):
    """The family run on the renamed crop gives what is stored for the true name: no name reaches a feature, and the
    family is deterministic."""
    _check_renamed(name, renamed)


@pytest.mark.parametrize("name", _families("gpu"))
def test_gpu_family_output_ignores_names(name, renamed, request):
    """Renamed against true name, both run here: a stored run may come from another device or precision (cloud bf16
    against local float32), which is the contract test's business, not a name effect."""
    if not request.config.getoption("--gpu"):
        pytest.skip("pass --gpu to test GPU families")
    _check_renamed(name, renamed, against_stored=False)


# ----------------------------------------------------------------------------------------------------
# lifted black level: imaging, never material
# ----------------------------------------------------------------------------------------------------
def _assert_same_material(moved, p0, what):
    """The crop-level material quantities of two versions of one crop agree: phase maps, thresholds, anchored BSE."""
    assert abs(moved.anchors["scale"] / p0.anchors["scale"] - 1) < 1e-3, f"{what}: the graphite scale moved"
    for k in ("void_threshold", "bright_threshold", "bse_noise_sigma"):
        assert abs(moved.anchors[k] - p0.anchors[k]) < 1e-3, f"{what}: {k} moved from {p0.anchors[k]} to {moved.anchors[k]}"
    for k in core.PHASES:
        changed = float((moved.masks[k] != p0.masks[k]).mean())
        assert changed < 1e-4, f"{what}: {changed:.2e} of the {k} map changed"
    worst = float(np.abs(moved.view("BSE", "anchored") - p0.view("BSE", "anchored")).max())
    drift = float(np.abs(moved.view("Inlens", "anchored") - p0.view("Inlens", "anchored")).mean())
    moved._cache.clear()
    p0._cache.clear()
    assert worst < 1e-3, f"{what}: anchored BSE moved by up to {worst:.2e} graphite units"
    assert drift < 1e-3, f"{what}: rank-normalised Inlens moved by {drift:.2e} on average"


@pytest.mark.parametrize("crop_id", LIFTED)
def test_lifted_black_crop_is_unchanged_by_black25(crop_id):
    """Stored black25 against stored P0 for each lifted-black crop: the black anchor follows the shift (it is an
    imaging quantity) and nothing a material feature is built on moves."""
    p0, moved = core.load_crop(crop_id), core.load_crop(crop_id, "black25")
    assert abs(moved.anchors["black"] - p0.anchors["black"] - 25) < 0.5, "black25 did not shift the black anchor by 25"
    assert p0.anchors["black"] > 15, f"{crop_id} is listed as lifted but its black level is {p0.anchors['black']:.1f}"
    _assert_same_material(moved, p0, f"{crop_id} black25 vs P0")


@pytest.mark.parametrize("lift", (9, 40))
def test_black_level_jitter_leaves_a_lifted_crop_unchanged(lift):
    """Any upward black-level shift, different per detector, on the lifted smoke crop (noise seed held, as build_views does)."""
    raw, p0 = _raw(LIFTED_SMOKE), core.load_crop(LIFTED_SMOKE)
    assert int(p0.raw["BSE"].max()) + lift <= 255                        # a pure shift: no BSE pixel of the window saturates
    shift = {"BSE": lift, "Inlens": lift // 3, "SE": lift // 2}
    moved = {d: np.clip(img.astype(np.int16) + shift[d], 0, 255).astype(np.uint8) for d, img in raw.items()}
    again = core.make_crop(moved["BSE"], moved["Inlens"], moved["SE"], seed=p0.anchors["seed"])
    assert abs(again.anchors["black"] - p0.anchors["black"] - lift) < 0.5
    _assert_same_material(again, p0, f"{LIFTED_SMOKE} with the black level lifted by {lift}")


def _material_names(name):
    try:
        cat = core.load_catalog(name)
    except Exception:
        pytest.skip(f"{name} has stored nothing yet")
    cat = cat[(cat.tag == "material") & ~cat.detector.isin(core.LEAKRISK_DETECTORS)]
    if cat.empty:
        pytest.skip(f"{name} has no output tagged material")
    return list(cat.name[cat.kind == "scalar"]), list(cat.name[cat.kind != "scalar"])


@pytest.mark.parametrize("name", families.family_names())
def test_family_material_features_stable_on_lifted_black(name, request):
    """Material-tagged output of the lifted-black crops must not move with the black level.

    Stored black25 against stored P0 where the family has both. Otherwise the family is run here on the stored
    black25 view of the lifted smoke crop and compared with its stored P0 result.
    With P0 for at least 10 crops, a scalar may move by at most 1 robust SD between crops (not FRAGILE) and the
    median material scalar by less than 0.25 (ROBUST); before that, by at most 2 % of its size. Arrays: 2 % of their norm.
    """
    scalars, arrays = _material_names(name)
    crops = [c for c in LIFTED if core.is_done(name, c) and core.is_done(name, c, "black25")]
    if crops:
        moved = core.load_scalars(name, perts=("black25",), crops=crops)
        moved_arrays = {c: core.load_arrays(name, c, "black25") for c in crops} if arrays else {}
    elif core.is_done(name, LIFTED_SMOKE):
        if not _gpu_ok(name, request):
            pytest.skip(f"{name} has no stored black25 for a lifted crop and runs on a GPU: pass --gpu")
        module = families.load(name)
        res = module.extract(core.load_crop(LIFTED_SMOKE, "black25"), dict(module.DEFAULT_CFG))
        crops = [LIFTED_SMOKE]
        moved = pd.DataFrame.from_dict({("black25", LIFTED_SMOKE): res.scalars}, orient="index")
        moved_arrays = {LIFTED_SMOKE: {**res.blocks, **res.tiles}}
    else:
        pytest.skip(f"{name} has neither a stored black25 run for a lifted crop nor a stored P0 run of {LIFTED_SMOKE}: "
                    f"run `python -m bank.run fam {name} --sites smoke --perts P0` first")
    p0_all = core.load_scalars(name)
    p0_all = p0_all.set_axis([crop for _, crop in p0_all.index])
    moved = moved.set_axis([crop for _, crop in moved.index])
    scalars = [s for s in scalars if s in p0_all.columns and s in moved.columns]
    problems = []
    if scalars:
        delta = (moved.loc[crops, scalars] - p0_all.loc[crops, scalars]).abs().to_numpy(float)
        if len(p0_all) >= MIN_SPREAD_CROPS:
            spread = _robust_sd(p0_all[scalars])
            shift = np.where(spread > 0, delta / np.where(spread > 0, spread, 1), np.where(delta > 1e-9, np.inf, 0.0)).max(axis=0)
            problems += [f"{s}: moves {v:.2f} robust SD" for s, v in zip(scalars, shift) if v > FRAGILE]
            if float(np.median(shift)) >= ROBUST:
                problems.append(f"the median material scalar moves {np.median(shift):.2f} robust SD (limit {ROBUST})")
        else:
            size = p0_all[scalars].abs().max(axis=0).to_numpy(float)
            worst = (delta / (0.02 * size + 1e-9)).max(axis=0)
            problems += [f"{s}: moves {2 * v:.1f} % of its size" for s, v in zip(scalars, worst) if v > 1]
    for c in crops:
        p0_arrays = core.load_arrays(name, c) if arrays else {}
        for k in arrays:
            if k in p0_arrays and k in moved_arrays[c]:
                a, b = np.asarray(p0_arrays[k], float), np.asarray(moved_arrays[c][k], float)
                if a.shape != b.shape or np.linalg.norm(b - a) > 0.02 * np.linalg.norm(a) + 1e-9:
                    problems.append(f"{k} on {c}: moves {np.linalg.norm(b - a) / (np.linalg.norm(a) + 1e-12):.3f} of its norm")
    assert not problems, (f"{name}: material-tagged output of the lifted-black crop(s) {crops} moves with the black level "
                          f"(tag it imaging or mixed, or build it on the anchored views; if the family file changed between "
                          f"the two stored runs, rerun both with --force):\n  " + "\n  ".join(problems[:25]))


# ----------------------------------------------------------------------------------------------------
# the harness: splits, held-out crops, shuffled labels, determinism (skipped until bank/harness.py exists)
# ----------------------------------------------------------------------------------------------------
N_SHUFFLES = 40


def _harness(*needs):
    """bank.harness, or a skip while it is not written. An import error or a missing function fails: that is a broken harness."""
    if importlib.util.find_spec("bank.harness") is None:
        pytest.skip("bank/harness.py is not there yet")
    harness = importlib.import_module("bank.harness")
    missing = [n for n in ("load_config", "design_from_bank", "make_splits") + needs if not hasattr(harness, n)]
    if missing:
        pytest.fail(f"bank.harness no longer has {missing}: tests/test_bank_leakage.py must follow the harness")
    return harness, harness.load_config()


@functools.lru_cache(maxsize=1)
def _bank_design():
    """The design of the bank on disk, loaded once for every test that wants it."""
    harness, cfg = _harness()
    return harness.design_from_bank(cfg)[0]


def _synthetic_design(harness, cfg, changed=(), with_excluded=False):
    """A small design on the real crops, folders, source images and joins, built by the harness's own
    design_from_bank. Two spaces of random numbers in which crops of one source image look alike (as real features
    do), one of them with per-tile arrays. `changed` crops get wildly different values. `with_excluded` adds an
    imaging space and an SE (leakrisk) space."""
    from types import SimpleNamespace
    table = core.crops_table()
    n = len(table)
    rng = np.random.default_rng(5)
    image = np.unique(table.source_image, return_inverse=True)[1]
    effect = rng.standard_normal((image.max() + 1, 6))[image]
    a = effect + 0.5 * rng.standard_normal((n, 6))
    b = rng.standard_normal((n, 40))
    tiles = [effect[i, :5] + rng.standard_normal((12, 5)) for i in range(n)]
    for i in changed:
        a[i], b[i], tiles[i] = a[i] * 50 + 7, b[i] + 100, tiles[i] * 30 - 9
    spaces = [SimpleNamespace(key="syn_a|BSE|anchored|material", family="syn_a", detector="BSE", view="anchored", tag="material", X=a,
                              columns=[f"a{i}" for i in range(6)], tile_sets=[dict(names=["syn_a|BSE|anchored|25|t"], tiles=tiles)],
                              pooled=False, legacy=False),
              SimpleNamespace(key="syn_b|Inlens|harmonised|mixed", family="syn_b", detector="Inlens", view="harmonised", tag="mixed", X=b,
                              columns=[f"b{i}" for i in range(40)], tile_sets=[], pooled=False, legacy=False)]
    if with_excluded:
        for family, det, view, tag in (("syn_q", "BSE", "raw", "imaging"), ("syn_se", "SE", "anchored", "leakrisk")):
            spaces.append(SimpleNamespace(key=f"{family}|{det}|{view}|{tag}", family=family, detector=det, view=view, tag=tag,
                                          X=effect + 0.1 * rng.standard_normal((n, 6)), columns=[f"c{i}" for i in range(6)],
                                          tile_sets=[], pooled=False, legacy=False))
    bank = SimpleNamespace(crops=tuple(table.site), y=table.folder.to_numpy(str), groups=table.source_image.to_numpy(str),
                           families={}, complete_families=lambda: [], spaces=lambda *a, **k: spaces, missing=[],
                           summary=lambda *a, **k: {})
    return harness.design_from_bank(cfg, bank)[0]


def test_no_source_image_on_both_sides_of_a_split():
    """LOSO-13: every fold tests one whole source image and trains on none of it, the inner folds included.
    LOCO-nbr: the test crop and the crops touching it are out of training; its inner folds also split by source image."""
    harness, cfg = _harness()
    design = _synthetic_design(harness, cfg)
    table = core.crops_table()
    assert list(design.crops) == list(table.site) and list(design.groups) == list(table.source_image)
    groups, n = np.asarray(design.groups), len(table)
    splits = harness.make_splits(design.groups, design.neighbours)

    def check_inner(fold):
        for inner in fold["inner"]:
            assert set(inner["train"]) <= set(fold["train"]) and set(inner["val"]) <= set(fold["train"]), "an inner fold reaches outside its training crops"
            assert not set(inner["train"]) & set(fold["test"]), "an inner fold trains on the outer test crops"
            assert not set(groups[list(inner["train"])]) & set(groups[list(inner["val"])]), "a source image on both sides of an inner fold"

    loso = splits["loso13"]
    assert len(loso) == table.source_image.nunique() == 13
    assert sorted(i for f in loso for i in f["test"]) == list(range(n)), "every crop is tested exactly once"
    for fold in loso:
        test, train = list(fold["test"]), list(fold["train"])
        assert len(set(groups[test])) == 1 and not set(groups[test]) & set(groups[train]), f"fold {fold['name']}: a source image on both sides"
        assert sorted(test + train) == list(range(n))
        check_inner(fold)

    at = {c: i for i, c in enumerate(design.crops)}
    joins = pd.read_csv(core.META_DIR / "analysis_only.csv").dropna(subset=["right_neighbour"])
    touching = {i: set() for i in range(n)}
    for row in joins.itertuples():
        touching[at[row.site]].add(at[row.right_neighbour])
        touching[at[row.right_neighbour]].add(at[row.site])
    assert sum(len(v) for v in touching.values()) == 2 * len(joins) == 24
    loco = splits["loco_nbr"]
    assert sorted(i for f in loco for i in f["test"]) == list(range(n))
    for fold in loco:
        (i,) = fold["test"]
        assert not ({i} | touching[i]) & set(fold["train"]), f"{design.crops[i]}: it or a crop touching it is in its own training set"
        assert set(fold["train"]) == set(range(n)) - {i} - touching[i]
        check_inner(fold)


def _model_spaces(design, model):
    return [design.spaces[design.kernels[k]["space"]] for k in design.models[model]["kernels"]]


def test_leakrisk_and_imaging_spaces_stay_out_of_the_models():
    """Nothing from SE and nothing tagged leakrisk reaches any model or baseline; model B also takes nothing tagged
    imaging. Checked on a design that offers both kinds of space, and on the bank on disk."""
    harness, cfg = _harness()
    synthetic = _synthetic_design(harness, cfg, with_excluded=True)
    offered = {s["tag"] for s in synthetic.spaces}
    assert {"leakrisk", "imaging", "material", "mixed"} <= offered and "A" in synthetic.models and "B" in synthetic.models
    assert set() < {s["tag"] for s in _model_spaces(synthetic, "A")} <= {"material", "mixed", "imaging"}
    assert set() < {s["tag"] for s in _model_spaces(synthetic, "B")} <= {"material", "mixed"}
    for design in (synthetic, _bank_design()):
        for name in design.models:
            used = _model_spaces(design, name)
            assert not [s["key"] for s in used if s["tag"] == "leakrisk" or s["detector"] in core.LEAKRISK_DETECTORS], f"model {name} uses a leakrisk space"
            if name in ("B", "uniform_B"):
                assert not [s["key"] for s in used if s["tag"] == "imaging"], f"model {name} uses an imaging space"
        if not hasattr(design, "family_spaces"):
            pytest.fail("bank.harness.Design no longer has family_spaces: tests/test_bank_leakage.py must follow the harness")
        for family, members in design.family_spaces.items():           # the single-family logistic baselines
            bad = [design.spaces[i]["key"] for i in members
                   if design.spaces[i]["tag"] == "leakrisk" or design.spaces[i]["detector"] in core.LEAKRISK_DETECTORS]
            assert members and not bad, f"the single-family baseline of {family} holds leakrisk columns: {bad}"


def test_held_out_crops_do_not_reach_a_fit():
    """Every scaler, PCA, bandwidth, centring and weight is fitted on the training crops alone: change the held-out
    crops' features, tiles and labels beyond recognition and nothing fitted moves."""
    harness, cfg = _harness("fit_fold")
    base = _synthetic_design(harness, cfg)
    fold = harness.make_splits(base.groups, base.neighbours)["loso13"][6]
    held, train = list(fold["test"]), list(fold["train"])
    other = _synthetic_design(harness, cfg, changed=held)
    assert not np.allclose(other.spaces[0]["X"][held], base.spaces[0]["X"][held])
    assert np.array_equal(other.spaces[0]["X"][train], base.spaces[0]["X"][train])
    relabelled = base.y.copy()
    relabelled[held] = (relabelled[held] + 1) % len(base.classes)
    a = harness.fit_fold(base, fold["train"], base.y[None], cfg, with_state=True)
    b = harness.fit_fold(other, fold["train"], relabelled[None], cfg, with_state=True)
    assert a["weights"].keys() == b["weights"].keys() and a["state"].keys() == b["state"].keys() and len(a["state"]) > 0
    for model in a["weights"]:
        assert np.allclose(a["weights"][model], b["weights"][model], rtol=1e-9, atol=1e-12), f"kernel weights of {model} moved"
    for kernel in a["state"]:
        for k, v in a["state"][kernel].items():
            assert np.allclose(np.asarray(v, float), np.asarray(b["state"][kernel][k], float), rtol=1e-9, atol=1e-12), f"{kernel}: fitted {k} moved"
    block = np.ix_(range(len(a["K"])), train, train)
    assert np.allclose(a["K"][block], b["K"][block], rtol=1e-9, atol=1e-12), "the training block of a kernel moved"


def test_shuffled_labels_give_chance():
    """Labels shuffled over the crops, and relabelled per source image, through the whole LOSO-13 pipeline (weights
    and temperature refitted for each labelling): the mean balanced accuracy must be 0.33 +/- 0.15, and not more than
    0.08 above chance (4 standard errors over 40 labellings), because a leak can only push it up."""
    harness, cfg = _harness("fit_jobs", "run_fits", "compose_kernel", "balanced_accuracy_many", "null_a_labels")
    design = _bank_design()
    which = "the bank on disk"
    if not any(m["null"] for m in design.models.values()):
        design, which = _synthetic_design(harness, cfg), "a synthetic design (no complete family on disk)"
    folds = harness.make_splits(design.groups, design.neighbours)["loso13"]
    rng = np.random.default_rng(11)
    free = np.stack([rng.permutation(design.y) for _ in range(N_SHUFFLES)])
    per_image = harness.null_a_labels(design.y, design.groups, len(design.classes), N_SHUFFLES, np.random.default_rng(12))
    Y = np.concatenate([design.y[None], free, per_image])
    results = harness.run_fits(design, Y, cfg, harness.fit_jobs({"loso13": folds}), workers=1)
    checked = 0
    for name, model in design.models.items():
        if not model["null"]:
            continue
        P, _ = harness.compose_kernel(design, folds, results, name, Y, cfg)
        ba = harness.balanced_accuracy_many(P, Y)
        for kind, part in (("shuffled over crops", ba[1:1 + N_SHUFFLES]), ("relabelled per source image", ba[1 + N_SHUFFLES:])):
            mean = float(part.mean())
            assert abs(mean - CHANCE) <= CHANCE_BAND and mean <= CHANCE + 0.08, (
                f"model {name} on {which}: labels {kind} give a mean balanced accuracy of {mean:.3f} over {N_SHUFFLES} labellings "
                f"(SD {part.std():.3f}); chance is {CHANCE:.3f}")
            checked += 1
    assert checked, "no model was scored"


def test_harness_is_deterministic():
    """The same design gives the same numbers twice, and the out-of-fold table shows the split it claims."""
    import json
    harness, cfg = _harness("run")
    out = [harness.run(_synthetic_design(harness, cfg), cfg, n_boot=20, n_null_a=3, n_null_b=3, workers=1) for _ in range(2)]
    assert json.dumps(out[0][0], sort_keys=True) == json.dumps(out[1][0], sort_keys=True)
    oof = out[0][1]
    loso, loco = oof[oof.split == "loso13"], oof[oof.split == "loco_nbr"]
    assert len(loso) and (loso.fold == loso.source_image).all(), "a LOSO-13 prediction was made by a fold that is not its source image"
    assert len(loco) and (loco.fold == loco.crop).all()
    for split in ("loso13", "loco_nbr"):
        assert abs(out[0][0]["results"][split]["majority"]["ba"] - CHANCE) < 1e-9


# ----------------------------------------------------------------------------------------------------
# the label-free report: right on planted structure, the same twice, and read by no model
# ----------------------------------------------------------------------------------------------------
def _planted_spaces():
    table = core.crops_table()
    y = np.unique(table.folder, return_inverse=True)[1]
    g = np.unique(table.source_image, return_inverse=True)[1]
    rng = np.random.default_rng(3)
    mats = {"by_folder": np.eye(3)[y] * 6 + rng.standard_normal((len(y), 3)),
            "by_image": rng.standard_normal((g.max() + 1, 5))[g] * 3 + 0.3 * rng.standard_normal((len(y), 5)),
            "noise": rng.standard_normal((len(y), 4)), "noise_wide": rng.standard_normal((len(y), 2000))}
    spaces = [dict(space=k, level="space", family="syn", detector="BSE", view="anchored", scale_nm="25", layer="-", tag="mixed",
                   rows=np.arange(len(y)), items=[m]) for k, m in mats.items()]
    return spaces, table.folder.to_numpy(), table.source_image.to_numpy()


def test_labelfree_statistics_are_right_on_planted_structure():
    from sklearn.metrics import adjusted_rand_score
    from bank import labelfree as lf
    rng = np.random.default_rng(0)
    for _ in range(50):                                                   # the vectorised ARI is sklearn's
        n = int(rng.integers(8, 40))
        a, b = rng.integers(0, 3, n), rng.integers(0, int(rng.integers(2, 14)), n)
        assert abs(float(lf.ari(lf._onehot(a, 3), lf._onehot(b, int(b.max()) + 1))) - adjusted_rand_score(a, b)) < 1e-9
    x, y = rng.standard_normal((31, 7)), rng.integers(0, 3, 31)           # nearest centroid from distances = from coordinates
    dist, _ = lf.distance_matrix([x], balance=False)
    z = (x - x.mean(0)) / x.std(0) / np.sqrt(7)
    direct = ((z[:, None, :] - np.stack([z[y == k].mean(0) for k in range(3)])[None]) ** 2).sum(-1).argmin(1)
    assert np.array_equal(direct, lf.nearest_centroid(dist ** 2, lf._onehot(y, 3)))

    spaces, folder, source = _planted_spaces()
    rows, null, skipped = lf.analyse(spaces, folder, source, n_perm=200, seed=0)
    by = {r["space"]: r for r in rows}
    assert not skipped and set(by) == {"by_folder", "by_image", "noise", "noise_wide"}
    for method in ("spectral", "agglo"):
        assert by["by_folder"][f"ari_folder_{method}"] > 0.9
        assert by["by_folder"][f"ari_folder_{method}__image_p_max"] <= 0.01 and by["by_folder"][f"ari_folder_{method}__crop_p_max"] <= 0.01
        for flat in ("by_image", "noise", "noise_wide"):
            assert by[flat][f"ari_folder_{method}"] < 0.3 and by[flat][f"ari_folder_{method}__image_p_max"] > 0.1
    assert by["by_image"]["ari_source_agglo_k13"] > 0.9 and by["by_image"]["ari_source_agglo_k13__source_p_max"] <= 0.01
    assert by["noise"]["ari_source_agglo_k13__source_p_max"] > 0.1
    assert by["by_folder"]["fixed_point"] == 1.0 and by["by_folder"]["fixed_point__image_p_max_z"] <= 0.01
    # in 2000 dimensions every labelling is a fixed point: only the null tells, and it says "nothing here"
    assert by["noise_wide"]["fixed_point"] > 0.95 and by["noise_wide"]["fixed_point__image_mean"] > 0.95
    assert by["noise_wide"]["fixed_point__image_p_max_z"] > 0.1


def test_labelfree_is_deterministic(tmp_path):
    from bank import labelfree as lf
    first, second = (lf.analyse(*_planted_spaces(), n_perm=100, seed=0) for _ in range(2))
    assert first == second
    args = ["--n-perm", "50", "--families", "legacy_acq,legacy_dinov2s"]     # the two families every machine with views has
    for name in ("a", "b"):
        lf.main(["--out", str(tmp_path / name)] + args)
    for file in ("labelfree.json", "labelfree.md", "labelfree_spaces.csv"):
        assert (tmp_path / "a" / file).read_bytes() == (tmp_path / "b" / file).read_bytes(), f"{file} differs between two runs"
    import json
    saved = json.loads((tmp_path / "a" / "labelfree.json").read_text())
    assert lf.table(saved) == (tmp_path / "a" / "labelfree.md").read_text()      # the table is the JSON and nothing else
    assert "never a model input" in saved["what"]


def test_nothing_reads_the_labelfree_report():
    """Label-free scores use the folder labels of every crop, so no model and no feature may read them."""
    readers = [p for p in sorted((ROOT / "bank").rglob("*.py")) + sorted((ROOT / "cloud").glob("*.py"))
               if p.name not in ("labelfree.py", "qa.py") and "labelfree" in p.read_text()]      # qa.py may run the report
    assert not readers, f"{[str(p.relative_to(ROOT)) for p in readers]} mention bank.labelfree: its output must never feed a model"
