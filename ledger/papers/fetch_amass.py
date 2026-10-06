"""Pull the electrode papers behind each feature from the Amass literature search.

    python ledger/papers/fetch_amass.py                 # every query in topics.yaml, 300 papers each
    python ledger/papers/fetch_amass.py --dry-run       # list the searches and what is already cached
    python ledger/papers/fetch_amass.py --budget 5000   # stop before spending more than this many credits

Reads   ledger/papers/topics.yaml (the searches) and AMASS_API_KEY from .secrets or the environment
Caches  processed/amass_cache/<hash>.json: the raw answer to each search, so a re-run only pays
        for searches it has not seen
Writes  ledger/papers/amass_papers.json: one entry per paper with title, abstract, journal, year, DOI,
        which topics found it, what it is useful for, and a relevance tier

Nothing else in the repo needs the key: the JSON is committed, so the harness just reads it with
papers.load_papers().
"""
import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
API = "https://api.amass.tech/api/v1"
OUT = HERE / "amass_papers.json"
CACHE = ROOT / "processed" / "amass_cache"
CREDITS_PER_SEARCH = 75  # measured cost of one 300-paper search, used only for the budget check

# Amass's corpus is mostly biomedical: "tortuosity" finds arteries and "electrode" finds EEG caps,
# and its search always returns 300 papers however far it has to drift. So every paper gets a tier:
#   core        a battery paper that talks about electrode structure or manufacturing
#               (a strong term in the title, or two different strong terms in the abstract)
#   method      not a battery paper, but a materials microstructure / imaging method (kept for method topics only)
#   peripheral  a battery paper about something else (new materials synthesis, electrolytes, ...)
# Anything else is dropped.
BATTERY = re.compile(r"batter|lithium|li-ion|sodium-ion|na-ion|graphite|\bLIBs?\b|electrode slurry", re.I)
STRONG = re.compile(
    r"calender|slurry|drying|binder|tortuos|porosity|pore (size|structure|network)|microstructur|cross-section"
    r"|tomograph|segmentation|particle size|lithium plating|thickness|mass loading|adhesion|delaminat|wetting"
    r"|heterogene|inhomogene|agglomerat|compaction|electrode density|orientation|alignment|crack|impurit"
    r"|contaminat|manufactur|quality control|defect|batch|carbon black|conductive additive|surface area"
    r"|electron microscop|\bSEM\b|image analysis|particle (shape|morpholog)|current collector|coating (weight|process)",
    re.I,
)
MICRO = re.compile(r"microstructur|micrograph|electron microscop|\bSEM\b|tomograph", re.I)
MATERIALS = re.compile(
    r"\bmaterials?\b|alloy|ceramic|porous media|grain|phase fraction|steel|composite|polymer|fuel cell|electrode"
    r"|metal|powder|mineral|crystal",
    re.I,
)
BIOMEDICAL = re.compile(
    r"patient|clinical|brain|bone|tumou?r|tissue|mice|\brats?\b|disease|white matter|\bMRI\b|dental|enamel"
    r"|neuro|cancer|protein|virus|bacteri|biolog|medical|surgery|cardiac|arter|retina|skin|blood|drug|cryo-EM",
    re.I,
)


def relevance(title, abstract, method_topic):
    """Tier for one paper, or None to drop it."""
    text = f"{title} {abstract}"
    if BATTERY.search(text):
        strong = {m.group(0).lower() for m in STRONG.finditer(text)}
        return "core" if STRONG.search(title) or len(strong) >= 2 else "peripheral"
    if method_topic and MICRO.search(text) and MATERIALS.search(text) and not BIOMEDICAL.search(text):
        return "method"
    return None


