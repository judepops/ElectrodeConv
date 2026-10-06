"""Assemble whatever part of the feature bank is on disk into the tables and spaces the harness scores.

    from bank.assemble import load_bank
    bank = load_bank()                          # P0, every family found on disk, plus the two legacy families
    bank.crops, bank.y, bank.groups             # meta/crops.csv order: crop ids, folder labels, source images
    bank.families["phase"].scalars              # DataFrame indexed by (pert, crop), one column per scalar
    bank.families["phase"].blocks["P0"]         # {name: (n_crops, d) array}; NaN rows for crops that are not done
    bank.families["emb_x"].tiles["P0"]          # {name: [one (n_tiles, d) array per crop, None where not done]}
    bank.families["phase"].catalog              # the family's tag table (bank/core.py)
    bank.missing                                # every gap, one dict each: family, pert, crop, what
    bank.spaces()                               # (family, detector, view, tag) spaces of the families that are complete

Tile arrays wider than `max_tile_width` (saved token grids, hundreds of thousands of numbers per tile) are for the
stretch work, not for kernels: they are left on disk and listed in `missing`.

A partial bank is fine: a family counts for the harness only when all crops of the requested version are done,
everything else is listed in `missing` and skipped. Nothing is fitted here and no provenance enters a feature:
crop ids, folders and source images are used to order rows, to label them and to group them, never as columns.

Two legacy families exist so the harness has something to score before the real families land:

    legacy_dinov2s   the old DINOv2-S tile embeddings (processed/representation/emb/orig/*.npz; only the keys bse,
                     inlens and is_edge are read, and the edge tiles are dropped). Tag: mixed. P0 only.
    legacy_acq       an interim acquisition block from the Crop anchors (black level, graphite level, BSE and Inlens
                     noise, bright mode). Tag: imaging. The imgqc family replaces it once it is complete.
"""
import json
from dataclasses import dataclass, field

import numpy.lib.format as npy_format

import numpy as np
import pandas as pd

from bank import core, families as _families

P0 = core.P0
LEGACY_EMB = "legacy_dinov2s"
LEGACY_ACQ = "legacy_acq"
LEGACY_FAMILIES = (LEGACY_EMB, LEGACY_ACQ)
LEGACY_EMB_DIR = core.PROCESSED_DIR / "representation" / "emb" / "orig"
CATALOG_COLUMNS = ["name", "kind", "family", "detector", "view", "scale_nm", "length_um", "layer", "tag"]
# anchors -> (detector, statistic) of the interim acquisition block
ACQ_ANCHORS = {"black": ("BSE", "black_level"), "graphite": ("BSE", "graphite_level"), "bse_noise_sigma": ("BSE", "noise_sigma"),
               "bright_mode": ("BSE", "bright_mode"), "inlens_noise_sigma": ("Inlens", "noise_sigma")}


@dataclass
class FamilyData:
    """Everything one family has written, for the requested crop versions."""
    name: str
    catalog: pd.DataFrame                 # name, kind (scalar | block | tiles), detector, view, scale_nm, length_um, layer, tag
    scalars: pd.DataFrame                 # index (pert, crop), only the finished crop versions
    blocks: dict                          # pert -> {name: (n_crops, d) float32, NaN rows where the crop is not done}
    tiles: dict                           # pert -> {name: [(n_tiles, d) float32 or None, one per crop]}
    done: dict                            # pert -> bool (n_crops,): the crop version is finished and readable
    expected: dict                        # pert -> bool (n_crops,): the crop version is supposed to exist
    legacy: bool = False

    def complete(self, pert=P0):
        """True when every expected crop of this version is there (and at least one is expected)."""
        if pert not in self.done:
            return False
        exp = self.expected[pert]
        return bool(exp.any() and self.done[pert][exp].all())


@dataclass
class Space:
    """One (family, detector, view, tag): what the harness turns into a linear, an RBF and an MMD kernel."""
    key: str                              # "family|detector|view|tag"
    family: str
    detector: str
    view: str
    tag: str
    X: np.ndarray                         # (n_crops, d) float64: scalars, then flattened blocks (tile means if neither exists)
    columns: list                         # d column names (block columns as name[i])
    tile_sets: list                       # [dict(names=[...], tiles=[(n_tiles, d) per crop])]: tile arrays with equal tile counts
    pooled: bool = False                  # True when X is the mean over tiles because the space has no crop-level values
    legacy: bool = False
    n_scalars: int = 0
    n_block_columns: int = 0


