"""Step 1: make every SEM spot comparable before any feature or model sees it.

"Fair" means: a feature measured on two spots must differ because the material differs, not because the
microscope session differed. Tonight's work showed that image height, black level, contrast and noise all
mark the session, and that a model can tell the batches apart from those alone. This module removes them.

    from preprocessing.preprocess import load_spot, preprocess, list_spots
    spot = preprocess(load_spot("data/Batch_1", "4ih2ggld"))
    spot.bse      # float32, graphite units: 0 = black level, 1 = graphite, Si phase about 2
    spot.inlens   # float32 in 0..1, rank-normalised (any brightness/contrast curve removed)
    spot.se       # float32 in 0..1, rank-normalised (ETD or SE detector; same thing, two names)
    spot.void     # bool, open pores
    spot.bright   # bool, Si-like bright phase
    spot.meta     # what was done, plus the session fingerprints (never feed these to a model)

Steps, in order, all fixed by the constants below (no per-batch or per-label tuning anywhere):
    1. crop      the same central window of every image: drop the top 250 rows (frame artefact), the bottom
                 25 (current-collector band), 8 px on each side, then keep the central 1336 rows. Every spot
                 covers the same area, and image height, the strongest session cue, can no longer leak.
    2. anchor    BSE grey levels -> "graphite units": 0 = the image's own black level, 1 = its graphite mode.
                 Removes the black-level lift and the contrast setting of a session.
    3. noise     top every image up with Gaussian noise to one fixed noise level, so pore edges and particle
                 counts are measured at the same noise everywhere (quiet sessions no longer look "cleaner").
    4. rank      Inlens and SE have no physical grey scale, so map them to their rank (0..1), which removes
                 any monotonic brightness or contrast mapping.
    5. segment   void = Otsu between the pore and graphite peaks (clamped); bright = midpoint between
                 graphite and the image's own bright-phase peak. Both thresholds come from the image itself.

What this does NOT do, on purpose: no per-image 1-99 % stretch (it depends on how much Si the image holds),
no rescaling (pixel size is physical), no vertical flips or rotations (the material is anisotropic).

Only numpy, scipy and Pillow. Deterministic: the noise seed is a hash of the spot id.
    python preprocessing/preprocess.py            # every spot -> processed/<Batch>/<id>/tile_rRcCC.npz + processed/tiles.csv
    python preprocessing/preprocess.py 4ih2ggld   # just these sample ids
    tiles = load_tiles("Batch_1", "4ih2ggld")                 # the spot's tiles back, no recompute
    tile = load_tile("Batch_1", "4ih2ggld", 0, 5)             # one tile: Tile(bse, inlens, se, void, bright, ...)

Tiling: the preprocessed window (1336 x ~6984 px) is cut into a centred, non-overlapping grid of TILE x TILE
(512 x 512 px = 12.8 x 12.8 um) tiles: 2 rows x 13 columns = 26 tiles per spot, every tile fully inside the
window. Each tile holds the five planes above plus its position; a spot-level model can average over its tiles,
a tile-level model can train on all ~800. The whole-spot arrays are never written (recompute takes 4 s).
"""
from __future__ import annotations

import json
import math
import os
import re
import zlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("LOSSLARP_DATA_DIR", ROOT / "data"))   # Batch_* folders of raw TIFs
# Phase masks. "seg3" (default on this branch): the multi-detector pore / graphite / Si segmentation in segmentation/
# (BSE + Inlens + SE; see segmentation/README.md). "harmonise": the original BSE-only thresholds below
# (segment_void / segment_bright). Each source writes to its own processed folders (here, cnn/, qc/), so tiles,
# runs and verdicts of the two never mix. Choose with LOSSLARP_MASKS=seg3|harmonise.
MASK_SOURCE = os.environ.get("LOSSLARP_MASKS", "seg3")
if MASK_SOURCE not in ("seg3", "harmonise"):
    raise ValueError(f"LOSSLARP_MASKS must be seg3 or harmonise, not {MASK_SOURCE!r}")
PROCESSED_NAME = "processed_seg3" if MASK_SOURCE == "seg3" else "processed"
PROCESSED_DIR = Path(__file__).resolve().parent / PROCESSED_NAME
PIXEL_UM = 0.025                       # 25 nm per pixel, every image
TILE = 512                             # tile side in px (12.8 um); the grid is centred and non-overlapping

