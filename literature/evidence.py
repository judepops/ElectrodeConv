"""Link every measured feature to battery outcomes, using papers that were actually read.

    python literature/evidence.py                    # every (concept, outcome) pair in evidence_terms.yaml
    python literature/evidence.py --only porosity    # one concept
    python literature/evidence.py --report           # rebuild evidence.json and EVIDENCE.md from the cache, no searches
    python literature/evidence.py --reverify         # re-check the cached quotes against the paper text

Needs   the GXL Paperclip CLI installed and logged in (https://paperclip.gxl.ai), Python 3.10+. Free for the hackathon.
Reads   literature/evidence_terms.yaml (what to ask), qc/impact_rules.yaml (the slider rules to check),
        literature/web_references.yaml (extra papers from a web search, shown but not counted)
Caches  literature/processed/evidence/<concept>__<outcome>.json (git-ignored)
Writes  literature/evidence.json and literature/EVIDENCE.md

For each pair, e.g. porosity x charging speed:
  1. Search Paperclip's full-text papers (PubMed Central and arXiv) for the pair.
  2. Paperclip's reader opens each paper and answers one fixed question: when the feature is higher, is the outcome
     higher or lower, and which sentence says so? Answers come back in a fixed schema.
  3. Each quoted sentence is looked up in the paper's text. A quote that cannot be found is dropped.
  4. The directions are counted. That count is compared with the sign of the matching rule in qc/impact_rules.yaml.
  5. Abstract-only papers on the same pair (the paywalled electrochemistry journals) are listed as further reading.
     Nothing read them, so they do not count towards the direction. The same goes for web_references.yaml: papers
     from an ordinary web search for the questions left unsettled, shown beside the evidence and never counted.

No language model in this file decides anything: the reader's answers are counted, and the count is reported.
"""
import argparse
import json
import os
import re
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / "processed" / "evidence"
OUT_JSON, OUT_MD = HERE / "evidence.json", HERE / "EVIDENCE.md"
N_READ, N_ABSTRACT = 25, 30       # full-text papers read per pair; abstract-only candidates looked at per pair
ABSTRACT_MIN_SCORE = 0.5          # Paperclip relevance score (0-1) an abstract-only paper needs to be listed

DIRECTIONS = ["feature_up_outcome_up", "feature_up_outcome_down", "non_monotonic", "no_clear_effect", "not_addressed"]
SCHEMA = {
    "type": "object",
    "required": ["addresses_question", "direction", "evidence_type", "quote"],
    "properties": {
        "addresses_question": {"type": "boolean"},
        "direction": {"type": "string", "enum": DIRECTIONS},
        "evidence_type": {"type": "string", "enum": ["experiment", "simulation", "review", "not_applicable"]},
        "material": {"type": "string", "description": "electrode material studied, a few words"},
        "quote": {"type": "string", "description": "ONE sentence copied word for word from the paper that supports the direction; empty if not addressed"},
    },
}


def question(concept, outcome):
    return (f"Does this paper report or review how {concept['phrase']} affects {outcome['phrase']} in a lithium-ion "
            f"battery electrode? Set addresses_question=true only if the paper itself links the two. "
            f"direction: feature_up_outcome_up if a HIGHER / LARGER / MORE of the first goes with a HIGHER / MORE of the "
            f"second; feature_up_outcome_down for the opposite; non_monotonic if there is an optimum; no_clear_effect if "
            f"it was tested and made no difference; not_addressed otherwise. quote: one sentence copied word for word.")


def client():
    warnings.filterwarnings("ignore")
    sys.path.insert(0, os.path.expanduser("~/.paperclip/lib"))
    from gxl_paperclip import PaperclipClient
    return PaperclipClient.from_env()


def retry(fn, tries=3):
    for attempt in range(tries):
        try:
            return fn()
        except Exception:
            time.sleep(3 * (attempt + 1))
    return None


