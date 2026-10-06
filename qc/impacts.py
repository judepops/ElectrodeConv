"""Battery-property sliders: measured microstructure changes -> "what the science expects" for a battery.

    python qc/impacts.py            # -> qc/processed/impacts.json  (needs qc/processed/verdicts.json)

Six properties (energy storage, charging speed, lifespan, first-charge loss, swelling, consistency). Each is a
weighted, cited combination of measured deltas, driven by the rule table qc/impact_rules.yaml; every number can be
recomputed by hand from the table and the verdict statistics. No language model touches it.

For one lot and one property:
  1. Per feature, from verdicts.json: delta (lot mean - baseline mean), its session-aware se and df, the baseline
     margin (1.5 x the baseline's site SD, "normal variation"), and the feature's trust level (yaml).
  2. Each rule gives the direction (sign), the literature support (confidence) and why (mechanism, citation).
     weight = confidence weight x trust weight.
  3. Monte Carlo: each delta is drawn from a scaled Student-t, turned into margin units, clipped to +-3 so one
     extreme feature cannot swamp the rest; score = sum(weight x sign x x) / sum(weight).
  4. Reported: mean score, 90 % interval, p_higher = P(score > +0.5), p_lower = P(score < -0.5), a label, and the
     contributions. Positive always means MORE of the property.
"Consistency" also uses "spread" terms: the lot's site-to-site SD over the baseline's, log scale, a doubling = 1.

New here: a point score per SPOT (level terms only, each spot against the baseline mean), so every batch gets a
median and an interquartile range per property, and the baseline its own band.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qc.features_table import OUT as TABLE  # noqa: E402
from qc.verdict import OUT as VERDICTS, clean  # noqa: E402
from preprocessing.preprocess import PROCESSED_NAME  # noqa: E402

RULES_PATH = Path(__file__).with_name("impact_rules.yaml")
OUT = ROOT / "qc" / PROCESSED_NAME / "impacts.json"
PROPERTY_ORDER = ["capacity", "charge_speed", "lifespan", "first_charge_loss", "swelling", "uniformity"]
PROPERTY_FIELDS = ["id", "label", "question", "higher_label", "lower_label", "blurb"]
RULE_KINDS = {"level", "spread"}
ESTIMATE_KINDS = {"si_capacity", "bruggeman_resistance", "relative_change"}


# ---- rules -----------------------------------------------------------------------------------------------------
def _is_excluded(feature, rules):
    if feature in set(rules.get("excluded_features") or []):
        return True
    return any(feature.startswith(prefix) for prefix in rules.get("excluded_prefixes") or [])


def load_rules(path=RULES_PATH):
    """Read and check the rule table, so a typo fails loudly instead of silently mis-weighting."""
    with open(path) as f:
        rules = yaml.safe_load(f)
    conf_w, trust_w = rules["weights"]["confidence"], rules["weights"]["trust"]
    for level in ("strong", "moderate", "low"):
        if level not in conf_w:
            raise ValueError(f"impact rules: weights.confidence is missing '{level}'")
    for level in ("high", "medium", "low", "unknown"):
        if level not in trust_w:
            raise ValueError(f"impact rules: weights.trust is missing '{level}'")
    ids = [p.get("id") for p in rules["properties"]]
    if ids != PROPERTY_ORDER:
        raise ValueError(f"impact rules: properties must be {PROPERTY_ORDER} in this order, got {ids}")
    for prop in rules["properties"]:
        pid = prop["id"]
        for field in PROPERTY_FIELDS:
            if not str(prop.get(field) or "").strip():
                raise ValueError(f"impact rules: property {pid} has no '{field}'")
        seen = set()
        for rule in prop.get("rules") or []:
            rule.setdefault("kind", "level")
            feature = rule.get("feature")
            where = f"impact rules: {pid} / {feature}"
            if not feature:
                raise ValueError(f"impact rules: {pid} has a rule without a feature")
            if rule["kind"] not in RULE_KINDS:
                raise ValueError(f"{where}: unknown kind '{rule['kind']}'")
            if rule.get("sign") not in (1, -1):
                raise ValueError(f"{where}: sign must be +1 or -1")
            if rule.get("confidence") not in conf_w:
                raise ValueError(f"{where}: confidence must be one of {list(conf_w)}")
            if not str(rule.get("mechanism") or "").strip() or not str(rule.get("citation") or "").strip():
                raise ValueError(f"{where}: every rule needs a mechanism and a citation")
            if _is_excluded(feature, rules):
                raise ValueError(f"{where}: acquisition columns may not drive a battery property")
            key = (feature, rule["kind"])
            if key in seen:
                raise ValueError(f"{where}: listed twice in one property")
            seen.add(key)
        for est in prop.get("estimates") or []:
            if est.get("kind") not in ESTIMATE_KINDS:
                raise ValueError(f"impact rules: {pid} has an unknown estimate kind '{est.get('kind')}'")
            if not str(est.get("assumption") or "").strip():
                raise ValueError(f"impact rules: {pid} estimate '{est.get('label')}' needs an assumption")
    return rules


def properties(rules):
    return [{field: " ".join(str(prop[field]).split()) for field in PROPERTY_FIELDS} for prop in rules["properties"]]


def trust_from_rules(rules):
    """Trust per feature: the measured table (qc/feature_quality.py) when it exists, else the yaml's hand-set levels."""
    trust = {f: {"level": lvl, "source": "impact_rules.yaml"} for f, lvl in (rules.get("trust") or {}).items()}
    fq = Path(__file__).resolve().parent / PROCESSED_NAME / "feature_quality.json"
    if fq.exists():
        for f, r in json.loads(fq.read_text())["features"].items():
            trust[f] = {"level": r["trust"], "source": "feature_quality.json", "split_half_r": r["split_half_r"],
                        "mask_agreement": r["mask_agreement"], "session_r2": r["session_r2"]}
    return trust


