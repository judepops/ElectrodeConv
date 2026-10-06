"""Run the bank: make crop versions, run a feature family, or show what is done.

    python -m bank.run views --sites smoke --perts P0          # the 2 smoke crops
    python -m bank.run views --sites all --perts all           # everything (31 x 7 + 6 x 5 crop versions)
    python -m bank.run fam phase --sites smoke --perts P0      # one family on the smoke crops
    python -m bank.run fam phase --sites all --perts imaging --workers 6
    python -m bank.run status

--sites: all | smoke | inject | a comma list.   --perts: P0 | imaging | inject | all | a comma list.
Finished crop versions are skipped unless --force. A crop version that fails is reported and the rest carry on.
"""
import argparse
import json
import sys
import time
import traceback
from multiprocessing import get_context
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bank import core, families   # noqa: E402


def _view_job(job):
    crop_id, pert, force = job
    t0 = time.time()
    try:
        core.build_views(crop_id, pert, force)
        return crop_id, pert, time.time() - t0, None
    except Exception:
        return crop_id, pert, time.time() - t0, traceback.format_exc()


def _family_job(job):
    family, crop_id, pert = job
    t0 = time.time()
    try:
        module = families.load(family)
        res = module.extract(core.load_crop(crop_id, pert), dict(module.DEFAULT_CFG))
        core.save_result(res, crop_id, pert, seconds=time.time() - t0)
        return crop_id, pert, time.time() - t0, None
    except Exception:
        return crop_id, pert, time.time() - t0, traceback.format_exc()


def _run(fn, jobs, workers, what):
    failed = 0
    t0 = time.time()
    pool = get_context("spawn").Pool(workers) if workers > 1 and len(jobs) > 1 else None
    results = pool.imap_unordered(fn, jobs) if pool else map(fn, jobs)
    for i, (crop_id, pert, seconds, error) in enumerate(results, 1):
        print(f"  [{i}/{len(jobs)}] {what} {pert:<13} {crop_id}  {seconds:.1f} s" + ("  FAILED" if error else ""), flush=True)
        if error:
            failed += 1
            print(error, flush=True)
            with open(core.STATUS_LOG, "a") as f:
                f.write(json.dumps(dict(t=time.strftime("%Y-%m-%dT%H:%M:%S"), family=what, pert=pert, crop=crop_id,
                                        error=error.strip().splitlines()[-1])) + "\n")
    if pool:
        pool.close()
        pool.join()
    print(f"{what}: {len(jobs) - failed}/{len(jobs)} ok in {time.time() - t0:.0f} s")
    return failed


def status():
    import pandas as pd
    perts = (core.P0,) + core.IMAGING_PERTS + core.MATERIAL_INJECTS
    rows = {"views": {p: len(list((core.VIEWS_DIR / p).glob("*.npz"))) for p in perts}}
    for family in families.family_names():
        rows[family] = {p: len(list((core.FEAT_DIR / family / p).glob("*.done"))) for p in perts}
    print(pd.DataFrame(rows).T.to_string())
    print(f"\nexpected: {len(core.all_crops())} per imaging column, {len(core.INJECT_CROPS)} per injection column")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("what", choices=["views", "fam", "status"])
    p.add_argument("family", nargs="?")
    p.add_argument("--sites", default="smoke")
    p.add_argument("--perts", default=core.P0)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--force", action="store_true")
    a = p.parse_args(argv)
    if a.what == "status":
        return status()
    versions = core.crop_versions(a.sites, a.perts)
    core.STATUS_LOG.parent.mkdir(parents=True, exist_ok=True)
    if a.what == "views":
        jobs = [(c, pert, a.force) for c, pert in versions if a.force or not core.views_path(c, pert).exists()]
        print(f"views: {len(jobs)} to make ({len(versions) - len(jobs)} already there)")
        sys.exit(1 if _run(_view_job, jobs, a.workers, "views") else 0)
    if not a.family:
        p.error("fam needs a family name: " + ", ".join(families.family_names()))
    module = families.load(a.family)
    if hasattr(module, "warmup") and a.workers <= 1:
        module.warmup(dict(module.DEFAULT_CFG))
    jobs = [(a.family, c, pert) for c, pert in versions if a.force or not core.is_done(a.family, c, pert)]
    print(f"{a.family}: {len(jobs)} to run ({len(versions) - len(jobs)} already done)")
    sys.exit(1 if _run(_family_job, jobs, a.workers, a.family) else 0)


if __name__ == "__main__":
    main()
