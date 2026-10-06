"""Accept / investigate / reject an incoming lot against the Batch_3 baseline, from the spot feature table.

    python qc/verdict.py            # -> qc/processed/verdicts.json (Batch_1, Batch_2, each test spot alone)

The rule, in order (a trimmed port of the old repo's analysis/verdict.py, same statistics, fewer gates):
  1. For every feature: delta = lot mean - baseline mean; a session-aware standard error (sites of one imaging
     session are not independent: one-way random-effects ANOVA on the baseline gives the within- and the
     between-session variance, Satterthwaite df); a 90 % CI; the margin = 1.5 x the baseline's site SD
     ("normal variation"). Zone: EQUIV if the CI sits inside +-margin, BEYOND if it sits outside, else INCONCL.
  2. Tier 1 (si_solid_frac, porosity_frac) decides. REJECT needs a Tier-1 feature BEYOND after Holm, the same
     sign in every session shared with the baseline, and a feature allowed to reject: only si_solid_frac (the old
     audit found porosity moves under a black-level shift, so a porosity shift leads to INVESTIGATE, never REJECT).
  3. Tier 2 (si_agglom_d50_um, interface_density_per_um) is a quality range: >= 6 of 7 sites inside the baseline
     mean +- 2.86 SD. Everything else is a diagnostic: shown, never decisive.
  4. ACCEPT: every Tier-1 zone EQUIV and no flag (Tier 2, heterogeneity). CONDITIONAL ACCEPT: nothing BEYOND, every
     |delta| inside the margin, every P(|delta| > margin) < 0.2. Otherwise INVESTIGATE, always with named reasons.
  5. Fewer than 3 sites: INSUFFICIENT DATA (the per-feature numbers are still shown).
Nothing here was tuned on Batch_1 or Batch_2; the thresholds are the ones frozen in the old repo.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qc.features_table import COLUMNS, OUT as TABLE  # noqa: E402
from preprocessing.preprocess import PROCESSED_NAME  # noqa: E402

OUT = ROOT / "qc" / PROCESSED_NAME / "verdicts.json"
BASELINE = "Batch_3"
TIER1 = ["si_solid_frac", "porosity_frac"]
REJECT_ALLOWED = ["si_solid_frac"]
TIER2 = ["si_agglom_d50_um", "interface_density_per_um"]
DIAGNOSTICS = [f for f in COLUMNS if f not in TIER1 + TIER2]
ALPHA, MARGIN_MULT, R2_MULT = 0.05, 1.5, 2.0
TOL_K, MIN_INSIDE, COND_P, MIN_SITES = 2.86, 0.857, 0.2, 3
DRAWS, SEED = 50000, 0
EQUIV, BEYOND, INCONCL = "EQUIV", "BEYOND", "INCONCL"

REASONS = {   # key -> (label, action)
    "reject_blocked": ("Shift beyond tolerance, REJECT not confirmed",
                       "Confirm in a session shared with >= 3 retained-reference sites"),
    "si_phase": ("Si-phase anomaly (fraction, size or clustering)",
                 "EDS on >= 3 bright particles from flagged and reference sites; ask the supplier for the Si-phase CoA"),
    "heterogeneity": ("Heterogeneity", "More sites from different electrode positions; check the mixing record"),
    "possible_shift": ("Possible shift beyond tolerance (not established)", "Image more sites"),
    "shifted_within": ("Shifted within tolerance", "Release to monitoring; image the next 2 lots alongside a reference"),
    "precision": ("Precision-limited (CI wider than 2 margins)", "Image more sites, in >= 2 sessions"),
    "tier2": ("Tier-2 quality range failed", "Review the flagged sites' images; re-measure them next to the baseline"),
    "acquisition": ("Session-matched contrasts disagree with the lot mean",
                    "Re-image with a retained reference in the same session"),
}
ACTIONS = {
    "ACCEPT": "Release the lot.",
    "CONDITIONAL ACCEPT": "Release to monitoring; image the next 2 lots alongside a retained reference.",
    "REJECT": "Reject the lot; send the driving KPI and its CI to the supplier.",
    "INSUFFICIENT DATA": "Image at least 3 sites, from >= 2 sessions or next to retained-reference sites.",
    "INVESTIGATE": "Hold the lot until the named reason is resolved.",
}


# ----------------------------------------------------------------------------------------------------
# error model (ported)
# ----------------------------------------------------------------------------------------------------
def variance_components(y, sess):
    """One-way random-effects ANOVA by method of moments: site-within-session and session components."""
    y, sess = np.asarray(y, float), np.asarray(sess)
    groups = [y[sess == s] for s in np.unique(sess)]
    a, n = len(groups), len(y)
    sizes = np.array([len(g) for g in groups])
    grand = y.mean()
    ss_w = sum(((g - g.mean()) ** 2).sum() for g in groups)
    ss_b = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
    df_w, df_b = n - a, a - 1
    ms_w = ss_w / df_w if df_w > 0 else math.nan
    ms_b = ss_b / df_b if df_b > 0 else math.nan
    n0 = (n - (sizes ** 2).sum() / n) / df_b if df_b > 0 else math.nan
    s2_s = max(0.0, (ms_b - ms_w) / n0) if df_b > 0 and df_w > 0 else math.nan
    return {"ms_w": ms_w, "ms_b": ms_b, "df_w": df_w, "df_b": df_b, "n0": n0, "n_sessions": a,
            "sigma_w": math.sqrt(ms_w) if ms_w == ms_w else math.nan,
            "sigma_s": math.sqrt(s2_s) if s2_s == s2_s else math.nan,
            "icc": s2_s / (s2_s + ms_w) if (s2_s + ms_w) > 0 else math.nan}


def session_weight(sess):
    counts = np.unique(sess, return_counts=True)[1]
    return float((counts ** 2).sum() / counts.sum() ** 2)


def satterthwaite(terms):
    num = sum(c * m for c, m, _ in terms) ** 2
    den = sum((c * m) ** 2 / d for c, m, d in terms if d > 0 and c * m != 0)
    return num / den if den > 0 else math.inf


class ErrorModel:
    """Variance of (lot mean - baseline mean) from the mean squares: point SE + df, and posterior draws."""

    def __init__(self, vc, lot_sess, ref_sess, lot_ms, lot_df):
        self.vc, self.lot_ms, self.lot_df = vc, lot_ms, lot_df
        self.n, self.n_ref = len(lot_sess), len(ref_sess)
        self.c_lot, self.c_ref = session_weight(lot_sess), session_weight(ref_sess)

    def variance(self, ms_w, ms_b, ms_lot):
        s2_s = np.maximum(0.0, (ms_b - ms_w) / self.vc["n0"])
        v_ref = ms_w / self.n_ref + s2_s * self.c_ref
        v_lot = ms_w / self.n + s2_s * self.c_lot
        if ms_lot is None:
            return v_ref + v_lot, np.zeros_like(v_lot, bool)
        own = ms_lot / self.n
        return v_ref + np.maximum(v_lot, own), own > v_lot

    def point(self):
        vc = self.vc
        var, own = self.variance(np.float64(vc["ms_w"]), np.float64(vc["ms_b"]),
                                 None if self.lot_ms is None else np.float64(self.lot_ms))
        own = bool(own)
        s_pos = (vc["ms_b"] - vc["ms_w"]) / vc["n0"] > 0
        cw = 1 / self.n_ref - (self.c_ref / vc["n0"] if s_pos else 0)
        cb = self.c_ref / vc["n0"] if s_pos else 0
        if own:
            terms = [(cw, vc["ms_w"], vc["df_w"]), (cb, vc["ms_b"], vc["df_b"]), (1 / self.n, self.lot_ms, self.lot_df)]
        else:
            cw += 1 / self.n - (self.c_lot / vc["n0"] if s_pos else 0)
            cb += self.c_lot / vc["n0"] if s_pos else 0
            terms = [(cw, vc["ms_w"], vc["df_w"]), (cb, vc["ms_b"], vc["df_b"])]
        return math.sqrt(float(var)), satterthwaite(terms), own

    def draws(self, rng, size):
        vc = self.vc

        def draw(ms, df):
            return ms * df / rng.chisquare(df, size) if df > 0 else np.full(size, ms)
        ms_w, ms_b = draw(vc["ms_w"], vc["df_w"]), draw(vc["ms_b"], vc["df_b"])
        ms_lot = draw(self.lot_ms, self.lot_df) if self.lot_ms is not None else None
        return self.variance(ms_w, ms_b, ms_lot)[0]


# ----------------------------------------------------------------------------------------------------
# one feature
# ----------------------------------------------------------------------------------------------------
def compare_kpi(name, lot, ref, seed=0):
    """lot / ref: DataFrames with [name, 'session', 'sample_id'] -> result dict (or {'skip': why})."""
    lot, ref = lot.dropna(subset=[name]), ref.dropna(subset=[name])
    y_lot, y_ref = lot[name].to_numpy(float), ref[name].to_numpy(float)
    s_lot, s_ref = lot["session"].to_numpy(), ref["session"].to_numpy()
    out = {"feature": name, "n": len(y_lot), "n_ref": len(y_ref), "n_sessions": int(len(np.unique(s_lot)))}
    if len(y_lot) < 1 or len(y_ref) < 3:
        return out | {"skip": f"too few values ({len(y_lot)} lot, {len(y_ref)} baseline)"}
    sd_ref = float(np.std(y_ref, ddof=1))
    if not sd_ref > 0:
        return out | {"skip": "the baseline has no spread"}
    vc = variance_components(y_ref, s_ref)
    margin = MARGIN_MULT * sd_ref
    d_hat = float(y_lot.mean() - y_ref.mean())
    lot_df = len(y_lot) - 1
    lot_ms = float(np.var(y_lot, ddof=1)) if lot_df > 0 else None
    rng = np.random.default_rng(SEED + seed)
    if vc["ms_w"] == vc["ms_w"] and vc["df_b"] > 0:
        model = ErrorModel(vc, s_lot, s_ref, lot_ms, lot_df)
        se, df, own = model.point()
        post = d_hat + np.sqrt(model.draws(rng, DRAWS)) * rng.standard_normal(DRAWS)
        mode = "session-aware"
    else:                                              # every baseline site its own session: plain Welch
        se, df, own = sd_ref * math.sqrt(1 / len(y_lot) + 1 / len(y_ref)), len(y_ref) - 1, False
        post = d_hat + se * rng.standard_t(df, DRAWS)
        mode = "welch"
    tq = stats.t.ppf(1 - ALPHA, df) if math.isfinite(df) else stats.norm.ppf(1 - ALPHA)
    lo, hi = d_hat - tq * se, d_hat + tq * se
    tdist = stats.t(df) if math.isfinite(df) else stats.norm()
    zone = EQUIV if (lo > -margin and hi < margin) else BEYOND if (lo > margin or hi < -margin) else INCONCL
    shared = [s for s in np.unique(s_lot) if (s_ref == s).any()]
    contrasts = [{"session": int(s), "n_lot": int((s_lot == s).sum()), "n_ref": int((s_ref == s).sum()),
                  "diff": float(y_lot[s_lot == s].mean() - y_ref[s_ref == s].mean())} for s in shared]
    lo_t, hi_t = y_ref.mean() - TOL_K * sd_ref, y_ref.mean() + TOL_K * sd_ref
    inside = (y_lot >= lo_t) & (y_lot <= hi_t)
    out |= {
        "mode": mode, "baseline_mean": float(y_ref.mean()), "baseline_sd": sd_ref, "baseline_sessions": vc["n_sessions"],
        "lot_mean": float(y_lot.mean()), "lot_sd": float(np.std(y_lot, ddof=1)) if lot_df > 0 else None,
        "spread_ratio": float(np.std(y_lot, ddof=1) / sd_ref) if lot_df > 0 else None,
        "sigma_w": vc["sigma_w"], "sigma_s": vc["sigma_s"], "icc": vc["icc"],
        "delta": d_hat, "se": se, "df": df, "lot_own_variance": own, "ci_lo": lo, "ci_hi": hi, "margin": margin,
        "delta_sd": d_hat / sd_ref, "ci_lo_sd": lo / sd_ref, "ci_hi_sd": hi / sd_ref, "margin_sd": MARGIN_MULT,
        "p_beyond_margin": float(np.mean(np.abs(post) > margin)), "zone": zone,
        "p_reject_r1": float(tdist.sf((abs(d_hat) - margin) / se)),
        "p_reject_r2": float(tdist.sf((abs(d_hat) - R2_MULT * margin) / se)),
        "p_zero": float(2 * tdist.sf(abs(d_hat) / se)),
        "contrasts": contrasts, "sign_ok": all(np.sign(c["diff"]) == np.sign(d_hat) for c in contrasts),
        "matched_pooled": (float(sum(c["diff"] / (1 / c["n_lot"] + 1 / c["n_ref"]) for c in contrasts)
                                 / sum(1 / (1 / c["n_lot"] + 1 / c["n_ref"]) for c in contrasts)) if contrasts else None),
        "range": [float(lo_t), float(hi_t)], "n_inside": int(inside.sum()),
        "outside_sites": [f"{sid} ({int(s)})" for sid, ok, s in zip(lot["sample_id"], inside, s_lot) if not ok],
        "values": [{"sample_id": sid, "session": int(s), "value": float(v)} for sid, s, v in zip(lot["sample_id"], s_lot, y_lot)],
    }
    return out


def tier2_check(r):
    need = math.ceil(MIN_INSIDE * r["n"] - 1e-9)
    return r["n_inside"] >= need, need


def heterogeneity(name, lot, ref):
    """Brown-Forsythe test of lot vs baseline spread, with a 90 % interval of the SD ratio."""
    a, b = lot[name].dropna().to_numpy(float), ref[name].dropna().to_numpy(float)
    if len(a) < 3 or len(b) < 3:
        return None
    p = float(stats.levene(a, b, center="median").pvalue)
    ratio = float(np.var(a, ddof=1) / np.var(b, ddof=1))
    d1, d2 = len(a) - 1, len(b) - 1
    ci = (ratio / stats.f.ppf(0.95, d1, d2), ratio / stats.f.ppf(0.05, d1, d2))
    return {"feature": name, "sd_ratio": math.sqrt(ratio), "sd_ratio_ci90": [math.sqrt(ci[0]), math.sqrt(ci[1])], "p_bf": p}


def holm(p):
    p = np.asarray(p, float)
    order, adj, running = np.argsort(p), np.empty_like(p), 0.0
    for i, j in enumerate(order):
        running = max(running, (len(p) - i) * p[j])
        adj[j] = min(1.0, running)
    return adj


def bh(p):
    p = np.asarray(p, float)
    if len(p) == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    q = np.empty_like(p)
    q[order] = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1)
    return q


# ----------------------------------------------------------------------------------------------------
# the decision
# ----------------------------------------------------------------------------------------------------
def decide(t1, t2, diag, het, n_sites):
    reasons = []

    def add(key, detail, action=None):
        label, default = REASONS[key]
        for r in reasons:
            if r["key"] == key:
                r["detail"] += f"; {detail}"
                return
        reasons.append({"key": key, "label": label, "detail": detail, "action": action or default})

    reject = []
    for r in t1:
        allowed = r["feature"] in REJECT_ALLOWED
        r["r1"] = bool(r["p_reject_r1_holm"] < ALPHA and r["sign_ok"] and allowed)
        r["r2"] = bool(r["p_reject_r2_holm"] < ALPHA and allowed)
        if r["r1"] or r["r2"]:
            reject.append(r)
        elif r["p_reject_r1_holm"] < ALPHA:
            blocked = [w for w, ok in [("feature not allowed to REJECT (moves under a black-level shift)", allowed),
                                       ("sign differs in a session-matched contrast", r["sign_ok"])] if not ok]
            add("reject_blocked", f"{r['feature']} BEYOND (Holm p = {r['p_reject_r1_holm']:.3g}); blocked by: {', '.join(blocked)}")
    for r in t1:
        si = r["feature"].startswith("si_")
        if si and (r["zone"] == BEYOND or abs(r["delta"]) > r["margin"]):
            add("si_phase", f"{r['feature']} delta {r['delta']:+.4g} beyond the margin {r['margin']:.3g} "
                            f"(P(|delta| > margin) = {r['p_beyond_margin']:.2f})")
        if r["zone"] == INCONCL:
            if abs(r["delta"]) > r["margin"]:
                add("possible_shift", f"{r['feature']} delta {r['delta']:+.4g} beyond the margin {r['margin']:.3g}, CI reaches inside")
            elif r["p_beyond_margin"] >= COND_P:
                add("shifted_within", f"{r['feature']} delta {r['delta']:+.4g}, P(|delta| > margin) = {r['p_beyond_margin']:.2f}")
            if r["ci_hi"] - r["ci_lo"] > 2 * r["margin"] and r["p_beyond_margin"] >= COND_P:
                add("precision", f"{r['feature']} CI width {r['ci_hi'] - r['ci_lo']:.3g} > 2 margins ({2 * r['margin']:.3g})")
        if r["zone"] == BEYOND and not r["p_reject_r1_holm"] < ALPHA:
            add("possible_shift", f"{r['feature']} CI beyond the margin, but not after Holm across Tier 1 (p = {r['p_reject_r1_holm']:.3g})")
        pooled = r["matched_pooled"]
        if r["zone"] != EQUIV and pooled is not None and np.sign(pooled) != np.sign(r["delta"]):
            add("acquisition", f"{r['feature']}: the session-matched contrasts (pooled {pooled:+.4g} over "
                               f"{len(r['contrasts'])} session(s)) point the other way from delta {r['delta']:+.4g}")
    t2_fail = [r for r in t2 if not r["tier2_pass"]]
    for r in t2_fail:
        detail = f"{r['feature']}: {r['n_inside']}/{r['n']} sites inside (need {r['tier2_need']}); outside: {', '.join(r['outside_sites'])}"
        add("si_phase" if r["feature"].startswith("si_") else "tier2", detail)
    for r in diag:
        if r["feature"].startswith("si_") and r.get("q_screen", 1) < ALPHA:
            add("si_phase", f"diagnostic {r['feature']} delta {r['delta']:+.4g} (screen q = {r['q_screen']:.3g})")
    het_flags = [h for h in het if h["flag"]]
    for h in het_flags:
        add("heterogeneity", f"{h['feature']}: lot SD {h['sd_ratio']:.2f}x the baseline's (Brown-Forsythe q = {h['q_bf']:.3g})")

    order = list(REASONS)
    reasons.sort(key=lambda r: order.index(r["key"]))
    if n_sites < MIN_SITES:
        return "INSUFFICIENT DATA", reasons
    if reject:
        r = reject[0]
        reasons.insert(0, {"key": "reject", "label": f"REJECT via {'R2 (large effect)' if r['r2'] else 'R1 (standard)'}: {r['feature']}",
                           "detail": f"delta {r['delta']:+.4g}, 90% CI [{r['ci_lo']:+.4g}, {r['ci_hi']:+.4g}], margin {r['margin']:.3g}",
                           "action": ACTIONS["REJECT"]})
        return "REJECT", reasons
    flags = bool(t2_fail or het_flags)
    if all(r["zone"] == EQUIV for r in t1) and not flags:
        return "ACCEPT", reasons
    if (not any(r["zone"] == BEYOND for r in t1) and not flags
            and all(abs(r["delta"]) <= r["margin"] for r in t1) and all(r["p_beyond_margin"] < COND_P for r in t1)):
        return "CONDITIONAL ACCEPT", reasons
    if not reasons:
        r = max(t1, key=lambda r: r["p_beyond_margin"])
        add("shifted_within", f"{r['feature']} delta {r['delta']:+.4g}, P(|delta| > margin) = {r['p_beyond_margin']:.2f}")
    return "INVESTIGATE", reasons


def judge(df, lot_mask, label):
    lot, ref = df[lot_mask], df[df.batch == BASELINE]
    cols = ["session", "sample_id"]
    kpis = {f: compare_kpi(f, lot[[f] + cols], ref[[f] + cols], seed=i) for i, f in enumerate(COLUMNS)}
    t1 = [kpis[f] for f in TIER1 if "skip" not in kpis[f]]
    t2 = [kpis[f] for f in TIER2 if "skip" not in kpis[f]]
    diag = [kpis[f] for f in DIAGNOSTICS if "skip" not in kpis[f]]
    for r, p1, p2 in zip(t1, holm([r["p_reject_r1"] for r in t1]), holm([r["p_reject_r2"] for r in t1])):
        r["p_reject_r1_holm"], r["p_reject_r2_holm"] = float(p1), float(p2)
    for r in t2:
        r["tier2_pass"], r["tier2_need"] = tier2_check(r)
    for r, q in zip(diag, bh([r["p_zero"] for r in diag])):
        r["q_screen"] = float(q)
    het = [h for h in (heterogeneity(f, lot, ref) for f in TIER1) if h]
    for h, q in zip(het, bh([h["p_bf"] for h in het])):
        h["q_bf"], h["flag"] = float(q), bool(q < ALPHA)
    for f in COLUMNS:
        kpis[f]["tier"] = "tier1" if f in TIER1 else "tier2" if f in TIER2 else "diagnostic"
        kpis[f]["can_reject"] = f in REJECT_ALLOWED
    verdict, reasons = decide(t1, t2, diag, het, len(lot))
    return {"lot": label, "verdict": verdict, "action": ACTIONS[verdict], "reasons": reasons, "n_sites": int(len(lot)),
            "n_sessions": int(lot.session.nunique()), "sites": lot.sample_id.tolist(),
            "sessions": [int(s) for s in lot.session], "kpis": kpis, "heterogeneity": het}


def clean(o):
    """JSON-safe: numpy scalars -> python, NaN/inf -> None (JSON.parse in the browser rejects NaN)."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return float(o) if math.isfinite(float(o)) else None
    return o


