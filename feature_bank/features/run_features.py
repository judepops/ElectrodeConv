"""Step 2: compute every feature for every sample and write features.csv.

Reads:   data/Batch_*/ through `preprocessing` (clean images are cached in processed/full/,
         made on the fly if missing), and every features/<name>/feature.py (each @feature function
         becomes one column; a dict return becomes one column per key).
Writes:  processed/features.csv: one row per sample (microscope spot), one column per
         feature, plus batch / sample_id / split. It is gitignored: anyone can regenerate it.
         With --train, each feature's train() also saves whatever it learns into models/.

Run from the repo root:
    python features/run_features.py                        # every batch, every feature
    python features/run_features.py --train                # first train the trained features on the BASELINE only
    python features/run_features.py --batches Batch_4      # (re)compute only Batch_4; rows of other batches are kept
    python features/run_features.py --csv other.csv        # write somewhere else (default: processed/features.csv)

Why train on the baseline only: a feature that learns what "normal" looks like must only ever see
the approved material, otherwise it would quietly learn the incoming batches' quirks as normal too.
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `preprocessing` and `features` import from the repo root

from preprocessing import BASELINE, ROOT, iter_samples, list_batches, list_samples, load_samples   # noqa: E402
from features import REGISTRY, compute_all, load_feature_modules, train_all                      # noqa: E402

META = ["batch", "sample_id", "split"]     # the non-feature columns of features.csv


def compute_rows(batches):
    """One dict per sample: batch, sample_id, split and every feature value. Prints progress."""
    todo = list_samples(batches)
    rows = []
    t0 = time.time()
    for i, sample in enumerate(iter_samples(batches), 1):
        rows.append({"batch": sample.batch, "sample_id": sample.sample_id, "split": sample.split,
                     **compute_all(sample)})
        # seconds include loading the 3 images (about 1 s from the processed/ cache) and every feature
        print(f"  [{i}/{len(todo)}] {sample.batch}/{sample.sample_id}  {time.time() - t0:.1f} s", flush=True)
        t0 = time.time()
    return rows


def merge_with_existing(new, csv_path, recomputed_batches):
    """Keep the old CSV's rows for batches we did not recompute, replace the rest with `new`."""
    old = pd.read_csv(csv_path)
    kept = old[~old["batch"].isin(recomputed_batches)]
    print(f"keeping {len(kept)} rows from {csv_path} for {sorted(kept['batch'].unique())}")
    return pd.concat([kept, new], ignore_index=True)


def print_summary(df):
    """Compact table: mean of every feature per batch (features down the side, batches across)."""
    feature_cols = [c for c in df.columns if c not in META]
    print("\nsamples per batch:", df["batch"].value_counts().sort_index().to_dict())
    if not feature_cols:
        return
    means = df.groupby("batch")[feature_cols].mean().T
    with pd.option_context("display.max_rows", None, "display.width", 200,
                           "display.float_format", "{:.4g}".format):
        print("\nmean of each feature per batch:")
        print(means)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batches", nargs="+", metavar="BATCH",
                        help="only (re)compute these batches, keeping other batches' rows in the CSV (default: all)")
    parser.add_argument("--train", action="store_true",
                        help="call train(baseline_samples) in every feature file that has one, before computing")
    parser.add_argument("--csv", default=str(ROOT / "processed" / "features.csv"), help="output CSV (default: processed/features.csv)")
    args = parser.parse_args(argv)

    csv_path = Path(args.csv)
    batches = args.batches
    if batches:
        unknown = sorted(set(batches) - set(list_batches()))
        if unknown:
            sys.exit(f"no such batch folder in data/: {unknown}. Available: {list_batches()}")

    load_feature_modules()
    print(f"{len(REGISTRY)} features registered: {', '.join(REGISTRY) or '(none - add a features/<name>/feature.py)'}")

    if args.train:
        print(f"\ntraining on the baseline ({BASELINE}) only ...")
        train_all(load_samples(BASELINE))

    print(f"\ncomputing features for {batches or 'all batches'} ...")
    t0 = time.time()
    df = pd.DataFrame(compute_rows(batches))
    print(f"done in {time.time() - t0:.0f} s")

    if batches and csv_path.exists():
        df = merge_with_existing(df, csv_path, batches)

    feature_cols = [c for c in df.columns if c not in META]
    df = df[META + feature_cols].sort_values(["batch", "sample_id"]).reset_index(drop=True)
    df.to_csv(csv_path, index=False)
    print(f"\nwrote {csv_path}  ({len(df)} rows x {len(feature_cols)} features)")
    print_summary(df)


if __name__ == "__main__":
    main()
