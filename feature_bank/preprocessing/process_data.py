"""Turns the raw TIFs in data/ into clean images, tiles and Samples. The only program in this folder.

    python preprocessing/process_data.py                        # settings from config.yaml
    python preprocessing/process_data.py --size 256 --stride 128
    python preprocessing/process_data.py --batches Batch_4      # a new batch only
    python preprocessing/process_data.py --force                # remake everything

Steps for each image:
    1. grey        read the TIF as one 8-bit channel (the files are grey saved as RGB)
    2. trim        drop plain white / black border rows and columns
    3. normalise   stretch brightness so every image uses the full 0-255 range
    4. tiles       cut into square tiles for training
    5. acquisition check (per spot)  was it imaged like the known spots? Prints a WARNING per problem
                   (curtaining, blur, noise, Inlens burn-out, ...); see preprocessing/acquisition.py

Reads:   data/{batch}/img_{sample_id}_{detector}.tif
Writes:  processed/full/{batch}/{sample_id}_{detector}.png                     clean image (steps 1-3)
         processed/tiles/{size}px_stride{stride}_scale{scale}/{split}/{batch}/{sample_id}_{detector}_y{y}_x{x}.png
         processed/tiles/{size}px_stride{stride}_scale{scale}/index.csv         one row per tile
         processed/acquisition.csv                                                step 5, one row per spot

{split} is train / val / test, decided per spot (never per tile) from config.yaml. Each split folder
works as a torchvision ImageFolder with class = batch. Mostly blank tiles are dropped. Images already
done are skipped unless --force.

Also the library the features import:
    from preprocessing import load_sample, iter_samples, tiles, CONFIG, BASELINE, PIXEL_SIZE_UM
Sections: SETTINGS -> ONE IMAGE -> ONE SPOT (Sample) -> THE COMMAND.
"""
import argparse
import os
import random
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from PIL import Image

__all__ = ["ROOT", "DATA_DIR", "PROCESSED_DIR", "MODELS_DIR", "CONFIG", "BASELINE", "PIXEL_SIZE_UM", "DETECTORS",
           "load_grey", "trim_border", "normalise_brightness", "clean", "tiles",
           "Sample", "list_batches", "list_samples", "raw_path", "load_image", "load_sample", "iter_samples",
           "load_samples", "split_of"]

# ----------------------------------------------------------------------------------------------------
# SETTINGS  (from config.yaml, read once)
# ----------------------------------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]   # the repo folder
# The three folders can be moved with environment variables (cloud/modal_app.py points them at a Modal Volume).
DATA_DIR = Path(os.environ.get("LOSSLARP_DATA_DIR", ROOT / "data"))                # raw TIFs, one folder per batch (committed to git)
PROCESSED_DIR = Path(os.environ.get("LOSSLARP_PROCESSED_DIR", ROOT / "processed")) # clean images + tiles made by this program (NOT in git)
MODELS_DIR = Path(os.environ.get("LOSSLARP_MODELS_DIR", ROOT / "models"))          # anything a feature learns in train() (small files only)
FULL_DIR = PROCESSED_DIR / "full"            # processed/full/{batch}/{sample_id}_{detector}.png

with open(Path(__file__).with_name("config.yaml")) as f:
    CONFIG = yaml.safe_load(f)

BASELINE = CONFIG["baseline_batch"]          # the approved material every other batch is compared against
PIXEL_SIZE_UM = float(CONFIG["pixel_size_um"])
DETECTORS = ("BSE", "SE", "Inlens")
DETECTOR_ALIASES = {"ETD": "SE"}             # same detector, two names in the files
SPLITS = ("train", "val", "test")

Image.MAX_IMAGE_PIXELS = None   # the TIFs are 7000 px wide; stop Pillow's "decompression bomb" warning


# ----------------------------------------------------------------------------------------------------
# ONE IMAGE  (steps 1-4)
# ----------------------------------------------------------------------------------------------------
def load_grey(path):
    """Step 1: read a TIF as a 2D uint8 array. The three RGB channels are identical, so take the first."""
    img = np.asarray(Image.open(path))
    return img[..., 0] if img.ndim == 3 else img