# ---- the recipe (change here, nowhere else) --------------------------------------------------------------
CROP_TOP, CROP_BOTTOM, CROP_SIDE, CROP_HEIGHT = 250, 25, 8, 1336
ANCHOR_BLUR = 2.0                      # anchors are read off a blurred copy (raw histograms are comb-quantised)
BLACK_PCT = 0.5                        # black level = this percentile of the blurred crop
GRAPHITE_WINDOW = (15, 92)             # graphite mode searched between these percentiles
BSE_NOISE_TARGET = 0.235               # graphite units, just above the noisiest known image
INLENS_NOISE_TARGET = 0.105            # rank units, same idea
SEG_BLUR = 2.0
VOID_OTSU_RANGE, VOID_CLAMP = (0.0, 1.2), (0.5, 0.75)
MIN_VOID_PX = 16
BRIGHT_BLUR = 1.5
BRIGHT_PEAK_RANGE = (1.1, 4.0)         # where the Si-phase peak is searched, in graphite units
BRIGHT_PEAK_MIN_SHARE = 0.002          # a peak must hold this share of pixels within +-0.05 of it
BRIGHT_FALLBACK = 2.1                  # used only when no peak is found (then meta["bright_peak_found"] is False)
BRIGHT_MARGIN = 0.1                    # an object must exceed its threshold by this somewhere
MIN_BRIGHT_PX, FILL_BRIGHT_HOLES_PX = 160, 400
DETECTOR_FILES = {"BSE": ("BSE",), "Inlens": ("Inlens",), "SE": ("ETD", "SE")}


@dataclass
class Spot:
    batch: str
    sample_id: str
    bse: np.ndarray
    inlens: np.ndarray
    se: np.ndarray
    void: np.ndarray
    bright: np.ndarray
    meta: dict = field(default_factory=dict)

    @property
    def solid(self):
        return ~self.void

    @property
    def area_um2(self):
        return self.void.size * PIXEL_UM ** 2


@dataclass
class Tile:
    batch: str
    sample_id: str
    row: int                           # grid row (0 = top)
    col: int                           # grid column (0 = left)
    y: int                             # top-left corner in the preprocessed window, px
    x: int
    bse: np.ndarray                    # (TILE, TILE) float32, graphite units
    inlens: np.ndarray                 # (TILE, TILE) float32 0..1
    se: np.ndarray
    void: np.ndarray                   # bool
    bright: np.ndarray
    meta: dict = field(default_factory=dict)   # the spot's meta + this tile's porosity / bright fraction

    @property
    def solid(self):
        return ~self.void

    @property
    def name(self):
        return f"tile_r{self.row}c{self.col:02d}"


@dataclass
class RawSpot:
    batch: str
    sample_id: str
    bse: np.ndarray                    # uint8 (H, W)
    inlens: np.ndarray
    se: np.ndarray


# ---- loading -------------------------------------------------------------------------------------------------
def list_spots(data_dir=DATA_DIR):
    """[(batch folder name, sample id)] for every spot under data_dir, sorted."""
    out = []
    for b in sorted(p for p in Path(data_dir).glob("Batch_*") if p.is_dir()):   # not data/Test (the unlabelled spots)
        ids = {p.stem.split("_")[1] for p in b.glob("img_*.tif")}
        out += [(b.name, s) for s in sorted(ids)]
    return out


def _read(path):
    img = np.asarray(Image.open(path))
    return img[..., 0] if img.ndim == 3 else img     # the RGB channels are identical


def load_spot(batch_dir, sample_id):
    """Read the three detector images of one spot. batch_dir: path to the batch folder."""
    batch_dir = Path(batch_dir)
    imgs = {}
    for det, names in DETECTOR_FILES.items():
        for n in names:
            p = batch_dir / f"img_{sample_id}_{n}.tif"
            if p.exists():
                imgs[det] = _read(p)
                break
        else:
            raise FileNotFoundError(f"no {det} image for {batch_dir.name}/{sample_id}")
    shapes = {v.shape for v in imgs.values()}
    if len(shapes) != 1:
        raise ValueError(f"{batch_dir.name}/{sample_id}: detector images differ in shape {shapes}")
    return RawSpot(batch_dir.name, sample_id, imgs["BSE"], imgs["Inlens"], imgs["SE"])


# ---- the steps ---------------------------------------------------------------------------------------------
def crop_box(height, width):
    """(r0, r1, c0, c1): the same-size central window of every image, inside the artefact-free rows."""
    top, bottom = CROP_TOP, height - CROP_BOTTOM
    n = min(CROP_HEIGHT, bottom - top)
    r0 = top + (bottom - top - n) // 2
    return r0, r0 + n, CROP_SIDE, width - CROP_SIDE