# ---- helpers ---------------------------------------------------------------------------------------------------
def _num(x):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _round(x, digits=3):
    return None if x is None else round(float(x), digits)


def _text(s):
    return " ".join(str(s).split())


def _trust_weight(feature, trust, rules):
    level = (trust.get(feature) or {}).get("level") or "unknown"
    weights = rules["weights"]["trust"]
    return weights.get(level, weights["unknown"])


def _term_inputs(rule, batch_stats, baseline_summary, margin_ratio):
    """What one rule needs from the statistics, or None when the feature cannot be used for this lot."""
    feature = rule["feature"]
    st = (batch_stats.get("features") or {}).get(feature)
    base = baseline_summary.get(feature)
    if not st or not base:
        return None
    if rule["kind"] == "level":
        delta, se, margin = _num(st.get("delta")), _num(st.get("se")), _num(base.get("margin"))
        if delta is None or se is None or margin is None or margin <= 0 or se < 0:
            return None
        df = _num(st.get("df"))
        return {"delta": delta, "se": se, "df": df if df is not None and df > 0 else None, "margin": margin, "point": delta / margin}
    if batch_stats.get("is_baseline"):
        return None
    ratio, n_lot, n_ref = _num(st.get("spread_ratio")), _num(st.get("n")), _num(base.get("n"))
    if ratio is None or ratio <= 0 or n_lot is None or n_ref is None or n_lot < 2 or n_ref < 2:
        return None
    return {"log_ratio": math.log(ratio), "se": math.sqrt(1.0 / (2.0 * (n_lot - 1)) + 1.0 / (2.0 * (n_ref - 1))),
            "point": math.log(ratio) / math.log(margin_ratio)}


def _draw(rng, centre, se, df, n):
    if se == 0:
        return np.full(n, centre)
    z = rng.standard_t(df, size=n) if df is not None else rng.standard_normal(n)
    return centre + se * z


def _label(p_higher, p_lower, p_similar, p_above, p_below, thresholds):
    if p_higher >= thresholds["likely"]:
        return "likely_higher"
    if p_lower >= thresholds["likely"]:
        return "likely_lower"
    direction, floor = thresholds["direction"], thresholds["direction_min_meaningful"]
    if p_higher >= thresholds["possibly"] or (p_above >= direction and p_higher >= floor):
        return "possibly_higher"
    if p_lower >= thresholds["possibly"] or (p_below >= direction and p_lower >= floor):
        return "possibly_lower"
    if p_similar >= thresholds["similar"]:
        return "similar"
    return "unclear"


def _interval(x, ci):
    lo, hi = np.percentile(x, [50 * (1 - ci), 50 * (1 + ci)])
    return float(lo), float(hi)


