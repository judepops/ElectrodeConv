"""Classify new spots with the best model: V1 + V2 side by side, three V2 seeds averaged (0.68 balanced accuracy on
held-out spots, chance 0.33; known test set 3/3 with the one-per-batch rule).

    python cnn/classify.py --dir /path/to/new_images                     # every img_<id>_{BSE,Inlens,ETD|SE}.tif in the folder
    python cnn/classify.py --dir /path/to/new_images --one-per-batch     # the set holds exactly one spot of each batch
    -> cnn/results/classify_<folder>.json and a table on stdout

What it does, per spot: the same fair preprocessing as training (harmonise masks; image height, black level and noise
are never inputs), 512 px tiles, then two embeddings averaged over the tiles:
  V1  the label-free encoder (cnn/processed/v_k7_con02/best.pt, cnn/v1net.py)
  V2  the batch-supervised early-fusion encoder trained on all 31 spots (cnn/processed/supcon/<v2>/full/last.pt);
      several V2 runs can be given (--v2 v2,v2s1,v2s2) and their probabilities are averaged
A logistic regression fitted on the 31 training spots' [V1 | V2] embeddings (each block standardised and weighted
equally, exactly as cnn/compare.py scored it) gives P(Batch_1, Batch_2, Batch_3). Stability = share of 31 refits with
one training spot left out that give the same call.

--one-per-batch: when the set is known to hold one spot of each batch (3 spots), every assignment of the three
batches is scored by the product of its probabilities and the best one is reported, with its share of the total
as the confidence. Use it only when that is true.
"""
from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import os
import sys
from pathlib import Path

os.environ["LOSSLARP_MASKS"] = "harmonise"          # V1 and V2 were trained on harmonise tiles
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

from cnn.common import DETECTORS, RUNS_DIR, pick_device  # noqa: E402
from cnn.v1net import load_v1  # noqa: E402
from preprocessing import preprocess as pp  # noqa: E402

BMAP = {"Batch_1": 1, "Batch_2": 2, "Batch_3": 3}
MODELS = REPO / "models"


def v1_dir(run):
    """models/v1 (tracked) for the default run, else cnn/processed/<run>."""
    return MODELS / "v1" if run == "v_k7_con02" and (MODELS / "v1" / "best.pt").exists() else RUNS_DIR / run


def v2_dir(run):
    """models/<run> (tracked: v2, v2s1, v2s2) when present, else cnn/processed/supcon/<run>/full."""
    return MODELS / run if (MODELS / run / "last.pt").exists() else RUNS_DIR / "supcon" / run / "full"


def std_block(Xtr, Xte):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd < 1e-8] = 1.0
    return (Xtr - mu) / sd / np.sqrt(Xtr.shape[1]), (Xte - mu) / sd / np.sqrt(Xtr.shape[1])


def lr_proba(blocks_tr, blocks_te, y, keep=None):
    keep = np.ones(len(y), bool) if keep is None else keep
    parts = [std_block(a[keep], b) for a, b in zip(blocks_tr, blocks_te)]
    Xtr, Xte = np.hstack([p[0] for p in parts]), np.hstack([p[1] for p in parts])
    return LogisticRegression(C=1.0, class_weight="balanced", max_iter=5000).fit(Xtr * 10, y[keep]).predict_proba(Xte * 10)


def spot_ids(folder):
    return sorted({p.stem.split("_")[1] for p in Path(folder).glob("img_*_*.tif")})


@torch.no_grad()
def embed_spot(tiles, nets, device, batch=2):
    x = torch.from_numpy(np.stack([np.stack([getattr(t, d) for d in DETECTORS]) for t in tiles]).astype(np.float32))
    out = {}
    for name, (net, kind) in nets.items():
        fs = []
        for i in range(0, len(x), batch):
            xb = x[i:i + batch].to(device)
            fs.append((net(xb) if kind == "v1" else net(xb, seg=False)["feat"]).float().cpu().numpy())
        out[name] = np.concatenate(fs).mean(0)
    return out