def api_key():
    if os.environ.get("AMASS_API_KEY"):
        return os.environ["AMASS_API_KEY"]
    secrets = ROOT / ".secrets"
    if secrets.exists():
        for line in secrets.read_text().splitlines():
            if line.startswith("AMASS_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("No AMASS_API_KEY in the environment or in .secrets")


def get(path, key, **params):
    url = f"{API}{path}?{urllib.parse.urlencode(params)}" if params else f"{API}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)["data"]
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise SystemExit(f"Amass returned {e.code} for {path}: {e.read().decode()[:300]}")
        except (urllib.error.URLError, TimeoutError):
            pass
    return None


def searches(cfg):
    """Flatten topics.yaml into one row per search: topic id, use, feature columns, API parameters."""
    rows = []
    for t in cfg["topics"]:
        for q in t["queries"]:
            rows.append({"topic": t["id"], "use": t["use"], "cols": t.get("feature_columns", []), "params": {"query": q}})
    for t in cfg["sweeps"]["topics"]:
        for lo, hi in cfg["sweeps"]["windows"]:
            params = {"query": t["query"]}
            if lo:
                params["minPublicationDate"] = lo
            if hi:
                params["maxPublicationDate"] = hi
            rows.append({"topic": t["id"], "use": t["use"], "cols": [], "params": params})
    for r in rows:
        r["params"]["limit"] = 300
        r["cache"] = CACHE / (hashlib.sha1(json.dumps(r["params"], sort_keys=True).encode()).hexdigest()[:16] + ".json")
    return rows


def run_search(row, key):
    hits = get("/cores/biomedcore/records", key, **row["params"])
    if hits is not None:
        row["cache"].write_text(json.dumps(hits))
    return row, hits


def journal_name(rec):
    j = rec.get("journal") or ""
    return (j.get("title") or j.get("name") or "") if isinstance(j, dict) else str(j)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="list the searches, spend nothing")
    ap.add_argument("--budget", type=int, default=15000, help="most credits this run may spend")
    args = ap.parse_args()

    rows = searches(yaml.safe_load((HERE / "topics.yaml").read_text()))
    todo = [r for r in rows if not r["cache"].exists()]
    print(f"{len(rows)} searches, {len(rows) - len(todo)} cached, {len(todo)} to run "
          f"(about {len(todo) * CREDITS_PER_SEARCH} credits)")
    if args.dry_run:
        return
    if len(todo) * CREDITS_PER_SEARCH > args.budget:
        raise SystemExit(f"That is over the --budget of {args.budget} credits. Raise it or trim topics.yaml.")

    CACHE.mkdir(parents=True, exist_ok=True)
    key = api_key() if todo else None
    credits_before = get("/credits/api-credits", key)["remaining"] if todo else 0
    failed = []
    with ThreadPoolExecutor(4) as pool:
        for i, (row, hits) in enumerate(pool.map(lambda r: run_search(r, key), todo), 1):
            if hits is None:
                failed.append(row["params"]["query"])
            print(f"  [{i}/{len(todo)}] {row['topic']:<28} {'FAILED' if hits is None else len(hits)}", flush=True)
    credits_used = credits_before - get("/credits/api-credits", key)["remaining"] if todo else 0

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
            tier_ = relevance(h.get("title") or "", h.get("abstract") or "", "method" in row["use"])
            if tier_ is None:
                continue
            rank += 1
            p = papers.setdefault(h["amassId"], {
                "amass_id": h["amassId"],
                "title": h.get("title"),
                "journal": journal_name(h),
                "year": int(h["publicationDate"][:4]) if h.get("publicationDate") else None,
                "doi": h.get("doi"),
                "pmid": h.get("pmid"),
                "url": h.get("url"),
                "citations": h.get("citationCount"),
                "has_fulltext": bool(h.get("hasFulltext")),
                "relevance": tier_,
                "abstract": h.get("abstract") if tier_ != "peripheral" else None,  # keeps the file small
                "n_searches": 0,        # how many separate searches found it: higher = more central
                "topics": {},           # topic id -> best rank in that topic's searches (1 = most relevant)
                "use": [],              # feature_selection / structure_function / method / material_identity / sample_prep
                "feature_columns": [],  # columns of processed/features.csv this paper speaks to
            })
            p["n_searches"] += 1
            p["topics"][row["topic"]] = min(rank, p["topics"].get(row["topic"], rank))
            p["use"] += [u for u in row["use"] if u not in p["use"]]
            p["feature_columns"] += [c for c in row["cols"] if c not in p["feature_columns"]]
            stats["kept"].add(h["amassId"])

    for s in per_topic.values():
        s["kept"] = len(s["kept"])
    previous = json.loads(OUT.read_text()) if OUT.exists() else {}
    tier = {"core": 0, "method": 1, "peripheral": 2}
    out = {
        "source": "Amass BiomedCore literature search (https://amass.tech)",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds") if todo else previous.get("fetched_at"),
        "searches": len(rows) - len(failed),
        "credits_used_this_run": credits_used,
        "failed_queries": failed,
        "topics": list(per_topic.values()),
        "papers": sorted(papers.values(), key=lambda p: (tier[p["relevance"]], -p["n_searches"], min(p["topics"].values()))),
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    n = {k: sum(p["relevance"] == k for p in papers.values()) for k in tier}
    print(f"\n{len(papers)} unique papers ({n['core']} core, {n['method']} method, {n['peripheral']} peripheral)"
          f" -> {OUT.relative_to(ROOT)}  ({credits_used} credits this run)")
    if failed:
        print(f"{len(failed)} searches failed and were skipped; re-run to retry them.")


if __name__ == "__main__":
    main()
