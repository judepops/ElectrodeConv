"""Where in the image does a batch call come from? Exact per-location attribution of the classifier's score.

    python cnn/attribute.py --run supcon/v2/full        # -> processed/supcon/v2/full/attribution.json + attr_img/

The spot score for class k is s = ((f - mu) / sd) . W[:, k] + b, with f the spot embedding = mean over tiles of
[mean_c, std_c] of the projected bottleneck p (C x h x w) of the fused encoder. Both halves can be written as a sum
over locations (i, j):
    mean half   sum_c w_c m_c          = sum_ij  (1/N) sum_c w_c p_cij
    std half    sum_c w_c s_c          = sum_ij  sum_c w_c (p_cij - m_c)^2 / ((N - 1) s_c)       (N = h w)
so A_ij = both terms summed is an exact decomposition: sum_ij A_ij equals the tile's score up to the constant
-mu . w + b (asserted). Red pushes the spot towards the called batch, blue away. Resolution is the bottleneck grid
(16 px cells for k7 at 512 px; each cell sees a much larger receptive field, so edges are soft). Per spot: a 2 x 13
mosaic over the BSE image, and the share of the positive attribution that falls on pore / graphite / Si pixels
against their area share (enrichment). The detectors go in as one 3-channel image, so there is no per-detector
share: `detector_share` is {"fused": 1.0}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
from PIL import Image  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn import evalkit as ek  # noqa: E402
from cnn.common import DETECTORS, pick_device, run_dir  # noqa: E402
from cnn.explain import lr_direction  # noqa: E402
from cnn.predict import load_net, tiles_to_x  # noqa: E402
from preprocessing.preprocess import load_tiles  # noqa: E402
from qc.features_table import TEST_IDS, TEST_TILES_DIR  # noqa: E402


def location_maps(net, device, x):
    """x (1, 3, H, W) -> list of projected bottleneck maps p (C, h, w), float32: one per pool_proj call (1 for FusionNet)."""
    caught = []
    h = net.encoder.pool_proj.register_forward_hook(lambda m, i, o: caught.append(o.detach().float()[0]))
    with torch.no_grad():
        net(x.to(device), seg=False)
    h.remove()
    return [c.cpu().numpy() for c in caught]


def attribute_tile(ps, w_tilde):
    """ps: list of hooked (C, h, w) maps, feat = concat over them of [mean_C, std_C]; w_tilde: (len(ps) * 2C,) direction
    in standardised units / sd. -> (A summed over maps (h, w), per-map |A| mass, exact tile score minus constant)."""
    C = ps[0].shape[0]
    A, mass = None, []
    for d, p in enumerate(ps):
        wm, ws = w_tilde[d * 2 * C: d * 2 * C + C], w_tilde[d * 2 * C + C: (d + 1) * 2 * C]
        N = p.shape[1] * p.shape[2]
        m = p.mean(axis=(1, 2))
        s = p.std(axis=(1, 2), ddof=1)
        s[s < 1e-12] = 1e-12
        a_mean = np.tensordot(wm, p, axes=(0, 0)) / N
        a_std = np.tensordot(ws / ((N - 1) * s), (p - m[:, None, None]) ** 2, axes=(0, 0))
        a = a_mean + a_std
        mass.append(float(np.abs(a).sum()))
        A = a if A is None else A + a
    return A, mass, float(A.sum())


def overlay(bse, A, scale):
    """Grey BSE with a signed heat overlay (red +, blue -), both downsampled by `scale`."""
    g = np.clip(bse[::scale, ::scale] / 2.6, 0, 1)
    a = np.asarray(Image.fromarray(A.astype(np.float32)).resize(g.shape[::-1], Image.BILINEAR))
    lim = np.percentile(np.abs(a), 99) or 1.0
    t = np.clip(a / lim, -1, 1)
    rgb = np.stack([g, g, g], -1)
    pos, neg = np.clip(t, 0, 1)[..., None], np.clip(-t, 0, 1)[..., None]
    rgb = rgb * (1 - 0.65 * (pos + neg)) + 0.65 * (pos * np.array([0.9, 0.15, 0.1]) + neg * np.array([0.1, 0.35, 0.9]))
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="supcon/v2/full", help="folder under processed/")
    ap.add_argument("--spots", default="", help="comma list of sample ids (default: the 3 test spots + 2 per batch)")
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()
    out = run_dir(a.run)
    img_dir = out / "attr_img"
    img_dir.mkdir(exist_ok=True)
    device = pick_device(a.device)
    net, ck = load_net(a.run, device)
    z = np.load(out / "embeddings.npz")
    X = z["site_feat"].astype(float)
    meta = ek.meta_for(z["batch"], z["sample_id"], z["session"])
    y = meta.y.to_numpy()
    mu, sd, W, b, classes = lr_direction(X, y)
    spots = [(str(bb), str(s)) for bb, s in zip(z["batch"], z["sample_id"])]
    if a.spots:
        want = set(a.spots.split(","))
        sel = [(bb, s) for bb, s in spots if s in want] + [("Test", s) for s in TEST_IDS if s in want]
    else:
        sel = [("Test", s) for s in TEST_IDS]
        for bb in ("Batch_1", "Batch_2", "Batch_3"):
            sel += [(b_, s) for b_, s in spots if b_ == bb][:2]
    res = {"run": a.run, "classes": classes, "cell_px": None, "spots": {}}
    for bb, sid in sel:
        tiles = load_tiles(bb, sid, out_dir=TEST_TILES_DIR) if bb == "Test" else load_tiles(bb, sid)
        feats, ps_all = [], []
        for t in tiles:
            x = tiles_to_x([t])
            ps = location_maps(net, device, x)
            ps_all.append(ps)
            feats.append(np.concatenate([np.concatenate([p.mean(axis=(1, 2)), p.std(axis=(1, 2), ddof=1)]) for p in ps]))
        site = np.mean(feats, 0)
        scores = ((site - mu) / sd) @ W + b
        k = int(np.argmax(scores))
        w_tilde = W[:, k] / sd
        const = float(-(mu / sd) @ W[:, k] + b[k])
        rows = max(t.row for t in tiles) + 1
        cols = max(t.col for t in tiles) + 1
        scale = 8
        cell = 512 // scale
        mosaic = np.zeros((rows * cell, cols * cell, 3), np.uint8)
        shares = np.zeros(3)
        area = np.zeros(3)
        det_mass = np.zeros(len(ps_all[0]))
        err, tile_scores = [], []
        for t, ps, f in zip(tiles, ps_all, feats):
            A, mass, s_tile = attribute_tile(ps, w_tilde)
            err.append(abs(s_tile + const - (((f - mu) / sd) @ W[:, k] + b[k])))
            tile_scores.append(s_tile + const)
            det_mass += mass
            up = np.asarray(Image.fromarray(A.astype(np.float32)).resize((512, 512), Image.BILINEAR))
            pos = np.clip(up, 0, None)
            masks = [t.void, t.bright, ~(t.void | t.bright)]
            shares += [pos[m].sum() for m in masks]
            area += [m.mean() for m in masks]
            mosaic[t.row * cell:(t.row + 1) * cell, t.col * cell:(t.col + 1) * cell] = overlay(t.bse, A, scale)
        key = f"{bb}/{sid}"
        Image.fromarray(mosaic).save(img_dir / f"{bb}_{sid}_mosaic.png")
        top = int(np.argmax(tile_scores))
        A_top, _, _ = attribute_tile(ps_all[top], w_tilde)
        Image.fromarray(overlay(tiles[top].bse, A_top, 2)).save(img_dir / f"{bb}_{sid}_top.png")
        shares, area = shares / max(shares.sum(), 1e-12), area / len(tiles)
        res["cell_px"] = 512 // ps_all[0][0].shape[1]
        det_names = ["fused"] if len(det_mass) == 1 else list(DETECTORS)
        res["spots"][key] = {
            "batch": bb, "sample_id": sid, "call": classes[k], "scores": [float(v) for v in scores],
            "mosaic": f"{bb}_{sid}_mosaic.png", "top": f"{bb}_{sid}_top.png", "top_tile": [int(tiles[top].row), int(tiles[top].col)],
            "share": {"pore": float(shares[0]), "si": float(shares[1]), "graphite": float(shares[2])},
            "area": {"pore": float(area[0]), "si": float(area[1]), "graphite": float(area[2])},
            "detector_share": {d: float(m / max(det_mass.sum(), 1e-12)) for d, m in zip(det_names, det_mass)},
            "completeness_max_err": float(max(err)), "grid": [rows, cols]}
        print(f"{key:18s} call B{classes[k]}  positive attribution on pore {shares[0]:.2f} (area {area[0]:.2f}), Si {shares[1]:.2f} "
              f"(area {area[1]:.2f}), graphite {shares[2]:.2f} (area {area[2]:.2f})  detectors {dict(zip(det_names, np.round(det_mass / det_mass.sum(), 2)))}  "
              f"max |exactness error| {max(err):.1e}", flush=True)
    (out / "attribution.json").write_text(json.dumps(res, indent=1))
    print(f"wrote {out / 'attribution.json'} and {len(list(img_dir.glob('*.png')))} images")


if __name__ == "__main__":
    main()