def trim_border(img, white=245, black=10, frac=0.95):
    """Step 2: remove any rows/columns at the edges that are almost entirely white or black.

    A row/column counts as border when >= `frac` of its pixels are >= `white` or <= `black`.
    Real microstructure never fills a whole 7000 px row with one value, so this is safe.
    """
    def border_lines(axis):
        w = (img >= white).mean(axis=axis) >= frac
        b = (img <= black).mean(axis=axis) >= frac
        return w | b

    def keep_span(border):
        keep = np.flatnonzero(~border)
        return (keep[0], keep[-1] + 1) if len(keep) else (0, len(border))

    r0, r1 = keep_span(border_lines(axis=1))
    c0, c1 = keep_span(border_lines(axis=0))
    return img[r0:r1, c0:c1]


def normalise_brightness(img, low=1, high=99):
    """Step 3: percentile stretch to 0-255 so images taken with different brightness settings line up.

    Deliberate small loss: the darkest 1 % and brightest 1 % of pixels are clipped.
    """
    lo, hi = np.percentile(img, [low, high])
    stretched = (img.astype(np.float32) - lo) / max(hi - lo, 1.0)
    return (np.clip(stretched, 0, 1) * 255).astype(np.uint8)


def clean(path):
    """Raw TIF path -> clean 2D uint8 image (steps 1-3)."""
    return normalise_brightness(trim_border(load_grey(path)))


def tiles(img, size=512, stride=None, scale=1.0):
    """Step 4: cut an image into square tiles. Returns a list of (y, x, tile), y/x in the (scaled) image.

    Images have different heights, so the number of tiles varies per image; the ragged edge that does
    not fit a whole tile is dropped (deliberate small loss). stride < size gives overlapping tiles.
    """
    stride = stride or size
    if scale != 1.0:
        im = Image.fromarray(img)
        img = np.asarray(im.resize((round(im.width * scale), round(im.height * scale)), Image.BILINEAR))
    h, w = img.shape[:2]
    return [(y, x, img[y:y + size, x:x + size])
            for y in range(0, h - size + 1, stride)
            for x in range(0, w - size + 1, stride)]


# ----------------------------------------------------------------------------------------------------
# ONE SPOT  (the Sample everyone's features take as input)
# ----------------------------------------------------------------------------------------------------
@dataclass
class Sample:
    """One spot on one sample, with its three detector images (2D uint8, clean)."""
    batch: str          # e.g. "Batch_1"
    sample_id: str      # e.g. "4ih2ggld"
    bse: np.ndarray     # backscattered electrons: brightness = atomic weight -> best for telling materials apart
    se: np.ndarray      # secondary electrons (ETD/SE): surface texture
    inlens: np.ndarray  # in-lens detector: edges and the fine binder/carbon network
    _raw: dict = field(default_factory=dict, repr=False, compare=False)   # raw images, loaded on first use

    def __post_init__(self):
        # raw images handed in at construction (perturbation tests) are not the files on disk: caches must skip them
        self.raw_injected = bool(self._raw)

    @property
    def is_baseline(self):
        return self.batch == BASELINE

    @property
    def split(self):
        return split_of(self.batch, self.sample_id)

    @property
    def shape(self):
        return self.bse.shape

    @property
    def session(self):
        """Acquisition session id: the image height in pixels. Spots imaged in one microscope session share it
        (and their black level, noise and grey mapping). For grouping and leakage checks only, never a model input."""
        return int(self.bse.shape[0])

    def raw(self, detector):
        """The raw TIF of one detector as 2D uint8 (step 1 only: no trim, no stretch), loaded once and cached.

        The harmonisation in features/_common/ needs the true grey levels: the 1-99 % stretch of `bse` depends on
        how much bright phase the image holds, so thresholds on it are not comparable between spots.
        """
        if detector not in self._raw:
            self._raw[detector] = load_grey(raw_path(self.batch, self.sample_id, detector))
        return self._raw[detector]


