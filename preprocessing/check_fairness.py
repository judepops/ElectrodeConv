"""Does the preprocessing leave any session cue behind? Run after any change to preprocess.py.

For every spot, a few plain numbers are read off the *preprocessed* arrays (mean BSE level, noise level, mean
Inlens, porosity, bright fraction). Then a classifier tries to predict the microscope session (= raw image
height, 13 values) from them, leave-one-spot-out. If the preprocessing is fair, it should do no better than
chance; a high score means a cue survived. The same test on the raw images is printed for comparison, and so is
the batch (which we WANT the material features to carry).

    python preprocessing/check_fairness.py        # ~2 min, writes preprocessing/fairness.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preprocessing.preprocess import DATA_DIR, crop_box, list_spots, load_spot, noise_sigma, preprocess  # noqa: E402


def describe(raw, spot):
    r0, r1, c0, c1 = crop_box(*raw.bse.shape)
    rb = raw.bse[r0:r1, c0:c1].astype(np.float32)
    return {
        # raw: what an unfair pipeline would see
        "raw_bse_mean": rb.mean(), "raw_bse_p1": np.percentile(rb, 1), "raw_bse_p99": np.percentile(rb, 99),
        "raw_bse_noise": noise_sigma(rb), "raw_inlens_mean": raw.inlens[r0:r1, c0:c1].mean(),
        # preprocessed: what the new pipeline sees
        "pp_bse_mean": spot.bse.mean(), "pp_bse_p1": np.percentile(spot.bse, 1), "pp_bse_p99": np.percentile(spot.bse, 99),
        "pp_bse_noise": noise_sigma(spot.bse), "pp_inlens_mean": spot.inlens.mean(), "pp_inlens_noise": noise_sigma(spot.inlens),
        "pp_porosity": spot.void.mean(), "pp_bright_frac": spot.bright.mean(),
    }


def balanced_accuracy(y, pred):
    return float(np.mean([(pred[y == c] == c).mean() for c in np.unique(y)]))


def predictability(X, y):
    """Leave-one-spot-out balanced accuracy of a small logistic regression; chance = 1 / n classes."""
    clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000))
    pred = cross_val_predict(clf, X, y, cv=LeaveOneOut())
    return balanced_accuracy(y, pred)


def main():
    rows = []
    for b, s in list_spots():
        raw = load_spot(DATA_DIR / b, s)
        spot = preprocess(raw)
        rows.append({"batch": b, "sample_id": s, "session": raw.bse.shape[0], **describe(raw, spot)})
        print(f"{b}/{s}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(Path(__file__).with_name("fairness.csv"), index=False)
    raw_cols = [c for c in df if c.startswith("raw_")]
    pp_cols = [c for c in df if c.startswith("pp_") and c not in ("pp_porosity", "pp_bright_frac")]
    mat_cols = ["pp_porosity", "pp_bright_frac"]
    sess = df["session"].to_numpy()
    batch = df["batch"].to_numpy()
    print(f"\nPredicting the SESSION (13 values, chance {1 / len(np.unique(sess)):.2f}) from:")
    print(f"  raw image levels/noise       {predictability(df[raw_cols].to_numpy(), sess):.2f}   <- the leak an unfair pipeline has")
    print(f"  preprocessed levels/noise    {predictability(df[pp_cols].to_numpy(), sess):.2f}   <- should be near chance")
    print(f"  material (porosity, Si)      {predictability(df[mat_cols].to_numpy(), sess):.2f}   (material can legitimately vary by image)")
    print(f"\nPredicting the BATCH (3 values, chance 0.33) from:")
    print(f"  raw image levels/noise       {predictability(df[raw_cols].to_numpy(), batch):.2f}")
    print(f"  preprocessed levels/noise    {predictability(df[pp_cols].to_numpy(), batch):.2f}   <- should be near chance")
    print(f"  material (porosity, Si)      {predictability(df[mat_cols].to_numpy(), batch):.2f}")


if __name__ == "__main__":
    main()
