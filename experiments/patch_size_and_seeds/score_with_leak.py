"""Score a set of V1 runs: batch accuracy AND the session-leak test, one row per run.

    python experiments/patch_size_and_seeds/score_with_leak.py "exp_*"            # runs under cnn/processed/
    python experiments/patch_size_and_seeds/score_with_leak.py "exp_*" --runs-dir /path/to/cnn/processed

Reads   <runs-dir>/<pattern>/embeddings.npz (written by cnn/v1/embed.py)
Prints  per run: balanced accuracy with a whole imaging session held out (chance 0.33) and its permutation p, the same
        on the sessions that hold more than one batch ("mixed strips", where imaging cannot be the cue), and the two
        leak measures of cnn/predict.session_leak: how often a spot's nearest neighbour comes from its own session
        (chance 0.06), and how well the session can be guessed from the embedding (chance 0.09).
"""
import argparse
import glob
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("LOSSLARP_MASKS", "harmonise")
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import torch  # noqa: E402,F401  (before evalkit, as in the repo's own scripts)

from cnn import evalkit as ek  # noqa: E402
from cnn.predict import session_leak  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pattern", help='run folders to score, e.g. "exp_*"')
    ap.add_argument("--runs-dir", default=str(REPO / "cnn" / "processed"))
    a = ap.parse_args()
    rows = []
    for f in sorted(glob.glob(f"{a.runs_dir}/{a.pattern}/embeddings.npz")):
        z = np.load(f)
        X = z["site_feat"].astype(float)
        meta = ek.meta_for(z["batch"], z["sample_id"], z["session"])
        r = ek.score(X, meta, clfs=("lr",), n_perm=100)
        leak = session_leak(X, meta.session.to_numpy(), n_perm=300)
        rows.append((Path(f).parent.name, r["lr_losess"], r["lr_losess_perm_p"], r["lr_mixed"],
                     leak["nn_same_session_rate"], leak["nn_perm_p"], leak["loo_session_bacc_multi"]))
    print(f"{'run':<24}{'session held out':>17}{'p':>7}{'mixed strips':>14}{'same-session neighbour':>24}{'p':>7}{'session guessable':>19}")
    print(f"{'(chance)':<24}{0.33:>17.2f}{'':>7}{0.33:>14.2f}{0.06:>24.2f}{'':>7}{0.09:>19.2f}")
    for name, acc, p, mixed, nn, nn_p, guess in rows:
        print(f"{name:<24}{acc:>17.2f}{p:>7.3f}{mixed:>14.2f}{nn:>24.2f}{nn_p:>7.3f}{guess:>19.2f}")


if __name__ == "__main__":
    main()
