"""Embedding sweep on Modal: many frozen backbones x input variants -> one embedding per spot (train + test).

Why: Polaron built the batches by cutting ~20 large images into crops (our spots) and grouping the crops by
high-dimensional features they extracted. To reproduce that grouping we need to find a representation close to
theirs, so this sweeps the plausible ones instead of committing to one. analysis/embeddings/evalkit.py scores them.

Run from the repo root (CPU only: the workspace has no GPU payment method; one container per backbone x spot):
    modal run cloud/embed_sweep.py --backbones dv2_s --spots Batch_1/4ih2ggld,Test/3e122cbj --out-dir /tmp/x  # smoke
    modal run cloud/embed_sweep.py --backbones dv2_s,dv3_s,clip_b16        # -> processed/emb_sweep/<backbone>.npz
    modal run cloud/embed_sweep.py --backbones all

What one spot gives, per backbone:
    window     the harmonisation crop of every image (features/_common: central 1336 rows away from the top-of-frame
               artefact, 8 px off each side), so every spot covers the same area and image height never leaks in.
    modes      raw       the TIF grey levels / 255 (keeps black level, contrast: what an outside pipeline would see)
               pstretch  per-image 1-99 % stretch (preprocessing.normalise_brightness)
               harm      the harmonised arrays (BSE in graphite units clipped to [0, 2.6]; Inlens/SE rank units)
    channels   BSE, Inlens, SE (= ETD) each replicated to 3 channels; rgb = (BSE, Inlens, SE) as (R, G, B)
    scales     s1, s2, s4: the window average-pooled by 1, 2, 4, then a centred grid of 224 px tiles
               (s1 = 5.6 um tiles, 155 per spot; s2 = 11.2 um, 30; s4 = 22.4 um, 7);
               s8: the whole window pooled by 8 and embedded in one pass (160 x 864 px, positions interpolated)
    tokens     ViT: pool (the model's own pooled output: CLS for DINOv2, mean patch for DINOv3), cls (the CLS token
               when pool is not it), patch (mean last-layer patch token), mid (mean patch token of the middle block).
               CNN: pool (GAP of the last stage), mid (GAP of stage n-2).
    site       mean over the spot's tiles (and the SD over tiles for s1, s2).
Heavy backbones (HEAVY) run modes raw + harm and channels BSE, Inlens, rgb only.

Model weights download once into the Volume (/vol/hf_home, prefetch) and are read from there by every container.
Tile-level arrays (s1, s2; float16) stay on the Volume: /vol/processed/emb_sweep/tiles/<backbone>/<batch>__<id>.npz
(fetch with `modal volume get losslarp-data processed/emb_sweep/tiles/<backbone> <dir>`).
Every function has a timeout; `modal run` is ephemeral, so nothing keeps running after it returns.
"""
import io
import json
import os
import re
import time
import zlib
from pathlib import Path

import modal

APP_NAME = "losslarp-embsweep"
VOLUME_NAME = "losslarp-data"
VOL = "/vol"
REMOTE_REPO = "/root/losslarp"
HF_HOME = f"{VOL}/hf_home"
TEST_DIR = f"{VOL}/test_data/Test"          # the Polaron test release: modal volume put losslarp-data <dir> /test_data/Test
TILES_VOL = f"{VOL}/processed/emb_sweep/tiles"
REPO = Path(__file__).resolve().parents[1] if modal.is_local() else Path(REMOTE_REPO)