def _histogram_mode(values, lo, hi, bin_width=0.25, smooth_bins=4):
    edges = np.arange(lo, hi + bin_width, bin_width)
    hist, _ = np.histogram(values, edges)
    smooth = ndi.gaussian_filter1d(hist.astype(float), smooth_bins)
    i = int(np.argmax(smooth))
    shift = 0.0
    if 0 < i < len(smooth) - 1:
        a, b, c = smooth[i - 1], smooth[i], smooth[i + 1]
        if a - 2 * b + c != 0:
            shift = 0.5 * (a - c) / (a - 2 * b + c)        # parabolic refinement
    return float(edges[i] + (0.5 + shift) * bin_width)


def anchor(bse_crop):
    """-> (black level, graphite level) in raw grey levels, read off a blurred copy."""
    blur = ndi.gaussian_filter(bse_crop.astype(np.float32), ANCHOR_BLUR)
    sub = blur[::2, ::2].ravel()
    black = float(np.percentile(sub, BLACK_PCT))
    lo, hi = np.percentile(sub, GRAPHITE_WINDOW)
    graphite = _histogram_mode(sub[(sub >= lo) & (sub <= hi)], lo, hi)
    return black, graphite


def noise_sigma(img):
    """Noise SD by Immerkaer (1996): Laplacian-difference filter, mean absolute response."""
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    r = ndi.convolve(img.astype(np.float32), k, mode="reflect")[1:-1, 1:-1]
    return float(math.sqrt(math.pi / 2) * np.abs(r).mean() / 6)


def top_up_noise(img, target, seed):
    """Add Gaussian noise so the image's noise level reaches `target`. -> (image, sigma before, sigma added)."""
    sigma = noise_sigma(img)
    extra = math.sqrt(max(target ** 2 - sigma ** 2, 0.0))
    if extra > 0:
        img = img + np.random.default_rng(seed).standard_normal(img.shape, dtype=np.float32) * np.float32(extra)
    return img, sigma, extra


def rank_normalise(img_uint8, ref=None):
    """Grey level -> mid-rank CDF in 0..1: removes any monotonic brightness/contrast mapping. `ref`: the array the
    CDF is read from (default: the image itself; a caller can pass the central crop so statistics never depend on
    image height)."""
    hist = np.bincount((img_uint8 if ref is None else ref).ravel(), minlength=256).astype(np.float64)
    cdf = (np.cumsum(hist) - hist / 2) / hist.sum()
    return cdf[img_uint8].astype(np.float32)


def _otsu(values, bins=256):
    hist, edges = np.histogram(values, bins)
    centres = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centres) / np.maximum(w0, 1)
    m1 = (np.cumsum((hist * centres)[::-1])[::-1] / np.maximum(w1, 1))
    between = w0[:-1] * w1[:-1] * (m0[:-1] - m1[1:]) ** 2
    return float(centres[int(np.argmax(between))])


def _drop_small(mask, min_px):
    labels, n = ndi.label(mask, ndi.generate_binary_structure(2, 2))
    if n == 0:
        return mask
    sizes = np.bincount(labels.ravel())
    keep = sizes >= min_px
    keep[0] = False
    return keep[labels]


def _fill_small_holes(mask, max_px):
    return ~_drop_small(~mask, max_px + 1)


def segment_void(bse, threshold=None):
    """Open pores: Otsu between the pore and graphite peaks of the blurred, anchored BSE (clamped). `threshold`:
    reuse a threshold estimated elsewhere (e.g. on the central crop)."""
    blur = ndi.gaussian_filter(bse, SEG_BLUR)
    if threshold is None:
        sub = blur[::4, ::4].ravel()
        lo, hi = VOID_OTSU_RANGE
        threshold = float(np.clip(_otsu(sub[(sub >= lo) & (sub < hi)]), *VOID_CLAMP))
    void = _drop_small(blur < threshold, MIN_VOID_PX)
    return _fill_small_holes(void, MIN_VOID_PX), threshold


def bright_peak(bright_blur):
    """The Si phase's own grey level: the tallest real peak above graphite. -> (level, found)."""
    lo, hi = BRIGHT_PEAK_RANGE
    sub = bright_blur[::2, ::2].ravel()
    edges = np.arange(lo, hi + 0.01, 0.01)
    hist = ndi.gaussian_filter1d(np.histogram(sub, edges)[0].astype(float), 3)
    centres = (edges[:-1] + edges[1:]) / 2
    peaks, _ = find_peaks(hist, prominence=hist.max() * 0.05 if hist.max() > 0 else 1)
    for i in peaks[np.argsort(-hist[peaks])]:
        if (np.abs(sub - centres[i]) < 0.05).mean() >= BRIGHT_PEAK_MIN_SHARE:
            return float(centres[i]), True
    return BRIGHT_FALLBACK, False


