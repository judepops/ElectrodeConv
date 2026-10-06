"""Step 1: the tile dataset, the material-map target, and spot-level splits.

    from cnn.data import TileDataset, make_folds, tile_index
    idx = tile_index()                                   # DataFrame: one row per tile (batch, sample_id, session, row, col)
    train_ids, val_ids = make_folds(idx, by="session", n_folds=13)[0]
    ds = TileDataset(idx[idx.sample_id.isin(train_ids)], augment=True)
    x, y, info = ds[0]     # x (3, H, W) float32 [bse, inlens, se]; y (H, W) int64 material map; info dict

The split is ALWAYS by spot (sample_id) or by session; tiles of one spot are the same material and must stay
together. `--smoke` keeps 2 spots per batch. Training and evaluation both use the fixed 512 x 512 tiles (26 per
spot, the central 1024 x 6656 px of the 1336-row window).

Augmentation sets (train only). "base": random crop (no resize: pixel size is physical), horizontal flip,
per-channel brightness / contrast jitter and extra Gaussian noise (imaging invariance). "flips" adds the vertical
flip and "rot" adds 90-degree rotations as well; both break the through-thickness direction and the flakes'
horizontal lie, so they are not the default.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from cnn.common import DETECTORS, TILES_CSV, TILES_DIR, load_tile, material_map

TILE = 512
AUGS = {"base": ("hflip",), "flips": ("hflip", "vflip"), "rot": ("hflip", "vflip", "rot90")}


def tile_index(csv=TILES_CSV) -> pd.DataFrame:
    df = pd.read_csv(csv)
    return df[["batch", "sample_id", "session", "row", "col"]].copy()


def spots_of(idx: pd.DataFrame) -> pd.DataFrame:
    return idx.drop_duplicates("sample_id")[["batch", "sample_id", "session"]].reset_index(drop=True)


def make_folds(idx: pd.DataFrame, by: str = "sample_id", n_folds: int = 5, seed: int = 0):
    """-> [(train sample_ids, val sample_ids)] with whole spots (by='sample_id') or whole sessions (by='session')
    held out together, batches spread across folds."""
    spots = spots_of(idx)
    rng = np.random.default_rng(seed)
    groups = spots[by].unique()
    rng.shuffle(groups)
    if by == "sample_id":            # stratify: deal each batch's spots round-robin into folds
        order = []
        for b in sorted(spots.batch.unique()):
            ids = spots[spots.batch == b].sample_id.to_numpy()
            rng.shuffle(ids)
            order.append(ids)
        dealt = [[] for _ in range(n_folds)]
        k = 0
        for ids in order:
            for s in ids:
                dealt[k % n_folds].append(s)
                k += 1
        folds = [set(f) for f in dealt]
    else:
        folds = [set() for _ in range(n_folds)]
        for i, g in enumerate(groups):
            folds[i % n_folds].update(spots[spots[by] == g].sample_id)
    all_ids = set(spots.sample_id)
    return [(sorted(all_ids - f), sorted(f)) for f in folds]


def smoke_subset(idx: pd.DataFrame, per_batch: int = 2, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    keep = []
    for b, g in spots_of(idx).groupby("batch"):
        keep += list(rng.choice(g.sample_id.to_numpy(), per_batch, replace=False))
    return idx[idx.sample_id.isin(keep)].reset_index(drop=True)


def augment(x, y, rng, ops=AUGS["base"], crop=None):
    """x (C, H, W) float32, y (H, W): random crop to `crop` (if given and smaller), geometric ops, photometric jitter."""
    if crop and crop < x.shape[1]:
        oy, ox = rng.integers(0, x.shape[1] - crop + 1), rng.integers(0, x.shape[2] - crop + 1)
        x, y = x[:, oy:oy + crop, ox:ox + crop], y[oy:oy + crop, ox:ox + crop]
    if "hflip" in ops and rng.random() < 0.5:
        x, y = x[:, :, ::-1], y[:, ::-1]
    if "vflip" in ops and rng.random() < 0.5:
        x, y = x[:, ::-1, :], y[::-1, :]
    if "rot90" in ops:
        k = int(rng.integers(0, 4))
        if k:
            x, y = np.rot90(x, k, axes=(1, 2)), np.rot90(y, k, axes=(0, 1))
    x = np.ascontiguousarray(x)
    for k in range(x.shape[0]):             # per-channel photometric jitter + noise (imaging invariance)
        gain = rng.uniform(0.85, 1.15)
        bias = rng.uniform(-0.05, 0.05)
        x[k] = x[k] * gain + bias
        sigma = rng.uniform(0.0, 0.05)
        if sigma > 0:
            x[k] = x[k] + rng.standard_normal(x[k].shape, dtype=np.float32) * np.float32(sigma)
    return x, np.ascontiguousarray(y)


class TileDataset(Dataset):
    def __init__(self, idx: pd.DataFrame, augment: bool = False, crop: int = TILE, channels=DETECTORS,
                 preload: bool = False, seed: int = 0, aug: str = "base", tiles_dir=None):
        self.idx = idx.reset_index(drop=True)
        self.augment, self.crop, self.channels = augment, crop, tuple(channels)
        self.ops = AUGS[aug]
        self.tiles_dir = tiles_dir or TILES_DIR
        self.rng = np.random.default_rng(seed)
        self.cache = None
        if preload:
            self.cache = [self._load(i) for i in range(len(self.idx))]

    def __len__(self):
        return len(self.idx)

    def _load(self, i):
        r = self.idx.iloc[i]
        t = load_tile(r.batch, r.sample_id, int(r.row), int(r.col), out_dir=self.tiles_dir)
        x = np.stack([getattr(t, c) for c in self.channels]).astype(np.float32)
        return x, material_map(t)

    def __getitem__(self, i):
        x, y = self.cache[i] if self.cache is not None else self._load(i)
        x, y = x.copy(), y.copy()
        if self.augment:
            x, y = augment(x, y, self.rng, self.ops, self.crop)
        elif self.crop != TILE:                   # centre crop for eval
            o = (TILE - self.crop) // 2
            x, y = x[:, o:o + self.crop, o:o + self.crop], y[o:o + self.crop, o:o + self.crop]
        r = self.idx.iloc[i]
        info = {"batch": r.batch, "sample_id": r.sample_id, "session": int(r.session), "row": int(r.row), "col": int(r.col)}
        return torch.from_numpy(np.ascontiguousarray(x)), torch.from_numpy(np.ascontiguousarray(y)), info


def collate(batch):
    xs, ys, infos = zip(*batch)
    return torch.stack(xs), torch.stack(ys), list(infos)
