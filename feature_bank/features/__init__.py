"""The feature registry. One folder per feature: features/<name>/feature.py + config.yaml.

    from features import feature, load_config
    CFG = load_config(__file__)          # config.yaml in the same folder, as a dict

    @feature
    def porosity_frac(sample):
        return float((sample.bse < CFG["threshold"]).mean())

run_features.py imports every features/<name>/feature.py (folders starting with _ are skipped).
Each @feature function becomes a column; a dict return becomes one column per key, <function>_<key>.
A feature.py with a train(baseline_samples) function gets called by run_features.py --train.
"""
import importlib
import math
from pathlib import Path

import yaml

FEATURES_DIR = Path(__file__).resolve().parent
REGISTRY = {}                # feature name -> function
MODULES = []                 # imported feature modules


def feature(fn):
    """Register fn as a feature named after the function."""
    REGISTRY[fn.__name__] = fn
    return fn


def load_config(feature_file):
    """The config.yaml next to feature_file (pass __file__) as a dict. {} if there is none."""
    path = Path(feature_file).resolve().with_name("config.yaml")
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def feature_dirs():
    """Every features/<name>/ folder with a feature.py, skipping names starting with _."""
    return sorted(p.parent for p in FEATURES_DIR.glob("*/feature.py") if not p.parent.name.startswith("_"))


def load_feature_modules():
    """Import every feature.py so its @feature functions register."""
    MODULES.clear()          # safe to call twice
    for folder in feature_dirs():
        MODULES.append(importlib.import_module(f"features.{folder.name}.feature"))
    return MODULES


def compute_all(sample):
    """Run every feature on one sample -> {column: value}. A feature that raises gives NaN."""
    out = {}
    for name, fn in REGISTRY.items():
        try:
            result = fn(sample)
        except Exception as e:
            print(f"  [{name}] failed on {sample.batch}/{sample.sample_id}: {e}")
            result = math.nan
        if isinstance(result, dict):
            out.update({f"{name}_{k}": float(v) for k, v in result.items()})
        else:
            out[name] = float(result)
    return out


def train_all(baseline_samples):
    """Call train(baseline_samples) in every feature module that has one."""
    for module in MODULES:
        if hasattr(module, "train"):
            print(f"training {module.__name__} on {len(baseline_samples)} baseline samples ...")
            module.train(baseline_samples)