# name -> timm model id. All public on the Hugging Face hub (timm mirror; DINOv3 under its own licence).
BACKBONES = {
    "dv2_s": "vit_small_patch14_dinov2.lvd142m",
    "dv2_s_reg": "vit_small_patch14_reg4_dinov2.lvd142m",
    "dv2_b_reg": "vit_base_patch14_reg4_dinov2.lvd142m",
    "dv2_l_reg": "vit_large_patch14_reg4_dinov2.lvd142m",
    "dv2_g_reg": "vit_giant_patch14_reg4_dinov2.lvd142m",
    "dv3_s": "vit_small_patch16_dinov3.lvd1689m",
    "dv3_splus": "vit_small_plus_patch16_dinov3.lvd1689m",
    "dv3_b": "vit_base_patch16_dinov3.lvd1689m",
    "dv3_l": "vit_large_patch16_dinov3.lvd1689m",
    "dv3_hplus": "vit_huge_plus_patch16_dinov3.lvd1689m",
    "dv3_cnx_b": "convnext_base.dinov3_lvd1689m",
    "clip_b16": "vit_base_patch16_clip_224.openai",
    "siglip2_b16": "vit_base_patch16_siglip_224.v2_webli",
    "mae_b16": "vit_base_patch16_224.mae",
    "cnx_b_in22k": "convnext_base.fb_in22k",
    "r50": "resnet50.tv2_in1k",
}
HEAVY = {"dv2_g_reg", "dv3_hplus"}
MODES = ("raw", "pstretch", "harm")
CHANS = ("BSE", "Inlens", "SE", "rgb")
SCALES = (1, 2, 4, 8)
TILE = 224
GLOBAL_HW = (160, 864)                        # s8 input (multiple of 16; 154 x 868 for patch-14 models)
TILE_SCALES = (1, 2)                          # tile arrays kept on the Volume, and site SD computed, for these
BATCH = 32

PINNED = {"numpy": "1.26.4", "scipy": "1.16.3", "scikit-image": "0.26.0", "scikit-learn": "1.7.2",
          "pandas": "2.2.3", "matplotlib": "3.10.7", "pillow": "10.2.0", "pyyaml": "6.0.1"}
TORCH = ["torch==2.8.0", "torchvision==0.23.0"]
KEEP = ("requirements.txt", "preprocessing", "features/__init__.py", "features/_common")


def ignore(rel):
    p = rel.as_posix()
    if "__pycache__" in p or p.endswith((".pyc", ".DS_Store")):
        return True
    inside = any(p == k or p.startswith(k + "/") for k in KEEP)
    parent = any(k.startswith(p + "/") for k in KEEP)
    return not (inside or parent)


def requirements():
    path = REPO / "requirements.txt"
    if not path.exists():
        return []
    lines = [ln.split("#")[0].strip() for ln in path.read_text().splitlines()]
    return [f"{ln}=={PINNED[ln.lower()]}" if ln.lower() in PINNED else ln for ln in lines if ln]


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(*requirements())
    .pip_install(*TORCH, index_url="https://download.pytorch.org/whl/cpu")
    .pip_install("timm==1.0.30", "huggingface_hub>=0.34", "safetensors")
    .env({
        "LOSSLARP_DATA_DIR": f"{VOL}/data",
        "LOSSLARP_PROCESSED_DIR": f"{VOL}/processed",
        "LOSSLARP_MODELS_DIR": f"{VOL}/models",
        "HF_HOME": HF_HOME,
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "PYTHONPATH": REMOTE_REPO,
        "PYTHONUNBUFFERED": "1",
    })
    .add_local_dir(REPO, REMOTE_REPO, ignore=ignore)
)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
app = modal.App(APP_NAME, image=image)
VOLUMES = {VOL: volume}


# ----------------------------------------------------------------------------------------------------
# REMOTE helpers
# ----------------------------------------------------------------------------------------------------
def _raw_path(batch, sid, det):
    root = Path(TEST_DIR) if batch == "Test" else Path(VOL) / "data" / batch
    names = {"SE": ("SE", "ETD"), "BSE": ("BSE",), "Inlens": ("Inlens",)}[det]
    for n in names:
        p = root / f"img_{sid}_{n}.tif"
        if p.exists():
            return p
    raise FileNotFoundError(f"no {det} image for {batch}/{sid}")