def list_batches():
    """Every data/Batch_* folder, sorted."""
    return sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir() and p.name.startswith("Batch"))


def list_samples(batches=None):
    """Sorted (batch, sample_id) pairs. `batches` can be a name, a list of names, or None for all."""
    if isinstance(batches, str):
        batches = [batches]
    out = []
    for batch in batches or list_batches():
        ids = {p.stem.split("_")[1] for p in (DATA_DIR / batch).glob("img_*.tif")}
        out += [(batch, sid) for sid in sorted(ids)]
    return out


def raw_path(batch, sample_id, detector):
    """Path of the raw TIF, trying the detector's alias too (ETD/SE)."""
    names = [detector] + [alias for alias, canon in DETECTOR_ALIASES.items() if canon == detector]
    for name in names:
        p = DATA_DIR / batch / f"img_{sample_id}_{name}.tif"
        if p.exists():
            return p
    raise FileNotFoundError(f"no {detector} image for {batch}/{sample_id}")


def load_image(batch, sample_id, detector, force=False):
    """One clean image (2D uint8). Uses processed/full/ if present, otherwise makes it from the TIF.

    force=True ignores the saved PNG and remakes it (--force).
    """
    png = FULL_DIR / batch / f"{sample_id}_{detector}.png"
    if png.exists() and not force:
        return np.asarray(Image.open(png))
    img = clean(raw_path(batch, sample_id, detector))
    png.parent.mkdir(parents=True, exist_ok=True)
    tmp = png.with_name(png.name + ".tmp")       # write next to it, then rename: another process running
    Image.fromarray(img).save(tmp, format="PNG")  # run_features.py at the same time never reads a half file
    os.replace(tmp, png)
    return img


def load_sample(batch, sample_id):
    return Sample(batch, sample_id, *(load_image(batch, sample_id, d) for d in DETECTORS))


def iter_samples(batches=None):
    """Yield one Sample at a time (low memory). Same `batches` argument as list_samples."""
    for batch, sid in list_samples(batches):
        yield load_sample(batch, sid)


def load_samples(batches=None):
    """All Samples as a list (about 50 MB each: fine for one batch, heavy for everything)."""
    return list(iter_samples(batches))


def split_of(batch, sample_id):
    """'train' / 'val' / 'test' for a sample, from config.yaml. Deterministic: same seed -> same split.

    Done per batch: the batch's sample ids are shuffled with the seed and cut by the ratios.
    """
    cfg = CONFIG["split"]
    ids = sorted(sid for _, sid in list_samples(batch))
    random.Random(cfg["seed"]).shuffle(ids)
    n = len(ids)
    n_train = round(n * cfg["train"])
    n_val = round(n * cfg["val"])
    i = ids.index(sample_id)
    return "train" if i < n_train else "val" if i < n_train + n_val else "test"


# ----------------------------------------------------------------------------------------------------
# THE COMMAND  (python preprocessing/process_data.py)
# ----------------------------------------------------------------------------------------------------
INDEX_COLUMNS = ["path", "batch", "sample_id", "detector", "split", "is_baseline", "y", "x", "size", "scale"]


def parse_args():
    defaults = CONFIG["tiles"]
    p = argparse.ArgumentParser(description="Make clean full images and training tiles from the raw TIFs. "
                                            "Defaults for --size/--stride/--scale come from preprocessing/config.yaml.")
    p.add_argument("--size", type=int, default=defaults["size"],
                   help=f"square tile side in pixels (default {defaults['size']})")
    p.add_argument("--stride", type=int, default=defaults["stride"],
                   help=f"step between tiles in pixels; smaller than --size gives overlapping tiles (default {defaults['stride']})")
    p.add_argument("--scale", type=float, default=defaults["scale"],
                   help=f"shrink the image by this factor before tiling; 0.5 = a tile covers twice the area (default {defaults['scale']})")
    p.add_argument("--batches", nargs="+", metavar="BATCH", help="only these batches (default: every data/Batch_*)")
    p.add_argument("--force", action="store_true",
                   help="remake the clean full images and the tiles of these batches even if they exist")
    p.add_argument("--no-acquisition-check", action="store_true",
                   help="skip step 5 (the acquisition check, ~10 s per spot the first time)")
    return p.parse_args()


