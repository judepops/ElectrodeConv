"""Step 2b: train the encoder. Two losses, no batch labels anywhere:
    seg   cross-entropy of the per-pixel material map (pore / graphite / Si) from all three detectors
    con   NT-Xent between the BSE, Inlens and SE embeddings of the same tile (positives) vs other tiles (negatives)

    python cnn/v1/train.py --name run1                      # full: 5-fold split by spot, fold 0 held out, 60 epochs
    python cnn/v1/train.py --smoke --epochs 2               # laptop check: 6 spots, small crop
    python cnn/v1/train.py --name run1 --holdout session    # hold out whole sessions instead of spots
    python cnn/v1/train.py --name run1 --minutes 10         # fit the run into ~10 minutes
Progress: one line per epoch on stdout, and cnn/processed/<name>/progress.txt (epoch, ETA, latest metrics).
Writes cnn/processed/<name>/{config.json, train_log.csv, best.pt, last.pt}.
The held-out spots are used only for the sanity metrics (seg accuracy / mIoU, cross-detector retrieval); nothing
is tuned on them. The embedding never sees a batch label, so it can be scored leave-one-spot-out without retraining.
"""
from __future__ import annotations

import os as _os
_os.environ.setdefault("LOSSLARP_MASKS", "harmonise")   # the masks V1 was trained on; seg3 also works
import argparse
import csv
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

# Cap the Apple-GPU (MPS) memory before torch starts: on a Mac the GPU shares RAM with everything else, and an
# oversized batch otherwise eats all of it and freezes the machine. With the cap, too big a batch raises a clean
# "MPS backend out of memory" error instead. 0.4 = 40 % of the recommended GPU working set (~4 GB on a 16 GB M1 Pro).
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # repo root, so `cnn.*` / `preprocessing.*` imports work when run as a script
import torch.nn.functional as F
from torch.utils.data import DataLoader

from cnn.common import N_CLASSES, TILES_DIR, pick_device, run_dir, save_json, seed_all
from cnn.v1.data import AUGS, TileDataset, WindowDataset, collate, make_folds, smoke_subset, spots_of, tile_index
from cnn.v1.model import ARCHS, MaterialNet, contrastive_loss, seg_metrics


def class_weights(ds, n=64):
    """Inverse-frequency weights from a sample of training targets (pore and Si are minorities)."""
    counts = np.zeros(N_CLASSES)
    for i in np.linspace(0, len(ds) - 1, min(n, len(ds))).astype(int):
        _, y, _ = ds[i]
        counts += np.bincount(y.numpy().ravel(), minlength=N_CLASSES)
    w = counts.sum() / np.maximum(counts, 1) / N_CLASSES
    return torch.tensor(np.clip(w, 0.2, 5.0), dtype=torch.float32)