def _inputs(batch, sid, modes):
    """-> ({mode: {chan: float32 window in [0, 1]}}, height, width). Same window for every mode."""
    import numpy as np
    from features._common.harmonise import crop_box, harmonise_arrays
    from preprocessing import load_grey
    raw = {d: load_grey(_raw_path(batch, sid, d)) for d in ("BSE", "Inlens", "SE")}
    H, W = raw["BSE"].shape
    r0, r1, c0, c1 = crop_box(H, W)
    win = {d: v[r0:r1, c0:c1] for d, v in raw.items()}
    out = {}
    if "raw" in modes:
        out["raw"] = {d: v.astype(np.float32) / 255 for d, v in win.items()}
    if "pstretch" in modes:
        def stretch(v):
            lo, hi = np.percentile(v, [1, 99])
            return np.clip((v.astype(np.float32) - lo) / max(hi - lo, 1.0), 0, 1)
        out["pstretch"] = {d: stretch(v) for d, v in win.items()}
    if "harm" in modes:
        h = harmonise_arrays(raw["BSE"], raw["Inlens"], raw["SE"], zlib.crc32(f"{batch}/{sid}".encode()))
        assert h.bse.shape == win["BSE"].shape, (h.bse.shape, win["BSE"].shape)
        out["harm"] = {"BSE": np.clip(h.bse, 0, 2.6) / 2.6, "Inlens": np.clip(h.inlens, 0, 1),
                       "SE": np.clip(h.se, 0, 1)}
    for m in out:
        out[m] = {k: v.astype(np.float32) for k, v in out[m].items()}
        out[m]["rgb"] = np.stack([out[m]["BSE"], out[m]["Inlens"], out[m]["SE"]])
    return out, H, W


