"""The feature-bank contract (bank/core.py), checked on the two smoke crops and on every registered family.

    pytest tests/test_bank_contract.py -q             # everything local
    pytest tests/test_bank_contract.py -q -k phase    # one family
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from bank import core, families

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"^[a-z0-9_]+\|(BSE|Inlens|BSExInlens|SE)\|[a-z0-9_]+\|\d+\|[A-Za-z0-9_.+-]+$")
# Things a family file must never contain: provenance, the stretched images, the old split, forbidden transforms.
BANNED_SOURCE = ["crop._id", "analysis_only", "crops.csv", "crops_table", "CHAINS", "TOUCHING", "END_TILES", "split_of",
                 "processed/full", "processed/tiles", "load_sample", "threshold_multiotsu", "flipud", "rot90", "raw_path",
                 "porosity"]


@pytest.fixture(scope="module", params=core.SMOKE_CROPS)
def crop(request):
    return core.load_crop(request.param)


def test_window_and_types(crop):
    assert crop.shape == core.WINDOW == (1336, 6944)
    for det in core.DETECTORS + core.LEAKRISK_DETECTORS:
        assert crop.raw[det].shape == core.WINDOW and crop.raw[det].dtype == np.uint8
        for view in ("anchored", "harmonised", "smoothed"):
            v = crop.view(det, view)
            assert v.shape == core.WINDOW and v.dtype == np.float32 and np.isfinite(v).all()
    for name in core.PHASES + ("valid",):
        m = crop.masks[name]
        assert m.shape == core.WINDOW and m.dtype == bool
    assert crop.view("BSE", "anchored", 4).shape == (334, 1736)
    assert core.tiles(crop.view("BSE", "raw"), 512).shape == (26, 512, 512)


def test_anchoring_and_bands(crop):
    bse = crop.view("BSE", "anchored")
    graphite = np.median(bse[(bse > 0.8) & (bse < 1.2)])
    assert abs(graphite - 1.0) < 0.05                                  # graphite sits at 1
    assert crop.phase("void_lo").mean() <= crop.phase("void").mean() <= crop.phase("void_hi").mean()
    assert crop.phase("bright_lo").mean() <= crop.phase("bright").mean() <= crop.phase("bright_hi").mean()
    assert 0.02 < crop.phase("void").mean() < 0.3 and 0.005 < crop.phase("bright").mean() < 0.3


def test_views_are_deterministic_and_name_free(crop):
    """The same pixels under another id give the same Crop: the noise seed comes from the content."""
    folder = core.crops_table().set_index("site").folder[crop._id]
    raw = {d: core.load_grey(core.raw_path(folder, crop._id, d)) for d in ("BSE", "Inlens", "SE")}
    again = core.make_crop(raw["BSE"], raw["Inlens"], raw["SE"], crop_id="renamed")
    assert again.anchors == crop.anchors
    assert all(np.array_equal(again.masks[k], crop.masks[k]) for k in crop.masks)
    assert np.array_equal(again.view("BSE", "harmonised"), crop.view("BSE", "harmonised"))


def test_outer_columns_do_not_matter(crop):
    """The 8 trimmed columns each side (which carry the green end-of-strip marker) never reach a Crop."""
    folder = core.crops_table().set_index("site").folder[crop._id]
    raw = {d: core.load_grey(core.raw_path(folder, crop._id, d)).copy() for d in ("BSE", "Inlens", "SE")}
    rng = np.random.default_rng(0)
    for img in raw.values():
        img[:, :8] = rng.integers(0, 256, (img.shape[0], 8))
        img[:, -8:] = rng.integers(0, 256, (img.shape[0], 8))
    again = core.make_crop(raw["BSE"], raw["Inlens"], raw["SE"])
    assert again.anchors == crop.anchors and np.array_equal(again.raw["BSE"], crop.raw["BSE"])


def test_forbidden_name_parts():
    assert core.forbidden_tokens("phase|BSE|phase|25|void_frac_mid") == set()
    assert core.forbidden_tokens("glcm_lbp|Inlens|harmonised|50|contrast_d4_a90") == set()
    for bad in ("x|BSE|raw|25|height", "x|BSE|raw|25|tile_row_mean", "x|BSE|raw|25|batch_mean", "x|BSE|raw|25|strip_pos"):
        assert core.forbidden_tokens(bad)


def test_validate_rejects_bad_results():
    res = core.FeatureResult("fam")
    res.scalar("BSE", "anchored", 25, "ok", 1.0)
    core.validate(res)
    for build in (lambda r: r.scalar("BSE", "anchored", 25, "nan", float("nan")),
                  lambda r: r.scalar("BSE", "anchored", 25, "width", 1.0),
                  lambda r: r.scalar("SE", "anchored", 25, "mean", 1.0, tag="material"),
                  lambda r: r.scalar("BSE", "anchored", 25, "m", 1.0, tag="nonsense"),
                  lambda r: r.tile_block("BSE", "anchored", 25, "t", np.ones(5))):
        bad = core.FeatureResult("fam")
        build(bad)
        with pytest.raises(ValueError):
            core.validate(bad)


def test_crop_versions():
    assert len(core.crop_versions("all", "P0")) == 31
    assert len(core.crop_versions("all", "imaging")) == 31 * 6
    assert len(core.crop_versions("all", "inject")) == 6 * 5
    assert len(core.crop_versions("all", "all")) == 31 * 7 + 30


def _families(runs_on):
    """Families by where they run. A family that fails to import counts as CPU, so its own test fails and nobody else's."""
    out = []
    for f in families.family_names():
        try:
            kind = families.load(f).RUNS_ON
        except Exception:
            kind = "cpu"
        if kind == runs_on:
            out.append(f)
    return out


