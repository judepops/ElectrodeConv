"""The numbers behind section 09 of the team page (the research harness), read from the files the harness writes.

    python ledger/site_data.py        # -> dashboard/site/harness.js  (seconds; ~1 min with the column tests)

Reads   ledger/entries/*.yaml (the ideas, their papers, their status), ledger/papers/*.json (the Amass and Paperclip
        paper index), literature/evidence.json (the GXL reader's answers), qc/spot_features/ (the plug-ins),
        qc/processed/features_table.csv (to test every built column, if it exists), .claude/skills/ and
        research/notes/ (the local agent tooling, counted if present: they are git-ignored).
Runs nothing else: no search, no model. Re-run after the ledger, the evidence or the features change.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ledger"))
sys.path.insert(0, str(ROOT))
import ledger as L  # noqa: E402

OUT = ROOT / "dashboard" / "site" / "harness.js"
SOURCES = ("gxl-evidence", "paperclip", "amass", "openalex", "crossref", "hyperresearch")
CHAIN = ["sae_patch_latents", "thin_solid", "binder_depth_profile"]      # the worked example, in order


def ref_source(r):
    n = str(r.get("note") or "").lower()
    return next((s for s in SOURCES if s in n), "team")


def skills():
    out = []
    for f in sorted((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        m = re.search(r"^description:\s*(.+)$", f.read_text(encoding="utf-8"), re.M)
        out.append({"name": f.parent.name, "about": (m.group(1).strip() if m else "")[:220]})
    return out


def column_tests(entries, n_perm=500):
    """ledger.separation() on every built column of an implemented entry (spot = unit)."""
    if not L.FEATURES_TABLE.exists():
        return []
    import pandas as pd
    df = pd.read_csv(L.FEATURES_TABLE)
    rows = []
    for e in entries:
        for c in e.get("columns") or []:
            if e.get("status") == "implemented" and c in df.columns and df[c].notna().sum() >= 20:
                s = L.separation(df, c, n_perm)
                rows.append({"entry": e["id"], "column": c, "auc3": round(s["auc3"], 3), "p3": round(s["p3"], 4),
                             "within": s["within"], "p_within": round(s["p_within"], 4), "auc12": round(s["auc12"], 3),
                             "p12": round(s["p12"], 4), "means": {k: round(v, 5) for k, v in s["means"].items()}})
    return rows


def main():
    entries = [e for _, e in L.load_entries()]
    built = L.built_feature_folders()
    refs = {}
    for e in entries:
        for r in e.get("refs") or []:
            refs.setdefault(r["doi"], {**r, "used_by": []})["used_by"].append(e["id"])
    index = {}
    for name in ("amass", "paperclip"):
        d = json.loads((ROOT / "ledger" / "papers" / f"{name}_papers.json").read_text(encoding="utf-8"))
        s = d.get("searches") or 0
        index[name] = {"papers": len(d["papers"]), "searches": s if isinstance(s, int) else len(s),
                       "tiers": dict(collections.Counter(p.get("relevance") for p in d["papers"]))}
    ev = json.loads((ROOT / "literature" / "evidence.json").read_text(encoding="utf-8"))["pairs"]
    terms = yaml.safe_load((ROOT / "literature" / "evidence_terms.yaml").read_text(encoding="utf-8"))
    evidence = {"questions": len(ev), "concepts": len(terms["concepts"]), "outcomes": len(terms["outcomes"]),
                "answers": sum(p["n_papers"] for p in ev), "dropped": sum(p.get("n_dropped_unverified_quote", 0) for p in ev),
                "papers": len({r.get("doi") or r.get("paperclip_id") for p in ev for r in p["read"]}),
                "abstract_only": sum(len(p.get("abstract_only") or []) for p in ev),
                "consensus": dict(collections.Counter(p["consensus"] for p in ev)),
                "by_concept": {c["id"]: {"features": c["features"], "pairs": {p["outcome"]: {"consensus": p["consensus"], "n": p["n_papers"]}
                                                                         for p in ev if p["concept"] == c["id"]}} for c in terms["concepts"]}}
    notes = ROOT / "research" / "notes"
    out = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "masks": L.MASKS,
        "ledger": {"n": len(entries), "status": dict(collections.Counter(e.get("status") for e in entries)),
                   "family": dict(collections.Counter(e.get("family") for e in entries)),
                   "owners": dict(collections.Counter(e.get("owner") or "unclaimed" for e in entries)),
                   "papers": len(refs), "verified": sum(bool(r.get("verified")) for r in refs.values()),
                   "ref_sources": dict(collections.Counter(ref_source(r) for e in entries for r in e.get("refs") or [])),
                   "entries": [{"id": e["id"], "name": e.get("name") or e["id"], "family": e.get("family"), "status": e.get("status"),
                                "owner": e.get("owner"), "implemented_in": e.get("implemented_in") or e.get("v1_implemented_in"),
                                "columns": e.get("columns") or [], "n_refs": len(e.get("refs") or []),
                                "sources": sorted({ref_source(r) for r in e.get("refs") or []}),
                                "relevance": " ".join(str(e.get("battery_relevance") or "").split())[:300],
                                "findings": " ".join(str(e.get("findings") or "").split())[:600]} for e in entries]},
        "index": index,
        "vault_notes": len(list(notes.glob("*.md"))) if notes.exists() else None,
        "skills": skills(),
        "plugins": {m: cols for m, (cols, _) in built.items()},
        "evidence": evidence,
        "chain": CHAIN,
        "tests": column_tests(entries),
    }
    OUT.write_text("window.HARNESS = " + json.dumps(out, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(entries)} entries, {len(refs)} papers, {evidence['questions']} evidence questions, "
          f"{len(out['tests'])} column tests, {len(out['skills'])} skills")


if __name__ == "__main__":
    main()
