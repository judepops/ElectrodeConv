"""Which batch? Batch probabilities from the images alone, for every training spot (out of fold) and the test spots.

    python cnn/predict.py --run supcon/v2/full    # -> processed/supcon/v2/full/{predictions.json, test_embeddings.npz}

Training spots are called leave-one-session-out and leave-one-spot-out (evalkit.oof, logistic regression on PCA
scores, C = 0.1), so every call shown is one the classifier made without seeing that spot (or its whole session).
The three test spots are embedded here with the same checkpoint and code path as the training tiles (checked: two
training tiles are re-embedded and must match the stored embedding), then called by the classifier fitted on all 31.
Honesty numbers next to the calls: chance 0.33, the evalkit scorecard with its permutation p, and a session-leak
check (does the embedding group spots by imaging session?). Image height is never an input; it is only used to
describe sessions.

The FusionNet encoder was trained WITH the batch labels (cnn/supcon.py), so the out-of-fold numbers here are only
out of fold for the logistic regression, not for the encoder: they are in-sample and optimistic. The fair number is
the nested leave-one-session-out score in processed/supcon/<name>/score.json (`supcon.py score`); predictions.json
says so in its `honest_score` field.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.4")
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.3")
import torch  # noqa: E402  (before evalkit, which caps BLAS threads)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cnn import evalkit as ek  # noqa: E402
from cnn.common import DETECTORS, TILES_CSV, load_tile, pick_device, run_dir  # noqa: E402
from cnn.model import net_from_config  # noqa: E402
from preprocessing.preprocess import load_tiles  # noqa: E402
from qc.features_table import TEST_IDS, TEST_TILES_DIR  # noqa: E402
from qc.verdict import clean  # noqa: E402


def load_net(run, device, ckpt="last.pt"):
    """run: a folder under processed/, e.g. supcon/v2/full. -> (FusionNet in eval mode, the checkpoint dict)."""
    ck = torch.load(run_dir(run) / ckpt, map_location="cpu", weights_only=False)
    net = net_from_config(ck["config"]).to(device)
    net.load_state_dict(ck["model"])
    net.eval()
    return net, ck


def tiles_to_x(tiles):
    return torch.from_numpy(np.stack([np.stack([getattr(t, d) for d in DETECTORS]) for t in tiles]).astype(np.float32))


@torch.no_grad()
def embed_x(net, device, x, batch=2):
    """x (n, 3, H, W) -> (n, feat_dim) tile embeddings (mean + std of the fused bottleneck), as supcon.embed_all."""
    out = []
    for i in range(0, len(x), batch):
        o = net(x[i:i + batch].to(device), seg=False)
        out.append(o["feat"].float().cpu().numpy())
    return np.concatenate(out)


def embed_tiles(net, device, tiles, batch=2):
    return embed_x(net, device, tiles_to_x(tiles), batch)


def session_leak(X, sess, n_perm=1000, seed=0):
    """Does the embedding group spots by imaging session? Cosine 1-NN same-session rate vs its chance, and a
    leave-one-out logistic regression restricted to sessions that hold >= 2 spots."""
    from sklearn.linear_model import LogisticRegression
    Z = X - X.mean(0)
    Z /= np.maximum(X.std(0), 1e-8)
    U = Z / np.maximum(np.linalg.norm(Z, axis=1, keepdims=True), 1e-12)
    S = U @ U.T
    np.fill_diagonal(S, -np.inf)
    nn = S.argmax(1)
    rate = float(np.mean(sess[nn] == sess))
    counts = np.unique(sess, return_counts=True)[1]
    chance = float((counts * (counts - 1)).sum() / (len(sess) * (len(sess) - 1)))
    rng = np.random.default_rng(seed)
    null = np.array([np.mean(sess[nn] == rng.permutation(sess)) for _ in range(n_perm)])
    p = float((1 + (null >= rate - 1e-12).sum()) / (1 + n_perm))
    multi = np.isin(sess, np.unique(sess)[counts >= 2])
    idx = np.flatnonzero(multi)
    bacc = float("nan")
    if len(idx) >= 4:                               # smoke runs have too few multi-spot sessions for a leave-one-out
        pred = np.empty(len(idx), dtype=sess.dtype)
        for j, i in enumerate(idx):
            tr = idx[idx != i]
            a, b = ek._std(X[tr], X[[i]])
            Ptr, Pte = ek._pca_scores(a, b, k=min(10, len(tr) - 2))
            pred[j] = LogisticRegression(C=0.1, class_weight="balanced", max_iter=5000).fit(Ptr, sess[tr]).predict(Pte)[0]
        bacc = ek._bacc(sess[idx], pred)
    return {"nn_same_session_rate": rate, "nn_chance": chance, "nn_perm_p": p,
            "loo_session_bacc_multi": float(bacc), "n_multi_sessions": int((counts >= 2).sum()),
            "loo_chance": float(1 / max((counts >= 2).sum(), 1))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="supcon/v2/full", help="folder under processed/")
    ap.add_argument("--n-perm", type=int, default=200)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--device", default="auto")
    a = ap.parse_args()
    out = run_dir(a.run)
    device = pick_device(a.device)
    net, ck = load_net(a.run, device)
    z = np.load(out / "embeddings.npz")
    X = z["site_feat"].astype(float)
    meta = ek.meta_for(z["batch"], z["sample_id"], z["session"])
    y, sess = meta.y.to_numpy(), meta.session.to_numpy()
    n = len(y)

    # guard: the same code path must reproduce the stored tile embeddings
    tb, ts, tr_, tc = z["tile_batch"], z["tile_sample_id"], z["tile_row"], z["tile_col"]
    chk = [0, len(tb) // 2]
    tiles = [load_tile(str(tb[i]), str(ts[i]), int(tr_[i]), int(tc[i])) for i in chk]
    e = embed_tiles(net, device, tiles, a.batch)
    cos = [float(e[j] @ z["tile_feat"][i] / (np.linalg.norm(e[j]) * np.linalg.norm(z["tile_feat"][i]))) for j, i in enumerate(chk)]
    print(f"embedding path check: cosine with the stored tile embeddings {cos}")
    assert min(cos) > 0.99, "predict.py embeds tiles differently from supcon.py; re-run supcon.py train --fold -1 on this machine"

    # test spots
    test_feats, test_rows = [], []
    sess_batches = pd.read_csv(TILES_CSV).drop_duplicates(["batch", "sample_id"]).groupby("session").batch.apply(lambda s: sorted(set(s))).to_dict()
    tfe, tid = [], []
    test_ids = [s for s in TEST_IDS if (TEST_TILES_DIR / "Test" / s).exists()]   # tiled by qc/features_table.py
    if not test_ids:
        print(f"no test tiles under {TEST_TILES_DIR}: training spots only")
    for sid in test_ids:
        tiles = load_tiles("Test", sid, out_dir=TEST_TILES_DIR)
        f = embed_tiles(net, device, tiles, a.batch)
        tfe.append(f)
        tid += [(sid, t.row, t.col) for t in tiles]
        test_feats.append(f.mean(0))
        h = int(tiles[0].meta["raw_height"])
        test_rows.append({"sample_id": sid, "session": h, "session_batches": sess_batches.get(h, []),
                          "seam_guess": ek.SEAM_GUESS.get(sid)})
        print(f"test spot {sid}: {len(tiles)} tiles embedded, height {h}, session holds {sess_batches.get(h, [])}")
    if test_ids:
        Xte = np.stack(test_feats)
        np.savez(out / "test_embeddings.npz", tile_feat=np.concatenate(tfe), tile_sample_id=np.array([t[0] for t in tid]),
                 tile_row=np.array([t[1] for t in tid], np.int16), tile_col=np.array([t[2] for t in tid], np.int16),
                 site_feat=Xte, sample_id=np.array(test_ids), session=np.array([r["session"] for r in test_rows], np.int32))
        P_test = ek.fit_predict("lr", X, y, Xte)
        for r, p in zip(test_rows, P_test):
            r["p"] = [float(v) for v in p]
            r["call"] = int(p.argmax() + 1)
            r["agrees_with_seam"] = bool(r["call"] == r["seam_guess"])

    # training spots, out of fold
    P_sess = ek.oof(X, y, sess, "lr", sess)
    P_loso = ek.oof(X, y, np.arange(n), "lr", sess)
    c_sess, c_loso = P_sess.argmax(1) + 1, P_loso.argmax(1) + 1
    spots = [{"batch": str(b), "sample_id": str(s), "session": int(h), "y": int(yy), "p_losess": [float(v) for v in ps],
              "call_losess": int(cs), "p_loso": [float(v) for v in pl], "call_loso": int(cl)}
             for b, s, h, yy, ps, cs, pl, cl in zip(meta.batch, meta.sample_id, sess, y, P_sess, c_sess, P_loso, c_loso)]
    conf = [[int(((y == i) & (c_sess == j)).sum()) for j in (1, 2, 3)] for i in (1, 2, 3)]
    recall = [float(np.mean(c_sess[y == i] == i)) for i in (1, 2, 3)]
    b3 = {"bacc": float(ek._bacc((y == 3).astype(int), (c_sess == 3).astype(int))),
          "b3_recall": float(np.mean(c_sess[y == 3] == 3)), "rest_as_rest": float(np.mean(c_sess[y != 3] != 3))}
    b12 = y != 3                                   # Batch_1 vs Batch_2 only; a call of 3 counts as wrong
    b12_bacc = float(ek._bacc(y[b12], c_sess[b12]))
    print(f"losess balanced accuracy {ek._bacc(y, c_sess):.3f}, loso {ek._bacc(y, c_loso):.3f}; B3 vs rest {b3['bacc']:.3f}")

    scores = ek.score(X, meta, n_perm=a.n_perm)
    leak = session_leak(X, sess)
    print(f"scorecard: losess {scores['lr_losess']:.3f} (perm p {scores['lr_losess_perm_p']:.3f}), loso {scores['lr_loso']:.3f}, "
          f"mixed {scores['lr_mixed']:.3f}, joins {scores['lr_joins']:.3f}")
    print(f"session leak: 1-NN same session {leak['nn_same_session_rate']:.2f} (chance {leak['nn_chance']:.2f}, p {leak['nn_perm_p']:.3f}); "
          f"LOO session LR {leak['loo_session_bacc_multi']:.2f} (chance {leak['loo_chance']:.2f})")
    res = {"run": a.run, "epoch": int(ck.get("epoch", -1)), "chance": 1 / 3, "n_spots": int(n), "n_sessions": int(len(np.unique(sess))),
           "scores": {k: v for k, v in scores.items() if not k.startswith("test_")},
           "losess_bacc": float(ek._bacc(y, c_sess)), "loso_bacc": float(ek._bacc(y, c_loso)),
           "confusion_losess": conf, "recall_losess": recall, "b3_vs_rest": b3, "b1_vs_b2_losess_bacc": b12_bacc,
           "spots": spots, "test": test_rows, "leak": leak,
           "encoder_saw_labels": True, "honest_score": "see score.json (nested leave-one-session-out)"}
    (out / "predictions.json").write_text(json.dumps(clean(res), indent=1))
    for r in test_rows:
        print(f"  {r['sample_id']}: P(B1,B2,B3) = {np.round(r['p'], 2).tolist()} -> Batch_{r['call']}  "
              f"(its session {r['session']} holds {r['session_batches']})")
    print(f"wrote {out / 'predictions.json'}")


if __name__ == "__main__":
    main()