def _check_family(name):
    module = families.load(name)
    assert module.TIER in (1, 2, 3) and isinstance(module.DEFAULT_CFG, dict)
    crop_id = core.SMOKE_CROPS[0]
    res = module.extract(core.load_crop(crop_id), dict(module.DEFAULT_CFG))
    core.validate(res)                                                   # finite, named, tagged, catalogued
    for c in res.catalog:
        assert NAME.match(c["name"]), c["name"]
    assert res.scalars or res.blocks or res.tiles
    if core.is_done(name, crop_id):                                      # determinism: equal to the stored run
        stored = core.load_scalars(name, crops=[crop_id]).iloc[0]
        assert set(stored.index) == set(res.scalars), "column set changed: rerun the family with --force"
        got = np.array([res.scalars[k] for k in stored.index])
        assert np.allclose(got, stored.to_numpy(float), rtol=1e-6, atol=1e-9), "not deterministic (or stale stored results)"
        arrays = core.load_arrays(name, crop_id)
        for k, v in {**res.blocks, **res.tiles}.items():
            assert np.allclose(v, arrays[k], rtol=1e-4, atol=1e-5), k


@pytest.mark.parametrize("name", _families("cpu"))
def test_cpu_family(name):
    _check_family(name)


@pytest.mark.parametrize("name", _families("gpu"))
def test_gpu_family(name, request):
    if not request.config.getoption("--gpu"):
        pytest.skip("pass --gpu to test GPU families")
    _check_family(name)


@pytest.mark.parametrize("name", families.family_names())
def test_family_source_is_clean(name):
    text = (ROOT / "bank" / "families" / f"{name}.py").read_text()
    found = [b for b in BANNED_SOURCE if b in text]
    assert not found, f"bank/families/{name}.py uses {found}"


@pytest.mark.modal
@pytest.mark.parametrize("name", ["_example"] + _families("cpu"))
def test_modal_parity(name):
    """The same family on the same smoke crops, in the cloud and here, agrees."""
    out = subprocess.run([sys.executable, "-m", "modal", "run", "cloud/modal_bank.py", "--stage", "parity", "--fam", name],
                         cwd=ROOT, capture_output=True, text=True, timeout=1800)
    assert out.returncode == 0, out.stderr[-2000:]
    remote = json.loads(out.stdout[out.stdout.index("PARITY_JSON=") + len("PARITY_JSON="):].splitlines()[0])
    module = families.load(name)
    for crop_id, scalars in remote.items():
        local = module.extract(core.load_crop(crop_id), dict(module.DEFAULT_CFG)).scalars
        assert set(local) == set(scalars)
        worst = max(abs(local[k] - scalars[k]) / (abs(local[k]) + 1e-9) for k in local)
        assert worst < 1e-4, f"{name} {crop_id}: local and Modal differ by up to {worst:.2e}"