def classify_joint(a):
    """Same as main, for one combined network (cnn/joint.py): embedding = [V1 branch | V2 branch]."""
    from cnn.joint import JointNet
    device = pick_device(a.device)
    d = RUNS_DIR / "supcon" / a.joint / "full"
    ck = torch.load(d / "last.pt", map_location="cpu", weights_only=False)
    net = JointNet()
    net.load_state_dict(ck["model"])
    net = net.to(device).eval()
    z = np.load(d / "embeddings.npz")
    o = np.argsort(z["sample_id"])
    X, y = z["site_feat"][o].astype(float), np.array([BMAP[str(b)] for b in z["batch"][o]])

    def emb(folder, sid):
        raw = dataclasses.replace(pp.load_spot(folder, sid), batch="New")
        tiles = pp.tiles_of(pp.preprocess(raw))
        x = torch.from_numpy(np.stack([np.stack([getattr(t, k) for k in DETECTORS]) for t in tiles]).astype(np.float32))
        with torch.no_grad():
            return np.concatenate([net(x[i:i + 2].to(device), seg=False)["feat"].float().cpu().numpy() for i in range(0, len(x), 2)]).mean(0)
    if a.add_labelled:
        from qc.features_table import TEST_DIR
        extra = dict(kv.split("=") for kv in a.add_labelled.split(","))
        X = np.vstack([X, [emb(TEST_DIR, s) for s in extra]])
        y = np.concatenate([y, [BMAP[b] for b in extra.values()]])
    ids = [s for s in a.ids.split(",") if s] or spot_ids(a.dir)
    T = np.stack([emb(a.dir, s) for s in ids])
    P = lr_proba([X], [T], y)
    res = {"model": f"V1 V2 combined ({a.joint})", "spots": []}
    for j, sid in enumerate(ids):
        res["spots"].append({"sample_id": sid, "call": f"Batch_{P[j].argmax() + 1}", "p": [round(float(v), 3) for v in P[j]]})
        print(f"{sid:10s} Batch_{P[j].argmax() + 1}   {np.round(P[j], 2)}")
    if a.per_batch and len(ids) == 3 * a.per_batch:
        labels = [b for b in range(3) for _ in range(a.per_batch)]
        best = max((float(np.sum([np.log(max(P[j, b], 1e-9)) for j, b in enumerate(perm)])), perm) for perm in set(itertools.permutations(labels)))
        res["per_batch_assignment"] = {sid: f"Batch_{b + 1}" for sid, b in zip(ids, best[1])}
        print("exactly %d per batch: " % a.per_batch + ", ".join(f"{sid} -> Batch_{b + 1}" for sid, b in zip(ids, best[1])))
    out = REPO / "cnn" / "results" / f"classify_{Path(a.dir).name}_{a.joint}.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="folder with img_<id>_{BSE,Inlens,ETD|SE}.tif")
    ap.add_argument("--ids", default="", help="comma list of spot ids (default: every spot in the folder)")
    ap.add_argument("--v1", default="v_k7_con02")
    ap.add_argument("--v2", default="v2,v2s1,v2s2,v2_noseg", help="comma list of supcon runs whose full model is used (probabilities averaged)")
    ap.add_argument("--one-per-batch", action="store_true")
    ap.add_argument("--per-batch", type=int, default=0, help="the set holds exactly this many spots of each batch (3 x N spots): best joint assignment")
    ap.add_argument("--add-labelled", default="", help="extra labelled spots for the classifier, e.g. 3e122cbj=Batch_2,fn0mhxef=Batch_1 (the earlier test "
                    "spots; their embeddings come from the stored test embeddings, the encoders are unchanged)")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--joint", default="", help="use a V1 V2 combined run (cnn/joint.py) instead, e.g. j_comb12: one network, one embedding")
    a = ap.parse_args()
    if a.joint:
        return classify_joint(a)
    device = pick_device(a.device)
    from cnn.model import net_from_config
    nets = {"V1": (load_v1(v1_dir(a.v1) / "best.pt", device), "v1")}
    v2s = [v for v in a.v2.split(",") if v]
    for v in v2s:
        ck = torch.load(v2_dir(v) / "last.pt", map_location="cpu", weights_only=False)
        net = net_from_config(ck["config"])
        missing, unexpected = net.load_state_dict(ck["model"], strict=False)
        assert not unexpected and all(k.startswith("adv.") for k in missing), (missing, unexpected)   # older runs: no session head
        nets[v] = (net.to(device).eval(), "v2")
    # training embeddings (the 31 labelled spots), as stored by embed / supcon
    z1 = np.load(v1_dir(a.v1) / "embeddings.npz")
    o1 = np.argsort(z1["sample_id"])
    ids_tr = z1["sample_id"][o1].astype(str)
    y = np.array([BMAP[str(b)] for b in z1["batch"][o1]])
    tr = {"V1": z1["site_feat"][o1].astype(float)}
    for v in v2s:
        z2 = np.load(v2_dir(v) / "embeddings.npz")
        o2 = np.argsort(z2["sample_id"])
        assert list(z2["sample_id"][o2].astype(str)) == list(ids_tr)
        tr[v] = z2["site_feat"][o2].astype(float)
    if a.add_labelled:                                 # earlier test spots, now labelled: more training spots for the classifier
        extra = dict(kv.split("=") for kv in a.add_labelled.split(","))
        t1 = np.load(v1_dir(a.v1) / "test_embeddings.npz")
        r1 = {str(s): i for i, s in enumerate(t1["sample_id"])}
        tr["V1"] = np.vstack([tr["V1"], [t1["site_feat"][r1[s]] for s in extra]])
        for v in v2s:
            z2 = np.load(v2_dir(v) / "embeddings.npz")
            r2 = {str(s): i for i, s in enumerate(z2["test_sample_id"])}
            tr[v] = np.vstack([tr[v], [z2["test_site_feat"][r2[s]] for s in extra]])
        y = np.concatenate([y, [BMAP[b] for b in extra.values()]])
        print("classifier trained on %d spots (+ %s)" % (len(y), ", ".join("%s=%s" % kv for kv in extra.items())))
    ids = [s for s in a.ids.split(",") if s] or spot_ids(a.dir)
    emb = {}
    for sid in ids:
        raw = dataclasses.replace(pp.load_spot(a.dir, sid), batch="New")
        tiles = pp.tiles_of(pp.preprocess(raw))
        emb[sid] = embed_spot(tiles, nets, device)
        print(f"{sid}: {len(tiles)} tiles embedded (image {raw.bse.shape[0]} x {raw.bse.shape[1]})", flush=True)
    te = {k: np.stack([emb[s][k] for s in ids]) for k in nets}
    np.savez(RUNS_DIR / f"classify_{Path(a.dir).name}_embeddings.npz", ids=np.array(ids), **{f"test_{k}": v for k, v in te.items()},
             **{f"train_{k}": v for k, v in tr.items()}, y=y)
    P = np.mean([lr_proba([tr["V1"], tr[v]], [te["V1"], te[v]], y) for v in v2s], 0)
    loo = np.stack([np.mean([lr_proba([tr["V1"], tr[v]], [te["V1"], te[v]], y, np.arange(len(y)) != i) for v in v2s], 0)
                    for i in range(len(y))])
    res = {"model": f"V1 ({a.v1}) + V2 ({', '.join(v2s)}) side by side", "spots": []}
    print(f"\n{'spot':10s} call      P(B1, B2, B3)        stable")
    for j, sid in enumerate(ids):
        call = int(P[j].argmax() + 1)
        stab = float((loo[:, j].argmax(1) + 1 == call).mean())
        res["spots"].append({"sample_id": sid, "call": f"Batch_{call}", "p": [round(float(v), 3) for v in P[j]], "stable": stab})
        print(f"{sid:10s} Batch_{call}   {np.round(P[j], 2)}   {stab:.0%}")
    if a.one_per_batch and len(ids) == 3:
        scored = sorted(((float(np.prod([P[j, b] for j, b in enumerate(perm)])), perm) for perm in itertools.permutations(range(3))), reverse=True)
        total = sum(s for s, _ in scored)
        best_s, best = scored[0]
        res["one_per_batch"] = {"assignment": {sid: f"Batch_{b + 1}" for sid, b in zip(ids, best)}, "confidence": best_s / total,
                                "runner_up": {sid: f"Batch_{b + 1}" for sid, b in zip(ids, scored[1][1])}, "runner_up_confidence": scored[1][0] / total}
        print("\none spot per batch: " + ", ".join(f"{sid} -> Batch_{b + 1}" for sid, b in zip(ids, best)) +
              f"  (confidence {best_s / total:.0%}; runner-up {scored[1][0] / total:.0%})")
    if a.per_batch and len(ids) == 3 * a.per_batch:     # best assignment with exactly per_batch spots of each batch
        labels = [b for b in range(3) for _ in range(a.per_batch)]
        best = max((float(np.sum([np.log(max(P[j, b], 1e-9)) for j, b in enumerate(perm)])), perm) for perm in set(itertools.permutations(labels)))
        res["per_batch_assignment"] = {"per_batch": a.per_batch, "assignment": {sid: f"Batch_{b + 1}" for sid, b in zip(ids, best[1])}}
        print("exactly %d per batch: " % a.per_batch + ", ".join(f"{sid} -> Batch_{b + 1}" for sid, b in zip(ids, best[1])))
    out = REPO / "cnn" / "results" / f"classify_{Path(a.dir).name}.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
