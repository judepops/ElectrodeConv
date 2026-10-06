"""Does a new spot look like anything in training? A "none of these batches" check next to the batch call.

    python cnn/novelty.py --run supcon/v2/full       # -> processed/supcon/v2/full/novelty.json, and a table on stdout

Reads   processed/<run>/embeddings.npz        the 31 training spots (cnn/supcon.py)
        processed/<run>/test_embeddings.npz   the test spots (cnn/predict.py)
Needs only numpy: no checkpoint, no torch, a second or two.

cnn/predict.py always splits 100 % between Batch_1, Batch_2 and Batch_3, so a spot from none of them still gets a
confident-looking call. Polaron's test may hold such spots ("what batch each sample comes from, if any"). This
script keeps the bet and adds how far to trust that the spot belongs to any batch at all.

The score: a spot's distance to its 3 nearest training spots in the embedding (features standardised on the training
spots; root-mean-square difference per feature, so 0 = identical and about 1.4 = unrelated).

What counts as far: every training spot is scored the same way with its WHOLE imaging session left out, because a
test spot usually comes from a source image the model has not seen. Those 31 scores are the reference. A test spot's
percentile is the share of them that it exceeds. Above the 95th percentile it is flagged "unlike training".
The flag is deliberately conservative: a held-out training spot has fewer neighbours than a test spot does.

Control: a training spot with its features shuffled is real embedding values in the wrong places. It must flag;
the script prints whether it does.
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

# follows LOSSLARP_MASKS like preprocessing/preprocess.py (seg3, the default on this branch -> processed_seg3/)
RUNS_DIR = Path(__file__).resolve().parent / ("processed" if os.environ.get("LOSSLARP_MASKS", "seg3") == "harmonise"
                                              else "processed_seg3")
K, FLAG_PERCENTILE = 3, 95


def standardise(Xtr, X):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd < 1e-8] = 1.0
    return (Xtr - mu) / sd, (X - mu) / sd


def distances(Xtr, x):
    """RMS standardised difference between spot x and every training spot."""
    Ztr, z = standardise(Xtr, x[None])
    return np.sqrt(((Ztr - z) ** 2).mean(1))


def knn_score(d, k=K):
    return float(np.sort(d)[:k].mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", default="supcon/v2/full", help="folder under processed/")
    a = ap.parse_args()
    out = RUNS_DIR / a.run
    z = np.load(out / "embeddings.npz")
    X, batch, sid, sess = z["site_feat"].astype(float), z["batch"].astype(str), z["sample_id"].astype(str), z["session"]

    # reference: each training spot against the spots of all OTHER sessions
    ref = np.empty(len(X))
    for i in range(len(X)):
        keep = sess != sess[i]
        ref[i] = knn_score(distances(X[keep], X[i]))
    cut = float(np.percentile(ref, FLAG_PERCENTILE))

    def describe(x, exclude=None):
        keep = np.ones(len(X), bool) if exclude is None else exclude
        d = distances(X[keep], x)
        order = np.argsort(d)[:K]
        score = knn_score(d)
        return {
            "score": round(score, 3), "percentile": round(float((ref < score).mean() * 100), 1),
            "unlike_training": bool(score > cut),
            "nearest": [{"sample_id": sid[keep][j], "batch": batch[keep][j], "session": int(sess[keep][j]), "distance": round(float(d[j]), 3)} for j in order],
            "nearest_per_batch": {b: round(float(d[batch[keep] == b].min()), 3) for b in sorted(set(batch))},
        }

    result = {"run": a.run, "k": K, "reference": {"n": len(ref), "median": round(float(np.median(ref)), 3),
              "p95": round(cut, 3), "max": round(float(ref.max()), 3)},
              "training": [{"sample_id": sid[i], "batch": batch[i], "session": int(sess[i]), "score": round(float(ref[i]), 3)} for i in range(len(X))]}

    rng = np.random.default_rng(0)
    control = describe(rng.permutation(X[0]))
    result["control_shuffled_spot"] = {k: control[k] for k in ("score", "percentile", "unlike_training")}

    print(f"reference (training spots, own session left out): median {result['reference']['median']}, "
          f"95th percentile {result['reference']['p95']}, max {result['reference']['max']}")
    print(f"control (a shuffled spot): score {control['score']}, flagged: {control['unlike_training']}"
          + ("" if control["unlike_training"] else "   <-- the control did NOT flag: do not trust the flags below"))

    test_file = out / "test_embeddings.npz"
    result["test"] = []
    if test_file.exists():
        t = np.load(test_file)
        for x, s in zip(t["site_feat"].astype(float), t["sample_id"].astype(str)):
            r = {"sample_id": s, **describe(x)}
            result["test"].append(r)
            near = min(r["nearest_per_batch"], key=r["nearest_per_batch"].get)
            print(f"test spot {s}: score {r['score']} (higher than {r['percentile']:.0f} % of training spots) -> "
                  f"{'UNLIKE TRAINING' if r['unlike_training'] else 'looks like training'}; nearest batch by distance {near}; "
                  f"nearest spots {', '.join(n['sample_id'] + ' (' + n['batch'] + ')' for n in r['nearest'])}")
    else:
        print(f"no {test_file.name}: run cnn/predict.py --run {a.run} first to score the test spots")
    (out / "novelty.json").write_text(json.dumps(result, indent=1))
    print(f"wrote {out / 'novelty.json'}")


if __name__ == "__main__":
    main()