def parse_map(text):
    """Paperclip prints one block per paper: a tick, the title, the paper id, then the JSON answer."""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)
    answers = {}
    for block in re.split(r"\n\s*(?=[✓✗] )", text):
        if not block.lstrip().startswith("✓"):
            continue
        pid = re.search(r"\n\s*(\S+) · \d+ms", block)
        body = re.search(r"\{.*\}", block, re.S)
        if pid and body:
            try:
                answers[pid.group(1)] = json.loads(body.group(0))
            except json.JSONDecodeError:
                pass
    return answers


def quote_found(pc, pid, quote):
    """True if a run of five consecutive words from the quote appears in the paper's text."""
    words = re.findall(r"[A-Za-z0-9]+", quote)
    if len(words) < 8:
        return False
    for start in (len(words) // 3, 1, max(0, len(words) - 6)):   # try three places: PDFs break lines mid-sentence
        frag = "[^A-Za-z0-9]+".join(words[start:start + 5])
        res = retry(lambda: pc.papers.grep(frag, f"/papers/{pid}/content.lines", ignore_case=True, extended=True))
        if res is not None and res.exit_code == 0 and re.search(frag, res.output or "", re.I):
            return True
    return False


def reverify(pc):
    """Re-check the quotes already in the cache (no searches, no reading)."""
    for f in sorted(CACHE.glob("*.json")):
        p = json.loads(f.read_text())
        for r in p["read"]:
            if not r["quote_verified"]:
                r["quote_verified"] = quote_found(pc, r["paperclip_id"], r["quote"])
        f.write_text(json.dumps(p, indent=1, ensure_ascii=False))


def run_pair(pc, concept, outcome):
    path = CACHE / f"{concept['id']}__{outcome['id']}.json"
    if path.exists():
        return json.loads(path.read_text())
    query = f"{concept['search']} {outcome['search']} lithium-ion battery"
    read = []
    res = retry(lambda: pc.search(query, source="pmc,arxiv", all=True, limit=N_READ))
    hits = res.papers if res is not None and res.exit_code == 0 else []
    if hits:
        last = None
        events = retry(lambda: list(pc.map_(question(concept, outcome), from_results=res.result_id, output_schema=SCHEMA, timeout=900)))
        if events:
            last = events[-1]
        answers = parse_map(getattr(last, "output", "") or "") if last else {}
        by_id = {h["document_id"]: h for h in hits}
        for pid, a in answers.items():
            h = by_id.get(pid) or by_id.get(f"arx_{pid}") or {}
            if not a.get("addresses_question") or a.get("direction") in (None, "not_addressed"):
                continue
            read.append({
                "paperclip_id": pid, "title": " ".join((h.get("title") or "").split()), "doi": h.get("doi"),
                "year": h.get("pub_year") or (h.get("pub_date") or "")[:4], "source": h.get("source"),
                "direction": a["direction"], "evidence_type": a.get("evidence_type"), "material": a.get("material"),
                "quote": a.get("quote") or "", "quote_verified": quote_found(pc, pid, a.get("quote") or ""),
            })
    res2 = retry(lambda: pc.search(query, source="abstracts", all=True, limit=N_ABSTRACT))
    abstract_only = [{"title": " ".join((h.get("title") or "").split()), "doi": h.get("doi"), "year": h.get("pub_year"),
                      "score": round(h.get("rerank_score") or 0, 2)}
                     for h in (res2.papers if res2 is not None and res2.exit_code == 0 else [])
                     if h.get("corpus") == "abstract_only" and h.get("doi") and (h.get("rerank_score") or 0) >= ABSTRACT_MIN_SCORE]
    out = {"concept": concept["id"], "outcome": outcome["id"], "query": query, "n_fulltext_searched": len(hits),
           "read": read, "abstract_only": abstract_only[:8]}
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def summarise(pair):
    """Count the directions of the verified answers and name the consensus."""
    ok = [r for r in pair["read"] if r["quote_verified"]]
    n = {d: sum(r["direction"] == d for r in ok) for d in DIRECTIONS[:4]}
    up, down, total = n["feature_up_outcome_up"], n["feature_up_outcome_down"], len(ok)
    if total < 2:
        consensus = "too few papers"
    elif up >= 2 and up >= 2 * max(down, 1) and up > n["non_monotonic"]:
        consensus = "more"
    elif down >= 2 and down >= 2 * max(up, 1) and down > n["non_monotonic"]:
        consensus = "less"
    elif n["non_monotonic"] >= max(up, down) and n["non_monotonic"] >= 2:
        consensus = "optimum"
    else:
        consensus = "mixed"
    return {"n_papers": total, "counts": n, "consensus": consensus,
            "n_dropped_unverified_quote": len(pair["read"]) - len(ok)}


def report(terms, rules):
    concepts = {c["id"]: c for c in terms["concepts"]}
    outcomes = {o["id"]: o for o in terms["outcomes"]}
    feature_concept = {f: c["id"] for c in terms["concepts"] for f in c["features"]}
    rule_sign = {}  # (concept, outcome) -> list of (feature, sign, confidence, citation)
    for prop in rules["properties"]:
        for r in prop.get("rules", []):
            cid = feature_concept.get(r["feature"])
            if cid:
                flip = -1 if r["feature"] in concepts[cid].get("inverse", []) else 1   # rule sign in the concept's sense
                rule_sign.setdefault((cid, prop["id"]), []).append(
                    {"feature": r["feature"], "sign": r["sign"], "sign_as_concept": flip * r["sign"],
                     "confidence": r.get("confidence"), "citation": r.get("citation")})
    web_file = HERE / "web_references.yaml"                    # abstract-level papers from a web search; never counted
    web = yaml.safe_load(web_file.read_text()) if web_file.exists() else []
    def rules_for(p, consensus):
        rs = [dict(r) for r in rule_sign.get((p["concept"], p["outcome"]), [])]
        for r in rs:
            want = "more" if r["sign_as_concept"] > 0 else "less"
            r["literature"] = ("agrees" if consensus == want else
                               "disagrees" if consensus in ("more", "less") else
                               "optimum, not one direction" if consensus == "optimum" else
                               "not settled by the papers read")
        return rs

    pairs = {}
    for f in sorted(CACHE.glob("*.json")):
        p = json.loads(f.read_text())
        if p["concept"] not in concepts or p["outcome"] not in outcomes:
            continue
        s = summarise(p)
        pairs[f.name] = {**p, **s, "features": concepts[p["concept"]]["features"], "slider_rules": rules_for(p, s["consensus"]),
                         "web_references": [w for w in web if w["pair"] == f"{p['concept']}|{p['outcome']}"],
                         "read": [r for r in p["read"] if r["quote_verified"]]}
    if OUT_JSON.exists():      # pairs searched on another machine (the cache is git-ignored): keep them as committed
        for p in json.loads(OUT_JSON.read_text())["pairs"]:
            key = f"{p['concept']}__{p['outcome']}.json"
            if key not in pairs and p["concept"] in concepts and p["outcome"] in outcomes:
                pairs[key] = {**p, "features": concepts[p["concept"]]["features"],
                              "slider_rules": rules_for(p, p["consensus"]),
                              "web_references": [w for w in web if w["pair"] == f"{p['concept']}|{p['outcome']}"]}
    pairs = [pairs[k] for k in sorted(pairs)]
    OUT_JSON.write_text(json.dumps({
        "about": "Feature -> battery outcome evidence. Each direction is a count of full-text papers read by GXL "
                 "Paperclip whose quoted sentence was found in the paper. See literature/README.md.",
        "pairs": pairs}, indent=1, ensure_ascii=False))

    word = {"more": "higher feature → MORE", "less": "higher feature → LESS", "optimum": "has an optimum",
            "mixed": "mixed", "too few papers": "too few papers"}
    L = ["# Feature → battery outcome: what the papers say", "",
         "Generated by `python literature/evidence.py`. Do not edit by hand.", "",
         "Each row is one question, e.g. *when porosity is higher, is charging faster or slower?* The counts are "
         "full-text papers that GXL Paperclip's reader opened and answered, kept only when the sentence it quoted was "
         "found in the paper. **up** = higher feature goes with more of the outcome, **down** = less, **opt** = an "
         "optimum, **none** = tested, no effect. *Slider rule* compares the count with the sign already used in "
         "`qc/impact_rules.yaml`.", "",
         "**Where each item comes from.** `[GXL read]` = found and read in full text by GXL Paperclip; only these are "
         "counted. `[GXL abstract]` = found by GXL Paperclip, abstract only, not read. `[web]` = from an ordinary web "
         "search, not from GXL, not read in full. The citations inside `qc/impact_rules.yaml` are the team's own and "
         "came from neither. Amass was not used for this table.", ""]
    for o in terms["outcomes"]:
        rows = [p for p in pairs if p["outcome"] == o["id"]]
        if not rows:
            continue
        L += [f"## {o['id']}: {o['phrase']}", "", "| Feature columns | Papers | up / down / opt / none | Papers say | Slider rule |", "|---|---|---|---|---|"]
        for p in sorted(rows, key=lambda p: -p["n_papers"]):
            c = p["counts"]
            rule = "; ".join(f"`{r['feature']}` sign {r['sign']:+d}: {r['literature']}" for r in p["slider_rules"]) or "no rule"
            L.append(f"| {', '.join('`' + f + '`' for f in p['features'])} | {p['n_papers']} | {c['feature_up_outcome_up']} / "
                     f"{c['feature_up_outcome_down']} / {c['non_monotonic']} / {c['no_clear_effect']} | {word[p['consensus']]} | {rule} |")
        L.append("")
    L += ["## The sentences", "", "Up to three per question, experiments first.", ""]
    order = {"experiment": 0, "simulation": 1, "review": 2}
    for p in sorted(pairs, key=lambda p: (p["outcome"], -p["n_papers"])):
        if not p["read"] and not p["web_references"]:
            continue
        L += [f"### {p['concept']} → {p['outcome']}", ""]
        for r in sorted(p["read"], key=lambda r: order.get(r["evidence_type"], 3))[:3]:
            ref = f"https://doi.org/{r['doi']}" if r["doi"] else r["paperclip_id"]
            L.append(f"- `[GXL read]` **{r['direction'].replace('feature_up_outcome_', '')}** ({r['evidence_type']}, {r['material'] or 'material not stated'}): "
                     f"\"{r['quote'].strip()}\" — *{r['title']}* ({r['year']}), {ref}")
        for w in p["web_references"]:
            L.append(f"- `[web]` Not read in full: [{w['title']}]({w['url']}) ({w['authors']}, {w['venue']}). "
                     f"{' '.join(w['says'].split())} *Our reading: {w['reading']}.*")
        if p["abstract_only"]:
            L.append("- `[GXL abstract]` Not read: " + "; ".join(f"[{a['title'][:70]}](https://doi.org/{a['doi']}) ({a['year']})" for a in p["abstract_only"][:4]))
        L.append("")
    OUT_MD.write_text("\n".join(L))
    n_read = sum(p["n_papers"] for p in pairs)
    print(f"{len(pairs)} questions, {n_read} verified paper answers -> {OUT_JSON.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="one concept id from evidence_terms.yaml")
    ap.add_argument("--report", action="store_true", help="rebuild the outputs from the cache, run no searches")
    ap.add_argument("--reverify", action="store_true", help="re-check cached quotes against the paper text, then report")
    args = ap.parse_args()

    terms = yaml.safe_load((HERE / "evidence_terms.yaml").read_text())
    rules = yaml.safe_load((ROOT / "qc" / "impact_rules.yaml").read_text())
    CACHE.mkdir(parents=True, exist_ok=True)
    if args.reverify:
        reverify(client())
    elif not args.report:
        pc = client()
        todo = [(c, o) for c in terms["concepts"] if not args.only or c["id"] == args.only for o in terms["outcomes"]]
        with ThreadPoolExecutor(3) as pool:
            for i, p in enumerate(pool.map(lambda co: run_pair(pc, *co), todo), 1):
                ok = sum(r["quote_verified"] for r in p["read"])
                print(f"  [{i}/{len(todo)}] {p['concept']:<24} x {p['outcome']:<18} searched {p['n_fulltext_searched']:>2}, "
                      f"answered {len(p['read']):>2}, quote found {ok:>2}, abstract-only {len(p['abstract_only'])}", flush=True)
    report(terms, rules)


if __name__ == "__main__":
    main()