def segment_bright(bse, peak=None, found=None):
    """Si-like bright phase: threshold at the midpoint between graphite (1) and the image's own bright peak.
    `peak`, `found`: reuse a peak estimated elsewhere (e.g. on the central crop)."""
    blur = ndi.gaussian_filter(bse, BRIGHT_BLUR)
    if peak is None:
        peak, found = bright_peak(blur)
    t = (1.0 + peak) / 2
    mask = ndi.binary_opening(blur > t, structure=np.ones((3, 3), bool))
    mask = _fill_small_holes(mask, FILL_BRIGHT_HOLES_PX)
    mask = _drop_small(mask, MIN_BRIGHT_PX)
    labels, n = ndi.label(mask, ndi.generate_binary_structure(2, 2))
    if n:
        peak_val = ndi.maximum(blur, labels, index=np.arange(1, n + 1))
        keep = np.concatenate([[False], peak_val >= t + BRIGHT_MARGIN])
        mask = keep[labels]
    return mask, t, peak, found


# ---- the whole thing ---------------------------------------------------------------------------------------
def _seg3_labels(raw):
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from segmentation.masks import seg3_labels
    return seg3_labels(raw)


def preprocess(raw: RawSpot, box=None) -> Spot:
    """box: (r0, r1, c0, c1) to override the standard window (qc/depth_profile.py uses the full height)."""
    H, W = raw.bse.shape
    r0, r1, c0, c1 = box or crop_box(H, W)
    seed = zlib.crc32(f"{raw.batch}/{raw.sample_id}".encode())

    bse_raw = raw.bse[r0:r1, c0:c1]
    black, graphite = anchor(bse_raw)
    bse = (bse_raw.astype(np.float32) - black) / np.float32(max(graphite - black, 1.0))
    bse, bse_sigma, bse_added = top_up_noise(bse, BSE_NOISE_TARGET, seed)

    inlens, inl_sigma, inl_added = top_up_noise(rank_normalise(raw.inlens[r0:r1, c0:c1]), INLENS_NOISE_TARGET, seed + 1)
    se = rank_normalise(raw.se[r0:r1, c0:c1])

    void, t_void = segment_void(bse)
    bright, t_bright, peak, found = segment_bright(bse)
    porosity_harmonise, bright_frac_harmonise = float(void.mean()), float(bright.mean())
    if MASK_SOURCE == "seg3":                # replace both masks; the BSE / Inlens / SE planes are unchanged
        lab = _seg3_labels(raw)[r0:r1, c0:c1]
        void, bright = lab == 0, lab == 2    # 255 (not electrode, e.g. Cu foil) counts as neither

    meta = {
        "crop": (r0, r1, c0, c1), "raw_height": H, "raw_width": W,
        # session fingerprints: useful for audits, never model inputs
        "bse_black_level": black, "bse_graphite_level": graphite, "bse_contrast": graphite - black,
        "bse_noise_sigma": bse_sigma, "bse_noise_added": bse_added, "bse_noisier_than_target": bse_added == 0.0,
        "inlens_noise_sigma": inl_sigma, "inlens_noise_added": inl_added,
        "void_threshold": t_void, "bright_peak": peak, "bright_peak_found": found, "bright_threshold": t_bright,
        "porosity": float(void.mean()), "bright_frac": float(bright.mean()), "mask_source": MASK_SOURCE,
        "porosity_harmonise": porosity_harmonise, "bright_frac_harmonise": bright_frac_harmonise,
    }
    return Spot(raw.batch, raw.sample_id, bse, inlens, se, void, bright, meta)


def load_and_preprocess(batch_dir, sample_id):
    return preprocess(load_spot(batch_dir, sample_id))


# ---- tiling ------------------------------------------------------------------------------------------------
def tile_grid(shape, tile=TILE):
    """[(row, col, y, x)] of a centred non-overlapping grid of tile x tile squares inside an (H, W) window."""
    H, W = shape
    nr, nc = H // tile, W // tile
    y0, x0 = (H - nr * tile) // 2, (W - nc * tile) // 2
    return [(r, c, y0 + r * tile, x0 + c * tile) for r in range(nr) for c in range(nc)]


