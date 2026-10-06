"""Plug-in spot features: one file per feature, so several people (or agents) can add features at once without
touching the same file.

A plug-in is qc/spot_features/<id>.py with
    COLUMNS = ["<id>_<what>_<unit>", ...]      # a literal list: read without importing (ledger, verdict)
    LABELS = {"<column>": "page label"}        # optional literal dict, for the team page
    def measure(spot, raw) -> dict             # one value per column (nan if it cannot measure)
spot = preprocessing.preprocess.preprocess(raw): the standard fair window (bse in graphite units, inlens / se ranked,
void / bright masks). raw = the RawSpot (full uint8 images) for anything that needs the whole height:
preprocess(raw, box=(pp.CROP_TOP, H - pp.CROP_BOTTOM, pp.CROP_SIDE, W - pp.CROP_SIDE)) as qc/depth_profile.py does.

    python qc/spot_features/run.py <id>       # -> qc/processed/spot_features/<id>.csv (31 training + test spots)
    python qc/features_table.py               # merges every plug-in CSV; then qc/verdict.py, qc/impacts.py
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# follows LOSSLARP_MASKS like preprocessing/preprocess.py, so seg3 and harmonise results never mix
PROCESSED_NAME = "processed_seg3" if os.environ.get("LOSSLARP_MASKS", "seg3") == "seg3" else "processed"
OUT_DIR = ROOT / "qc" / PROCESSED_NAME / "spot_features"


def plugins():
    return sorted(p.stem for p in HERE.glob("*.py") if not p.stem.startswith("_") and p.stem != "run")


def literal(plugin, name, default=None):
    """The literal value assigned to `name` in a plug-in file, without importing it."""
    for node in ast.parse((HERE / f"{plugin}.py").read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    return default


def columns():
    """{plugin: [columns]} for every plug-in."""
    return {p: list(literal(p, "COLUMNS", [])) for p in plugins()}


def labels():
    out = {}
    for p in plugins():
        out.update(literal(p, "LABELS", {}) or {})
    return out