def run_epoch(net, loader, opt, device, w_seg, w_con, cw, train, scaler=None, temperature=0.1):
    net.train(train)
    tot = {"loss": 0.0, "seg": 0.0, "con": 0.0, "acc": 0.0, "miou": 0.0, "ret": 0.0, "n": 0}
    with torch.set_grad_enabled(train):
        for x, y, _ in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            if device.type == "cuda":
                x = x.contiguous(memory_format=torch.channels_last)
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                out = net(x)
                has_seg = "seg" in out                      # no decoder (w_seg 0): contrastive only
                l_seg = F.cross_entropy(out["seg"].float(), y, weight=cw) if has_seg else torch.zeros((), device=device)
                l_con, accs = contrastive_loss({k: v.float() for k, v in out["z"].items()}, temperature=temperature)
                loss = w_seg * l_seg + w_con * l_con
            if train:
                opt.zero_grad(set_to_none=True)
                if scaler:
                    scaler.scale(loss).backward()
                    scaler.unscale_(opt)
                    torch.nn.utils.clip_grad_norm_(net.parameters(), 2.0)
                    scaler.step(opt)
                    scaler.update()
                else:
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(net.parameters(), 2.0)
                    opt.step()
            acc, miou = seg_metrics(out["seg"].detach(), y) if has_seg else (0.0, 0.0)
            b = len(x)
            tot["loss"] += loss.item() * b
            tot["seg"] += l_seg.item() * b
            tot["con"] += l_con.item() * b
            tot["acc"] += acc * b
            tot["miou"] += miou * b
            tot["ret"] += float(np.mean(list(accs.values()))) * b
            tot["n"] += b
    n = max(tot.pop("n"), 1)
    return {k: v / n for k, v in tot.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="smoke")
    ap.add_argument("--arch", default="k7", help="encoder kernel setup, a key of model.ARCHS: " + ", ".join(ARCHS))
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--crop", type=int, default=128, help="training crop; 128 x batch 16 fits ~4 GB (laptop). On a big GPU use 448 x 32")
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--w-seg", type=float, default=1.0, help="material-map weight; 0 = no decoder at all (contrastive only)")
    ap.add_argument("--source", choices=["tiles", "windows"], default="tiles",
                    help="training crops from the fixed 512 px tiles, or from anywhere in each spot's full fair window (preprocessing/windows.py)")
    ap.add_argument("--tiles-dir", default=None, help="tile folder (default: the mask source's processed/); e.g. preprocessing/processed_seg3")
    ap.add_argument("--aug", choices=sorted(AUGS), default="base", help="augmentation set: base (hflip), flips (+vflip), rot (+90 deg rotations)")
    ap.add_argument("--fold-seed", type=int, default=0, help="seed of the spot split (kept fixed across versions; --seed changes init and augmentation only)")
    ap.add_argument("--w-con", type=float, default=0.2,
                    help="contrastive weight. 0.2: with the BatchNorm head, weight 1.0 learns tile identity and the spot "
                         "embedding loses batch information (losess 0.51 vs 0.58 at 0.2); 0 (segmentation only) is at chance")
    ap.add_argument("--temperature", type=float, default=0.1)
    ap.add_argument("--holdout", choices=["sample_id", "session"], default="sample_id")
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--n-folds", type=int, default=5)
    ap.add_argument("--smoke", action="store_true", help="6 spots, batch 8, crop 256")
    ap.add_argument("--preload", action="store_true", help="hold every tile in RAM (~4 GB float32)")
    ap.add_argument("--workers", type=int, default=0, help="DataLoader worker processes (0 on macOS: workers deadlocked)")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--minutes", type=float, default=0,
                    help="time budget: after epoch 1 the epoch count is cut to fit (the LR schedule follows)")
    a = ap.parse_args()
    seed_all(a.seed)
    device = pick_device(a.device)
    idx = tile_index()
    if a.smoke:
        idx = smoke_subset(idx)
        a.batch, a.crop = min(a.batch, 8), min(a.crop, 256)
        a.name = a.name if a.name != "smoke" else "smoke"
    tiles_dir = Path(a.tiles_dir) if a.tiles_dir else TILES_DIR
    train_ids, val_ids = make_folds(idx, by=a.holdout, n_folds=a.n_folds, seed=a.fold_seed)[a.fold]
    if a.source == "windows":
        ds_tr = WindowDataset(spots_of(idx[idx.sample_id.isin(train_ids)]), crop=a.crop, seed=a.seed, aug=a.aug)
    else:
        ds_tr = TileDataset(idx[idx.sample_id.isin(train_ids)], augment=True, crop=a.crop, preload=a.preload, seed=a.seed,
                            aug=a.aug, tiles_dir=tiles_dir)
    ds_va = TileDataset(idx[idx.sample_id.isin(val_ids)], augment=False, crop=a.crop, preload=a.preload, tiles_dir=tiles_dir)
    pin = device.type == "cuda"
    dl_tr = DataLoader(ds_tr, a.batch, shuffle=True, drop_last=True, num_workers=a.workers, collate_fn=collate, pin_memory=pin)
    dl_va = DataLoader(ds_va, a.batch, shuffle=False, num_workers=a.workers, collate_fn=collate, pin_memory=pin)
    net = MaterialNet(a.arch, with_decoder=a.w_seg > 0).to(device)
    if device.type == "cuda":
        net = net.to(memory_format=torch.channels_last)
    cw = class_weights(ds_tr).to(device) if a.w_seg > 0 else None
    enc = [p for n, p in net.named_parameters() if n.startswith("encoder.")]
    rest = [p for n, p in net.named_parameters() if not n.startswith("encoder.")]
    enc_lr = a.lr * (0.1 if net.pretrained else 1.0)       # pretrained backbones: fine-tune gently
    opt = torch.optim.AdamW([{"params": enc, "lr": enc_lr}, {"params": rest, "lr": a.lr}], weight_decay=1e-4)
    plan = {"steps": a.epochs * len(dl_tr)}          # mutable, so a time budget can shorten the cosine schedule
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: 0.5 * (1 + math.cos(math.pi * min(s, plan["steps"]) / max(plan["steps"], 1))))
    scaler = None                                    # bfloat16 autocast on CUDA needs no loss scaling
    out = run_dir(a.name)
    cfg = {**vars(a), "device": str(device), "n_train_tiles": len(ds_tr), "n_val_tiles": len(ds_va),
           "train_spots": train_ids, "val_spots": val_ids, "class_weights": cw.tolist() if cw is not None else None,
           "with_decoder": a.w_seg > 0, "tiles_dir": str(tiles_dir),
           "params_M": sum(p.numel() for p in net.parameters()) / 1e6, "arch_resolved": net.arch}
    save_json(out / "config.json", cfg)
    print(f"{device} | arch {a.arch} {net.arch} | {cfg['params_M']:.2f} M params | train {len(ds_tr)} tiles / {len(train_ids)} spots | "
          f"val {len(ds_va)} tiles / {len(val_ids)} spots | {len(dl_tr)} steps/epoch", flush=True)
    log = open(out / "train_log.csv", "w", newline="")
    wr = csv.writer(log)
    wr.writerow(["epoch", "split", "loss", "seg", "con", "acc", "miou", "ret", "lr", "s"])
    best = -1.0
    progress = out / "progress.txt"
    t_start = time.time()
    n_epochs = a.epochs
    ep = 0
    while ep < n_epochs:
        ep += 1
        t0 = time.time()
        tr = run_epoch(net, dl_tr, opt, device, a.w_seg, a.w_con, cw, True, scaler, a.temperature)
        for _ in range(len(dl_tr)):
            sched.step()
        va = run_epoch(net, dl_va, opt, device, a.w_seg, a.w_con, cw, False, None, a.temperature)
        dt = time.time() - t0
        if a.minutes and ep == 1:                     # fit the run into the time budget, measured on epoch 1
            n_epochs = max(2, min(a.epochs, int(a.minutes * 60 // max(dt, 1))))
            plan["steps"] = n_epochs * len(dl_tr)
            print(f"time budget {a.minutes:.0f} min at {dt:.0f} s/epoch -> {n_epochs} epochs", flush=True)
        elapsed = time.time() - t_start
        eta = (n_epochs - ep) * elapsed / ep
        progress.write_text(f"epoch {ep}/{n_epochs}  elapsed {elapsed / 60:.1f} min  ETA {eta / 60:.1f} min\n"
                            f"train: loss {tr['loss']:.3f}  seg acc {tr['acc']:.3f}  retrieval {tr['ret']:.2f}\n"
                            f"val:   loss {va['loss']:.3f}  seg acc {va['acc']:.3f}  mIoU {va['miou']:.3f}  retrieval {va['ret']:.2f}"
                            f"  (retrieval chance = 1/{a.batch} = {1 / a.batch:.2f})\n")
        for split, m in (("train", tr), ("val", va)):
            wr.writerow([ep, split] + [f"{m[k]:.4f}" for k in ("loss", "seg", "con", "acc", "miou", "ret")] + [f"{opt.param_groups[0]['lr']:.2e}", f"{dt:.0f}"])
        log.flush()
        print(f"ep {ep:3d}/{n_epochs} | train loss {tr['loss']:.3f} (seg {tr['seg']:.3f} con {tr['con']:.3f}) acc {tr['acc']:.3f} ret {tr['ret']:.2f} | "
              f"val loss {va['loss']:.3f} acc {va['acc']:.3f} mIoU {va['miou']:.3f} ret {va['ret']:.2f} | {dt:.0f} s, ETA {eta / 60:.1f} min", flush=True)
        score = va["miou"] + va["ret"]                   # label-free; with no decoder mIoU is 0 and this is retrieval alone
        torch.save({"model": net.state_dict(), "config": cfg, "epoch": ep, "val": va}, out / "last.pt")
        if score > best:
            best = score
            torch.save({"model": net.state_dict(), "config": cfg, "epoch": ep, "val": va}, out / "best.pt")
    log.close()
    print(f"done: best val mIoU+retrieval {best:.3f}; checkpoints in {out}")


if __name__ == "__main__":
    main()