@dataclass
class Bank:
    crops: tuple
    y: np.ndarray                         # folder label of each crop
    groups: np.ndarray                    # source image of each crop
    perts: tuple
    families: dict                        # name -> FamilyData
    missing: list = field(default_factory=list)

    def complete_families(self, pert=P0):
        return [name for name, fam in self.families.items() if fam.complete(pert)]

    def spaces(self, pert=P0, families=None):
        """The spaces of every complete family (or of `families`), in a fixed order. Incomplete families are skipped."""
        out, gaps = [], []
        for name in sorted(self.families):
            if families is not None and name not in families:
                continue
            fam = self.families[name]
            if fam.complete(pert) and fam.expected[pert].all():
                out.extend(_family_spaces(fam, self.crops, pert, gaps))
        self.missing.extend(g for g in gaps if g not in self.missing)           # calling twice reports each gap once
        return out

    def summary(self, pert=P0):
        """A small, JSON-ready description of what is there and what is not."""
        fams = {}
        for name in sorted(self.families):
            fam = self.families[name]
            kinds = fam.catalog.kind.value_counts().to_dict() if len(fam.catalog) else {}
            fams[name] = dict(complete=fam.complete(pert), n_done=int(fam.done[pert].sum()) if pert in fam.done else 0,
                              n_expected=int(fam.expected[pert].sum()) if pert in fam.expected else 0, legacy=fam.legacy,
                              n_scalars=int(kinds.get("scalar", 0)), n_blocks=int(kinds.get("block", 0)),
                              n_tile_arrays=int(kinds.get("tiles", 0)),
                              tags=sorted(fam.catalog.tag.unique().tolist()) if len(fam.catalog) else [])
        gaps = {}
        for m in self.missing:
            gaps.setdefault(f"{m['family']}: {m['what']}", []).append(f"{m['pert']}/{m['crop']}")
        return dict(n_crops=len(self.crops), pert=pert, families=fams,
                    missing={k: dict(n=len(v), examples=v[:6]) for k, v in sorted(gaps.items())})


# ----------------------------------------------------------------------------------------------------
# families on disk
# ----------------------------------------------------------------------------------------------------
def _gap(missing, family, pert, crop, what):
    missing.append(dict(family=family, pert=pert, crop=crop, what=what))


def _expected(crops, pert):
    if pert in core.MATERIAL_INJECTS:
        return np.array([c in core.INJECT_CROPS for c in crops])
    return np.ones(len(crops), bool)


def _read_arrays(path, kind, max_tile_width, wide):
    """{name: array} of one crop version, reading each header first so that over-wide tile arrays are never loaded."""
    out = {}
    if not path.exists():
        return out
    with np.load(path) as z:
        for k in z.files:
            if kind.get(k) == "tiles":
                with z.zip.open(k + ".npy") as f:
                    version = npy_format.read_magic(f)
                    shape = (npy_format.read_array_header_1_0 if version == (1, 0) else npy_format.read_array_header_2_0)(f)[0]
                if len(shape) == 2 and shape[1] > max_tile_width:
                    wide[k] = int(shape[1])
                    continue
            out[k] = z[k]
    return out


