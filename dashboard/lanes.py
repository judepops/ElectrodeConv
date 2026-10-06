"""Section 00 of the team page: the 13 lanes. Writes site/lanes.js and the pictures in site/img/lanes/.

    LOSSLARP_DATA_DIR=../losslarp/data python3 dashboard/lanes.py        # ~30 s, numpy and pillow only

Reads   dashboard/data/lanes.csv   one row per spot: its lane, its place along the lane, its batch, which spot it touches
                                   next and whether that neighbour is in a different batch folder, and whether the file
                                   carries an edge marker. (Order and joins come from matching the pixel columns at the
                                   edges of neighbouring images, see notes/seam_examples/README.md in the first repo.)
        the raw BSE images         data/Batch_*/img_<spot>_BSE.tif

Writes  site/lanes.js              window.LANES: the lanes, the seam close-ups and the edge-match numbers below
        site/img/lanes/<spot>.jpg  one thumbnail per spot, with one display stretch per lane so that neighbours match
        site/img/lanes/seam_*.jpg  the 4 joins that cross batch folders: 12 µm either side of the edge, at 25 nm per pixel

The pictures are for display only: a linear stretch per lane and a light gamma. Nothing in the data changes.

Edge match (the same idea as the seam examples): the mean of the last 4 pixel columns of the left image against the
mean of the first 4 of the right image, BSE channel 0, allowing the right image to slide up or down by up to 40 px;
the score is the best Pearson correlation. 1 = identical edges. For comparison, 80 random pairs of spots from
different lanes are scored the same way.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
IMG = SITE / "img" / "lanes"
LANES_CSV = HERE / "data" / "lanes.csv"
DATA = Path(os.environ.get("LOSSLARP_DATA_DIR", HERE.parent / "data"))

THUMB_REDUCE = 16      # 7000 px -> 437 px
SEAM_SIDE = 480        # pixels kept on each side of an edge (25 nm each: 12 µm)
SEAM_ROWS = 560
SEAM_OUT = (720, 420)
SHIFT = 40             # vertical slide allowed when matching two edges
EDGE_COLS = 4
GAMMA = 0.85
N_RANDOM = 80
SEED = 0


def load_bse(spot, batch):
    path = DATA / f"Batch_{batch}" / f"img_{spot}_BSE.tif"
    if not path.exists():
        sys.exit(f"{path} not found: set LOSSLARP_DATA_DIR to the folder that holds Batch_1, Batch_2 and Batch_3")
    a = np.asarray(Image.open(path))
    return np.ascontiguousarray(a[..., 0] if a.ndim == 3 else a)      # the three RGB channels are identical


def stretch(a, lo, hi):
    x = np.clip((a.astype(np.float32) - lo) / max(hi - lo, 1e-6), 0, 1) ** GAMMA
    return (255 * x + 0.5).astype(np.uint8)


def edge_profiles(img):
    """(first EDGE_COLS columns, last EDGE_COLS columns), each averaged over the columns: one value per row."""
    f = img.astype(np.float32)
    return f[:, :EDGE_COLS].mean(axis=1), f[:, -EDGE_COLS:].mean(axis=1)


def edge_score(a, b):
    """Best Pearson correlation of profile a (right edge of the left image) with b (left edge of the right image)
    over vertical slides of up to SHIFT rows. Returns (score, slide)."""
    best = (-2.0, 0)
    for dy in range(-SHIFT, SHIFT + 1):
        lo, hi = max(0, -dy), min(len(a), len(b) - dy)
        if hi - lo < 200:
            continue
        c = float(np.corrcoef(a[lo:hi], b[lo + dy:hi + dy])[0, 1])
        if c > best[0]:
            best = (c, dy)
    return best


def main():
    rows = list(csv.DictReader(open(LANES_CSV, encoding="utf-8")))
    for r in rows:
        r["lane"], r["position"], r["batch"] = int(r["lane"]), int(r["position"]), int(r["batch"])
    lane_ids = sorted({r["lane"] for r in rows})
    IMG.mkdir(parents=True, exist_ok=True)

    # ---- thumbnails, one display stretch per lane --------------------------------------------------------------
    aspect, profiles = {}, {}
    for lane in lane_ids:
        members = [r for r in rows if r["lane"] == lane]
        small = {}
        for r in members:
            img = load_bse(r["spot"], r["batch"])
            aspect[r["spot"]] = img.shape[0] / img.shape[1]
            profiles[r["spot"]] = edge_profiles(img)
            small[r["spot"]] = np.asarray(Image.fromarray(img).reduce(THUMB_REDUCE))
            del img
        lo, hi = np.percentile(np.concatenate([a.ravel() for a in small.values()]), [0.5, 99.7])
        for spot, a in small.items():
            Image.fromarray(stretch(a, lo, hi)).save(IMG / f"{spot}.jpg", quality=80, optimize=True)
        print(f"lane {lane:2d}: {len(members)} spots, stretch {lo:.0f}..{hi:.0f}", flush=True)

    # ---- edge-match numbers --------------------------------------------------------------------------------------
    by_id = {r["spot"]: r for r in rows}
    joins = [(r["spot"], r["touches_next"], r["join"]) for r in rows if r["touches_next"]]
    scores = {(a, b): edge_score(profiles[a][1], profiles[b][0]) for a, b, _ in joins}
    rng = np.random.default_rng(SEED)
    spots = [r["spot"] for r in rows]
    random_scores = []
    while len(random_scores) < N_RANDOM:
        a, b = rng.choice(spots, 2, replace=False)
        if by_id[a]["lane"] != by_id[b]["lane"]:
            random_scores.append(edge_score(profiles[a][1], profiles[b][0])[0])
    cross = [(a, b) for a, b, j in joins if j == "cross"]
    all_s, cross_s = [scores[(a, b)][0] for a, b, _ in joins], [scores[(a, b)][0] for a, b in cross]
    evidence = dict(joins=len(joins), cross=len(cross), join_min=round(min(all_s), 2), join_max=round(max(all_s), 2),
                    cross_min=round(min(cross_s), 2), cross_max=round(max(cross_s), 2), random_n=N_RANDOM,
                    random_mean=round(float(np.mean(random_scores)), 2), random_max=round(float(np.max(random_scores)), 2),
                    method=f"mean of the last {EDGE_COLS} pixel columns of the left image against the first {EDGE_COLS} of the right image, "
                           f"BSE, best Pearson correlation over vertical slides of up to {SHIFT} px")
    print("edge match:", evidence, flush=True)

    # ---- close-ups of the joins that cross batch folders --------------------------------------------------------
    seams = []
    for a, b in cross:
        ra, rb = by_id[a], by_id[b]
        left, right = load_bse(a, ra["batch"]), load_bse(b, rb["batch"])
        score, dy = scores[(a, b)]
        r0 = left.shape[0] // 2 - SEAM_ROWS // 2
        r0 = int(np.clip(r0, max(0, -dy), min(left.shape[0], right.shape[0] - dy) - SEAM_ROWS))
        crop = np.concatenate([left[r0:r0 + SEAM_ROWS, -SEAM_SIDE:], right[r0 + dy:r0 + dy + SEAM_ROWS, :SEAM_SIDE]], axis=1)
        lo, hi = np.percentile(crop, [0.5, 99.7])
        Image.fromarray(stretch(crop, lo, hi)).resize(SEAM_OUT, Image.LANCZOS).save(IMG / f"seam_{a}_{b}.jpg", quality=86, optimize=True)
        seams.append(dict(left=a, right=b, left_batch=ra["batch"], right_batch=rb["batch"], lane=ra["lane"],
                          img=f"img/lanes/seam_{a}_{b}.jpg", score=round(score, 2), slide_px=dy))
        del left, right
    print("seam close-ups:", [(s["left"], s["right"], s["score"]) for s in seams], flush=True)

    # ---- the file the page reads ---------------------------------------------------------------------------------
    lanes = []
    for lane in lane_ids:
        members = sorted((r for r in rows if r["lane"] == lane), key=lambda r: r["position"])
        lanes.append(dict(id=lane, session_px=int(members[0]["session_px"]), mixed=len({r["batch"] for r in members}) > 1,
                          spots=[dict(id=r["spot"], batch=r["batch"], aspect=round(aspect[r["spot"]], 4), img=f"img/lanes/{r['spot']}.jpg",
                                      touches_next=r["touches_next"], join=r["join"], edge=r["edge"]) for r in members]))
    out = dict(version=1, built=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), n_spots=len(rows), n_lanes=len(lanes),
               batch_sizes={str(b): sum(r["batch"] == b for r in rows) for b in (1, 2, 3)}, lanes=lanes, seams=seams, seam_side_px=SEAM_SIDE,
               evidence=evidence,
               source="dashboard/data/lanes.csv (order and joins from matching pixel columns at the edges of neighbouring images); "
                      "lane = what Polaron calls a lane = one imaging session, identified by the image height in pixels")
    (SITE / "lanes.js").write_text("window.LANES = " + json.dumps(out, separators=(",", ":")) + ";\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in IMG.glob("*.jpg")) / 1e6
    print(f"wrote site/lanes.js and {len(list(IMG.glob('*.jpg')))} pictures ({size:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
