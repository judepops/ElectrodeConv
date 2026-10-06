"""Run from the repo root: LOSSLARP_MASKS=harmonise python3.11 demo/make_confusion.py demo/confusion.js
Held-out confusion matrices for the demo: V1 alone and V1 + four V2 members (same folds and classifier as compare.py)."""
import json, sys
import numpy as np
sys.path.insert(0, ".")
from cnn.classify import lr_proba
from cnn.compare import load, BMAP
from cnn.data import make_folds, tile_index
folds = make_folds(tile_index(), by="sample_id", n_folds=5, seed=0)
v1 = load("models/v1/embeddings.npz"); ids = v1["ids"]; y = np.array([BMAP[b] for b in v1["batch"]])
members = ("v2", "v2s1", "v2s2", "v2_noseg")
runs = {r: [load(f"cnn/processed/supcon/{r}/fold{k:02d}/embeddings.npz") for k in range(5)] for r in members}
P1, P12 = np.zeros((len(y), 3)), np.zeros((len(y), 3))
for k, (tr_ids, te_ids) in enumerate(folds):
    tr, te = np.isin(ids, tr_ids), np.isin(ids, te_ids)
    P1[te] = lr_proba([v1["site"][tr]], [v1["site"][te]], y[tr])
    P12[te] = np.mean([lr_proba([v1["site"][tr], runs[r][k]["site"][tr]], [v1["site"][te], runs[r][k]["site"][te]], y[tr]) for r in members], 0)
out = {}
for name, P in (("V1", P1), ("V1 + V2", P12)):
    pred = P.argmax(1) + 1
    cm = [[int(((y == i) & (pred == j)).sum()) for j in (1, 2, 3)] for i in (1, 2, 3)]
    out[name] = {"confusion": cm, "recall": [cm[i][i] / sum(cm[i]) for i in range(3)], "n": [sum(r) for r in cm]}
    print(name, cm, [round(r, 2) for r in out[name]["recall"]])
out["note"] = "rows = true batch, columns = called batch; each spot called by a model that never saw it (5 folds by spot)"

# how V1 and V2 are fused (slide "fuse"): block sizes from the saved embeddings, held-out scores on the same folds
from cnn.compare import lr_calls
from cnn import uncertainty as U
def bacc_of(blocks_of_fold):
    pred = np.zeros_like(y)
    for k, (tr_ids, te_ids) in enumerate(folds):
        tr, te = np.isin(ids, tr_ids), np.isin(ids, te_ids)
        bl = blocks_of_fold(k)
        pred[te] = lr_calls([b[tr] for b in bl], [b[te] for b in bl], y[tr])
    return U.bacc(y, pred)
fus = {"v1_dims": int(v1["site"].shape[1]), "v2_dims": int(runs["v2"][0]["site"].shape[1]), "members": list(members),
       "late": U.bacc(y, P12.argmax(1) + 1), "v1": U.bacc(y, P1.argmax(1) + 1)}
for key, run in (("joint_scratch", "j_comb12"), ("joint_warm", "j_init")):
    try:
        J = [load(f"cnn/processed/supcon/{run}/fold{k:02d}/embeddings.npz") for k in range(5)]
        fus[key] = bacc_of(lambda k, J=J: [J[k]["site"]])
    except FileNotFoundError:
        pass
out["fusion"] = fus
print("fusion", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in fus.items()})
open(sys.argv[1], "w").write("window.DEMO_CONFUSION = " + json.dumps(out, indent=1) + ";\n")