def tiles_of(spot: Spot, tile=TILE):
    out = []
    for r, c, y, x in tile_grid(spot.bse.shape, tile):
        sl = (slice(y, y + tile), slice(x, x + tile))
        void, bright = spot.void[sl], spot.bright[sl]
        meta = {**spot.meta, "tile_px": tile, "tile_porosity": float(void.mean()), "tile_bright_frac": float(bright.mean())}
        out.append(Tile(spot.batch, spot.sample_id, r, c, y, x, spot.bse[sl], spot.inlens[sl], spot.se[sl], void, bright, meta))
    return out


# ---- saving / loading the tiles ------------------------------------------------------------------------------
def save_tiles(spot: Spot, out_dir=PROCESSED_DIR, tile=TILE):
    """-> the tiles written, one compressed .npz each under processed/<batch>/<sample_id>/."""
    folder = Path(out_dir) / spot.batch / spot.sample_id
    folder.mkdir(parents=True, exist_ok=True)
    tiles = tiles_of(spot, tile)
    for t in tiles:
        np.savez_compressed(folder / f"{t.name}.npz", bse=t.bse, inlens=t.inlens, se=t.se, void=t.void, bright=t.bright,
                            pos=np.array([t.row, t.col, t.y, t.x], np.int32), meta=np.array(json.dumps(t.meta)))
    return tiles


def load_tile(batch, sample_id, row, col, out_dir=PROCESSED_DIR) -> Tile:
    with np.load(Path(out_dir) / batch / sample_id / f"tile_r{row}c{col:02d}.npz") as z:
        r, c, y, x = (int(v) for v in z["pos"])
        return Tile(batch, sample_id, r, c, y, x, z["bse"], z["inlens"], z["se"], z["void"], z["bright"],
                    json.loads(str(z["meta"])))


def load_tiles(batch, sample_id, out_dir=PROCESSED_DIR):
    """Every tile of one spot, in grid order."""
    folder = Path(out_dir) / batch / sample_id
    out = []
    for p in sorted(folder.glob("tile_*.npz")):
        m = re.fullmatch(r"tile_r(\d+)c(\d+)", p.stem)
        out.append(load_tile(batch, sample_id, int(m.group(1)), int(m.group(2)), out_dir))
    return out


def list_processed(out_dir=PROCESSED_DIR):
    """[(batch, sample_id)] of every spot with tiles on disk."""
    return sorted({(p.parent.parent.name, p.parent.name) for p in Path(out_dir).glob("*/*/tile_*.npz")})


if __name__ == "__main__":
    import csv
    import sys
    import time
    spots = list_spots()
    only = sys.argv[1:]      # optional: sample ids to run
    spots = [(b, s) for b, s in spots if not only or s in only]
    print(f"{len(spots)} spots under {DATA_DIR} -> {PROCESSED_DIR}")
    keys = ["raw_height", "bse_black_level", "bse_contrast", "bse_noise_sigma", "bright_peak", "bright_peak_found",
            "porosity", "bright_frac"]
    print("batch    id        " + " ".join(f"{k[:14]:>14}" for k in keys))
    rows = []
    for b, s in spots:
        t0 = time.time()
        spot = load_and_preprocess(DATA_DIR / b, s)
        tiles = save_tiles(spot)
        m = spot.meta
        for t in tiles:
            rows.append({"batch": b, "sample_id": s, "session": m["raw_height"], "tile": t.name, "row": t.row, "col": t.col,
                         "y": t.y, "x": t.x, "tile_porosity": t.meta["tile_porosity"], "tile_bright_frac": t.meta["tile_bright_frac"],
                         **{k: v for k, v in m.items() if not isinstance(v, tuple)}})
        print(f"{b:8s} {s:9s} " + " ".join(f"{m[k]:14.3f}" if isinstance(m[k], float) else f"{m[k]!s:>14}" for k in keys)
              + f"   {len(tiles)} tiles  {time.time() - t0:.1f}s", flush=True)
    index = PROCESSED_DIR / "tiles.csv"
    old = {}
    if index.exists() and only:                      # partial run: keep the other spots' rows
        with open(index) as f:
            old = {(r["batch"], r["sample_id"], r["tile"]): r for r in csv.DictReader(f)}
    for r in rows:
        old[(r["batch"], r["sample_id"], r["tile"])] = r
    rows = [old[k] for k in sorted(old)]
    with open(index, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {index} ({len(rows)} tiles)")
