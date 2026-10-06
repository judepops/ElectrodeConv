"""histogram_anomaly_z: how unusual the BSE brightness histogram is compared to the baseline.

The example of a trained feature. train() stores the histogram of every baseline sample in
models/histogram_anomaly.npz. The feature returns the mean |z| of a sample's histogram against
the stored ones (0 = typical, above ~2 = clearly different). Tuning in config.yaml; retrain
after changing it:  python features/run_features.py --train

A baseline sample is scored against the other baseline samples (its own histogram is left
out), otherwise baseline spots would look artificially normal.

Why it matters: the histogram catches changes no named feature was written for. It says that
something changed, not what.
"""
import numpy as np

from features import feature, load_config
from preprocessing import MODELS_DIR

CFG = load_config(__file__)
MODEL_FILE = MODELS_DIR / "histogram_anomaly.npz"


def histogram(sample):
    counts, _ = np.histogram(sample.bse, bins=CFG["bins"], range=(0, 256))
    return counts / counts.sum()


def sample_key(sample):
    return f"{sample.batch}/{sample.sample_id}"


def train(baseline_samples):
    """Save every baseline sample's histogram, with its id, to models/."""
    hists = np.array([histogram(s) for s in baseline_samples])
    keys = np.array([sample_key(s) for s in baseline_samples])
    MODEL_FILE.parent.mkdir(exist_ok=True)
    np.savez(MODEL_FILE, hists=hists, keys=keys)
    print(f"  saved {MODEL_FILE.relative_to(MODELS_DIR.parent)}  ({len(hists)} baseline histograms)")


@feature
def histogram_anomaly_z(sample):
    if not MODEL_FILE.exists():
        raise FileNotFoundError(f"{MODEL_FILE} is missing. Run:  python features/run_features.py --train")
    model = np.load(MODEL_FILE)
    others = model["hists"][model["keys"] != sample_key(sample)]   # leave this sample out
    mean, std = others.mean(axis=0), np.maximum(others.std(axis=0), CFG["std_floor"])
    z = (histogram(sample) - mean) / std
    return float(np.abs(z).mean())