def _load_family(name, crops, perts, missing, max_tile_width):
    """One family from processed/bank/feat/<name>/, or None when it has no readable catalog yet."""
    try:
        catalog = core.load_catalog(name)[CATALOG_COLUMNS].drop_duplicates("name").reset_index(drop=True)
    except Exception as e:                                      # another lane may be half-way through writing it
        _gap(missing, name, "*", "*", f"no readable catalog ({type(e).__name__})")
        return None
    kind = dict(zip(catalog.name, catalog.kind))
    rows, blocks, tiles, done, expected = {}, {}, {}, {}, {}
    for pert in perts:
        expected[pert] = _expected(crops, pert)
        ok = np.zeros(len(crops), bool)
        arrays, wide = [None] * len(crops), {}
        for i, c in enumerate(crops):
            if not expected[pert][i]:
                continue
            parquet, npz, done_file = core.feat_paths(name, c, pert)
            if not done_file.exists():
                _gap(missing, name, pert, c, "not done")
                continue
            try:
                frame = pd.read_parquet(parquet)
                arrays[i] = _read_arrays(npz, kind, max_tile_width, wide)
            except Exception as e:
                _gap(missing, name, pert, c, f"unreadable ({type(e).__name__})")
                continue
            rows[(pert, c)] = frame.iloc[0] if len(frame) else pd.Series(dtype=float)
            ok[i] = True
        done[pert] = ok
        blocks[pert], tiles[pert] = {}, {}
        for k, width in sorted(wide.items()):
            _gap(missing, name, pert, "*", f"tile array {k} is {width} wide (> {max_tile_width}): left on disk, not used for kernels")
        names = sorted({k for a in arrays if a for k in a})
        for k in names:
            if k not in kind:
                _gap(missing, name, pert, "*", f"array {k} is not in the catalog (skipped)")
                continue
            have = [a.get(k) if a is not None else None for a in arrays]
            if any(h is None for h, good in zip(have, ok) if good):
                _gap(missing, name, pert, "*", f"array {k} is absent from some finished crops (skipped)")
                continue
            if kind[k] == "tiles":
                widths = {h.shape[1] for h in have if h is not None}
                if len(widths) != 1:
                    _gap(missing, name, pert, "*", f"tile array {k} changes width between crops (skipped)")
                    continue
                tiles[pert][k] = [None if h is None else np.asarray(h, np.float32) for h in have]
            else:
                sizes = {h.size for h in have if h is not None}
                if len(sizes) != 1:
                    _gap(missing, name, pert, "*", f"block {k} changes size between crops (skipped)")
                    continue
                stack = np.full((len(crops), sizes.pop()), np.nan, np.float32)
                for i, h in enumerate(have):
                    if h is not None:
                        stack[i] = np.asarray(h, np.float32).ravel()
                blocks[pert][k] = stack
    scalars = pd.DataFrame.from_dict(rows, orient="index") if rows else pd.DataFrame()
    if len(scalars):
        scalars.index = pd.MultiIndex.from_tuples(scalars.index, names=["pert", "crop"])
    return FamilyData(name, catalog, scalars, blocks, tiles, done, expected)


# ----------------------------------------------------------------------------------------------------
# the two legacy families
# ----------------------------------------------------------------------------------------------------
def _catalog_row(family, kind, det, view, scale_nm, stat, length_um, layer, tag):
    return dict(name=core.column(family, det, view, scale_nm, stat), kind=kind, family=family, detector=det, view=view,
                scale_nm=int(scale_nm), length_um=np.nan if length_um is None else float(length_um), layer=layer, tag=tag)


def _legacy_embeddings(crops, perts, missing):
    """The old DINOv2-S tile embeddings (class token + mean patch token of 504 px tiles), edge tiles dropped. P0 only."""
    cols = {"BSE": ("bse", _catalog_row(LEGACY_EMB, "tiles", "BSE", "harmonised", core.PX_NM, "cls_patchmean_tiles", 12.6, "final", "mixed")),
            "Inlens": ("inlens", _catalog_row(LEGACY_EMB, "tiles", "Inlens", "harmonised", core.PX_NM, "cls_patchmean_tiles", 12.6, "final", "mixed"))}
    catalog = pd.DataFrame([row for _, row in cols.values()])[CATALOG_COLUMNS]
    blocks, tiles, done, expected = {}, {}, {}, {}
    for pert in perts:
        expected[pert] = np.full(len(crops), pert == P0)
        done[pert] = np.zeros(len(crops), bool)
        blocks[pert], tiles[pert] = {}, {}
        if pert != P0:
            continue
        per = {row["name"]: [None] * len(crops) for _, row in cols.values()}
        for i, c in enumerate(crops):
            hits = sorted(LEGACY_EMB_DIR.glob(f"*__{c}.npz"))
            if not hits:
                _gap(missing, LEGACY_EMB, pert, c, "no legacy embedding file")
                continue
            try:
                with np.load(hits[0]) as z:
                    keep = ~z["is_edge"].astype(bool)
                    got = {row["name"]: np.asarray(z[key][keep], np.float32) for key, row in cols.values()}
            except Exception as e:
                _gap(missing, LEGACY_EMB, pert, c, f"unreadable ({type(e).__name__})")
                continue
            if any(v.ndim != 2 or v.shape[0] == 0 or not np.isfinite(v).all() for v in got.values()):
                _gap(missing, LEGACY_EMB, pert, c, "empty or not finite")
                continue
            for k, v in got.items():
                per[k][i] = v
            done[pert][i] = True
        tiles[pert] = per
    return FamilyData(LEGACY_EMB, catalog, pd.DataFrame(), blocks, tiles, done, expected, legacy=True)


