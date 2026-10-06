"""Uncertainty for a balanced-accuracy score on 31 spots in 13 imaging sessions.

    from cnn.uncertainty import session_bootstrap, paired_delta, wilson, gained_lost

The unit of replication is the imaging session (spots imaged together are partly the same measurement), so the
bootstrap resamples sessions, not spots. Every function works on FIXED out-of-fold calls: the classifier is not
refit per draw, so the intervals leave out refitting variance and are a little optimistic. They answer "how much,
and how sure", while the permutation p (evalkit) answers "is there any signal at all".
"""
from __future__ import annotations

import numpy as np

DRAWS = 2000


def bacc(y, pred):
    """Balanced accuracy over the classes present in y."""
    classes = np.unique(y)
    return float(np.mean([(pred[y == c] == c).mean() for c in classes]))


def _draws(sess, draws, seed):
    """Index sets of spots: `draws` resamples of the sessions with replacement."""
    rng = np.random.default_rng(seed)
    sessions = np.unique(sess)
    by = {s: np.flatnonzero(sess == s) for s in sessions}
    for _ in range(draws):
        pick = rng.choice(sessions, len(sessions), replace=True)
        yield np.concatenate([by[s] for s in pick])


def session_bootstrap(y, pred, sess, draws=DRAWS, seed=0, level=0.90):
    """-> {bacc, lo, hi, se} of the balanced accuracy of fixed calls `pred`, resampling sessions."""
    y, pred, sess = np.asarray(y), np.asarray(pred), np.asarray(sess)
    vals = np.array([bacc(y[i], pred[i]) for i in _draws(sess, draws, seed)])
    a = (1 - level) / 2
    return {"bacc": bacc(y, pred), "lo": float(np.quantile(vals, a)), "hi": float(np.quantile(vals, 1 - a)),
            "se": float(vals.std()), "level": level, "draws": draws, "unit": "session"}


def paired_delta(y, pred_a, pred_b, sess, draws=DRAWS, seed=0, level=0.90):
    """Difference bacc(a) - bacc(b) on the SAME resampled sessions. -> {delta, lo, hi, p_gt0}."""
    y, pa, pb, sess = np.asarray(y), np.asarray(pred_a), np.asarray(pred_b), np.asarray(sess)
    d = np.array([bacc(y[i], pa[i]) - bacc(y[i], pb[i]) for i in _draws(sess, draws, seed)])
    a = (1 - level) / 2
    return {"delta": bacc(y, pa) - bacc(y, pb), "lo": float(np.quantile(d, a)), "hi": float(np.quantile(d, 1 - a)),
            "p_gt0": float((d > 0).mean()), "level": level}


def gained_lost(y, pred_a, pred_b, ids, sess, mixed):
    """Spots a calls right and b wrong (gained) and the reverse (lost), with their batch, session and whether the
    session holds more than one batch (the leak-proof evidence)."""
    y, pa, pb = np.asarray(y), np.asarray(pred_a), np.asarray(pred_b)
    rows = lambda m: [{"sample_id": str(ids[i]), "batch": int(y[i]), "session": int(sess[i]), "mixed": bool(mixed[i])}
                      for i in np.flatnonzero(m)]
    return {"gained": rows((pa == y) & (pb != y)), "lost": rows((pa != y) & (pb == y))}


def wilson(k, n, z=1.96):
    """Wilson score interval of a proportion k/n. -> (lo, hi)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(max(0.0, c - h)), float(min(1.0, c + h)))


def recall_table(y, pred, labels=(1, 2, 3)):
    """Per-class recall with Wilson 95 % intervals. -> [{batch, recall, n, lo, hi}]"""
    y, pred = np.asarray(y), np.asarray(pred)
    out = []
    for c in labels:
        m = y == c
        k, n = int((pred[m] == c).sum()), int(m.sum())
        lo, hi = wilson(k, n)
        out.append({"batch": int(c), "recall": k / n if n else float("nan"), "n": n, "k": k, "lo": lo, "hi": hi})
    return out
