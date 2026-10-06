"""Compute one plug-in spot feature on every spot (31 training + the test spots if present).

    python qc/spot_features/run.py local_porosity              # -> qc/processed/spot_features/local_porosity.csv
    python qc/spot_features/run.py local_porosity --workers 4 --only 4ih2ggld,xrv9xvzb   # quick check on two spots
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from preprocessing import preprocess as pp  # noqa: E402
from qc.features_table import TEST_DIR, TEST_IDS  # noqa: E402
from qc.spot_features import OUT_DIR, literal  # noqa: E402


def _job(args):
    plugin, batch_dir, sample_id, batch = args
    mod = importlib.import_module(f"qc.spot_features.{plugin}")
    raw = dataclasses.replace(pp.load_spot(batch_dir, sample_id), batch=batch)
    t0 = time.time()
    vals = mod.measure(pp.preprocess(raw), raw)
    missing = [c for c in mod.COLUMNS if c not in vals]
    if missing:
        raise KeyError(f"{plugin}.measure returned no {missing}")
    return {"batch": batch, "sample_id": sample_id, "session": raw.bse.shape[0],
            **{c: float(vals[c]) for c in mod.COLUMNS}, "_s": time.time() - t0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", help="comma-separated sample ids (quick check; does not write the CSV)")
    a = ap.parse_args()
    cols = literal(a.plugin, "COLUMNS")
    jobs = [(a.plugin, pp.DATA_DIR / b, s, b) for b, s in pp.list_spots()]
    jobs += [(a.plugin, TEST_DIR, s, "Test") for s in TEST_IDS] if TEST_DIR.exists() else []
    if a.only:
        jobs = [j for j in jobs if j[2] in a.only.split(",")]
    rows = []
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(_job, jobs):
            rows.append(r)
            print(f"{r['batch']:8s} {r['sample_id']:9s} " + " ".join(
                f"{r[c]:.4g}" if not math.isnan(r[c]) else "nan" for c in cols) + f"   {r.pop('_s'):.1f}s", flush=True)
    df = pd.DataFrame(rows).sort_values(["batch", "sample_id"]).reset_index(drop=True)
    print(df.groupby("batch")[cols].mean().to_string())
    if not a.only:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"{a.plugin}.csv"
        df.to_csv(out, index=False)
        print(f"wrote {out}: {df.shape}. Next: python qc/features_table.py && python qc/verdict.py && python ledger/ledger.py report")


if __name__ == "__main__":
    main()