def check_acquisition(batch, sample_id, known, force):
    """Step 5 for one spot: -> (row for processed/acquisition.csv, warnings). Reuses the stored row unless force."""
    if str(ROOT) not in sys.path:     # run as a script: make preprocessing/ and features/ importable
        sys.path.insert(0, str(ROOT))
    from preprocessing import acquisition
    if not force and (batch, sample_id) in known.index:
        values = known.loc[(batch, sample_id)].to_dict()
    else:
        values = acquisition.measure(load_sample(batch, sample_id))
    status, _ = acquisition.gate_status(values)
    return {"batch": batch, "sample_id": sample_id, "acq_status": status, **values}, acquisition.warnings_for(values)


def is_blank(tile, frac=0.5):
    """True when a tile is not microstructure: mostly pure white/black, or (almost) no contrast at all.

    A leftover border, a scale bar or an empty region looks like this; real electrode material always
    has pores (dark) and particles (bright) mixed within a tile, so it never trips this test.
    """
    extreme = ((tile >= 250) | (tile <= 5)).mean()
    return extreme >= frac or tile.std() < 3


def existing_tiles(tiles_dir, batch, sample_id, detector):
    """Tile PNGs already on disk for this image, in whichever split folder they are."""
    return sorted(tiles_dir.glob(f"*/{batch}/{sample_id}_{detector}_y*_x*.png"))