def crop_anchors(crop_id, pert=P0):
    """bank.core.load_crop(crop_id, pert).anchors, read straight from the views file (the masks stay packed)."""
    path = core.views_path(crop_id, pert)
    if not path.exists():
        raise FileNotFoundError(path)
    with np.load(path) as z:
        return json.loads(str(z["anchors"]))


def _legacy_acquisition(crops, perts, missing):
    """Interim acquisition block: the Crop anchors that describe how the picture was taken. Tag: imaging."""
    catalog = pd.DataFrame([_catalog_row(LEGACY_ACQ, "scalar", det, "raw", core.PX_NM, stat, None, "", "imaging")
                            for det, stat in ACQ_ANCHORS.values()])[CATALOG_COLUMNS]
    rows, done, expected = {}, {}, {}
    for pert in perts:
        expected[pert] = _expected(crops, pert)
        done[pert] = np.zeros(len(crops), bool)
        for i, c in enumerate(crops):
            if not expected[pert][i]:
                continue
            try:
                a = crop_anchors(c, pert)
                row = {core.column(LEGACY_ACQ, det, "raw", core.PX_NM, stat): float(a[key]) for key, (det, stat) in ACQ_ANCHORS.items()}
            except Exception as e:
                _gap(missing, LEGACY_ACQ, pert, c, f"no anchors ({type(e).__name__}): run `python -m bank.run views`")
                continue
            if not np.isfinite(list(row.values())).all():
                _gap(missing, LEGACY_ACQ, pert, c, "anchors not finite")
                continue
            rows[(pert, c)] = pd.Series(row)
            done[pert][i] = True
    scalars = pd.DataFrame.from_dict(rows, orient="index") if rows else pd.DataFrame()
    if len(scalars):
        scalars.index = pd.MultiIndex.from_tuples(scalars.index, names=["pert", "crop"])
    empty = {p: {} for p in perts}
    return FamilyData(LEGACY_ACQ, catalog, scalars, dict(empty), {p: {} for p in perts}, done, expected, legacy=True)