def _pool(img, s):
    """(C, H, W) or (H, W) float32 -> average-pooled by s (crops to a multiple of s)."""
    if s == 1:
        return img
    H, W = img.shape[-2:]
    img = img[..., : H // s * s, : W // s * s]
    return img.reshape(*img.shape[:-2], H // s, s, W // s, s).mean(axis=(-3, -1))


def _tiles(img, s):
    """-> (n, 3, 224, 224) tiles of the window pooled by s on a centred grid, and their (row, col)."""
    import numpy as np
    x = _pool(img, s)
    x = np.repeat(x[None], 3, axis=0) if x.ndim == 2 else x
    _, H, W = x.shape
    nr, nc = H // TILE, W // TILE
    r0, c0 = (H - nr * TILE) // 2, (W - nc * TILE) // 2
    t = [x[:, r0 + i * TILE: r0 + (i + 1) * TILE, c0 + j * TILE: c0 + (j + 1) * TILE]
         for i in range(nr) for j in range(nc)]
    return np.stack(t).astype(np.float32), np.array([(i, j) for i in range(nr) for j in range(nc)], np.int16)


def _global(img, patch):
    import numpy as np
    x = _pool(img, 8)
    x = np.repeat(x[None], 3, axis=0) if x.ndim == 2 else x
    h, w = GLOBAL_HW if patch != 14 else (154, 868)
    _, H, W = x.shape
    r0, c0 = (H - h) // 2, (W - w) // 2
    return x[None, :, r0:r0 + h, c0:c0 + w].astype(np.float32)


def _load(name):
    import timm
    import torch
    kind_vit = not BACKBONES[name].startswith(("convnext", "resnet"))
    kw = {"pretrained": True, "num_classes": 0}
    if kind_vit:
        kw["dynamic_img_size"] = True
    model = timm.create_model(BACKBONES[name], **kw).eval()
    cfg = timm.data.resolve_model_data_config(model)
    n = len(model.feature_info)
    mid = n // 2 if kind_vit else n - 2
    patch = getattr(getattr(model, "patch_embed", None), "patch_size", (16, 16))[0] if kind_vit else 32
    info = {"timm_id": BACKBONES[name], "vit": kind_vit, "mid_index": mid, "n_levels": n, "patch": int(patch),
            "mean": list(cfg["mean"]), "std": list(cfg["std"]), "global_pool": str(getattr(model, "global_pool", "")),
            "params_M": round(sum(p.numel() for p in model.parameters()) / 1e6, 1)}
    torch.set_grad_enabled(False)
    return model, info


def _embed(model, info, x):
    """(n, 3, h, w) float32 in [0, 1] -> {token: (n, D) float32}."""
    import numpy as np
    import torch
    mean = torch.tensor(info["mean"])[None, :, None, None]
    std = torch.tensor(info["std"])[None, :, None, None]
    acc = {}
    for i in range(0, len(x), BATCH):
        xb = (torch.from_numpy(np.ascontiguousarray(x[i:i + BATCH])) - mean) / std
        final, inter = model.forward_intermediates(xb, indices=[info["mid_index"]], intermediates_only=False)
        toks = {"pool": model.forward_head(final, pre_logits=True), "mid": inter[0].mean(dim=(2, 3))}
        if info["vit"]:
            toks["patch"] = final[:, model.num_prefix_tokens:].mean(dim=1)
            if getattr(model, "cls_token", None) is not None and info["global_pool"] != "token":
                toks["cls"] = final[:, 0]
        for k, v in toks.items():
            acc.setdefault(k, []).append(v.float().numpy())
    return {k: np.concatenate(v).astype(np.float32) for k, v in acc.items()}


def _npz_bytes(arrays):
    import numpy as np
    buf = io.BytesIO()
    np.savez_compressed(buf, **arrays)
    return buf.getvalue()


def _npz_load(data):
    import numpy as np
    with np.load(io.BytesIO(data), allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


# ----------------------------------------------------------------------------------------------------
# REMOTE functions
# ----------------------------------------------------------------------------------------------------
@app.function(volumes=VOLUMES, cpu=4.0, memory=16384, timeout=1800)
def prefetch(names: list) -> dict:
    """List every spot (train + test); download each backbone's weights into the Volume once."""
    import timm
    spots = []
    for b in sorted(p.name for p in (Path(VOL) / "data").glob("Batch_*")):
        spots += [[b, s] for s in sorted({p.stem.split("_")[1] for p in (Path(VOL) / "data" / b).glob("img_*.tif")})]
    if Path(TEST_DIR).exists():
        spots += [["Test", s] for s in sorted({p.stem.split("_")[1] for p in Path(TEST_DIR).glob("img_*.tif")})]
    done = {}
    for n in names:
        t0 = time.time()
        try:
            m = timm.create_model(BACKBONES[n], pretrained=True, num_classes=0)
            done[n] = f"ok {sum(p.numel() for p in m.parameters()) / 1e6:.0f}M params, {time.time() - t0:.0f} s"
            del m
        except Exception as e:   # noqa: BLE001  (a gated or missing model is reported, the others still run)
            done[n] = f"FAILED {type(e).__name__}: {str(e)[:300]}"
        volume.commit()
    return {"spots": spots, "models": done}


@app.function(volumes=VOLUMES, cpu=8.0, memory=16384, timeout=3600, max_containers=100, retries=1)
def embed_light(job: list) -> bytes:
    return _embed_spot(*job)


@app.function(volumes=VOLUMES, cpu=24.0, memory=32768, timeout=3600, max_containers=40, retries=1)
def embed_heavy(job: list) -> bytes:
    return _embed_spot(*job)


def _embed_spot(name, batch, sid):
    """One backbone x one spot -> npz bytes with the site embeddings (tile arrays go to the Volume)."""
    import numpy as np
    import torch
    os.environ["HF_HUB_OFFLINE"] = "1"                       # prefetch filled the cache; never download here
    torch.set_num_threads(os.cpu_count() or 8)
    t0 = time.time()
    model, info = _load(name)
    heavy = name in HEAVY
    modes = ("raw", "harm") if heavy else MODES
    chans = ("BSE", "Inlens", "rgb") if heavy else CHANS
    inp, H, W = _inputs(batch, sid, modes)
    t_in = time.time() - t0
    site, tiles = {}, {}
    n_fwd = 0
    for m in modes:
        for c in chans:
            img = inp[m][c]
            for s in SCALES:
                if s == 8:
                    x, rc = _global(img, info["patch"]), np.zeros((1, 2), np.int16)
                else:
                    x, rc = _tiles(img, s)
                emb = _embed(model, info, x)
                n_fwd += len(x)
                for tok, v in emb.items():
                    key = f"{m}|{c}|s{s}|{tok}"
                    site[f"{key}|mean"] = v.mean(axis=0)
                    if s in TILE_SCALES:
                        site[f"{key}|std"] = v.std(axis=0)
                        tiles[key] = v.astype(np.float16)
                if s in TILE_SCALES:
                    tiles[f"rowcol|s{s}"] = rc
    dt = time.time() - t0
    meta = {"backbone": name, "batch": batch, "sample_id": sid, "height": int(H), "width": int(W),
            "info": info, "n_forward": n_fwd, "input_s": round(t_in, 1), "total_s": round(dt, 1),
            "cpus": os.cpu_count()}
    out = Path(TILES_VOL) / name / f"{batch}__{sid}.npz"
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, **tiles, meta=np.array(json.dumps(meta)))
    volume.commit()
    print(f"{name} {batch}/{sid}: {n_fwd} forwards in {dt:.0f} s", flush=True)
    return _npz_bytes({**site, "meta": np.array(json.dumps(meta))})


# ----------------------------------------------------------------------------------------------------
# LOCAL entrypoint
# ----------------------------------------------------------------------------------------------------
def _merge(name, parts):
    """Per-spot npz bytes -> one npz: meta columns + site|<mode>|<chan>|s<k>|<token>|<mean|std> arrays (n, D)."""
    import numpy as np
    spots = [_npz_load(p) for p in parts]
    metas = [json.loads(str(s["meta"])) for s in spots]
    order = sorted(range(len(metas)), key=lambda i: (metas[i]["batch"] == "Test", metas[i]["batch"],
                                                     metas[i]["sample_id"]))
    spots, metas = [spots[i] for i in order], [metas[i] for i in order]
    keys = sorted(set.intersection(*[set(k for k in s if k != "meta") for s in spots]))
    arrays = {"batch": np.array([m["batch"] for m in metas]), "sample_id": np.array([m["sample_id"] for m in metas]),
              "height": np.array([m["height"] for m in metas], np.int32),
              "width": np.array([m["width"] for m in metas], np.int32),
              "info": np.array(json.dumps({"backbone": name, **metas[0]["info"],
                                           "seconds": [m["total_s"] for m in metas]}))}
    for k in keys:
        arrays[f"site|{k}"] = np.stack([s[k] for s in spots]).astype(np.float32)
    return arrays


@app.local_entrypoint()
def main(backbones: str = "dv2_s", spots: str = "", out_dir: str = ""):
    import numpy as np
    names = list(BACKBONES) if backbones == "all" else [b for b in re.split(r"[,\s]+", backbones) if b]
    bad = [n for n in names if n not in BACKBONES]
    if bad:
        raise SystemExit(f"unknown backbones {bad}; known: {list(BACKBONES)}")
    out = Path(out_dir) if out_dir else REPO / "processed" / "emb_sweep"
    out = out if out.is_absolute() else Path.cwd() / out
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    pre = prefetch.remote(names)
    print(json.dumps(pre["models"], indent=1))
    names = [n for n in names if pre["models"][n].startswith("ok")]
    todo = [s.split("/", 1) for s in re.split(r"[,\s]+", spots.strip()) if s] or pre["spots"]
    print(f"{len(todo)} spots x {len(names)} backbones")
    light = [[n, b, s] for n in names if n not in HEAVY for b, s in todo]
    heavy = [[n, b, s] for n in names if n in HEAVY for b, s in todo]
    calls = [(job, (embed_heavy if job[0] in HEAVY else embed_light).spawn(job)) for job in light + heavy]
    results = {}
    for job, call in calls:                                  # every job is already running; collect in order
        try:
            res = call.get()
        except Exception as e:   # noqa: BLE001
            print(f"FAILED {job}: {type(e).__name__}: {str(e)[:300]}")
            continue
        results.setdefault(job[0], []).append(res)
        if len(results[job[0]]) == len(todo):                # this backbone is complete: write it now
            arrays = _merge(job[0], results[job[0]])
            path = out / f"{job[0]}.npz"
            tmp = path.with_name(path.name + ".tmp.npz")
            np.savez(tmp, **arrays)
            tmp.replace(path)
            info = json.loads(str(arrays["info"]))
            print(f"wrote {path} ({len(arrays['batch'])} spots, {sum(k.startswith('site|') for k in arrays)} "
                  f"site arrays, median {np.median(info['seconds']):.0f} s/spot) at {time.time() - t0:.0f} s",
                  flush=True)
    for n in names:
        if len(results.get(n, [])) != len(todo):
            print(f"INCOMPLETE {n}: {len(results.get(n, []))}/{len(todo)} spots")
    print(f"total {time.time() - t0:.0f} s")