def write_tiles(img, out_dir, prefix, size, stride, scale):
    """Cut `img` into tiles and save the non-blank ones as PNGs. Returns (n_written, n_blank_dropped)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n_written = n_blank = 0
    for y, x, tile in tiles(img, size, stride, scale):
        if is_blank(tile):
            n_blank += 1
            continue
        Image.fromarray(tile).save(out_dir / f"{prefix}_y{y}_x{x}.png")
        n_written += 1
    return n_written, n_blank


def build_index(tiles_dir, size, scale):
    """One row per tile PNG under tiles_dir. Rebuilt from the file names, so it always matches the folder."""
    rows = []
    for png in sorted(tiles_dir.glob("*/*/*.png")):
        split, batch = png.parent.parent.name, png.parent.name
        sample_id, detector, y, x = png.stem.rsplit("_", 3)   # "{sample_id}_{detector}_y{y}_x{x}"
        rows.append(dict(path=png.relative_to(ROOT).as_posix(), batch=batch, sample_id=sample_id,
                         detector=detector, split=split, is_baseline=batch == BASELINE,
                         y=int(y[1:]), x=int(x[1:]), size=size, scale=scale))
    index = pd.DataFrame(rows, columns=INDEX_COLUMNS)
    return index.sort_values(["batch", "sample_id", "detector", "y", "x"], ignore_index=True)


def main():
    args = parse_args()
    t0 = time.perf_counter()

    batches = args.batches or list_batches()
    unknown = sorted(set(batches) - set(list_batches()))
    if unknown:
        sys.exit(f"unknown batch(es) {unknown}; data/ has {list_batches()}")

    setting = f"{args.size}px_stride{args.stride}_scale{args.scale}"
    tiles_dir = PROCESSED_DIR / "tiles" / setting
    print(f"tiles: {args.size} px, stride {args.stride}, scale {args.scale}  ->  {tiles_dir.relative_to(ROOT)}")
    print(f"batches: {', '.join(batches)}   (baseline = {BASELINE})\n")

    if args.force:   # clean slate for the requested batches only; other batches' tiles stay
        for split in SPLITS:
            for batch in batches:
                shutil.rmtree(tiles_dir / split / batch, ignore_errors=True)

    acq_csv = PROCESSED_DIR / "acquisition.csv"
    acq_old = pd.read_csv(acq_csv) if acq_csv.exists() else pd.DataFrame(columns=["batch", "sample_id", "acq_status"])
    acq_known = acq_old.drop(columns="acq_status").set_index(["batch", "sample_id"])
    acq_rows, acq_warned = [], []

    n_images = n_written = n_blank = n_skipped = n_trimmed = 0
    for batch, sample_id in list_samples(batches):
        split = split_of(batch, sample_id)
        for detector in DETECTORS:
            raw_w, raw_h = Image.open(raw_path(batch, sample_id, detector)).size   # header only, cheap
            img = load_image(batch, sample_id, detector, force=args.force)         # makes processed/full/...png
            n_images += 1
            h, w = img.shape
            label = f"{batch}/{sample_id}  {detector:<6} {split:<5} {h}x{w}"

            if (h, w) != (raw_h, raw_w):
                n_trimmed += 1
                print(f"{label}  BORDER TRIMMED: raw TIF was {raw_h}x{raw_w}")

            old = existing_tiles(tiles_dir, batch, sample_id, detector)
            if old and all(p.parent.parent.name == split for p in old):
                n_skipped += 1
                print(f"{label}  already tiled ({len(old)} tiles), skipped")
                continue
            for p in old:            # tiles sit in another split folder: config.yaml's split changed, so redo
                p.unlink()

            written, blank = write_tiles(img, tiles_dir / split / batch, f"{sample_id}_{detector}",
                                         args.size, args.stride, args.scale)
            n_written += written
            n_blank += blank
            print(f"{label}  {written} tiles" + (f", {blank} blank dropped" if blank else ""), flush=True)

        if not args.no_acquisition_check:
            row, warns = check_acquisition(batch, sample_id, acq_known, args.force)
            acq_rows.append(row)
            print(f"{batch}/{sample_id}  acquisition {row['acq_status']}" + ("" if warns else ": imaged like the known spots"))
            for w in warns:
                print(f"{batch}/{sample_id}  WARNING: {w}", flush=True)
            if warns:
                acq_warned.append((f"{batch}/{sample_id}", row["acq_status"], warns))

    index = build_index(tiles_dir, args.size, args.scale)
    index.to_csv(tiles_dir / "index.csv", index=False)

    print(f"\ntiles per batch x split in {tiles_dir.relative_to(ROOT)} (all batches on disk):")
    if len(index):
        table = index.pivot_table(index="batch", columns="split", values="path", aggfunc="count",
                                  fill_value=0, margins=True, margins_name="total")
        table = table[[s for s in SPLITS if s in table.columns] + ["total"]]
        print(table.to_string())
    else:
        print("  (no tiles)")

    print(f"\nimages processed:     {n_images}  (clean PNGs in {PROCESSED_DIR.relative_to(ROOT) / 'full'})")
    print(f"images border-trimmed: {n_trimmed}")
    print(f"images skipped:       {n_skipped}  (already tiled; use --force to redo)")
    print(f"tiles written:        {n_written}  ({n_blank} blank tiles dropped)")
    print(f"index:                {(tiles_dir / 'index.csv').relative_to(ROOT)}  ({len(index)} rows)")
    if acq_rows:
        done = {(r["batch"], r["sample_id"]) for r in acq_rows}
        keep = acq_old[[(b, i) not in done for b, i in zip(acq_old["batch"], acq_old["sample_id"])]]
        table = pd.concat([keep, pd.DataFrame(acq_rows)], ignore_index=True).sort_values(["batch", "sample_id"])
        table.to_csv(acq_csv, index=False)
        print(f"acquisition check:    {len(acq_rows)} spots, {len(acq_warned)} with warnings  "
              f"({acq_csv.relative_to(ROOT)})")
    print(f"time:                 {time.perf_counter() - t0:.1f} s")
    if acq_warned:
        print(f"\n{'=' * 100}\nACQUISITION WARNINGS: {len(acq_warned)} spot(s) were not imaged like the known spots.\n"
              "Their features may reflect the microscope, not the material. G-C = not comparable, re-image next to a "
              "retained reference.\n")
        for spot, status, warns in acq_warned:
            print(f"  {spot}  {status}")
            for w in warns:
                print(f"      - {w}")
        print("=" * 100)


if __name__ == "__main__":
    main()
