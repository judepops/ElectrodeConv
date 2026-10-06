"""One file per feature family. A family module defines:

    FAMILY = "phase"            # must equal the file name
    TIER = 1                    # 1 = tonight, 2 = overnight, 3 = stretch
    RUNS_ON = "cpu"             # or "gpu"
    DEFAULT_CFG = {...}         # every tunable number, so a run is reproducible from the file alone
    def extract(crop, cfg): ... # -> bank.core.FeatureResult
    def warmup(cfg): ...        # optional: load model weights once per process

Files starting with _ are skipped.
"""
import importlib
import pkgutil


def family_names():
    return sorted(m.name for m in pkgutil.iter_modules(__path__) if not m.name.startswith("_"))


def load(name):
    module = importlib.import_module(f"bank.families.{name}")
    if getattr(module, "FAMILY", None) != name:
        raise ValueError(f"bank/families/{name}.py must set FAMILY = {name!r}")
    return module