def _estimate(est, delta_draws, baseline_summary, rng, ci):
    feature = est["feature"]
    d = delta_draws.get(feature)
    base = baseline_summary.get(feature) or {}
    if d is None:
        return None
    n = len(d)
    if est["kind"] == "si_capacity":
        c_lo, c_hi = est["c_si_phase"]
        values = d * (rng.uniform(c_lo, c_hi, n) - float(est["c_graphite"]))
    elif est["kind"] == "bruggeman_resistance":
        eps_base = _num(base.get("mean"))
        if eps_base is None or eps_base <= 0:
            return None
        a_lo, a_hi = est["alpha"]
        eps_lot = np.maximum(eps_base + d, 0.1 * eps_base)
        values = 100.0 * ((eps_lot / eps_base) ** (-rng.uniform(a_lo, a_hi, n)) - 1.0)
    else:
        mean = _num(base.get("mean"))
        if mean is None or mean == 0:
            return None
        values = 100.0 * d / abs(mean)
    lo, hi = _interval(values, ci)
    return {"label": _text(est["label"]), "unit": est["unit"], "value": _round(float(np.median(values)), 1),
            "lo": _round(lo, 1), "hi": _round(hi, 1), "assumption": _text(est["assumption"])}


# ---- one lot ---------------------------------------------------------------------------------------------------
def compute_impacts(batch_stats, trust, baseline_summary, rules, n_draws=20000, seed=0):
    """{property_id: {score, ci90, p_higher, p_lower, label, contributions, estimates, missing_features}}."""
    comp = rules["composite"]
    clip, band, ci = float(comp["clip_margin_units"]), float(comp["band"]), float(comp["ci"])
    margin_ratio = float(rules["spread"]["margin_ratio"])
    conf_w = rules["weights"]["confidence"]
    rng = np.random.default_rng(seed)
    terms = {}
    for prop in rules["properties"]:
        for rule in prop.get("rules") or []:
            key = (rule["feature"], rule.get("kind", "level"))
            if key not in terms:
                terms[key] = _term_inputs(dict(rule, kind=key[1]), batch_stats, baseline_summary, margin_ratio)
    draws_margin, delta_draws = {}, {}
    for key in sorted(terms):
        t = terms[key]
        if t is None:
            continue
        if key[1] == "level":
            d = _draw(rng, t["delta"], t["se"], t["df"], n_draws)
            delta_draws[key[0]] = d
            draws_margin[key] = d / t["margin"]
        else:
            draws_margin[key] = _draw(rng, t["log_ratio"], t["se"], None, n_draws) / math.log(margin_ratio)
    out = {}
    for prop in rules["properties"]:
        used, missing = [], []
        for rule in prop.get("rules") or []:
            key = (rule["feature"], rule.get("kind", "level"))
            if terms.get(key) is None:
                if rule["feature"] not in missing:
                    missing.append(rule["feature"])
                continue
            used.append((rule, key, conf_w[rule["confidence"]] * _trust_weight(rule["feature"], trust, rules)))
        estimates = [e for e in (_estimate(est, delta_draws, baseline_summary, rng, ci) for est in prop.get("estimates") or []) if e]
        if not used:
            out[prop["id"]] = {"score": None, "ci90": None, "p_higher": None, "p_lower": None, "label": "unclear",
                               "contributions": [], "estimates": estimates, "missing_features": missing}
            continue
        total_w = sum(w for _, _, w in used)
        score = np.zeros(n_draws)
        contributions = []
        for rule, key, weight in used:
            score += weight * rule["sign"] * np.clip(draws_margin[key], -clip, clip)
            point = terms[key]["point"]
            contributions.append({
                "feature": rule["feature"], "kind": key[1], "sign": rule["sign"], "weight": _round(weight),
                "delta_margin": _round(point),
                "contribution": _round(weight * rule["sign"] * max(-clip, min(clip, point)) / total_w),
                "mechanism": _text(rule["mechanism"]), "citation": _text(rule["citation"]), "confidence": rule["confidence"],
                "trust": (trust.get(rule["feature"]) or {}).get("level", "unknown")})
        score /= total_w
        contributions.sort(key=lambda c: -abs(c["contribution"]))
        p_higher, p_lower = float(np.mean(score > band)), float(np.mean(score < -band))
        p_above, p_below = float(np.mean(score > 0)), float(np.mean(score < 0))
        lo, hi = _interval(score, ci)
        out[prop["id"]] = {
            "score": _round(float(np.mean(score))), "ci90": [_round(lo), _round(hi)],
            "p_higher": _round(p_higher), "p_lower": _round(p_lower),
            "p_above_zero": _round(p_above), "p_below_zero": _round(p_below),
            "label": _label(p_higher, p_lower, 1.0 - p_higher - p_lower, p_above, p_below, rules["labels"]),
            "contributions": contributions, "estimates": estimates, "missing_features": missing}
    return out


