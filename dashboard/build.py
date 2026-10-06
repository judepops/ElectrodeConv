"""Build the pipeline page's data: every picture and number on dashboard/site comes from here, from real data.

    LOSSLARP_DATA_DIR=/path/to/data python dashboard/build.py [--spot Batch_1/4ih2ggld] [--tile 0,5]
        [--run supcon/v2/full] [--n-tiles 8]
Writes dashboard/site/pipeline.js (window.PIPELINE = {...}, so the page opens straight from disk) and
dashboard/site/img/*.

Part 1 replays preprocessing/preprocess.py step by step on one raw spot, keeping every intermediate, and checks the
end result against preprocess() itself, so the page cannot drift from the real recipe.
Part 2 runs the CNN checkpoint cnn/processed/<run>/{last,best}.pt (and a randomly initialised copy, "before
training") on one tile of that spot: the first conv layer's kernel sweeping the tile, the deeper feature maps and the
embedding. For the old MaterialNet (one detector at a time) it also builds the BSE-vs-Inlens similarity matrix; for
the V2 FusionNet (cnn/supcon.py, the three detectors fused at the input) the kernel has three planes and there is no
per-detector embedding, so the page hides the matching section.
Part 3 reads the result JSON files: qc/, the run's predictions / explain / attribution / probe, the baselines table,
and for V2 cnn/processed/supcon/v2/score.json (nested leave-one-session-out) and full/difference.json.
Needs torch for part 2 (python3.11 on the team Mac).
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from preprocessing import preprocess as pp  # noqa: E402

SITE = HERE / "site"
IMG = SITE / "img"
BSE_DISPLAY_MAX = 2.6              # graphite units shown as white (same as cnn/embed.py)
WIDE = 1600                        # display width of full-frame / window images
COMPARE_SPOTS = ("Batch_2/avn74qx1", "Batch_3/71vgq3fw")   # other sessions, for the anchoring histogram
GRID = 32                          # kernel scan positions per side in the page animation
NOISE_PATCH = 160                  # px, zoom patch for the noise step


# ---- small helpers -----------------------------------------------------------------------------------------
def to_u8(a, lo=0.0, hi=1.0):
    return (np.clip((np.asarray(a, np.float32) - lo) / max(hi - lo, 1e-9), 0, 1) * 255).round().astype(np.uint8)


def save_img(name, arr_u8, width=None, quality=85):
    """Save a uint8 (H, W) or (H, W, 3/4) array under site/img; resize to `width` (area average). -> relative path."""
    im = Image.fromarray(arr_u8)
    if width and im.width != width:
        im = im.resize((width, round(im.height * width / im.width)), Image.BOX)
    path = IMG / name
    if name.endswith(".jpg"):
        im.convert("RGB").save(path, quality=quality, optimize=True)
    else:
        im.save(path, optimize=True)
    return f"img/{name}"


def b64(arr_u8):
    return base64.b64encode(np.ascontiguousarray(arr_u8, np.uint8).tobytes()).decode()


def pool(a, f):
    """Mean-pool a 2-D array by an integer factor."""
    h, w = a.shape[0] // f * f, a.shape[1] // f * f
    return a[:h, :w].reshape(h // f, f, w // f, f).mean((1, 3))


def robust_u8(a, lo_pct=1, hi_pct=99, margin=0.0):
    """-> (uint8 image, lo, hi), the range read off the interior (zero padding makes the border extreme)."""
    m = int(round(a.shape[0] * margin))
    lo, hi = np.percentile(a[m:a.shape[0] - m, m:a.shape[1] - m] if m else a, [lo_pct, hi_pct])
    return to_u8(a, lo, hi), float(lo), float(hi)


def hist(values, lo, hi, bins, smooth=0.0):
    h, _ = np.histogram(values, bins, (lo, hi))
    h = h.astype(float)
    if smooth:
        h = ndi.gaussian_filter1d(h, smooth)
    return [round(v, 5) for v in (h / h.max()).tolist()]


def r(x, n=4):
    return round(float(x), n)


# ---- part 1: preprocessing, step by step ---------------------------------------------------------------------
def prep_part(data_dir, batch, sid, tile_rc):
    raw = pp.load_spot(data_dir / batch, sid)
    H, W = raw.bse.shape
    r0, r1, c0, c1 = pp.crop_box(H, W)
    seed = zlib.crc32(f"{raw.batch}/{raw.sample_id}".encode())

    # the same calls, in the same order, as pp.preprocess()
    bse_raw = raw.bse[r0:r1, c0:c1]
    black, graphite = pp.anchor(bse_raw)
    bse_anch = (bse_raw.astype(np.float32) - black) / np.float32(max(graphite - black, 1.0))
    bse, bse_sigma, bse_added = pp.top_up_noise(bse_anch, pp.BSE_NOISE_TARGET, seed)
    inl_rank = pp.rank_normalise(raw.inlens[r0:r1, c0:c1])
    inlens, inl_sigma, inl_added = pp.top_up_noise(inl_rank, pp.INLENS_NOISE_TARGET, seed + 1)
    se = pp.rank_normalise(raw.se[r0:r1, c0:c1])
    void, t_void = pp.segment_void(bse)
    bright, t_bright, peak, found = pp.segment_bright(bse)

    ref = pp.preprocess(raw)
    assert np.array_equal(ref.void, void) and np.array_equal(ref.bright, bright), "replay differs from preprocess()"
    assert np.allclose(ref.bse, bse) and np.allclose(ref.inlens, inlens) and np.allclose(ref.se, se)
    print(f"part 1: {batch}/{sid} raw {W}x{H} -> window {c1 - c0}x{r1 - r0}; replay matches preprocess()")

    p = f"{sid}_"
    raw_imgs = {d: save_img(f"{p}raw_{d}.jpg", getattr(raw, d), WIDE) for d in ("bse", "inlens", "se")}
    win = {
        "bse_raw": save_img(f"{p}win_bse_raw.jpg", bse_raw, WIDE),
        "bse": save_img(f"{p}win_bse.jpg", to_u8(bse, 0, BSE_DISPLAY_MAX), WIDE),
        "inlens_raw": save_img(f"{p}win_inlens_raw.jpg", raw.inlens[r0:r1, c0:c1], WIDE),
        "inlens": save_img(f"{p}win_inlens.jpg", to_u8(inlens), WIDE),
        "se_raw": save_img(f"{p}win_se_raw.jpg", raw.se[r0:r1, c0:c1], WIDE),
        "se": save_img(f"{p}win_se.jpg", to_u8(se), WIDE),
    }
    # segmentation overlay: pores blue, Si-like amber, transparent elsewhere (area-averaged so thin pores survive)
    f = (c1 - c0) / WIDE
    small = lambda m: np.asarray(Image.fromarray(m.astype(np.uint8) * 255).resize(  # noqa: E731
        (WIDE, round((r1 - r0) / f)), Image.BOX), np.float32) / 255
    sv, sb = small(void), small(bright)
    rgba = np.zeros(sv.shape + (4,), np.uint8)
    rgba[..., :3] = np.where(sb[..., None] > sv[..., None], [245, 180, 0], [40, 120, 255])
    rgba[..., 3] = (np.clip(np.maximum(sv, sb) * 1.6, 0, 1) * 235).astype(np.uint8)
    win["overlay"] = save_img(f"{p}win_overlay.png", rgba)

    # anchoring: raw BSE histograms of this spot and two spots from other sessions
    anchor_spots = []
    for label in [f"{batch}/{sid}", *[s for s in COMPARE_SPOTS if s != f"{batch}/{sid}"]]:
        b, s = label.split("/")
        rs = raw if (b, s) == (batch, sid) else pp.load_spot(data_dir / b, s)
        h_, w_ = rs.bse.shape
        a0, a1, a2, a3 = pp.crop_box(h_, w_)
        crop = rs.bse[a0:a1, a2:a3]
        bl, gr = (black, graphite) if rs is raw else pp.anchor(crop)
        anchor_spots.append({"label": label, "batch": b, "sample_id": s, "height": h_, "black": r(bl, 2),
                             "graphite": r(gr, 2), "hist": hist(crop[::2, ::2], -0.5, 255.5, 256, smooth=1.5)})

    # noise: a zoom patch inside the chosen tile, before and after the top-up
    grid = pp.tile_grid(bse.shape)
    ty, tx = next((y, x) for rr, cc, y, x in grid if (rr, cc) == tile_rc)
    py, px = ty + 176, tx + 176
    sl = (slice(py, py + NOISE_PATCH), slice(px, px + NOISE_PATCH))
    noise = {
        "before": save_img(f"{p}noise_before.png", to_u8(bse_anch[sl], 0, BSE_DISPLAY_MAX)),
        "after": save_img(f"{p}noise_after.png", to_u8(bse[sl], 0, BSE_DISPLAY_MAX)),
        "size": NOISE_PATCH, "bse_sigma": r(bse_sigma), "bse_added": r(bse_added), "bse_target": pp.BSE_NOISE_TARGET,
        "inlens_sigma": r(inl_sigma), "inlens_added": r(inl_added), "inlens_target": pp.INLENS_NOISE_TARGET,
    }
    rank = {"inlens_raw": hist(raw.inlens[r0:r1:2, c0:c1:2], -0.5, 255.5, 64, smooth=0.7),
            "inlens": hist(inl_rank[::2, ::2], 0, 1, 24),
            "se_raw": hist(raw.se[r0:r1:2, c0:c1:2], -0.5, 255.5, 64, smooth=0.7),
            "se": hist(se[::2, ::2], 0, 1, 24)}

    t = next(t for t in pp.tiles_of(ref) if (t.row, t.col) == tile_rc)
    planes = {"bse": save_img(f"{p}tile_bse.png", to_u8(t.bse, 0, BSE_DISPLAY_MAX), 256),
              "inlens": save_img(f"{p}tile_inlens.png", to_u8(t.inlens), 256),
              "se": save_img(f"{p}tile_se.png", to_u8(t.se), 256),
              "void": save_img(f"{p}tile_void.png", t.void.astype(np.uint8) * 255, 256),
              "bright": save_img(f"{p}tile_bright.png", t.bright.astype(np.uint8) * 255, 256)}

    prep = {
        "raw": {"h": H, "w": W, "img": raw_imgs},
        "crop": {"r0": r0, "r1": r1, "c0": c0, "c1": c1, "top": pp.CROP_TOP, "bottom": pp.CROP_BOTTOM,
                 "side": pp.CROP_SIDE, "height": pp.CROP_HEIGHT},
        "window": {"h": r1 - r0, "w": c1 - c0, "img": win},
        "anchor": {"spots": anchor_spots, "raw_range": [-0.5, 255.5], "unit_range": [-0.6, 3.0]},
        "noise": noise,
        "rank": rank,
        "seg": {"t_void": r(t_void), "t_bright": r(t_bright), "bright_peak": r(peak), "peak_found": bool(found),
                "porosity": r(void.mean()), "bright_frac": r(bright.mean())},
        "tiles": {"size": pp.TILE, "um": pp.TILE * pp.PIXEL_UM, "grid": [list(g) for g in grid],
                  "chosen": {"row": t.row, "col": t.col, "y": t.y, "x": t.x, "planes": planes,
                             "porosity": r(t.meta["tile_porosity"]), "bright_frac": r(t.meta["tile_bright_frac"])}},
    }
    return prep, t


# ---- part 2: the CNN ---------------------------------------------------------------------------------------------
def legacy_material_net(cfg):
    """The old V1 MaterialNet (cnn/train.py, removed from cnn/model.py with the move to V2), rebuilt from the current
    Encoder / Decoder so the page can still load a V1 checkpoint (cnn/processed/v_k7_con02/best.pt): one shared
    1-channel encoder run per detector after a per-detector 1x1 adapter, one z per detector."""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from cnn.common import DETECTORS, N_CLASSES
    from cnn.model import Decoder, Encoder, resolve_arch

    class MaterialNet(nn.Module):
        def __init__(self, arch, with_decoder):
            super().__init__()
            self.arch = resolve_arch(arch)
            self.detectors = tuple(DETECTORS)
            self.pretrained = False
            widths = self.arch["widths"]
            self.adapters = nn.ModuleDict({d: nn.Conv2d(1, 1, 1) for d in self.detectors})
            self.encoder = Encoder(widths, self.arch["k"], self.arch["stem"], self.arch["dil"])
            self.decoder = Decoder(widths, len(self.detectors), N_CLASSES) if with_decoder else None
            self.feat_dim = 2 * widths[-1]
            self.proj = nn.Sequential(nn.BatchNorm1d(self.feat_dim), nn.Linear(self.feat_dim, widths[-1]), nn.GELU(),
                                      nn.Linear(widths[-1], 128))

        def forward(self, x, seg=True):
            skips = {d: self.encoder(self.adapters[d](x[:, i:i + 1])) for i, d in enumerate(self.detectors)}
            feat = {d: self.encoder.pooled(skips[d][-1]) for d in self.detectors}
            out = {"feat": feat, "z": {d: F.normalize(self.proj(feat[d]), dim=1) for d in self.detectors}}
            if seg and self.decoder is not None:
                out["seg"] = self.decoder([torch.cat([skips[d][i] for d in self.detectors], 1) for i in range(len(skips[self.detectors[0]]))])
            return out

    return MaterialNet(cfg.get("arch", "base"), float(cfg.get("w_seg", 1.0)) > 0)


def cnn_part(run, tile, n_tiles):
    import torch
    from cnn.common import RUNS_DIR, TILES_CSV
    from cnn.model import net_from_config

    torch.set_grad_enabled(False)
    run_dir = RUNS_DIR / run                                           # `run` may hold slashes (supcon/v2/full)
    cfg_file = json.loads((run_dir / "config.json").read_text()) if (run_dir / "config.json").exists() else {}
    fusion = cfg_file.get("fusion") == "early"
    ck_name = os.environ.get("LOSSLARP_CKPT") or ("last.pt" if fusion else "best.pt")   # supcon.py writes last.pt only
    if not (run_dir / ck_name).exists() and (run_dir / "last.pt").exists():
        ck_name = "last.pt"
    ck = torch.load(run_dir / ck_name, map_location="cpu", weights_only=False)
    cfg = ck["config"]
    arch = cfg.get("arch", "base")
    fusion = cfg.get("fusion") == "early"
    # a V2 FusionNet run (cnn/supcon.py, net_from_config) or a V1 MaterialNet checkpoint (legacy loader above)
    make = (lambda: net_from_config(cfg)) if fusion else (lambda: legacy_material_net(cfg))
    trained = make()
    # strict=False: supcon.py may have grown heads since the checkpoint was written (e.g. an adversarial session head);
    # the page only runs the encoder and the projection, which must be present
    missing, unexpected = trained.load_state_dict(ck["model"], strict=False)
    core = [k_ for k_ in missing if k_.startswith(("encoder.", "proj."))]
    if core:
        raise SystemExit(f"checkpoint {run_dir / ck_name} lacks encoder / projection weights: {core[:5]}")
    if missing or unexpected:
        print(f"part 2: checkpoint and current FusionNet differ outside the encoder (missing {sorted(missing)[:4]}, unexpected {sorted(unexpected)[:4]}); ignored")
    torch.manual_seed(0)
    untrained = make()
    trained.eval(), untrained.eval()
    if getattr(trained, "pretrained", False):
        raise SystemExit("the kernel animation expects a from-scratch encoder (3x3 first conv on 1 channel)")
    temperature = float(cfg.get("temperature", 0.1))

    def x_of(t):
        return torch.from_numpy(np.stack([t.bse, t.inlens, t.se]).astype(np.float32))[None]

    x = x_of(tile)
    val = ck.get("val", {}) or {}
    train_spots, val_spots = set(cfg.get("train_spots", [])), set(cfg.get("val_spots", cfg.get("heldout_spots", [])))
    run_info = {"name": run, "arch": arch, "epoch": int(ck.get("epoch", 0)), "epochs": cfg.get("epochs"),
                "n_train_tiles": cfg.get("n_train_tiles"), "n_val_tiles": cfg.get("n_val_tiles"),
                "train_spots": sorted(train_spots), "val_spots": sorted(val_spots), "checkpoint": ck_name,
                "params_M": r(cfg.get("params_M", 0), 2), "temperature": temperature, "fusion": cfg.get("fusion"),
                "loss": cfg.get("loss"), "w_seg": cfg.get("w_seg"), "w_ce": cfg.get("w_ce"), "level": cfg.get("level"),
                "batch_spots": cfg.get("batch_spots"), "tiles_per_spot": cfg.get("tiles_per_spot"), "w_adv": cfg.get("w_adv"),
                "val": {k_: r(v) for k_, v in val.items() if isinstance(v, (int, float))}}
    if fusion:
        return cnn_part_fusion(trained, untrained, tile, x, x_of, run_info, cfg, train_spots, val_spots, temperature)
    dets = ("bse", "inlens")
    adapted = {d: trained.adapters[d](x[:, i:i + 1]) for i, d in enumerate(dets)}
    conv1 = trained.encoder.stages[0][1][0]                       # stage 0 = (Identity, conv_block); [0] = 1st conv
    first = {d: conv1(adapted[d])[0] for d in dets}                # (C, 512, 512)

    # which kernel to show: the channel whose BSE and Inlens maps agree most (the shared kernel finds the same
    # structure through both detectors), among channels that actually respond (top half by spread)
    spread = torch.stack([first[d].flatten(1).std(1) for d in dets]).min(0).values
    a, b = (first[d].flatten(1) for d in dets)
    corr = torch.nn.functional.cosine_similarity(a - a.mean(1, keepdim=True), b - b.mean(1, keepdim=True), dim=1)
    corr[spread < spread.median()] = -2
    ch = int(corr.argmax())
    w = conv1.weight[ch, 0]                                        # (k, k): 3x3 for base, 7x7 for k7
    k = int(conv1.kernel_size[0])
    h = k // 2
    grid = GRID if k <= 3 else 24                                  # fewer scan positions when each carries k*k pixels

    step = pp.TILE // grid
    kernel = {"channel": ch, "n_channels": conv1.out_channels, "corr": r(corr[ch]), "grid": grid, "step": step, "k": k,
              "weights": [r(v) for v in w.flatten().tolist()], "display": 256,
              "adapter": {d: [r(trained.adapters[d].weight.item()), r(trained.adapters[d].bias.item())] for d in dets},
              "input": {}, "fmap": {}, "fmap_range": {}, "samples": {}}
    for i, d in enumerate(dets):
        plane = x[0, i].numpy()
        disp = to_u8(pool(plane, 2), 0, BSE_DISPLAY_MAX if d == "bse" else 1.0)
        fm = pool(first[d][ch].numpy(), 2)
        fm_u8, lo, hi = robust_u8(fm)
        kernel["input"][d], kernel["fmap"][d], kernel["fmap_range"][d] = b64(disp), b64(fm_u8), [r(lo), r(hi)]
        # at each scan position: the real k x k patch the kernel sees (after the detector's adapter) and its output
        ad, out = adapted[d][0, 0].numpy(), first[d][ch].numpy()
        samples = []
        for gy in range(grid):
            for gx in range(grid):
                cy, cx = gy * step + step // 2, gx * step + step // 2
                patch = ad[cy - h:cy + h + 1, cx - h:cx + h + 1]
                val = float((patch * w.numpy()).sum())
                assert abs(val - out[cy, cx]) < 1e-3, "kernel sample does not reproduce the conv output"
                samples.append([r(v, 3) for v in patch.flatten()] + [r(val, 3)])
        kernel["samples"][d] = samples

    # deeper stages: each stage's most active channel, shrinking with stride 2, 4, 8, 16
    feats = {d: trained.encoder(adapted[d]) for d in dets}
    stages = []
    for s in range(1, len(feats["bse"])):
        fb = feats["bse"][s][0]
        m = max(1, fb.shape[-1] // 10)
        c = int(fb[:, m:-m, m:-m].flatten(1).std(1).argmax())
        entry = {"stage": s, "channel": c, "channels": fb.shape[0], "res": fb.shape[-1], "maps": {}}
        for d in dets:
            m = feats[d][s][0, c].numpy()
            res = m.shape[-1]
            if res > 128:
                m = pool(m, res // 128)
            entry["maps"][d] = b64(robust_u8(m, margin=0.1)[0])
            entry["size"] = m.shape[-1]
        stages.append(entry)

    out_t = trained(x, seg=False)
    z = {d: out_t["z"][d][0].numpy() for d in dets}

    # the similarity matrix: tiles spread over the spots that have tiles on disk, the chosen tile first
    with open(TILES_CSV) as f:
        rows = list(csv.DictReader(f))
    by_spot = {}
    for rr in rows:
        by_spot.setdefault((rr["batch"], rr["sample_id"]), []).append((int(rr["row"]), int(rr["col"])))
    spots = sorted(by_spot)
    picks = [(tile.batch, tile.sample_id, tile.row, tile.col)]
    rng = np.random.default_rng(0)
    order = [s for s in spots if s != (tile.batch, tile.sample_id)] + [(tile.batch, tile.sample_id)]
    k = 0
    while len(picks) < n_tiles and k < 50 * n_tiles:
        b_, s_ = order[k % len(order)]
        rc = by_spot[(b_, s_)][rng.integers(len(by_spot[(b_, s_)]))]
        if (b_, s_, *rc) not in picks:
            picks.append((b_, s_, *rc))
        k += 1
    mtiles, zs = [], {"trained": {d: [] for d in dets}, "untrained": {d: [] for d in dets}}
    for b_, s_, rr, cc in picks:
        t = pp.load_tile(b_, s_, rr, cc)
        xt = x_of(t)
        for name, net in (("trained", trained), ("untrained", untrained)):
            zt = net(xt, seg=False)["z"]
            for d in dets:
                zs[name][d].append(zt[d][0].numpy())
        role = "train" if s_ in train_spots else "held-out" if s_ in val_spots else "unseen"
        mtiles.append({"batch": b_, "sample_id": s_, "row": rr, "col": cc, "role": role,
                       "thumb": {"bse": b64(to_u8(pool(t.bse, 8), 0, BSE_DISPLAY_MAX)),
                                 "inlens": b64(to_u8(pool(t.inlens, 8)))}})
    matrix = {"tiles": mtiles, "thumb_size": pp.TILE // 8, "temperature": temperature}
    for name in ("trained", "untrained"):
        A, B = np.stack(zs[name]["bse"]), np.stack(zs[name]["inlens"])
        S = A @ B.T                                                 # z is L2-normalised: cosine similarity
        hit = (S.argmax(1) == np.arange(len(S))).mean()
        matrix[name] = {"sim": [[r(v) for v in row] for row in S], "retrieval": r(hit)}
        print(f"part 2: {name:9s} BSE->Inlens retrieval {hit:.2f} over {len(S)} tiles "
              f"(chance {1 / len(S):.2f}); mean diag {np.diag(S).mean():.3f} vs off {S[~np.eye(len(S), dtype=bool)].mean():.3f}")

    print(f"part 2: run {run} ({arch}, epoch {run_info['epoch']}), kernel channel {ch} (BSE/Inlens map corr {corr[ch]:.2f})")
    return {"run": run_info, "fusion": None, "kernel": kernel, "stages": stages,
            "z": {d: [r(v) for v in z[d].tolist()] for d in dets}, "z_cos": r(float(z["bse"] @ z["inlens"])),
            "feat_dim": trained.feat_dim, "matrix": matrix}


def cnn_part_fusion(trained, untrained, tile, x, x_of, run_info, cfg, train_spots, val_spots, temperature):
    """Part 2 for the V2 FusionNet: the 3-channel tile goes in as one image, so the first-layer kernel has three
    planes (BSE, Inlens, SE) and one output. One patch per plane, three weight grids, one map pixel. There is no
    per-detector embedding to match, so section 03 shows the batch-contrastive loss instead (contrast_part)."""
    import torch
    planes = ("bse", "inlens", "se")
    conv1 = trained.encoder.stages[0][1][0]                        # (C, 3, k, k), bias=False
    first = conv1(x)[0]                                            # (C, 512, 512)
    # which kernel to show: one that responds (top half by spread) and uses all three detectors (largest smallest
    # per-plane weight norm), so the three-planes-in picture is honest
    spread = first.flatten(1).std(1)
    wnorm = conv1.weight.flatten(2).norm(dim=2)                    # (C, 3)
    score = wnorm.min(1).values.clone()
    score[spread < spread.median()] = -1
    ch = int(score.argmax())
    w = conv1.weight[ch].numpy()                                   # (3, k, k)
    k = int(conv1.kernel_size[0])
    h = k // 2
    grid = GRID if k <= 3 else 24
    step = pp.TILE // grid
    out = first[ch].numpy()
    fm_u8, lo, hi = robust_u8(pool(out, 2))
    kernel = {"fusion": True, "planes": list(planes), "channel": ch, "n_channels": conv1.out_channels, "grid": grid,
              "step": step, "k": k, "display": 256,
              "weights": {d: [r(v) for v in w[i].flatten().tolist()] for i, d in enumerate(planes)},
              "plane_norm": {d: r(wnorm[ch, i]) for i, d in enumerate(planes)},
              "input": {d: b64(to_u8(pool(x[0, i].numpy(), 2), 0, BSE_DISPLAY_MAX if d == "bse" else 1.0)) for i, d in enumerate(planes)},
              "fmap": b64(fm_u8), "fmap_range": [r(lo), r(hi)], "samples": []}
    xs = x[0].numpy()
    for gy in range(grid):
        for gx in range(grid):
            cy, cx = gy * step + step // 2, gx * step + step // 2
            patch = xs[:, cy - h:cy + h + 1, cx - h:cx + h + 1]    # (3, k, k): the real pixels of the three planes
            val = float((patch * w).sum())
            assert abs(val - out[cy, cx]) < 1e-3, "kernel sample does not reproduce the conv output"
            kernel["samples"].append([r(v, 3) for v in patch.flatten()] + [r(val, 3)])

    feats = trained.encoder(x)
    stages = []
    for s in range(1, len(feats)):
        fb = feats[s][0]
        m = max(1, fb.shape[-1] // 10)
        c = int(fb[:, m:-m, m:-m].flatten(1).std(1).argmax())
        mp = fb[c].numpy()
        res = mp.shape[-1]
        if res > 128:
            mp = pool(mp, res // 128)
        stages.append({"stage": s, "channel": c, "channels": fb.shape[0], "res": res, "size": mp.shape[-1],
                       "maps": {"fused": b64(robust_u8(mp, margin=0.1)[0])}})
    o = trained(x, seg=False)
    z = o["z"][0].numpy()
    print(f"part 2: run {run_info['name']} ({run_info['arch']}, early fusion, {run_info['checkpoint']}, epoch {run_info['epoch']}), "
          f"kernel channel {ch} of {conv1.out_channels}, plane weight norms " + ", ".join(f"{d} {kernel['plane_norm'][d]:.3f}" for d in planes))
    contrast = contrast_part(trained, untrained, tile, x_of, train_spots, val_spots, temperature)
    return {"run": run_info, "fusion": "early", "kernel": kernel, "stages": stages,
            "z": {"fused": [r(v) for v in z.tolist()]}, "z_cos": None, "feat_dim": trained.feat_dim, "matrix": None,
            "contrast": contrast}


def contrast_part(trained, untrained, tile, x_of, train_spots, val_spots, temperature, spots_per_batch=3, tiles_per_spot=2):
    """Section 03 for V2: a few spots of every batch, two tiles each, the walkthrough tile first. For the trained and
    the untrained network: the cosine similarity of every pair of z, and per row what the supervised contrastive loss
    asks for. relation[i][j]: 'pos' = same batch, different spot (pulled together); 'spot' = same spot (excluded from
    the loss, otherwise the network learns spot identity); 'neg' = other batch (pushed apart). pos_share[i] is the
    share of row i's softmax (temperature as in training, self excluded) that falls on its positives: the quantity the
    loss maximises; chance_share is what a flat row would give."""
    from cnn.common import TILES_CSV
    with open(TILES_CSV) as f:
        rows = list(csv.DictReader(f))
    by_spot = {}
    for rr in rows:
        by_spot.setdefault((rr["batch"], rr["sample_id"]), []).append((int(rr["row"]), int(rr["col"])))
    rng = np.random.default_rng(0)
    batches = [tile.batch] + sorted({b for b, _ in by_spot} - {tile.batch})      # the walkthrough tile's batch first
    picks = []
    for b in batches:
        ids = sorted(s_ for bb, s_ in by_spot if bb == b)
        own = [tile.sample_id] if b == tile.batch else []
        rest = [s_ for s_ in ids if s_ not in own]
        rng.shuffle(rest)
        for s_ in own + rest[:spots_per_batch - len(own)]:
            rcs = by_spot[(b, s_)]
            if s_ == tile.sample_id:
                others = [rc for rc in rcs if rc != (tile.row, tile.col)]
                sel = [(tile.row, tile.col)] + [others[i] for i in rng.choice(len(others), tiles_per_spot - 1, replace=False)]
            else:
                sel = [rcs[i] for i in rng.choice(len(rcs), min(tiles_per_spot, len(rcs)), replace=False)]
            picks += [(b, s_, *rc) for rc in sel]
    meta, Z = [], {"trained": [], "untrained": []}
    for b, s_, rr, cc in picks:
        t = pp.load_tile(b, s_, rr, cc)
        xt = x_of(t)
        for name, net in (("trained", trained), ("untrained", untrained)):
            Z[name].append(net(xt, seg=False)["z"][0].numpy())
        role = "train" if s_ in train_spots else "held-out" if s_ in val_spots else "unseen"
        meta.append({"batch": b, "sample_id": s_, "row": rr, "col": cc, "role": role,
                     "thumb": b64(to_u8(pool(t.bse, 8), 0, BSE_DISPLAY_MAX))})
    n = len(meta)
    bi = np.array([int(m["batch"][-1]) for m in meta])
    si = np.array([m["sample_id"] for m in meta])
    eye = np.eye(n, dtype=bool)
    pos = (bi[:, None] == bi[None, :]) & (si[:, None] != si[None, :])
    same_spot = (si[:, None] == si[None, :]) & ~eye
    neg = bi[:, None] != bi[None, :]
    out = {"tiles": meta, "thumb_size": pp.TILE // 8, "temperature": temperature,
           "relation": [["self" if eye[i, j] else "pos" if pos[i, j] else "spot" if same_spot[i, j] else "neg" for j in range(n)] for i in range(n)],
           "chance_share": [r(v) for v in (pos.sum(1) / (n - 1)).tolist()]}
    for name in Z:
        A = np.stack(Z[name])
        S = A @ A.T                                                 # z is L2-normalised: cosine similarity
        logits = S / temperature
        logits[eye] = -1e9
        pr = np.exp(logits - logits.max(1, keepdims=True))
        pr /= pr.sum(1, keepdims=True)
        share = (pr * pos).sum(1)
        loss = -(np.log(np.clip(pr, 1e-12, None)) * pos).sum(1) / pos.sum(1)
        S_off = np.where(eye, -9.0, S)
        best_is_pos = float(np.mean([pos[i, int(S_off[i].argmax())] for i in range(n)]))
        out[name] = {"sim": [[r(v) for v in row] for row in S], "pos_share": [r(v) for v in share.tolist()],
                     "loss": r(float(loss.mean())), "within": r(float(S[pos].mean())), "across": r(float(S[neg].mean())),
                     "same_spot": r(float(S[same_spot].mean())), "best_is_pos": r(best_is_pos)}
        print(f"part 2: {name:9s} contrast over {n} tiles: same batch/other spot {S[pos].mean():.3f}, other batch {S[neg].mean():.3f}, "
              f"share on positives {share.mean():.2f} (chance {out['chance_share'][0]:.2f}), best match is a positive {best_is_pos:.2f}")
    return out


FEATURE_LABELS = {
    "porosity_frac": "pore fraction", "si_solid_frac": "Si-like share of the solid", "si_n_per_1000um2": "Si particles per 1000 µm²",
    "si_d50_um": "Si particle size d50 (µm)", "si_d90_um": "Si particle size d90 (µm)", "si_aspect_aw": "Si particle aspect ratio",
    "si_agglom_d50_um": "Si agglomerate size (µm)", "interface_density_per_um": "pore-wall length per area (1/µm)",
    "pore_n_per_1000um2": "pores per 1000 µm²", "solid_chord_x_um": "solid chord across (µm)", "solid_chord_y_um": "solid chord down (µm)",
    "porosity_block_cv": "pore unevenness within a tile", "si_block_cv": "Si unevenness within a tile",
    "solid_chord_hv_ratio": "chord ratio across / down",
    "thin_solid_frac": "solid in ligaments < 0.5 µm", "depth_porosity_b0_frac": "pore fraction, bottom 11 µm",
    "depth_interface_b0_per_um": "pore-wall length, bottom 11 µm (1/µm)",
    "depth_interface_b1_per_um": "pore-wall length, 11-22 µm up (1/µm)",
    "depth_interface_slope_per_10um": "pore-wall length change towards the bottom (per 10 µm)",
}
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qc.spot_features import labels as _plugin_labels  # noqa: E402
FEATURE_LABELS.update(_plugin_labels())               # qc/spot_features/<id>.py LABELS


V1_RUN = "v_k7_con02"            # the old label-free MaterialNet run: its predictions.json gives V1's test-spot calls
V2_NAME = "v2"                   # cnn/processed/supcon/<V2_NAME>/score.json and full/difference.json


def predict_summary(pred):
    """The parts of a cnn/predict.py predictions.json the page uses."""
    keys = ["lr_loso", "lr_losess", "lr_mixed", "lr_joins", "ari_kmeans", "lr_losess_perm_p", "lr_loso_perm_p"]
    out = {k_: pred.get(k_) for k_ in ("run", "epoch", "chance", "n_spots", "n_sessions", "losess_bacc", "loso_bacc",
                                       "confusion_losess", "recall_losess", "b3_vs_rest", "b1_vs_b2_losess_bacc", "test", "leak")}
    out["scores"] = {k_: pred.get("scores", {}).get(k_) for k_ in keys}
    out["spots"] = [{k_: s.get(k_) for k_ in ("batch", "sample_id", "session", "y", "call_losess", "p_losess")} for s in pred.get("spots", [])]
    return out


def results_part(run, n_tiles_per_spot):
    """Part 3: the results of qc/ and cnn/{predict,explain,probe,supcon score,difference}.py, read from their JSON
    files only (no torch, no evalkit here). Returns None when the qc files are missing, so the page still shows parts
    1 and 2; every other file is optional and its block degrades on the page."""
    import shutil
    rd = ROOT / "cnn" / pp.PROCESSED_NAME / run
    qc = ROOT / "qc" / pp.PROCESSED_NAME
    sup = ROOT / "cnn" / pp.PROCESSED_NAME / "supcon" / V2_NAME

    def rd_json(p):
        return json.loads(p.read_text()) if p.exists() else None

    pred, verd, imp = rd_json(rd / "predictions.json"), rd_json(qc / "verdicts.json"), rd_json(qc / "impacts.json")
    probe, expl = rd_json(rd / "probe.json"), rd_json(rd / "explain.json")
    if verd is None or imp is None:
        print("part 3: qc verdicts.json / impacts.json missing, results section skipped")
        return None

    def copy_img(src, name):
        if not Path(src).exists():
            return None
        shutil.copy(src, IMG / name)
        return f"img/{name}"

    cfg = rd_json(rd / "config.json") or {}
    if cfg.get("fusion") == "early":
        run_label = f"{cfg.get('arch', run)} (early fusion, batch-supervised contrastive, w_seg {cfg.get('w_seg', '?')})"
    else:
        run_label = f"{cfg.get('arch', run)} (w_con {cfg.get('w_con', '?')})" if cfg else run
    out = {"run": run, "run_label": run_label, "feature_labels": FEATURE_LABELS, "n_tiles_per_spot": n_tiles_per_spot,
           "is_v2": cfg.get("fusion") == "early"}
    # the baselines (cnn/baselines.py): every number from that file
    baselines = rd_json(HERE / "data" / "baselines.json")
    if baselines:
        out["baselines"] = baselines
    # V2: score.json sits in the run's parent (cnn/processed/supcon/v2/), difference.json in the full model's folder.
    # When the page is built against another run, the canonical V2 location is used, so section 04 can still
    # compare V1 and V2.
    score = rd_json(rd.parent / "score.json") or rd_json(sup / "score.json")
    diff = rd_json(rd / "difference.json") or rd_json(sup / "full" / "difference.json")
    if score or diff:
        out["v2"] = {"score": score, "difference": diff}
    print(f"part 3: V2 score.json {'found' if score else 'missing'}, difference.json {'found' if diff else 'missing'}")
    # V1: the old model's predictions (test-spot calls with the session caveat, session leak), from its own run
    # folder when this page is built against a different run
    v1_pred = rd_json(ROOT / "cnn" / pp.PROCESSED_NAME / V1_RUN / "predictions.json")
    if v1_pred and run != V1_RUN:
        out["v1"] = {"run": V1_RUN, "predict": predict_summary(v1_pred)}
    out["novelty"] = rd_json(rd / "novelty.json")
    # V1 vs V2 vs V1+2 on the same spot folds, and the material checks (cnn/compare.py -> cnn/results/compare.json)
    cmp = rd_json(ROOT / "cnn" / "results" / "compare.json")
    if cmp:
        keep = ("bacc", "ci90", "recall", "mixed_bacc", "delta_vs_v1", "moved")
        out["compare"] = {"folds": cmp["folds"], "order": list(cmp["models"]),
                          "models": {k_: {kk: v.get(kk) for kk in keep} for k_, v in cmp["models"].items()},
                          "material": {k_: {kk: v.get(kk) for kk in ("mean_r2", "null_mean_r2", "batch_direction_named_share", "session_leak")}
                                       for k_, v in cmp.get("material", {}).items()}}
    extra = rd_json(ROOT / "cnn" / "results" / "compare_extra.json")
    if cmp and extra:                                            # the other combinations tried (best-of-K context)
        out["compare"]["extra"] = {k_: {kk: v.get(kk) for kk in keep} for k_, v in extra["models"].items() if k_ not in cmp["models"]}
    # test-spot calls of V1, V2 and V1 + V2, each refitted on all 31 spots, with the call's stability over refits
    tc = rd_json(ROOT / "cnn" / "results" / "test_calls.json")
    if tc:
        out["test_calls"] = tc
    print(f"part 3: compare.json {'found' if cmp else 'missing'}, compare_extra.json {'found' if extra else 'missing'}, test_calls.json {'found' if tc else 'missing'}")
    keys = ["lr_loso", "lr_losess", "lr_mixed", "lr_joins", "ari_kmeans", "lr_losess_perm_p", "lr_loso_perm_p"]
    if probe:
        out["probe"] = {"r2": probe["r2_by_session"], "complement_share": probe["complement_share_of_variance"],
                        "scores": {k_: {kk: v.get(kk) for kk in keys} for k_, v in probe["scores"].items()},
                        "synthetic_complement_losess": probe["synthetic"]["complement"]["lr_losess"],
                        "galleries": {f"B{b}": copy_img(rd / f"probe_gallery_B{b}.png", f"x_gallery_B{b}.png") for b in (1, 2, 3)}}
    out["predict"] = predict_summary(pred) if pred else None
    if pred is None:
        print(f"part 3: {rd.relative_to(ROOT)}/predictions.json missing; section 04 uses score.json / the V1 run instead")
    kpi_keys = ["tier", "can_reject", "zone", "delta", "delta_sd", "ci_lo_sd", "ci_hi_sd", "margin_sd", "n", "n_inside", "lot_mean",
                "baseline_mean", "baseline_sd", "p_beyond_margin", "tier2_pass", "tier2_need", "skip", "sign_ok", "values"]
    out["verdict"] = {"baseline": verd["baseline"], "config": verd["config"], "lots": {
        label: {**{k_: lot[k_] for k_ in ("verdict", "action", "reasons", "n_sites", "n_sessions", "sites", "sessions")},
                "kpis": {f: {k_: r_.get(k_) for k_ in kpi_keys if k_ in r_} for f, r_ in lot["kpis"].items()}}
        for label, lot in verd["lots"].items()}}
    out["impacts"] = {k_: imp[k_] for k_ in ("properties", "lots", "bands", "rules", "composite")}
    if expl:
        spots = {}
        for key, s in expl["spots"].items():
            top = [{**t, "bse": copy_img(rd / "explain_img" / t["bse"], "x_" + t["bse"]), "map": copy_img(rd / "explain_img" / t["map"], "x_" + t["map"])}
                   for t in s["heat"]["top"]]
            spots[key] = {**{k_: s[k_] for k_ in ("batch", "sample_id", "session", "y", "call", "scores", "p_insample", "decomposition", "neighbours")},
                          "heat": {**s["heat"], "top": top}}
            for k_ in ("ablation", "perturbation"):
                if k_ in s:
                    spots[key][k_] = s[k_]
        out["explain"] = {"classes": expl["classes"], "features": expl["features"], "spots": spots}
    fq = rd_json(qc / "feature_quality.json")
    if fq:
        out["feature_quality"] = fq["features"]
    attr = rd_json(rd / "attribution.json")
    if attr:
        out["attribution"] = {"cell_px": attr["cell_px"], "spots": {
            key: {**s, "mosaic": copy_img(rd / "attr_img" / s["mosaic"], "x_attr_" + s["mosaic"]),
                  "top": copy_img(rd / "attr_img" / s["top"], "x_attr_" + s["top"])} for key, s in attr["spots"].items()}}
    maps = sorted((rd / "maps").glob("*.png"))[:4] if (rd / "maps").exists() else []
    out["maps"] = [copy_img(p, "x_map_" + p.name) for p in maps]
    n_img = sum(1 for p in IMG.glob("x_*"))
    print(f"part 3: results for run {run}: {len(out.get('sweep', []))} sweep rows, {len(out.get('explain', {}).get('spots', {}))} explained spots, {n_img} images")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spot", default="Batch_1/4ih2ggld", help="<batch>/<sample_id> shown in the walkthrough")
    ap.add_argument("--tile", default="0,5", help="row,col of the tile carried into the CNN part")
    ap.add_argument("--run", default="supcon/v2/full",
                    help="cnn/processed/<run>/ (last.pt for a FusionNet run, best.pt otherwise; LOSSLARP_CKPT overrides)")
    ap.add_argument("--n-tiles", type=int, default=8, help="tiles in V1's BSE x Inlens similarity matrix")
    ap.add_argument("--v1-run", default=V1_RUN, help="the label-free V1 run shown as section 03a next to V2 (skipped if missing)")
    ap.add_argument("--data-dir", default=str(pp.DATA_DIR))
    a = ap.parse_args()
    batch, sid = a.spot.split("/")
    tile_rc = tuple(int(v) for v in a.tile.split(","))
    IMG.mkdir(parents=True, exist_ok=True)
    for old in IMG.glob("*"):
        # img/lanes/ belongs to dashboard/lanes.py (section 00) and img/lit_*.jpg to literature/feature_cards.py (section 08):
        # both are left alone, or a rebuild deletes pictures the page still needs
        if old.is_file() and not old.name.startswith("lit_"):
            old.unlink()

    prep, tile = prep_part(Path(a.data_dir), batch, sid, tile_rc)
    cnn = cnn_part(a.run, tile, a.n_tiles)
    if cnn.get("fusion") == "early" and a.v1_run:
        v1_dir = ROOT / "cnn" / pp.PROCESSED_NAME / a.v1_run
        if (v1_dir / "best.pt").exists() or (v1_dir / "last.pt").exists():
            v1 = cnn_part(a.v1_run, tile, a.n_tiles)              # the old MaterialNet: one pass per detector
            cnn["v1"] = {k_: v1[k_] for k_ in ("run", "matrix", "z", "z_cos")}
        else:
            print(f"part 2: V1 run {a.v1_run} has no checkpoint; section 03a skipped")
    results = results_part(a.run, len(prep["tiles"]["grid"]))
    data = {"version": 2, "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "spot": {"batch": batch, "sample_id": sid, "pixel_um": pp.PIXEL_UM}, "prep": prep, "cnn": cnn, "results": results}
    out = SITE / "pipeline.js"
    out.write_text("window.PIPELINE = " + json.dumps(data, separators=(",", ":")) + ";\n")
    size = sum(p.stat().st_size for p in IMG.glob("*")) + out.stat().st_size
    print(f"wrote {out.relative_to(ROOT)} and {len(list(IMG.glob('*')))} images ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
