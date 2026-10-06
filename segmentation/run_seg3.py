"""Precompute seg3 label maps in parallel (CPU; each worker uses 4 threads and ~1.5-2 GB).

    python segmentation/run_seg3.py --test                 # the 3 test spots in LOSSLARP_TEST_DIR (needed once per machine)
    python segmentation/run_seg3.py --all                  # every training spot too (only to re-check the committed maps)
    python segmentation/run_seg3.py --test --workers 3

Maps go to segmentation/processed/labels/ (git-ignored); preprocessing picks them up automatically.
"""
import argparse
import dataclasses
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _one(job):
    batch_dir, sid, batch = job
    from preprocessing import preprocess as pp
    from segmentation.masks import CACHE, compute_labels
    from PIL import Image
    t = time.time()
    raw = dataclasses.replace(pp.load_spot(batch_dir, sid), batch=batch)
    lab = compute_labels(raw.bse, raw.inlens, raw.se)
    CACHE.mkdir(parents=True, exist_ok=True)
    Image.fromarray(lab).save(CACHE / f"{batch}_{sid}_labels.png", optimize=True)
    return f"{batch}/{sid}: {time.time() - t:.0f}s  pore {float((lab == 0).mean()):.3f}  Si {float((lab == 2).mean()):.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="the test spots (qc/features_table.TEST_DIR, TEST_IDS)")
    ap.add_argument("--all", action="store_true", help="every training spot under LOSSLARP_DATA_DIR")
    ap.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 4) // 4)))
    a = ap.parse_args()
    from preprocessing import preprocess as pp
    jobs = []
    if a.test:
        from qc.features_table import TEST_DIR, TEST_IDS
        jobs += [(TEST_DIR, sid, "Test") for sid in TEST_IDS]
    if a.all:
        jobs += [(pp.DATA_DIR / b, sid, b) for b, sid in pp.list_spots()]
    if not jobs:
        ap.error("pass --test and/or --all")
    print(f"{len(jobs)} spot(s), {a.workers} worker(s)", flush=True)
    with ProcessPoolExecutor(a.workers) as ex:
        for line in ex.map(_one, jobs):
            print(line, flush=True)


if __name__ == "__main__":
    main()