# ----------------------------------------------------------------------------------------------------
# spaces
# ----------------------------------------------------------------------------------------------------
def _family_spaces(fam, crops, pert, missing):
    """Split one complete family into (detector, view, tag) spaces. Columns that are not finite everywhere are dropped."""
    cat = fam.catalog.copy()
    cat["tag"] = np.where(cat.detector.isin(core.LEAKRISK_DETECTORS), "leakrisk", cat.tag)     # belt and braces
    scal = fam.scalars.xs(pert, level="pert").reindex(list(crops)) if len(fam.scalars) else pd.DataFrame(index=list(crops))
    stray = sorted(set(scal.columns) - set(cat.name))
    if stray:                                              # a column nobody tagged cannot be placed in a space
        _gap(missing, fam.name, pert, "*", f"{len(stray)} scalar column(s) are not in the catalog (not used), e.g. {stray[0].replace('|', '/')}")
    blocks, tiles = fam.blocks.get(pert, {}), fam.tiles.get(pert, {})
    out = []
    for (det, view, tag), part in cat.groupby(["detector", "view", "tag"], sort=True):
        mats, columns, n_scalars, n_block = [], [], 0, 0
        names = [n for n in part.name[part.kind == "scalar"] if n in scal.columns]
        absent = int((part.kind == "scalar").sum()) - len(names)
        if absent:
            _gap(missing, fam.name, pert, "*", f"{absent} scalar(s) of {det}/{view} are in the catalog but in no crop's table")
        if names:
            m = scal[names].to_numpy(np.float64)
            good = np.isfinite(m).all(axis=0)
            if not good.all():
                _gap(missing, fam.name, pert, "*", f"{int((~good).sum())} scalar column(s) of {det}|{view} not finite (dropped)")
            mats.append(m[:, good])
            columns += [n for n, g in zip(names, good) if g]
            n_scalars = int(good.sum())
        for n in part.name[part.kind == "block"]:
            if n not in blocks:
                continue
            m = blocks[n].astype(np.float64)
            if not np.isfinite(m).all():
                _gap(missing, fam.name, pert, "*", f"block {n} not finite (dropped)")
                continue
            mats.append(m)
            columns += [f"{n}[{i}]" for i in range(m.shape[1])]
            n_block += m.shape[1]
        by_count = {}
        for n in part.name[part.kind == "tiles"]:
            if n not in tiles or any(t is None or not np.isfinite(t).all() for t in tiles[n]):
                continue
            by_count.setdefault(tuple(len(t) for t in tiles[n]), []).append(n)
        tile_sets = [dict(names=ns, tiles=[np.concatenate([tiles[n][i] for n in ns], axis=1) for i in range(len(crops))])
                     for _, ns in sorted(by_count.items())]
        pooled = False
        if not mats and tile_sets:                     # nothing at crop level: pool the tiles so linear and RBF kernels exist
            for ts in tile_sets:
                mats.append(np.stack([t.mean(axis=0) for t in ts["tiles"]]).astype(np.float64))
                columns += [f"{n}[mean]" for n in ts["names"]]
            pooled = True
        if not mats:
            continue
        X = np.concatenate(mats, axis=1)
        out.append(Space(f"{fam.name}|{det}|{view}|{tag}", fam.name, det, view, tag, X, columns, tile_sets, pooled, fam.legacy,
                         n_scalars, n_block))
    return out


# ----------------------------------------------------------------------------------------------------
# the loader
# ----------------------------------------------------------------------------------------------------
def load_bank(perts=(P0,), families=None, max_tile_width=4096):
    """Load the bank for the given crop versions.

    perts            crop versions to load ("P0", the imaging changes, the injections)
    families         None = every family with output on disk plus the two legacy families; or an explicit list of names
    max_tile_width   per-tile arrays wider than this are not loaded (token grids)
    Returns a Bank: crops in meta/crops.csv order, y, groups, per-family tables and arrays, and `missing`.
    """
    perts = (perts,) if isinstance(perts, str) else tuple(perts)
    table = core.crops_table()
    crops = tuple(table.site)
    missing, fams = [], {}
    on_disk = sorted(p.name for p in core.FEAT_DIR.iterdir() if p.is_dir()) if core.FEAT_DIR.exists() else []
    wanted = list(families) if families is not None else on_disk + list(LEGACY_FAMILIES)
    for name in wanted:
        if name == LEGACY_EMB:
            fams[name] = _legacy_embeddings(crops, perts, missing)
        elif name == LEGACY_ACQ:
            fams[name] = _legacy_acquisition(crops, perts, missing)
        elif name in on_disk:
            fam = _load_family(name, crops, perts, missing, max_tile_width)
            if fam is not None:
                fams[name] = fam
        else:
            _gap(missing, name, "*", "*", "no output on disk")
    if families is None:
        try:
            registered = _families.family_names()
        except Exception:
            registered = []
        for name in registered:
            if name not in on_disk:
                _gap(missing, name, "*", "*", "no output on disk")
    return Bank(crops, table.folder.to_numpy(str), table.source_image.to_numpy(str), perts, fams, missing)


if __name__ == "__main__":
    b = load_bank()
    print(json.dumps(b.summary(), indent=1))
    for s in b.spaces():
        print(f"{s.key:<50} X {s.X.shape}  tile sets {[(len(t['names']), t['tiles'][0].shape) for t in s.tile_sets]}")
