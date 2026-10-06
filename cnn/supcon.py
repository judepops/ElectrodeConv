"""V2: a batch-supervised embedding with early detector fusion.

    python cnn/supcon.py train --name v2 --fold 0          # hold out session 0 of 13; -> processed/supcon/v2/fold00/{last.pt, embeddings.npz}
    python cnn/supcon.py train --name v2 --fold -1         # the full model on all 31 spots (test spots, difference analysis)
    python cnn/supcon.py run --name v2 --gpu 0             # all 13 folds + the full model, 3 at a time on one GPU
    python cnn/supcon.py score --name v2                   # -> processed/supcon/v2/score.json (nested leave-one-session-out)

The three detector images of a tile go in together as one 3-channel image (early fusion). The loss is supervised
contrastive (Khosla et al. 2020) on the BATCH label: tiles of the same batch are pulled together, tiles of other
batches pushed apart. Positives are tiles of the same batch from a DIFFERENT spot (same-spot pairs are excluded,
otherwise the network only learns spot identity). Mini-batches hold several spots of every batch so positives exist. A plain cross-entropy head on the batch label
(w_ce) is added: on its own the contrastive term sat at chance (ln 23) for 8 epochs in every fold.
An optional light material-map term (w_seg, default 0.2) keeps the encoder on the structure.

Because the encoder sees batch labels, the honest score trains the encoder 13 times, each with one whole imaging
session hidden, and scores only the hidden session's spots (a logistic regression fitted on that fold's training-spot
embeddings). `score` assembles those out-of-fold calls: balanced accuracy, session-bootstrap interval, per-class
recall. No permutation p: that would need 5 x 200 retrainings. The full model gives the test-spot calls.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from cnn.common import DETECTORS, N_CLASSES, RUNS_DIR, pick_device, save_json, seed_all  # noqa: E402
from cnn.data import TileDataset, collate, make_folds, smoke_subset, tile_index  # noqa: E402
from cnn.model import Decoder, Encoder, resolve_arch, seg_metrics  # noqa: E402

SDIR = RUNS_DIR / "supcon"
N_FOLDS = 5                      # folds by spot (all spots are treated as one imaging sitting)


class GradReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x):
        return x.view_as(x)

    @staticmethod
    def backward(ctx, g):
        return -g


class FusionNet(nn.Module):
    """3-channel [bse, inlens, se] -> pooled embedding (mean + std of the projected bottleneck), contrastive z,
    optional material-map logits."""

    def __init__(self, arch="k7", proj_dim=128, with_decoder=True):
        super().__init__()
        self.arch = resolve_arch(arch)
        widths = self.arch["widths"]
        self.encoder = Encoder(widths, self.arch["k"], self.arch["stem"], self.arch["dil"], in_ch=len(DETECTORS))
        self.encoder.pool_proj = nn.Identity()
        self.decoder = Decoder(widths, 1, N_CLASSES) if with_decoder else None
        self.feat_dim = 2 * widths[-1]
        self.proj = nn.Sequential(nn.BatchNorm1d(self.feat_dim), nn.Linear(self.feat_dim, widths[-1]), nn.GELU(), nn.Linear(widths[-1], proj_dim))
        # batch logits: the plain supervised signal on the embedding. BatchNorm first: at init every tile's pooled vector
        # shares one big common direction, and without it both this head and the contrastive one sat at chance.
        self.cls = nn.Sequential(nn.BatchNorm1d(self.feat_dim), nn.Linear(self.feat_dim, N_CLASSES))
        self.adv = nn.Sequential(nn.BatchNorm1d(self.feat_dim), nn.Linear(self.feat_dim, 16))   # session head behind a gradient reversal (w_adv)

    def forward(self, x, seg=True):
        # The embedding is pooled from the last convolution BEFORE its GroupNorm: after the norm the spatial mean of
        # every channel is the same for every tile (spread 1e-5 measured), so nothing pooled from it can tell
        # tiles apart, let alone batches. encoder.pool_proj is an identity here so attribute.py can hook the map.
        skips, h = [], x
        for i, stage in enumerate(self.encoder.stages):
            h = stage[0](h)
            block = stage[1]
            if i == len(self.encoder.stages) - 1:
                pre = block[3](block[2](block[1](block[0](h))))
                h = block[5](block[4](pre))
            else:
                h = block(h)
            skips.append(h)
        p = self.encoder.pool_proj(pre)
        feat = torch.cat([p.mean(dim=(2, 3)), p.std(dim=(2, 3))], 1)
        out = {"feat": feat, "z": F.normalize(self.proj(feat), dim=1), "logits": self.cls(feat)}
        if seg and self.decoder is not None:
            out["seg"] = self.decoder(skips)
        return out


def load_pretrained_encoder(net, path):
    """Start from the old label-free MaterialNet encoder (same k7 stages). Its first conv saw one detector at a time
    (1 input channel): spread it over the 3 fused channels (/3). pool_proj and the decoder are not copied."""
    sd = torch.load(path, map_location="cpu", weights_only=False)["model"]
    own = net.encoder.state_dict()
    n = 0
    for k, v in sd.items():
        if not k.startswith("encoder.") or "pool_proj" in k:
            continue
        kk = k[len("encoder."):]
        if kk in own:
            if own[kk].shape != v.shape and v.dim() == 4 and v.shape[1] == 1:
                v = v.repeat(1, own[kk].shape[1], 1, 1) / own[kk].shape[1]
            if own[kk].shape == v.shape:
                own[kk] = v
                n += 1
    net.encoder.load_state_dict(own)
    return n


def supcon_loss(z, y, spot, temperature=0.1, hard_pair=None, hard_weight=1.0):
    """Supervised contrastive loss: positives = same batch, different spot. hard_pair=(a, b): negatives between
    classes a and b count hard_weight times in the denominator (more push on the confusable pair).
    -> (loss, fraction of anchors with a positive)."""
    sim = z @ z.t() / temperature
    n = len(z)
    eye = torch.eye(n, dtype=torch.bool, device=z.device)
    pos = (y[:, None] == y[None, :]) & (spot[:, None] != spot[None, :]) & ~eye
    logits = sim.masked_fill(eye, -1e9)
    if hard_pair is not None and hard_weight != 1.0:
        a_, b_ = hard_pair
        hard = ((y[:, None] == a_) & (y[None, :] == b_)) | ((y[:, None] == b_) & (y[None, :] == a_))
        logits = logits + hard.float() * float(np.log(hard_weight))       # weight w on exp(sim) = + log w on the logit
    log_prob = logits - torch.logsumexp(logits, dim=1, keepdim=True)
    n_pos = pos.sum(1)
    ok = n_pos > 0
    loss = -(log_prob * pos).sum(1)[ok] / n_pos[ok]       # hard weights only touch cross-class pairs, never positives
    return loss.mean() if ok.any() else z.sum() * 0, float(ok.float().mean())


def batches_of(idx, spots_per_batch, tiles_per_spot, rng):
    """One epoch of mini-batch index lists: every mini-batch holds `spots_per_batch` spots of each batch class,
    `tiles_per_spot` random tiles each, so same-batch / different-spot positives always exist."""
    by_spot = {s: g.index.to_numpy() for s, g in idx.groupby("sample_id")}
    by_batch = {b: sorted(set(g.sample_id)) for b, g in idx.groupby("batch")}
    n_steps = max(1, len(idx) // (spots_per_batch * tiles_per_spot * len(by_batch)))
    out = []
    for _ in range(n_steps):
        ids = []
        for b, spots in by_batch.items():
            pick = rng.choice(spots, min(spots_per_batch, len(spots)), replace=len(spots) < spots_per_batch)
            for s in pick:
                ids += list(rng.choice(by_spot[s], tiles_per_spot, replace=len(by_spot[s]) < tiles_per_spot))
        out.append(ids)
    return out


def embed_all(net, device, idx, batch=16, tiles_dir=None, tta=False):
    """Embeddings of every tile in idx (full 512 px, no augmentation) -> (tile_feat, DataFrame of tile info)."""
    from torch.utils.data import DataLoader
    ds = TileDataset(idx, augment=False, tiles_dir=tiles_dir)
    dl = DataLoader(ds, batch, shuffle=False, collate_fn=collate)
    feats, infos = [], []
    net.eval()
    with torch.no_grad():
        for x, _, info in dl:
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                xd = x.to(device)
                f = net(xd, seg=False)["feat"].float()
                if tta:
                    f = 0.5 * (f + net(torch.flip(xd, dims=[3]), seg=False)["feat"].float())
            feats.append(f.cpu().numpy())
            infos += info
    return np.concatenate(feats), infos


def cmd_train(a):
    seed_all(a.seed)
    device = pick_device(a.device)
    idx = tile_index()
    if a.smoke:
        idx = smoke_subset(idx)
        a.batch_spots, a.epochs = min(a.batch_spots, 2), min(a.epochs, 2)
    if a.fold >= 0:
        train_ids, val_ids = make_folds(idx, by="sample_id", n_folds=N_FOLDS, seed=0)[a.fold]
    else:
        train_ids, val_ids = sorted(set(idx.sample_id)), []
    excluded = [x for x in a.exclude.split(",") if x]
    train_ids = [t for t in train_ids if t not in excluded]        # never trained on; folds unchanged, still embedded and called
    tr_idx = idx[idx.sample_id.isin(train_ids)].reset_index(drop=True)
    ds = TileDataset(tr_idx, augment=True, crop=a.crop, preload=a.preload, seed=a.seed, aug=a.aug)
    ylab = {b: i for i, b in enumerate(sorted(idx.batch.unique()))}
    spotlab = {s: i for i, s in enumerate(sorted(idx.sample_id.unique()))}
    net = FusionNet(a.arch, with_decoder=a.w_seg > 0)
    if a.init:
        n_loaded = load_pretrained_encoder(net, a.init)
        print(f"initialised {n_loaded} encoder tensors from {a.init} (encoder lr x0.1)", flush=True)
    net = net.to(device)
    if device.type == "cuda":
        net = net.to(memory_format=torch.channels_last)
    enc = [p_ for n_, p_ in net.named_parameters() if n_.startswith("encoder.")]
    rest = [p_ for n_, p_ in net.named_parameters() if not n_.startswith("encoder.")]
    opt = torch.optim.AdamW([{"params": enc, "lr": a.lr * (0.1 if a.init else 1.0)}, {"params": rest, "lr": a.lr}], weight_decay=1e-4)
    sesslab = {s_: i for i, s_ in enumerate(sorted(idx.session.unique()))}
    rng = np.random.default_rng(a.seed)
    steps_per_epoch = len(batches_of(tr_idx, a.batch_spots, a.tiles_per_spot, rng))
    total = a.epochs * steps_per_epoch
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 0.5 * (1 + math.cos(math.pi * min(s, total) / max(total, 1))))
    out = SDIR / a.name / (f"fold{a.fold:02d}" if a.fold >= 0 else "full")
    out.mkdir(parents=True, exist_ok=True)
    held_sessions = sorted(set(idx[idx.sample_id.isin(val_ids)].session))
    cfg = {**vars(a), "device": str(device), "train_spots": train_ids, "heldout_spots": val_ids, "heldout_sessions": held_sessions,
           "params_M": sum(p.numel() for p in net.parameters()) / 1e6, "fusion": "early", "loss": "supcon(batch; positives = other spots of the same batch)"}
    save_json(out / "config.json", cfg)
    print(f"{device} | {a.name} fold {a.fold} | train {len(tr_idx)} tiles / {len(train_ids)} spots | held out {val_ids} (sessions {held_sessions}) | "
          f"{steps_per_epoch} steps/epoch of {a.batch_spots * a.tiles_per_spot * len(ylab)} tiles", flush=True)
    log = open(out / "train_log.csv", "w", newline="")
    wr = csv.writer(log)
    wr.writerow(["epoch", "loss", "con", "ce", "batch_acc", "seg", "pos_frac", "acc", "s"])
    cw = None
    t_start = time.time()
    for ep in range(1, a.epochs + 1):
        t0 = time.time()
        net.train()
        tot = {"loss": 0.0, "con": 0.0, "ce": 0.0, "seg": 0.0, "pos": 0.0, "acc": 0.0, "bacc": 0.0, "n": 0}
        for ids in batches_of(tr_idx, a.batch_spots, a.tiles_per_spot, rng):
            x, ymap, info = collate([ds[i] for i in ids])
            x, ymap = x.to(device, non_blocking=True), ymap.to(device, non_blocking=True)
            y = torch.tensor([ylab[i["batch"]] for i in info], device=device)
            sp = torch.tensor([spotlab[i["sample_id"]] for i in info], device=device)
            if device.type == "cuda":
                x = x.contiguous(memory_format=torch.channels_last)
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
                o = net(x)
                zz = o["z"].float()
                if a.center:                         # remove the direction every tile shares, compare only differences
                    zz = F.normalize(zz - zz.mean(0, keepdim=True), dim=1)
                pa, pb = (f"Batch_{c}" for c in a.hard_pair.split(","))
                hp = (ylab[pa], ylab[pb]) if pa in ylab and pb in ylab else None
                if a.level == "spot":               # contrast and classify spots, not tiles: average inside the mini-batch
                    us = torch.unique(sp)
                    zs = F.normalize(torch.stack([zz[sp == u].mean(0) for u in us]), dim=1)
                    ys = torch.stack([y[sp == u][0] for u in us])
                    l_con, pos_frac = supcon_loss(zs, ys, us, a.temperature, hp, a.hard_weight)
                    fs, y_ce = torch.stack([o["feat"].float()[sp == u].mean(0) for u in us]), ys
                else:
                    l_con, pos_frac = supcon_loss(zz, y, sp, a.temperature, hp, a.hard_weight)
                    fs, y_ce = o["feat"].float(), y
                if a.margin > 0:                     # cosine classifier with an additive margin on the true class
                    h = F.normalize(net.cls[0](fs), dim=1)
                    cos = h @ F.normalize(net.cls[1].weight, dim=1).t()
                    logits = 16.0 * (cos - a.margin * F.one_hot(y_ce, cos.shape[1]).float())
                else:
                    logits = net.cls(fs)
                l_adv = torch.zeros((), device=device)
                if a.w_adv > 0:                      # the session must NOT be readable from the embedding
                    ysess = torch.tensor([sesslab[i["session"]] for i in info], device=device)
                    l_adv = F.cross_entropy(net.adv(GradReverse.apply(o["feat"].float())), ysess)
                if "seg" in o:
                    if cw is None:
                        counts = torch.bincount(ymap.flatten(), minlength=N_CLASSES).float()
                        cw = (counts.sum() / torch.clamp(counts, min=1) / N_CLASSES).clamp(0.2, 5.0)
                    l_seg = F.cross_entropy(o["seg"].float(), ymap, weight=cw)
                    acc, _ = seg_metrics(o["seg"].detach(), ymap)
                else:
                    l_seg, acc = torch.zeros((), device=device), 0.0
                l_ce = F.cross_entropy(logits, y_ce)
                loss = l_con + a.w_ce * l_ce + a.w_seg * l_seg + a.w_adv * l_adv
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(), 2.0)
            opt.step()
            sched.step()
            b = len(x)
            for k, v in (("loss", loss.item()), ("con", l_con.item()), ("ce", l_ce.item()), ("seg", float(l_seg)), ("pos", pos_frac), ("acc", acc),
                         ("bacc", (logits.argmax(1) == y_ce).float().mean().item())):
                tot[k] += v * b
            tot["n"] += b
        n = max(tot["n"], 1)
        dt = time.time() - t0
        wr.writerow([ep] + [f"{tot[k] / n:.4f}" for k in ("loss", "con", "ce", "bacc", "seg", "pos", "acc")] + [f"{dt:.0f}"])
        log.flush()
        eta = (a.epochs - ep) * (time.time() - t_start) / ep
        (out / "progress.txt").write_text(f"epoch {ep}/{a.epochs}  ETA {eta / 60:.1f} min  con {tot['con'] / n:.3f} ce {tot['ce'] / n:.3f} train batch acc {tot['bacc'] / n:.2f}\n")
        print(f"ep {ep:3d}/{a.epochs} | loss {tot['loss'] / n:.3f} con {tot['con'] / n:.3f} ce {tot['ce'] / n:.3f} batch acc {tot['bacc'] / n:.2f} seg {tot['seg'] / n:.3f} | {dt:.0f} s, ETA {eta / 60:.1f} min", flush=True)
    log.close()
    torch.save({"model": net.state_dict(), "config": cfg, "epoch": a.epochs}, out / "last.pt")
    # embeddings of every training spot and every held-out spot (and the test tiles for the full model)
    feat, infos = embed_all(net, device, idx, a.embed_batch, tta=a.tta)
    tb, ts = np.array([i["batch"] for i in infos]), np.array([i["sample_id"] for i in infos])
    tsess = np.array([i["session"] for i in infos], np.int32)
    spots = sorted(set(zip(tb, ts)))
    site = np.stack([feat[(tb == b) & (ts == s)].mean(0) for b, s in spots])
    extra = {}
    if a.fold < 0:
        from qc.features_table import TEST_IDS, TEST_TILES_DIR
        from preprocessing.preprocess import load_tiles
        from cnn.predict import tiles_to_x
        tf, tid = [], []
        for sid in TEST_IDS:
            tiles = load_tiles("Test", sid, out_dir=TEST_TILES_DIR)
            with torch.no_grad():
                xs = tiles_to_x(tiles)
                fs = np.concatenate([net(xs[i:i + a.embed_batch].to(device), seg=False)["feat"].float().cpu().numpy() for i in range(0, len(xs), a.embed_batch)])
            tf.append(fs)
            tid += [sid] * len(tiles)
        extra = {"test_tile_feat": np.concatenate(tf), "test_tile_sample_id": np.array(tid), "test_site_feat": np.stack([f.mean(0) for f in tf]),
                 "test_sample_id": np.array(TEST_IDS)}
    np.savez(out / "embeddings.npz", tile_feat=feat, tile_batch=tb, tile_sample_id=ts, tile_session=tsess,
             tile_row=np.array([i["row"] for i in infos], np.int16), tile_col=np.array([i["col"] for i in infos], np.int16),
             site_feat=site, batch=np.array([b for b, _ in spots]), sample_id=np.array([s for _, s in spots]),
             session=np.array([tsess[(tb == b) & (ts == s)][0] for b, s in spots], np.int32),
             heldout=np.array(val_ids), **extra)
    print(f"done in {(time.time() - t_start) / 60:.1f} min: {out}", flush=True)


def cmd_run(a):
    """All 13 folds + the full model, packed on one GPU."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "4", "CUDA_VISIBLE_DEVICES": str(a.gpu)}
    (SDIR / a.name).mkdir(parents=True, exist_ok=True)
    folds = list(range(N_FOLDS)) + [-1]
    init_flag, tta_flag = (f" --init {a.init}" if a.init else ""), (" --tta" if a.tta else "")
    center_flag = " --center" if a.center else ""
    common = f"--name {a.name} --aug {a.aug} --arch {a.arch} --lr {a.lr} --epochs {a.epochs} --crop {a.crop} --w-seg {a.w_seg} --w-ce {a.w_ce} --temperature {a.temperature} --level {a.level} --w-adv {a.w_adv}{init_flag}{tta_flag}{center_flag} --margin {a.margin} --hard-weight {a.hard_weight} --hard-pair {a.hard_pair} --batch-spots {a.batch_spots} --tiles-per-spot {a.tiles_per_spot} --preload"
    pending, running, done, t0 = folds[:], {}, {}, time.time()
    while pending or running:
        while pending and len(running) < a.concurrent:
            f = pending.pop(0)
            log = open(SDIR / a.name / f"fold{f:02d}.log", "w")
            running[f] = (subprocess.Popen(f"{sys.executable} cnn/supcon.py train {common} --fold {f}", shell=True, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT), time.time())
        for f, (p, ts) in list(running.items()):
            if p.poll() is not None:
                done[f] = (p.returncode, time.time() - ts)
                del running[f]
        lines = [f"supcon {a.name}: {len(done)} done, {len(running)} running, {len(pending)} waiting, {(time.time() - t0) / 60:.0f} min"]
        for f in folds:
            st = f"done ({done[f][0]}) in {done[f][1] / 60:.1f} min" if f in done else "running: " + ((SDIR / a.name / (f"fold{f:02d}" if f >= 0 else "full") / "progress.txt").read_text().strip() if (SDIR / a.name / (f"fold{f:02d}" if f >= 0 else "full") / "progress.txt").exists() else "starting") if f in running else "waiting"
            lines.append(f"fold {f:3d}  {st}")
        (SDIR / a.name / "progress.txt").write_text("\n".join(lines) + "\n")
        if pending or running:
            time.sleep(10)
    print((SDIR / a.name / "progress.txt").read_text())


