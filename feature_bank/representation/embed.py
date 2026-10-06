"""Step 1-2 of notes/representation.md: harmonise each site, cut 504 px tiles, embed them with a frozen DINOv2.

    python representation/embed.py main       # every site as it is
    python representation/embed.py perturb    # 8 sites x 6 synthetic imaging changes (the imaging subspace)
    python representation/embed.py inject     # 6 sites x 5 injected material changes (the positive control)
    python representation/embed.py anchor     # every site with the crop anchored at the top and at the bottom

Reads:   data/{batch}/img_{site}_{detector}.tif (raw, channel 0) through features/_common/harmonise.py
Writes:  processed/representation/emb/{variant}/{batch}__{site}.npz, one file per site version, holding the
         BSE and Inlens tile embeddings (class token + mean patch token, 768 numbers each), tile positions,
         per-tile pore and bright-phase fractions and the site's acquisition descriptors.

Model: DINOv2 ViT-S/14 with registers through timm (`vit_small_patch14_reg4_dinov2.lvd142m`, Apache-2.0),
frozen, 504 px input = 36 x 36 patches of 350 nm, no rescaling. Needs torch and timm, which are not in
requirements.txt. Harmonising runs in worker processes; the model runs in this one.
"""
import json
import sys
import time
import zlib
from multiprocessing import get_context
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # so `preprocessing` and `features` import from the repo root

from preprocessing import PROCESSED_DIR, list_samples, load_grey, raw_path   # noqa: E402

OUT_DIR = PROCESSED_DIR / "representation" / "emb"
TILE = 504
MODEL_NAME = "vit_small_patch14_reg4_dinov2.lvd142m"
BSE_RANGE = (-0.5, 3.0)          # graphite units mapped onto the model's 0..1 input range (graphite = 1, bright phase about 2)

PERTURBATIONS = ["black25", "gamma0.8", "gamma1.25", "contrast0.85", "noise4", "blur1"]     # as in notes/feature_screen.md
PERTURB_SITES = ["kbdh4tri", "cfe5vt7s", "pl8uabbv", "hawkfj64", "f1vzngrs", "5n1q8atc", "avn74qx1", "rxax5ozo"]
INJECTIONS = ["pore_r2", "pore_r4", "pore_r8", "bright_rm50", "bright_rm100"]              # pores grown by r px; bright grains removed
INJECT_SITES = ["r17byphk", "epqdaau9", "x77cy643", "tuy3zymq", "hawkfj64", "hzumfsms"]    # one member of a touching pair per chain


# ----------------------------------------------------------------------------------------------------
# changes applied to the raw images
# ----------------------------------------------------------------------------------------------------
def perturb(raw, kind, seed=0):
    """A synthetic imaging change on a raw uint8 image: what a different microscope setting would do."""
    x = raw.astype(np.float32)
    if kind == "black25":
        x = x + 25
    elif kind.startswith("gamma"):
        x = 255 * (x / 255) ** float(kind[5:])
    elif kind == "contrast0.85":
        x = (x - x.mean()) * 0.85 + x.mean()
    elif kind == "noise4":
        x = x + np.random.default_rng(seed).standard_normal(x.shape, dtype=np.float32) * 4
    elif kind == "blur1":
        x = ndi.gaussian_filter(x, 1)
    else:
        raise ValueError(kind)
    return np.clip(np.rint(x), 0, 255).astype(np.uint8)


def inject(raw_bse, raw_inlens, h, kind, seed=0):
    """A known material change painted into the raw BSE and Inlens images, using the site's own masks.

    pore_rN      every pore grown by N px (25 nm each); new pore pixels copy the grey levels of existing pore pixels
    bright_rmP   P % of the bright grains replaced by graphite-interior grey levels
    BSE and Inlens copy from the same source pixel, so their joint statistics stay realistic. Crude, but known.
    """
    rng = np.random.default_rng(seed)
    r0, r1, c0, c1 = h.acq["crop"]
    bse, inlens = raw_bse.copy(), raw_inlens.copy()
    bse_crop, inl_crop = bse[r0:r1, c0:c1], inlens[r0:r1, c0:c1]     # views into the copies
    if kind.startswith("pore_r"):
        target = ndi.binary_dilation(h.void, iterations=int(kind[6:])) & ~h.void
        source = np.flatnonzero(h.void.ravel())
    elif kind.startswith("bright_rm"):
        labels, n = ndi.label(h.bright)
        gone = rng.choice(np.arange(1, n + 1), size=int(round(n * int(kind[9:]) / 100)), replace=False)
        target = ndi.binary_dilation(np.isin(labels, gone), iterations=4)          # also covers the grain's blurred rim
        interior = (np.abs(h.bse_blur - 1.0) < 0.12) & ~ndi.binary_dilation(h.void | h.bright, iterations=6)
        source = np.flatnonzero(interior.ravel())
    else:
        raise ValueError(kind)
    pick = rng.choice(source, size=int(target.sum()))
    bse_crop[target] = raw_bse[r0:r1, c0:c1].ravel()[pick]
    inl_crop[target] = raw_inlens[r0:r1, c0:c1].ravel()[pick]
    return bse, inlens


# ----------------------------------------------------------------------------------------------------
# one site version -> tiles (runs in a worker process)
# ----------------------------------------------------------------------------------------------------
def tile_grid(shape):
    """Centred grid of non-overlapping tiles, plus tiles flush with the left and right edge (for the seams)."""
    h, w = shape
    ny, nx = h // TILE, w // TILE
    y0, x0 = (h - ny * TILE) // 2, (w - nx * TILE) // 2
    grid = [(y0 + i * TILE, x0 + j * TILE, i, j, False) for i in range(ny) for j in range(nx)]
    edge = [(y0 + i * TILE, x, i, j, True) for i in range(ny) for x, j in ((0, -1), (w - TILE, nx))]
    return grid + edge


