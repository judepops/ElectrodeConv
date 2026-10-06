"""Papers behind each feature, for the harness to cite. Two sources, same layout:
amass_papers.json (Amass) and paperclip_papers.json (GXL Paperclip).

    sys.path.insert(0, 'ledger'); from papers import load_papers     # from the repo root
    load_papers(topic="binder_migration", top=10)             # the 10 most relevant papers on a topic
    load_papers(feature_column="porosity_frac", top=10)       # papers that explain this features.csv column
    load_papers(use="feature_selection", relevance="core")    # everything usable for choosing features
    load_papers(topic="tortuosity", source="paperclip")       # one source only ("amass", "paperclip", default "all")

Always pass top= (or a topic) when the papers go into a prompt: the files hold about 17,000 papers and
relevance drops quickly after the first few dozen of each topic.
"""
import json
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = {"amass": HERE / "amass_papers.json", "paperclip": HERE / "paperclip_papers.json"}
TIER = {"core": 0, "method": 1, "peripheral": 2}


@lru_cache(maxsize=None)
def _source(name):
    papers = json.loads(FILES[name].read_text(encoding="utf-8"))["papers"] if FILES[name].exists() else []
    return [{**p, "source": name} for p in papers]


@lru_cache(maxsize=1)
def _all():
    """Both sources, one entry per paper (matched on DOI). Topics and uses are merged; the Amass
    record wins where both have the paper, because it carries the full abstract."""
    merged = {}
    for p in _source("amass") + _source("paperclip"):
        key = (p.get("doi") or p.get("amass_id") or p.get("paperclip_id")).lower()
        if key not in merged:
            merged[key] = {**p, "topics": dict(p["topics"]), "use": list(p["use"]), "feature_columns": list(p["feature_columns"])}
            continue
        m = merged[key]
        m["source"] = "both"
        for t, rank in p["topics"].items():
            m["topics"][t] = min(rank, m["topics"].get(t, rank))
        m["use"] += [u for u in p["use"] if u not in m["use"]]
        m["feature_columns"] += [c for c in p["feature_columns"] if c not in m["feature_columns"]]
        m["n_searches"] += p["n_searches"]
        if TIER[p["relevance"]] < TIER[m["relevance"]]:
            m["relevance"] = p["relevance"]
        if not m.get("abstract") and p.get("abstract"):
            m["abstract"] = p["abstract"]
    return sorted(merged.values(), key=lambda p: (TIER[p["relevance"]], -p["n_searches"]))


def load_papers(topic=None, feature_column=None, use=None, relevance=None, top=None, source="all"):
    """Papers, most useful first. With a topic: most relevant to that topic first.
    Otherwise: core papers first, then the ones found by the most searches."""
    papers = _all() if source == "all" else _source(source)
    if topic:
        papers = sorted((p for p in papers if topic in p["topics"]), key=lambda p: p["topics"][topic])
    if feature_column:
        papers = [p for p in papers if feature_column in p["feature_columns"]]
    if use:
        papers = [p for p in papers if use in p["use"]]
    if relevance:
        papers = [p for p in papers if p["relevance"] == relevance]
    return papers[:top] if top else papers