def cmd_score(a):
    """Nested leave-one-session-out: each spot is called by the fold whose encoder never saw its session."""
    from cnn import evalkit as ek
    from cnn import uncertainty as U
    root = SDIR / a.name
    calls, probs, y_all, sess_all, ids = {}, {}, {}, {}, []
    for f in range(N_FOLDS):
        p = root / f"fold{f:02d}" / "embeddings.npz"
        if not p.exists():
            print(f"fold {f}: missing")
            continue
        z = np.load(p)
        meta = ek.meta_for(z["batch"], z["sample_id"], z["session"])
        held = set(str(s) for s in z["heldout"])
        te = np.array([s in held for s in z["sample_id"]])
        P = ek.fit_predict("lr", z["site_feat"][~te].astype(float), meta.y.to_numpy()[~te], z["site_feat"][te].astype(float))
        for sid, yy, ss, pr in zip(z["sample_id"][te], meta.y.to_numpy()[te], meta.session.to_numpy()[te], P):
            calls[str(sid)], probs[str(sid)], y_all[str(sid)], sess_all[str(sid)] = int(pr.argmax() + 1), [float(v) for v in pr], int(yy), int(ss)
    ids = sorted(calls)
    y = np.array([y_all[s] for s in ids])
    pred = np.array([calls[s] for s in ids])
    sess = np.array([sess_all[s] for s in ids])
    bacc = U.bacc(y, pred)
    ci = U.session_bootstrap(y, pred, sess)
    mixed = np.array([len({y_all[s2] for s2 in ids if sess_all[s2] == sess_all[s]}) > 1 for s in ids])
    res = {"name": a.name, "n_spots_called": len(ids), "n_folds": N_FOLDS, "losess_bacc": bacc, "ci90": ci,
           "mixed_bacc": U.bacc(y[mixed], pred[mixed]) if mixed.any() else None, "recall": U.recall_table(y, pred),
           "b3_vs_rest": float(np.mean([((pred == 3) == (y == 3))[y == c].mean() for c in (1, 2, 3)])),
           "confusion": [[int(((y == i) & (pred == j)).sum()) for j in (1, 2, 3)] for i in (1, 2, 3)],
           "spots": [{"sample_id": s, "y": y_all[s], "session": sess_all[s], "call": calls[s], "p": probs[s]} for s in ids],
           "note": "encoder retrained per held-out spot fold (5 folds); no permutation p (would need 5 x 200 retrainings)"}
    full = root / "full" / "embeddings.npz"
    if full.exists():
        z = np.load(full)
        meta = ek.meta_for(z["batch"], z["sample_id"], z["session"])
        P = ek.fit_predict("lr", z["site_feat"].astype(float), meta.y.to_numpy(), z["test_site_feat"].astype(float))
        res["test"] = [{"sample_id": str(s), "call": int(p.argmax() + 1), "p": [float(v) for v in p]} for s, p in zip(z["test_sample_id"], P)]
        from cnn.predict import session_leak
        res["leak_full_model"] = session_leak(z["site_feat"].astype(float), meta.session.to_numpy())
    (root / "score.json").write_text(json.dumps(res, indent=1, default=float))
    print(f"{a.name}: nested losess bacc {bacc:.3f} [{ci['lo']:.2f}, {ci['hi']:.2f}] on {len(ids)} spots; mixed {res['mixed_bacc']}; "
          f"recall {[round(r['recall'], 2) for r in res['recall']]}; test {[(t['sample_id'], t['call']) for t in res.get('test', [])]}")
    return res


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("train", "run"):
        p = sub.add_parser(name)
        p.add_argument("--name", default="v2")
        p.add_argument("--arch", default="k7")
        p.add_argument("--epochs", type=int, default=30)
        p.add_argument("--crop", type=int, default=320)
        p.add_argument("--w-seg", type=float, default=0.2)
        p.add_argument("--w-ce", type=float, default=1.0, help="weight of the batch cross-entropy head (the supervised contrastive term alone sat at chance)")
        p.add_argument("--lr", type=float, default=1e-3)
        p.add_argument("--temperature", type=float, default=0.1)
        p.add_argument("--batch-spots", type=int, default=4, help="spots per batch class in a mini-batch")
        p.add_argument("--tiles-per-spot", type=int, default=2)
        p.add_argument("--level", choices=["tile", "spot"], default="tile", help="contrast / classify single tiles, or spot means inside the mini-batch")
        p.add_argument("--init", default="", help="checkpoint of the old label-free encoder to start from (cnn/processed/v_k7_con02/best.pt)")
        p.add_argument("--w-adv", type=float, default=0.0, help="session-adversarial weight (gradient reversal on a session head)")
        p.add_argument("--tta", action="store_true", help="average the embedding over the horizontal flip")
        p.add_argument("--center", action="store_true", help="centre z in every mini-batch before the contrastive loss")
        p.add_argument("--exclude", default="", help="comma list of spots never used for training (e.g. the Batch_1 anomalies 4ih2ggld,5n1q8atc)")
        p.add_argument("--margin", type=float, default=0.0, help="additive cosine margin on the batch classifier (0 = plain linear head)")
        p.add_argument("--hard-weight", type=float, default=1.0, help="weight of the --hard-pair negatives in the contrastive loss")
        p.add_argument("--hard-pair", default="1,2", help="the confusable batch pair, e.g. 2,3 (Batch_2 vs Batch_3)")
        p.add_argument("--aug", default="base", help="base (hflip + brightness/contrast/noise jitter), flips (+ vflip), rot (+ vflip + 90-degree turns)")
        p.add_argument("--preload", action="store_true")
        p.add_argument("--embed-batch", type=int, default=16)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--device", default="auto")
        if name == "train":
            p.add_argument("--fold", type=int, default=0, help="0..4 = held-out spot fold; -1 = all spots")
            p.add_argument("--smoke", action="store_true")
        else:
            p.add_argument("--gpu", default="0")
            p.add_argument("--concurrent", type=int, default=6)
    s = sub.add_parser("score")
    s.add_argument("--name", default="v2")
    a = ap.parse_args()
    {"train": cmd_train, "run": cmd_run, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    main()