# ---- glue to verdicts.json and the per-spot bands ----------------------------------------------------------------
def batch_stats_from_verdict(lot):
    feats = {f: {"delta": r.get("delta"), "se": r.get("se"), "df": r.get("df"), "spread_ratio": r.get("spread_ratio"),
                 "n": r.get("n")} for f, r in lot["kpis"].items() if "skip" not in r}
    return {"features": feats, "is_baseline": False, "n": lot["n_sites"]}


def baseline_from_verdict(v):
    return {f: {"margin": b["margin"], "mean": b["mean"], "sd": b["sd"], "n": b["n"]} for f, b in v["baseline"].items()}


def spot_scores(table, baseline, rules, trust):
    """Point score per spot and property (level terms only): where each spot sits against the baseline mean."""
    comp_clip = float(rules["composite"]["clip_margin_units"])
    conf_w = rules["weights"]["confidence"]
    rows = []
    for r in table.itertuples():
        row = {"batch": r.batch, "sample_id": r.sample_id, "session": int(r.session)}
        for prop in rules["properties"]:
            num = den = 0.0
            for rule in prop.get("rules") or []:
                if rule.get("kind", "level") != "level":
                    continue
                f, base = rule["feature"], baseline.get(rule["feature"])
                v = getattr(r, f, None)
                if base is None or v is None or not math.isfinite(float(v)) or base["margin"] <= 0:
                    continue
                w = conf_w[rule["confidence"]] * _trust_weight(f, trust, rules)
                num += w * rule["sign"] * max(-comp_clip, min(comp_clip, (float(v) - base["mean"]) / base["margin"]))
                den += w
            row[prop["id"]] = num / den if den else None
        rows.append(row)
    return pd.DataFrame(rows)


def batch_bands(scores):
    out = {}
    for b, g in scores.groupby("batch"):
        out[b] = {}
        for pid in PROPERTY_ORDER:
            v = g[pid].dropna()
            out[b][pid] = {"n": int(len(v)), "median": _round(v.median()), "q25": _round(v.quantile(0.25)),
                           "q75": _round(v.quantile(0.75)), "min": _round(v.min()), "max": _round(v.max())}
    return out


def main():
    rules = load_rules()
    print(f"{RULES_PATH.name}: OK")
    v = json.loads(VERDICTS.read_text())
    table = pd.read_csv(TABLE)
    trust, baseline = trust_from_rules(rules), baseline_from_verdict(v)
    lots = {label: compute_impacts(batch_stats_from_verdict(lot), trust, baseline, rules) for label, lot in v["lots"].items()}
    scores = spot_scores(table, baseline, rules, trust)
    out = {"properties": properties(rules), "lots": lots, "spot_scores": scores.to_dict("records"), "bands": batch_bands(scores),
           "rules": {p["id"]: [{"feature": r["feature"], "kind": r.get("kind", "level"), "sign": r["sign"],
                                "confidence": r["confidence"], "trust": (trust.get(r["feature"]) or {}).get("level", "unknown"),
                                "mechanism": _text(r["mechanism"]), "citation": _text(r["citation"])}
                               for r in p.get("rules") or []] for p in rules["properties"]},
           "weights": rules["weights"], "composite": rules["composite"]}
    OUT.write_text(json.dumps(clean(out), indent=1))
    for label, imp in lots.items():
        print(f"\n{label}")
        for pid in PROPERTY_ORDER:
            r = imp[pid]
            sc = "   n/a" if r["score"] is None else f"{r['score']:+6.2f}"
            ci = "" if r["ci90"] is None else f" [{r['ci90'][0]:+.2f}, {r['ci90'][1]:+.2f}]"
            top = ", ".join(f"{c['feature']} {c['contribution']:+.2f}" for c in r["contributions"][:2])
            print(f"  {pid:18s} {sc}{ci:18s} {r['label']:16s} {top}")
    print("\nbands (median [q25, q75]):")
    for b, props in out["bands"].items():
        print(f"  {b:8s} " + "  ".join(f"{pid[:8]} {d['median']:+.2f} [{d['q25']:+.2f},{d['q75']:+.2f}]" for pid, d in props.items() if d["median"] is not None))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
