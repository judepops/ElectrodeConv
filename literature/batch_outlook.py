"""Which batch looks best for a customer, and why: measured feature shifts x what the papers say they do.

    python literature/batch_outlook.py        # -> literature/batch_outlook.json, literature/BATCH_OUTLOOK.md

Reads   dashboard/site/pipeline.js   the results already computed by qc/verdict.py and cnn/explain.py: how far each
                                     feature of Batch_1 and Batch_2 sits from Batch_3 (in Batch_3 standard deviations,
                                     with a 90 % interval), and how much the network leans on each feature
        literature/evidence.json     for each feature and battery outcome, which way the papers say it goes
Runs nothing else: no model, no search, no image processing.

The sum, for one batch and one outcome (say Batch_1, charging speed):
    for every feature whose direction the papers agree on:
        effect = (shift of the feature, in Batch_3 SDs, clipped to +-3) x (+1 if papers say "more", -1 if "less")
                 x evidence weight (number of papers / 5, at most 1)
    features that measure the same thing (e.g. the two silicon particle sizes) are averaged first, and a feature
    that runs opposite to its concept (`inverse` in evidence_terms.yaml) is flipped
    outcome score = sum of effects / sum of weights
Batch_3 is the reference, so its score is 0 by construction. The uncertainty comes from the feature shifts: each is
redrawn from its interval 20,000 times and the scores recomputed.

"Best for a customer" needs a view of what is good. The one used here: more capacity, faster charging, longer life
and more uniformity are good; more first-charge loss and more swelling are bad. All six count equally. That is a
choice, written in GOOD below; change it and re-run.

This is a literature-informed expectation, not a measurement. There is no cycling data for these batches.
"""
import json
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GOOD = {"capacity": 1, "charge_speed": 1, "lifespan": 1, "first_charge_loss": -1, "swelling": -1, "uniformity": 1}
NAMES = {"capacity": "Energy storage", "charge_speed": "Charging speed", "lifespan": "Lifespan",
         "first_charge_loss": "First-charge loss", "swelling": "Swelling", "uniformity": "Uniformity"}
CLIP, N_DRAWS, PAPERS_FOR_FULL_WEIGHT = 3.0, 20000, 5


def load_results():
    s = (ROOT / "dashboard" / "site" / "pipeline.js").read_text()
    return json.loads(s[s.index("{"):s.rindex("}") + 1])["results"]


def scenario(res, terms, direction, *, together=False, drop=(), weights=None, clear_only=False, seed=0):
    """The overall comparison re-run under one changed choice. Returns the chance each batch is the best of three."""
    rng, w_out = np.random.default_rng(seed), {**{o: 1.0 for o in GOOD}, **(weights or {})}
    overall = {}
    for b in ("Batch_1", "Batch_2"):
        kpis = res["verdict"]["lots"][b]["kpis"]
        z = rng.normal(size=N_DRAWS)                      # one shared draw = every feature moves together
        draws = {}
        for f, k in kpis.items():
            if "delta_sd" not in k:                       # skipped in the verdict (e.g. column not computed)
                continue
            sd = (k["ci_hi_sd"] - k["ci_lo_sd"]) / (2 * 1.645)
            clear = k["ci_lo_sd"] > 0 or k["ci_hi_sd"] < 0
            mean = k["delta_sd"] if (clear or not clear_only) else 0.0
            draws[f] = np.clip(mean + sd * (z if together else rng.normal(size=N_DRAWS)), -CLIP, CLIP)
        total, wsum = np.zeros(N_DRAWS), 0.0
        for o in GOOD:
            num, den = np.zeros(N_DRAWS), 0.0
            for c in terms["concepts"]:
                ev = direction.get((c["id"], o))
                feats = [f for f in c["features"] if f in draws]
                if not ev or ev["consensus"] not in ("more", "less") or not feats or c.get("outlook") is False or c["id"] in drop:
                    continue
                sign, w = (1 if ev["consensus"] == "more" else -1), min(1.0, ev["n_papers"] / PAPERS_FOR_FULL_WEIGHT)
                d = np.mean([(-1 if f in c.get("inverse", []) else 1) * draws[f] for f in feats], axis=0)
                num, den = num + w * sign * d, den + w
            total, wsum = total + w_out[o] * GOOD[o] * (num / den if den else 0), wsum + w_out[o]
        overall[b] = total / wsum
    best = np.vstack([overall["Batch_1"], overall["Batch_2"], np.zeros(N_DRAWS)]).argmax(0)
    return {b: round(float(np.mean(best == i)), 2) for i, b in enumerate(("Batch_1", "Batch_2", "Batch_3"))}