def prepare(task):
    """(batch, site, variant) -> everything the model needs, as small arrays."""
    from features._common import harmonise as H
    batch, site, variant = task
    seed = zlib.crc32(f"{batch}/{site}".encode())          # the same noise top-up as the cached harmonised spot
    raw = {d: load_grey(raw_path(batch, site, d)) for d in ("BSE", "Inlens", "SE")}
    bse, inlens = raw["BSE"], raw["Inlens"]

    original_crop_box = H.crop_box
    if variant.startswith("anchor_"):                      # same crop size, anchored at the top or bottom of the usable rows
        def crop_box(height, width, where=variant[7:]):
            c = H.CFG["crop"]
            top, bottom = c["top_px"], height - c["bottom_px"]
            n = min(c["height_px"], bottom - top)
            r0 = top if where == "top" else bottom - n
            return r0, r0 + n, c["side_px"], width - c["side_px"]
        H.crop_box = crop_box
    elif variant in PERTURBATIONS:
        bse, inlens = perturb(bse, variant), perturb(inlens, variant, seed=1)
    elif variant in INJECTIONS:
        bse, inlens = inject(bse, inlens, H.harmonise_arrays(bse, inlens, raw["SE"], seed), variant)
    try:
        h = H.harmonise_arrays(bse, inlens, raw["SE"], seed)
    finally:
        H.crop_box = original_crop_box

    lo, hi = BSE_RANGE
    bse8 = np.rint(np.clip((h.bse - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    inl8 = np.rint(np.clip(h.inlens, 0, 1) * 255).astype(np.uint8)
    grid = tile_grid(h.shape)
    cut = lambda img: np.stack([img[y:y + TILE, x:x + TILE] for y, x, *_ in grid])   # noqa: E731
    acq = {k: (list(v) if isinstance(v, tuple) else v) for k, v in h.acq.items()}
    return dict(batch=batch, site=site, variant=variant, session=int(raw["BSE"].shape[0]),
                tiles_bse=cut(bse8), tiles_inlens=cut(inl8),
                y=np.array([g[0] for g in grid]), x=np.array([g[1] for g in grid]),
                row=np.array([g[2] for g in grid]), col=np.array([g[3] for g in grid]),
                is_edge=np.array([g[4] for g in grid]),
                tile_void=cut(h.void).mean(axis=(1, 2)), tile_bright=cut(h.bright).mean(axis=(1, 2)),
                site_void=float(h.void.mean()), site_bright=float(h.bright.mean()), acq=json.dumps(acq, default=float))


# ----------------------------------------------------------------------------------------------------
# the model (runs in the main process)
# ----------------------------------------------------------------------------------------------------
def load_model():
    import timm
    import torch
    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    model = timm.create_model(MODEL_NAME, pretrained=True, img_size=TILE, num_classes=0).eval().to(device)
    return model, device


def embed(model, device, tiles, batch_size=16):
    """(n, 504, 504) uint8 -> (n, 768) float32: class token then mean patch token."""
    import torch
    mean = torch.tensor([0.485, 0.456, 0.406], device=device).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], device=device).view(1, 3, 1, 1)
    out = []
    with torch.inference_mode():
        for i in range(0, len(tiles), batch_size):
            x = torch.from_numpy(tiles[i:i + batch_size]).to(device).float().div_(255)
            tokens = model.forward_features((x[:, None].expand(-1, 3, -1, -1) - mean) / std)
            out.append(torch.cat([tokens[:, 0], tokens[:, model.num_prefix_tokens:].mean(dim=1)], dim=1).cpu().numpy())
    return np.concatenate(out).astype(np.float32)


def tasks_for(which):
    sites = {site: batch for batch, site in list_samples()}
    if which == "main":
        return [(b, s, "orig") for s, b in sites.items()]
    if which == "perturb":
        return [(sites[s], s, v) for s in PERTURB_SITES for v in PERTURBATIONS]
    if which == "inject":
        return [(sites[s], s, v) for s in INJECT_SITES for v in INJECTIONS]
    if which == "anchor":
        return [(b, s, v) for s, b in sites.items() for v in ("anchor_top", "anchor_bottom")]
    raise SystemExit(f"unknown set {which!r}: use main, perturb, inject or anchor")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "main"
    todo = [t for t in tasks_for(which) if not (OUT_DIR / t[2] / f"{t[0]}__{t[1]}.npz").exists()]
    print(f"{which}: {len(todo)} site versions to do")
    if not todo:
        return
    model, device = load_model()
    t0, n_tiles = time.time(), 0
    with get_context("spawn").Pool(5) as pool:
        for i, p in enumerate(pool.imap_unordered(prepare, todo), 1):
            e_bse = embed(model, device, p.pop("tiles_bse"))
            e_inl = embed(model, device, p.pop("tiles_inlens"))
            n_tiles += 2 * len(e_bse)
            path = OUT_DIR / p["variant"] / f"{p['batch']}__{p['site']}.npz"
            path.parent.mkdir(parents=True, exist_ok=True)
            np.savez(path, bse=e_bse, inlens=e_inl, **p)
            print(f"  [{i}/{len(todo)}] {p['batch']}/{p['site']} {p['variant']:<13} pore {p['site_void']:.3f} bright {p['site_bright']:.3f}"
                  f"  {time.time() - t0:.0f} s", flush=True)
    print(f"done: {n_tiles} tiles embedded on {device} in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