def main():
    df = pd.read_csv(TABLE)
    ref = df[df.batch == BASELINE]
    lots = {"Batch_1": df.batch == "Batch_1", "Batch_2": df.batch == "Batch_2"}
    for sid in df[df.batch == "Test"].sample_id:
        lots[f"Test/{sid}"] = (df.batch == "Test") & (df.sample_id == sid)
    out = {"baseline": {f: {"mean": float(ref[f].mean()), "sd": float(ref[f].std(ddof=1)),
                            "margin": MARGIN_MULT * float(ref[f].std(ddof=1)), "n": int(len(ref)),
                            "n_sessions": int(ref.session.nunique()),
                            "q25": float(ref[f].quantile(0.25)), "median": float(ref[f].median()), "q75": float(ref[f].quantile(0.75))}
                        for f in COLUMNS},
           "config": {"baseline": BASELINE, "tier1": TIER1, "reject_allowed": REJECT_ALLOWED, "tier2": TIER2,
                      "diagnostics": DIAGNOSTICS, "alpha": ALPHA, "margin_multiplier": MARGIN_MULT, "tolerance_k": TOL_K,
                      "min_inside_frac": MIN_INSIDE, "conditional_accept_p": COND_P, "min_sites": MIN_SITES},
           "lots": {label: judge(df, mask, label) for label, mask in lots.items()}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(clean(out), indent=1))
    for label, v in out["lots"].items():
        print(f"\n{label}: {v['verdict']}  ({v['n_sites']} sites, {v['n_sessions']} sessions)")
        for f in TIER1 + TIER2:
            r = v["kpis"][f]
            if "skip" in r:
                print(f"  {f:26s} skipped: {r['skip']}")
            else:
                print(f"  {f:26s} delta {r['delta_sd']:+.2f} SD  CI [{r['ci_lo_sd']:+.2f}, {r['ci_hi_sd']:+.2f}]  margin +-{MARGIN_MULT}  {r['zone']}"
                      + (f"  inside {r['n_inside']}/{r['n']}" if f in TIER2 else ""))
        for r in v["reasons"]:
            print(f"  - {r['label']}: {r['detail']}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