def main():
    res = load_results()
    terms = yaml.safe_load((HERE / "evidence_terms.yaml").read_text())
    evidence = json.loads((HERE / "evidence.json").read_text())["pairs"]
    labels = res["feature_labels"]
    concept_of = {f: c["id"] for c in terms["concepts"] for f in c["features"]}
    direction = {(p["concept"], p["outcome"]): p for p in evidence}

    # how much the network leans on each named feature when it calls the batch (mean |contribution| over spots)
    lean = {}
    for spot in ((res.get("explain") or {}).get("spots") or {}).values():   # absent on a V2 page build
        for f in spot["decomposition"]["features"]:
            lean.setdefault(f["feature"], []).append(abs(f["contribution"]))
    lean = {f: float(np.mean(v)) for f, v in lean.items()}
    lean_rank = {f: i + 1 for i, f in enumerate(sorted(lean, key=lean.get, reverse=True))}

    rng = np.random.default_rng(0)
    batches, out = ["Batch_1", "Batch_2"], {"reference": "Batch_3", "good": GOOD, "features": {}, "batches": {}}
    draws = {}                                                   # batch -> outcome -> N_DRAWS scores
    for b in batches:
        kpis = res["verdict"]["lots"][b]["kpis"]
        shifts = {}
        for f, k in kpis.items():
            if "delta_sd" not in k:                       # skipped in the verdict (e.g. column not computed)
                continue
            sd = (k["ci_hi_sd"] - k["ci_lo_sd"]) / (2 * 1.645)   # the interval is 90 %
            shifts[f] = {"shift_sd": k["delta_sd"], "ci90": [k["ci_lo_sd"], k["ci_hi_sd"]], "zone": k["zone"],
                         "clear": k["ci_lo_sd"] > 0 or k["ci_hi_sd"] < 0,
                         "draws": np.clip(rng.normal(k["delta_sd"], sd, N_DRAWS), -CLIP, CLIP)}
        out["features"][b] = {f: {k_: v for k_, v in s.items() if k_ != "draws"} for f, s in shifts.items()}
        out["batches"][b], draws[b] = {}, {}
        for o in GOOD:
            parts, num, den = [], np.zeros(N_DRAWS), 0.0
            for c in terms["concepts"]:
                ev = direction.get((c["id"], o))
                feats = [f for f in c["features"] if f in shifts]
                if not ev or ev["consensus"] not in ("more", "less") or not feats or c.get("outlook") is False:
                    continue
                inv = {f: -1 if f in c.get("inverse", []) else 1 for f in feats}   # feature shift -> concept shift
                sign = 1 if ev["consensus"] == "more" else -1
                w = min(1.0, ev["n_papers"] / PAPERS_FOR_FULL_WEIGHT)
                d = np.mean([inv[f] * shifts[f]["draws"] for f in feats], axis=0)
                point = float(np.mean([inv[f] * np.clip(shifts[f]["shift_sd"], -CLIP, CLIP) for f in feats]))
                num, den = num + w * sign * d, den + w
                best = next((r for r in ev["read"] if r["evidence_type"] == "experiment"), ev["read"][0] if ev["read"] else None)
                parts.append({"concept": c["id"], "features": feats, "shift_sd": round(point, 2),
                              "clear": any(shifts[f]["clear"] for f in feats), "papers_say": ev["consensus"],
                              "n_papers": ev["n_papers"], "counts": ev["counts"], "weight": round(w, 2),
                              "effect": round(w * sign * point, 2),
                              "quote": best and {"text": best["quote"].strip(), "title": best["title"], "year": best["year"], "doi": best["doi"]}})
            score = num / den if den else np.zeros(N_DRAWS)
            draws[b][o] = score
            out["batches"][b][o] = {
                "score": round(float(np.mean(score)), 2), "ci90": [round(float(x), 2) for x in np.quantile(score, [0.05, 0.95])],
                "p_better_than_reference": round(float(np.mean(GOOD[o] * score > 0)), 2),
                "drivers": sorted(parts, key=lambda p: -abs(p["effect"]))}

    overall = {b: np.mean([GOOD[o] * draws[b][o] for o in GOOD], axis=0) for b in batches}
    overall["Batch_3"] = np.zeros(N_DRAWS)
    stack = np.vstack([overall[b] for b in ("Batch_1", "Batch_2", "Batch_3")])
    best = stack.argmax(0)
    out["overall"] = {b: {"score": round(float(np.mean(overall[b])), 2),
                          "ci90": [round(float(x), 2) for x in np.quantile(overall[b], [0.05, 0.95])],
                          "p_best": round(float(np.mean(best == i)), 2)} for i, b in enumerate(("Batch_1", "Batch_2", "Batch_3"))}
    out["overall"]["p_batch1_better_than_batch2"] = round(float(np.mean(overall["Batch_1"] > overall["Batch_2"])), 2)
    si = [c["id"] for c in terms["concepts"] if c["id"].startswith("si_")]
    out["sensitivity"] = [
        {"choice": "As above", **scenario(res, terms, direction)},
        {"choice": "Features move together instead of independently", **scenario(res, terms, direction, together=True)},
        {"choice": "Only shifts that are clear of zero count", **scenario(res, terms, direction, clear_only=True)},
        {"choice": "Without the silicon fraction", **scenario(res, terms, direction, drop=("si_fraction",))},
        {"choice": "Without any silicon feature", **scenario(res, terms, direction, drop=tuple(si))},
        {"choice": "A customer who weights capacity three times", **scenario(res, terms, direction, weights={"capacity": 3.0})},
        {"choice": "A customer who weights capacity and charging speed three times", **scenario(res, terms, direction, weights={"capacity": 3.0, "charge_speed": 3.0})},
    ]
    out["network_leans_on"] = {f: {"mean_abs_contribution": round(v, 3), "rank": lean_rank[f]} for f, v in lean.items()}
    (HERE / "batch_outlook.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))

    # the same numbers for section 08 of the team page (dashboard/site/literature.js; the page hides the section
    # when the file is missing)
    rules = [r for p in evidence for r in p["slider_rules"]]
    page = {
        "concepts": [{"id": c["id"], "label": c["id"].replace("_", " ").replace("si ", "Si "), "features": c["features"],
                      "in_outlook": c.get("outlook") is not False} for c in terms["concepts"]],
        "outcomes": [{"id": o, "label": NAMES[o], "good": GOOD[o]} for o in GOOD],
        "pairs": {f"{p['concept']}|{p['outcome']}": {
            "n": p["n_papers"], "counts": list(p["counts"].values()), "consensus": p["consensus"],
            "quotes": [{k: r[k] for k in ("direction", "evidence_type", "material", "quote", "title", "year", "doi")}
                       for r in sorted(p["read"], key=lambda r: {"experiment": 0, "simulation": 1}.get(r["evidence_type"], 2))[:3]],
            "abstract_only": p["abstract_only"][:3],
            "web": [{k: " ".join(str(w[k]).split()) for k in ("title", "authors", "venue", "url", "says", "reading")} for w in p.get("web_references", [])],
            "rules": [{k: r[k] for k in ("feature", "sign", "literature")} for r in p["slider_rules"]]} for p in evidence},
        "sensitivity": out["sensitivity"],
        # per batch: what each concept's measured shift does to each outcome, for the by-batch view of the grid
        "grid": {b: {f"{d['concept']}|{o}": {"effect": d["effect"], "shift": d["shift_sd"], "clear": d["clear"], "papers_say": d["papers_say"], "n": d["n_papers"]}
                     for o, v in out["batches"][b].items() for d in v["drivers"]} for b in batches},
        "cards": json.loads((HERE / "feature_cards.json").read_text()) if (HERE / "feature_cards.json").exists() else None,
        "overall": out["overall"], "batches": {b: {o: {**v, "drivers": v["drivers"][:4]} for o, v in out["batches"][b].items()} for b in batches},
        "totals": {"questions": len(evidence), "answers": sum(p["n_papers"] for p in evidence),
                   "papers": len({r["paperclip_id"] for p in evidence for r in p["read"]}),
                   "gxl_abstract_only": sum(len(p["abstract_only"]) for p in evidence),
                   "web": sum(len(p.get("web_references", [])) for p in evidence),
                   "rules": len(rules), "rules_agree": sum(r["literature"] == "agrees" for r in rules),
                   "rules_disagree": sum(r["literature"] == "disagrees" for r in rules)},
    }
    site = ROOT / "dashboard" / "site"
    if site.exists():
        (site / "literature.js").write_text("window.LITERATURE = " + json.dumps(page, separators=(",", ":"), ensure_ascii=False) + ";\n")

    # ---- the readable version -------------------------------------------------------------------------------------
    ov = out["overall"]
    order = sorted(("Batch_1", "Batch_2", "Batch_3"), key=lambda b: -ov[b]["p_best"])
    L = ["# Batch outlook: how Batch_1 and Batch_2 differ from the baseline, and what that would mean", "",
         "Generated by `python literature/batch_outlook.py`. Do not edit by hand.", "",
         "**What this is.** The measured difference of each feature from Batch_3, multiplied by the direction the "
         "papers give for that feature and each battery outcome. A literature-informed expectation, not a measurement: "
         "there is no cycling data for these batches.", "",
         "## Overall", "",
         "| Batch | Chance it is the best of the three | Score vs Batch_3 (90 % interval) |", "|---|---|---|"]
    for b in order:
        L.append(f"| {b} | {ov[b]['p_best']:.0%} | {ov[b]['score']:+.2f} ({ov[b]['ci90'][0]:+.2f} to {ov[b]['ci90'][1]:+.2f}) |"
                 if b != "Batch_3" else f"| {b} | {ov[b]['p_best']:.0%} | 0 (the reference) |")
    L += ["", f"Chance Batch_1 is better than Batch_2: {ov['p_batch1_better_than_batch2']:.0%}. "
              "A chance near one in three for every batch means the data cannot tell them apart.", "",
          "### How much this depends on the choices", "",
          "Batch_3 is the baseline: Polaron describes it as what the supplier promised, with Batch_1 and Batch_2 arriving afterwards. Baseline does not mean defect-free, and its score is 0 because the other two are measured against it.", "", "Positive = more of the outcome than Batch_3. The last column says whether more is good.", "",
          "| Outcome | Batch_1 | Batch_2 | More is |", "|---|---|---|---|"]
    for o in GOOD:
        cells = [f"{out['batches'][b][o]['score']:+.2f} ({out['batches'][b][o]['ci90'][0]:+.2f} to {out['batches'][b][o]['ci90'][1]:+.2f})" for b in batches]
        L.append(f"| {NAMES[o]} | {cells[0]} | {cells[1]} | {'good' if GOOD[o] > 0 else 'bad'} |")
    L += ["", "## Which features differ", "",
          "Shift from Batch_3 in Batch_3 standard deviations, with the 90 % interval from `qc/verdict.py`. **Clear** = the "
          "interval excludes zero. *Network rank* = how much the CNN leans on the feature when it calls the batch (1 = most).", "",
          "| Feature | Batch_1 | Batch_2 | Network rank |", "|---|---|---|---|"]
    feats = sorted(out["features"]["Batch_1"], key=lambda f: -max(abs(out["features"][b][f]["shift_sd"]) for b in batches))
    for f in feats:
        cells = []
        for b in batches:
            s = out["features"][b][f]
            cells.append(f"{s['shift_sd']:+.1f} ({s['ci90'][0]:+.1f} to {s['ci90'][1]:+.1f}){' **clear**' if s['clear'] else ''}")
        L.append(f"| {labels.get(f, f)} | {cells[0]} | {cells[1]} | {lean_rank.get(f, '-')} |")
    L += ["", "## Why: the drivers behind each outcome", ""]
    for b in batches:
        L += [f"### {b}", ""]
        for o in GOOD:
            r = out["batches"][b][o]
            L.append(f"**{NAMES[o]}: {r['score']:+.2f}.**")
            if not r["drivers"]:
                L += ["No feature has an agreed direction in the papers read.", ""]
                continue
            for p in r["drivers"][:3]:
                names = ", ".join(labels.get(f, f) for f in p["features"])
                c = p["counts"]
                q = p["quote"]
                L.append(f"- {names}: concept shift {p['shift_sd']:+.1f} SD{'' if p['clear'] else ' (not clear of zero)'}; papers say higher means "
                         f"**{p['papers_say']}** ({c['feature_up_outcome_up']} up, {c['feature_up_outcome_down']} down, "
                         f"{c['non_monotonic']} optimum, {c['no_clear_effect']} no effect); effect {p['effect']:+.2f}."
                         + (f" \"{q['text']}\" — *{q['title']}* ({q['year']}){', https://doi.org/' + q['doi'] if q['doi'] else ''}" if q else ""))
            L.append("")
    L += ["## What this cannot tell you", "",
          "- **Silicon is confirmed, silicon oxide is not.** Polaron says the bright particles are silicon and the dark ones graphite. Several papers read are about silicon oxide, which swells less than silicon.",
          "- **Most shifts are not clear of zero.** Seven sites per batch, and sites from one imaging session are not independent.",
          "- **The chances are too confident.** Features are redrawn independently although several move together, so the intervals are too narrow. Read 85 % as 'leans this way', not as a measured probability.",
          "- **The batches are constructed groups.** Polaron made them by cutting about 20 large images into crops and grouping the crops on features it extracted. So neighbouring crops of one strip can sit in different batches, and a batch is a kind of microstructure, not a production lot.",
          "- **Papers were read by a machine.** Each quoted sentence was found in the paper, but whether the paper's setting matches this electrode was not checked by a person.",
          "- **Open-access papers only.** The reader cannot open the paywalled electrochemistry journals; those are listed in `EVIDENCE.md` as not read."]
    (HERE / "BATCH_OUTLOOK.md").write_text("\n".join(L) + "\n")
    print("overall:", {b: ov[b] for b in ("Batch_1", "Batch_2", "Batch_3")}, "| P(B1 > B2)", ov["p_batch1_better_than_batch2"])


if __name__ == "__main__":
    main()
