"""Pull the electrode papers behind each feature from GXL Paperclip (free for the hackathon).

    python ledger/papers/fetch_paperclip.py              # every query in topics.yaml, 300 papers each
    python ledger/papers/fetch_paperclip.py --dry-run    # list the searches and what is already cached

Needs   the Paperclip CLI installed and logged in (https://paperclip.gxl.ai), run with Python 3.10+
Reads   ledger/papers/topics.yaml, the same searches as fetch_amass.py
Caches  processed/paperclip_cache/<hash>.json: the raw answer to each search
Writes  ledger/papers/paperclip_papers.json, same layout as amass_papers.json, read with
        papers.load_papers(source="paperclip")

Paperclip covers the electrochemistry journals Amass lacks (J. Electrochem. Soc., J. Power Sources,
Energy Storage Materials) through OpenAlex and Crossref abstracts, plus arXiv and PubMed Central.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_amass import relevance  # same tier rules for both sources

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "paperclip_papers.json"
CACHE = ROOT / "processed" / "paperclip_cache"
SWEEP_YEARS = range(2012, 2027)  # sweeps are repeated per publication year to get past the 300 cap

# Paperclip gives no journal name for OpenAlex / Crossref records, but the DOI prefix identifies the main ones.
DOI_JOURNALS = [
    ("10.1016/j.jpowsour", "Journal of Power Sources"), ("10.1149/", "Journal of The Electrochemical Society"),
    ("10.1016/j.electacta", "Electrochimica Acta"), ("10.1016/j.ensm", "Energy Storage Materials"),
    ("10.1016/j.joule", "Joule"), ("10.1016/j.est.", "Journal of Energy Storage"),
    ("10.1002/aenm", "Advanced Energy Materials"), ("10.1002/ente", "Energy Technology"),
    ("10.1002/batt", "Batteries & Supercaps"), ("10.3390/batteries", "Batteries"),
    ("10.1021/acsami", "ACS Applied Materials & Interfaces"), ("10.1021/acsaem", "ACS Applied Energy Materials"),
    ("10.1021/acsenergylett", "ACS Energy Letters"), ("10.1016/j.powtec", "Powder Technology"),
    ("10.1016/j.carbon", "Carbon"), ("10.1016/j.softx", "SoftwareX"), ("10.1038/s41467", "Nature Communications"),
    ("10.1038/s42256", "Nature Machine Intelligence"), ("10.1038/s41560", "Nature Energy"),
    ("10.1080/07373937", "Drying Technology"), ("10.1016/j.cej", "Chemical Engineering Journal"),
    ("10.1016/j.matdes", "Materials & Design"), ("10.1016/j.jmatprotec", "Journal of Materials Processing Technology"),
]


def client():
    warnings.filterwarnings("ignore")
    sys.path.insert(0, os.path.expanduser("~/.paperclip/lib"))
    from gxl_paperclip import PaperclipClient
    return PaperclipClient.from_env()


def searches(cfg):
    """Flatten topics.yaml into one row per search."""
    rows = []
    for t in cfg["topics"]:
        for q in t["queries"]:
            rows.append({"topic": t["id"], "use": t["use"], "cols": t.get("feature_columns", []), "params": {"query": q}})
    for t in cfg["sweeps"]["topics"]:
        for year in SWEEP_YEARS:
            rows.append({"topic": t["id"], "use": t["use"], "cols": [], "params": {"query": t["query"], "year": year}})
    for r in rows:
        r["cache"] = CACHE / (hashlib.sha1(json.dumps(r["params"], sort_keys=True).encode()).hexdigest()[:16] + ".json")
    return rows


def run_search(row, pc):
    hits = None
    for attempt in range(3):  # searches fail now and then when several run at once
        try:
            res = pc.search(row["params"]["query"], source="abstracts", all=True, limit=300, year=row["params"].get("year"))
            if res.exit_code == 0:
                hits = res.papers
                break
        except Exception:
            pass
        time.sleep(3 * (attempt + 1))
    if hits is not None:
        row["cache"].write_text(json.dumps(hits))
    return row, hits


def journal_name(h):
    if h.get("journal_title"):
        return h["journal_title"]
    doi = (h.get("doi") or "").lower()
    for prefix, name in DOI_JOURNALS:
        if doi.startswith(prefix):
            return name
    return "arXiv preprint" if h.get("source") == "arxiv" else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="list the searches, run nothing")
    args = ap.parse_args()

    rows = searches(yaml.safe_load((HERE / "topics.yaml").read_text()))
    todo = [r for r in rows if not r["cache"].exists()]
    print(f"{len(rows)} searches, {len(rows) - len(todo)} cached, {len(todo)} to run")
    if args.dry_run:
        return

    CACHE.mkdir(parents=True, exist_ok=True)
    failed = []
    if todo:
        pc = client()
        with ThreadPoolExecutor(2) as pool:
            for i, (row, hits) in enumerate(pool.map(lambda r: run_search(r, pc), todo), 1):
                if hits is None:
                    failed.append(row["params"])
                print(f"  [{i}/{len(todo)}] {row['topic']:<28} {'FAILED' if hits is None else len(hits)}", flush=True)

    papers, per_topic = {}, {}
    for row in rows:
        if not row["cache"].exists():
            continue
        hits = json.loads(row["cache"].read_text())
        stats = per_topic.setdefault(row["topic"], {"id": row["topic"], "use": row["use"], "searches": 0, "returned": 0, "kept": set()})
        stats["searches"] += 1
        stats["returned"] += len(hits)
        rank = 0
        for h in hits:
            abstract = h.get("abstract") or h.get("abstract_snippet") or ""
            tier_ = relevance(h.get("title") or "", abstract, "method" in row["use"])
            if tier_ is None:
                continue
            rank += 1
            key = (h.get("doi") or h["document_id"]).lower()
            p = papers.setdefault(key, {
                "paperclip_id": h["document_id"],
                "title": " ".join((h.get("title") or "").split()),
                "journal": journal_name(h),
                "year": h.get("pub_year") or (int(h["pub_date"][:4]) if h.get("pub_date") else None),
                "doi": h.get("doi"),
                "pmid": h.get("pmid"),
                "url": f"https://doi.org/{h['doi']}" if h.get("doi") else None,
                "citations": h.get("citations"),
                "has_fulltext": h.get("source") in ("pmc", "arxiv"),  # the rest are title + abstract only
                "relevance": tier_,
                "abstract": abstract if tier_ != "peripheral" else None,
                "abstract_is_snippet": not h.get("abstract"),  # first ~200 characters only; `paperclip cat /papers/<id>/meta.json` has the rest
                "score": 0.0,           # Paperclip's own relevance score for its best-matching search (0-1)
                "n_searches": 0,
                "topics": {},
                "use": [],
                "feature_columns": [],
            })
            p["score"] = max(p["score"], h.get("rerank_score") or 0.0)
            p["n_searches"] += 1
            p["topics"][row["topic"]] = min(rank, p["topics"].get(row["topic"], rank))
            p["use"] += [u for u in row["use"] if u not in p["use"]]
            p["feature_columns"] += [c for c in row["cols"] if c not in p["feature_columns"]]
            stats["kept"].add(key)

    for s in per_topic.values():
        s["kept"] = len(s["kept"])
    previous = json.loads(OUT.read_text()) if OUT.exists() else {}
    tier = {"core": 0, "method": 1, "peripheral": 2}
    out = {
        "source": "GXL Paperclip, abstracts corpus: OpenAlex, Crossref, arXiv, PubMed Central (https://paperclip.gxl.ai)",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds") if todo else previous.get("fetched_at"),
        "searches": len(rows) - len(failed),
        "failed_queries": failed,
        "topics": list(per_topic.values()),
        "papers": sorted(papers.values(), key=lambda p: (tier[p["relevance"]], -p["n_searches"], -p["score"])),
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    n = {k: sum(p["relevance"] == k for p in papers.values()) for k in tier}
    print(f"\n{len(papers)} unique papers ({n['core']} core, {n['method']} method, {n['peripheral']} peripheral)"
          f" -> {OUT.relative_to(ROOT)}")
    if failed:
        print(f"{len(failed)} searches failed and were skipped; re-run to retry them.")


if __name__ == "__main__":
    main()
