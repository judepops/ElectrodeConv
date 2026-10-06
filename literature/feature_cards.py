"""What each feature looks like: three real tiles (low, typical, high) with the measured phase highlighted.

    python literature/feature_cards.py     # -> literature/feature_cards.json + dashboard/site/img/lit_<concept>_<0|1|2>.jpg
    python literature/batch_outlook.py     # then this puts the cards into dashboard/site/literature.js for section 08

Reads   the tiles of preprocessing/ and the per-tile features of cnn/tile_features.py (whichever masks LOSSLARP_MASKS
        selects), and literature/evidence.json for what the papers say more of each feature does.
Writes  one card per concept: the tile at the 5th, 50th and 95th percentile of the feature, where the three batches
        sit between those two ends, and the outcomes the papers agree on.

The pictures are the BSE plane of a 512 px tile (12.8 um), shown at half size, with the phase the feature measures
tinted: silicon yellow, pores blue. The tint is a display aid; the number under each picture is the feature value
computed by cnn/tile_features.py for exactly that tile.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from cnn.tile_features import OUT as TILE_FEATURES_CSV  # noqa: E402
from preprocessing.preprocess import MASK_SOURCE, load_tile  # noqa: E402

IMG_DIR = ROOT / "dashboard" / "site" / "img"
GOOD = {"capacity": 1, "charge_speed": 1, "lifespan": 1, "first_charge_loss": -1, "swelling": -1, "uniformity": 1}
NAMES = {"capacity": "energy storage", "charge_speed": "charging speed", "lifespan": "lifespan",
         "first_charge_loss": "first-charge loss", "swelling": "swelling", "uniformity": "uniformity"}
QUANTILES = (0.05, 0.50, 0.95)
SI, PORE = (255, 196, 46), (77, 147, 255)

# concept -> the one feature shown, what to tint, the plain name, how to print the value
CARDS = [
    ("si_fraction", "si_solid_frac", "si", "Silicon share of the solid", lambda v: f"{100 * v:.0f} % silicon"),
    ("si_particle_size", "si_d50_um", "si", "Silicon particle size", lambda v: f"{v:.1f} µm typical particle"),
    ("si_agglomeration", "si_agglom_d50_um", "si", "Silicon clumping", lambda v: f"{v:.1f} µm typical clump"),
    ("porosity", "porosity_frac", "pore", "Pore fraction", lambda v: f"{100 * v:.0f} % pore"),
    ("pore_size", "pore_n_per_1000um2", "pore", "Pore count (many small vs few large)", lambda v: f"{v:.0f} pores per 1000 µm²"),
    ("heterogeneity", "porosity_block_cv", "pore", "Unevenness of the pores", lambda v: f"unevenness {v:.2f}"),
    ("surface_area", "interface_density_per_um", "pore", "Pore-wall length (surface area)", lambda v: f"{v:.2f} µm of pore wall per µm²"),
    ("graphite_particle_size", "solid_chord_y_um", "pore", "Solid thickness (graphite particle size)", lambda v: f"{v:.1f} µm typical solid thickness"),
]


def render(tile, tint):
    """BSE plane as an RGB picture at half size, the measured phase tinted."""
    g = np.clip((tile.bse + 0.3) / 2.9, 0, 1) * 255
    rgb = np.repeat(g[..., None], 3, 2)
    for mask, colour, on in ((tile.bright, SI, tint == "si"), (tile.void, PORE, tint == "pore")):
        if on:
            rgb[mask] = 0.5 * rgb[mask] + 0.5 * np.array(colour)
    return Image.fromarray(rgb.astype(np.uint8)).resize((256, 256), Image.LANCZOS)


def main():
    df = pd.read_csv(TILE_FEATURES_CSV)
    terms = yaml.safe_load((HERE / "evidence_terms.yaml").read_text())
    evidence = {(p["concept"], p["outcome"]): p for p in json.loads((HERE / "evidence.json").read_text())["pairs"]}
    inverse = {f for c in terms["concepts"] for f in c.get("inverse", [])}
    spot = df.groupby(["batch", "sample_id"], as_index=False).mean(numeric_only=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    cards = []
    for concept, feat, tint, label, fmt in CARDS:
        d = df[np.isfinite(df[feat])].sort_values(feat).reset_index(drop=True)
        lo, hi = d[feat].quantile(QUANTILES[0]), d[feat].quantile(QUANTILES[-1])
        tiles = []
        for k, q in enumerate(QUANTILES):
            r = d.iloc[int(round(q * (len(d) - 1)))]
            t = load_tile(r.batch, r.sample_id, int(r.row), int(r.col))
            name = f"lit_{concept}_{k}.jpg"
            render(t, tint).save(IMG_DIR / name, quality=85, optimize=True)
            tiles.append({"img": f"img/{name}", "value": float(r[feat]), "text": fmt(float(r[feat])), "batch": r.batch, "sample_id": r.sample_id})
        pos = lambda v: float(np.clip((v - lo) / (hi - lo), 0, 1)) if hi > lo else 0.5
        batches = {b: {"mean": float(g[feat].mean()), "text": fmt(float(g[feat].mean())), "pos": pos(float(g[feat].mean())), "n": int(len(g))}
                   for b, g in spot.groupby("batch") if str(b).startswith("Batch_")}
        flip = -1 if feat in inverse else 1          # e.g. more pores per area = SMALLER pores, the concept the papers answer
        effects, good, bad = [], [], []
        for o in GOOD:
            ev = evidence.get((concept, o))
            if not ev or ev["consensus"] not in ("more", "less"):
                continue
            more = (1 if ev["consensus"] == "more" else -1) * flip > 0      # does a HIGHER feature value mean more of it?
            effects.append({"outcome": o, "label": NAMES[o], "more": bool(more), "n": ev["n_papers"], "counts": list(ev["counts"].values())})
            (good if (1 if more else -1) * GOOD[o] > 0 else bad).append(("more " if more else "less ") + NAMES[o])
        lean = ("no agreed effect in the papers read" if not effects else
                "mostly good for the cell: " + ", ".join(good) if not bad else
                "mostly bad for the cell: " + ", ".join(bad) if not good else
                "a trade-off: " + ", ".join(good) + "; but " + ", ".join(bad))
        cards.append({"concept": concept, "feature": feat, "label": label, "tint": tint, "tiles": tiles, "batches": batches,
                      "effects": effects, "lean": lean})
        print(f"{label:<42} low {tiles[0]['text']:<28} high {tiles[2]['text']:<28} -> higher is {lean}")
    (HERE / "feature_cards.json").write_text(json.dumps({"masks": MASK_SOURCE, "tile_um": 12.8, "quantiles": QUANTILES, "cards": cards},
                                                        indent=1, ensure_ascii=False))
    print(f"wrote literature/feature_cards.json and {3 * len(cards)} pictures to dashboard/site/img/ (masks: {MASK_SOURCE})")


if __name__ == "__main__":
    main()
