"""V1 and V2 trained together as one network (compare with V1 + V2 trained apart and joined at the classifier).

    python cnn/joint.py --name j_a --fold 0                  # one fold (0..4 by spot; -1 = all spots)
    python cnn/joint.py --name j_b --fold 0 --detach-a       # same, but the V1 branch never receives a label gradient

Two branches on the same tiles in every step:
  A  the V1 design: one encoder per detector image (shared weights, per-detector 1x1 gain), material-map decoder,
     cross-detector contrastive loss (the BSE, Inlens and SE views of a tile are matched). No labels.
  B  the V2 design: the three images as one 3-channel input (FusionNet), supervised contrastive on the batch label
     (positives = other spots of the same batch) + a batch classifier head.
A shared classifier on the spot means of [A | B] adds a batch cross-entropy. Its gradient reaches both branches
(j_a) or only branch B (--detach-a, j_b: A stays label-free while trained at the same time).
Writes the supcon.py layout (cnn/processed/supcon/<name>/foldNN/{embeddings.npz, last.pt, ...}) with site_feat =
[A | B], so `supcon.py score` and `compare.py` read it unchanged.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("LOSSLARP_MASKS", "harmonise")
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn.common import DETECTORS, N_CLASSES, pick_device, save_json, seed_all  # noqa: E402
from cnn.data import TileDataset, collate, make_folds, smoke_subset, tile_index  # noqa: E402
from cnn.supcon import N_FOLDS, SDIR, FusionNet, batches_of, supcon_loss  # noqa: E402
from cnn.v1net import V1Net  # noqa: E402


def nt_xent(za, zb, temperature=0.1):
    logits = za @ zb.t() / temperature
    t = torch.arange(len(za), device=za.device)
    return 0.5 * (F.cross_entropy(logits, t) + F.cross_entropy(logits.t(), t))


class JointNet(nn.Module):
    def __init__(self, arch="k7"):
        super().__init__()
        self.a = V1Net(arch, with_decoder=True)
        self.b = FusionNet(arch, with_decoder=False)
        dim = self.a.feat_dim * len(DETECTORS) + self.b.feat_dim
        self.head = nn.Sequential(nn.BatchNorm1d(dim), nn.Linear(dim, N_CLASSES))

    def forward_a(self, x, seg=True):
        skips = {d: self.a.encoder(self.a.adapters[d](x[:, i:i + 1])) for i, d in enumerate(DETECTORS)}
        feat = {d: self.a.encoder.pooled(skips[d][-1]) for d in DETECTORS}
        z = {d: F.normalize(self.a.proj(feat[d]), dim=1) for d in DETECTORS}
        out = {"feat": torch.cat([feat[d] for d in DETECTORS], 1), "z": z}
        if seg:
            fused = [torch.cat([skips[d][i] for d in DETECTORS], 1) for i in range(len(skips[DETECTORS[0]]))]
            out["seg"] = self.a.decoder(fused)
        return out

    def forward(self, x, seg=True):
        oa, ob = self.forward_a(x, seg), self.b(x, seg=False)
        return {"a": oa, "b": ob, "feat": torch.cat([oa["feat"], ob["feat"]], 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="j_a")
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--detach-a", action="store_true", help="the shared classifier's gradient does not reach the V1 branch")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--crop", type=int, default=320)
    ap.add_argument("--batch-spots", type=int, default=4)
    ap.add_argument("--tiles-per-spot", type=int, default=2)
    ap.add_argument("--w-xdet", type=float, default=0.2, help="cross-detector contrastive weight in branch A (V1 used 0.2)")
    ap.add_argument("--w-head", type=float, default=1.0)
    ap.add_argument("--init-a", default="", help="start branch A from the trained V1 checkpoint (cnn/processed/v_k7_con02/best.pt)")
    ap.add_argument("--init-b", default="", help="start branch B from a trained V2 run: supcon/<run>/foldNN/last.pt of the same fold (full for -1)")
    ap.add_argument("--preload", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()
    seed_all(a.seed)
    device = pick_device(a.device)
    idx = tile_index()
    if a.smoke:
        idx, a.epochs, a.batch_spots = smoke_subset(idx), min(a.epochs, 2), 2
    train_ids, val_ids = (make_folds(idx, by="sample_id", n_folds=N_FOLDS, seed=0)[a.fold] if a.fold >= 0
                          else (sorted(set(idx.sample_id)), []))
    tr_idx = idx[idx.sample_id.isin(train_ids)].reset_index(drop=True)
    ds = TileDataset(tr_idx, augment=True, crop=a.crop, preload=a.preload, seed=a.seed)
    ylab = {b: i for i, b in enumerate(sorted(idx.batch.unique()))}
    spotlab = {s: i for i, s in enumerate(sorted(idx.sample_id.unique()))}
    net = JointNet()
    if a.init_a:
        net.a.load_state_dict(torch.load(a.init_a, map_location="cpu", weights_only=False)["model"])
    if a.init_b:
        sd = torch.load(SDIR / a.init_b / (f"fold{a.fold:02d}" if a.fold >= 0 else "full") / "last.pt", map_location="cpu", weights_only=False)["model"]
        sd = {k: v for k, v in sd.items() if not k.startswith("decoder.")}   # branch B has no material-map head here
        missing, unexpected = net.b.load_state_dict(sd, strict=False)
        assert not unexpected and all(k.startswith(("adv.", "decoder.")) for k in missing), (missing, unexpected)
    net = net.to(device)
    if device.type == "cuda":
        net = net.to(memory_format=torch.channels_last)
    lr_scale = 0.1 if (a.init_a or a.init_b) else 1.0                   # started from trained weights: refine gently
    opt = torch.optim.AdamW([{"params": net.a.parameters(), "lr": 3e-4 * lr_scale},
                             {"params": net.b.parameters(), "lr": 1e-3 * lr_scale},
                             {"params": net.head.parameters(), "lr": 1e-3}], weight_decay=1e-4)
    rng = np.random.default_rng(a.seed)
    steps = len(batches_of(tr_idx, a.batch_spots, a.tiles_per_spot, rng))
    total = a.epochs * steps
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 0.5 * (1 + math.cos(math.pi * min(s, total) / max(total, 1))))
    out = SDIR / a.name / (f"fold{a.fold:02d}" if a.fold >= 0 else "full")
    out.mkdir(parents=True, exist_ok=True)
    cfg = {**vars(a), "device": str(device), "train_spots": train_ids, "heldout_spots": val_ids, "model": "joint V1 + V2",
           "params_M": sum(p.numel() for p in net.parameters()) / 1e6}
    save_json(out / "config.json", cfg)
    print(f"{device} | {a.name} fold {a.fold} | {'A detached from the head' if a.detach_a else 'head trains both branches'} | "
          f"train {len(tr_idx)} tiles / {len(train_ids)} spots | {steps} steps/epoch | {cfg['params_M']:.1f} M params", flush=True)
    log = csv.writer(open(out / "train_log.csv", "w", newline=""))
    log.writerow(["epoch", "loss", "seg", "xdet", "sup", "ce_b", "head", "head_acc", "s"])
    cw, t_start = None, time.time()
    for ep in range(1, a.epochs + 1):
        t0, tot, n = time.time(), np.zeros(7), 0
        net.train()
        for ids in batches_of(tr_idx, a.batch_spots, a.tiles_per_spot, rng):
            x, ymap, info = collate([ds[i] for i in ids])
            x, ymap = x.to(device, non_blocking=True), ymap.to(device, non_blocking=True)
            y = torch.tensor([ylab[i["batch"]] for i in info], device=device)
            sp = torch.tensor([spotlab[i["sample_id"]] for i in info], device=device)
            if device.type == "cuda":
                x = x.contiguous(memory_format=torch.channels_last)
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                o = net(x)
                if cw is None:
                    counts = torch.bincount(ymap.flatten(), minlength=N_CLASSES).float()
                    cw = (counts.sum() / torch.clamp(counts, min=1) / N_CLASSES).clamp(0.2, 5.0)
                l_seg = F.cross_entropy(o["a"]["seg"].float(), ymap, weight=cw)
                za = {k: v.float() for k, v in o["a"]["z"].items()}
                l_xdet = torch.stack([nt_xent(za[p], za[q]) for p, q in (("bse", "inlens"), ("bse", "se"), ("inlens", "se"))]).mean()
                l_sup, _ = supcon_loss(o["b"]["z"].float(), y, sp, 0.1)
                l_ceb = F.cross_entropy(o["b"]["logits"].float(), y)
                fa = o["a"]["feat"].float().detach() if a.detach_a else o["a"]["feat"].float()
                feat = torch.cat([fa, o["b"]["feat"].float()], 1)
                us = torch.unique(sp)
                fs = torch.stack([feat[sp == u].mean(0) for u in us])
                ys = torch.stack([y[sp == u][0] for u in us])
                lg = net.head(fs)
                l_head = F.cross_entropy(lg, ys)
                loss = l_seg + a.w_xdet * l_xdet + l_sup + l_ceb + a.w_head * l_head
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 2.0)
            opt.step()
            sched.step()
            tot += np.array([loss.item(), l_seg.item(), l_xdet.item(), l_sup.item(), l_ceb.item(), l_head.item(),
                             (lg.argmax(1) == ys).float().mean().item()])
            n += 1
        m = tot / max(n, 1)
        dt = time.time() - t0
        log.writerow([ep] + [f"{v:.4f}" for v in m] + [f"{dt:.0f}"])
        eta = (a.epochs - ep) * (time.time() - t_start) / ep
        (out / "progress.txt").write_text(f"epoch {ep}/{a.epochs}  ETA {eta / 60:.1f} min  seg {m[1]:.3f} xdet {m[2]:.3f} sup {m[3]:.3f} head acc {m[6]:.2f}\n")
        print(f"ep {ep:3d}/{a.epochs} | loss {m[0]:.3f} seg {m[1]:.3f} xdet {m[2]:.3f} sup {m[3]:.3f} ce_b {m[4]:.3f} head {m[5]:.3f} "
              f"acc {m[6]:.2f} | {dt:.0f} s, ETA {eta / 60:.1f} min", flush=True)
    torch.save({"model": net.state_dict(), "config": cfg, "epoch": a.epochs}, out / "last.pt")
    net.eval()
    ds_all = TileDataset(idx, augment=False)
    feats, infos = [], []
    with torch.no_grad():
        for i in range(0, len(ds_all), 8):
            x, _, info = collate([ds_all[j] for j in range(i, min(i + 8, len(ds_all)))])
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                feats.append(net(x.to(device), seg=False)["feat"].float().cpu().numpy())
            infos += info
    feat = np.concatenate(feats)
    tb, ts = np.array([i["batch"] for i in infos]), np.array([i["sample_id"] for i in infos])
    tsess = np.array([i["session"] for i in infos], np.int32)
    spots = sorted(set(zip(tb, ts)))
    np.savez(out / "embeddings.npz", tile_feat=feat, tile_batch=tb, tile_sample_id=ts, tile_session=tsess,
             tile_row=np.array([i["row"] for i in infos], np.int16), tile_col=np.array([i["col"] for i in infos], np.int16),
             site_feat=np.stack([feat[(tb == b) & (ts == s)].mean(0) for b, s in spots]), batch=np.array([b for b, _ in spots]),
             sample_id=np.array([s for _, s in spots]), session=np.array([tsess[(tb == b) & (ts == s)][0] for b, s in spots], np.int32),
             heldout=np.array(val_ids), dims_a=np.array(net.a.feat_dim * len(DETECTORS)))
    print(f"done in {(time.time() - t_start) / 60:.1f} min: {out}", flush=True)


if __name__ == "__main__":
    main()
