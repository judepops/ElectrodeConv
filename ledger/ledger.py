"""The feature ledger: every feature idea, the papers behind it, and whether it is built yet.

One YAML file per feature in ledger/entries/<id>.yaml (one file each, so people adding features
at the same time don't get merge conflicts). ledger/LEDGER.md is generated from them: don't edit it.
A paper can back many features; a feature can cite many papers.

    python ledger/ledger.py search "binder migration drying electrode"   # find papers (OpenAlex)
    python ledger/ledger.py check "pore size from local thickness"        # is this feature already in the ledger or built?
    python ledger/ledger.py add local_thickness --name "Pore size by local thickness" --family morphology \
        --doi 10.1046/j.1365-2818.1997.1340694.x --detector BSE            # new idea (runs check first)
    python ledger/ledger.py normalize                                     # tidy every file, verify DOIs, rebuild LEDGER.md
    python ledger/ledger.py normalize --offline                           # same, without looking DOIs up
    python ledger/ledger.py report                                        # every built column: how it separates the batches

`check` exits with code 1 when the feature looks like a duplicate, so scripts and agents can stop on it.

Carried over from the first repo (a-rune/losslarp). There, a feature was a features/<folder>; here it is a set of
columns of qc/processed/features_table.csv, made by one of the modules in BUILT. `implemented_in` names that module
and `columns` lists its columns. Entries built only in the first repo keep that path in `v1_implemented_in` (and their
old columns in `v1_columns`) with status `v1_only`: a port candidate, with its first-repo findings.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER_DIR = ROOT / "ledger" / "entries"
LEDGER_MD = ROOT / "ledger" / "LEDGER.md"
MASKS = os.environ.get("LOSSLARP_MASKS", "seg3")             # as preprocessing/preprocess.py: which results to read
_PROCESSED = "processed_seg3" if MASKS == "seg3" else "processed"
FEATURES_TABLE = ROOT / "qc" / _PROCESSED / "features_table.csv"
VERDICTS = ROOT / "qc" / _PROCESSED / "verdicts.json"
USER_AGENT = "losslarp-ledger/0.1 (https://github.com/lucavendruscolo/LossLarpV2)"
# module that makes the columns -> [(file, list variable)] holding their names, + columns computed elsewhere from them
BUILT = {"cnn/tile_features.py": ([("cnn/tile_features.py", "FEATURES")], ["solid_chord_hv_ratio"]),
         "qc/depth_profile.py": ([("qc/features_table.py", "DEPTH_COLUMNS")], [])}
BUILT.update({f"qc/spot_features/{p.stem}.py": ([(f"qc/spot_features/{p.stem}.py", "COLUMNS")], [])   # plug-ins
              for p in sorted((ROOT / "qc" / "spot_features").glob("*.py")) if not p.stem.startswith("_") and p.stem != "run"})

FAMILIES = ("morphology", "spatial_statistics", "texture", "transport", "composition", "orientation",
            "depth_profile", "learned", "acquisition")
STATUSES = ("idea", "in_progress", "implemented", "v1_only", "rejected")
DETECTORS = {"bse": "BSE", "se": "SE", "etd": "SE", "inlens": "Inlens"}
FIELDS = ["id", "name", "aliases", "family", "detectors", "status", "owner", "implemented_in", "columns",
          "v1_implemented_in", "v1_columns", "description", "battery_relevance", "findings", "refs"]
REF_FIELDS = ["doi", "title", "authors", "year", "venue", "verified", "note"]

DUPLICATE, RELATED = 0.55, 0.30   # check() similarity cut-offs (0-1)


# ----------------------------------------------------------------------------------------------------
# NORMALISING  (ids, DOIs, words)
# ----------------------------------------------------------------------------------------------------
def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")


def norm_doi(doi):
    """'https://doi.org/10.1109/TSMC.1979.4310076' -> '10.1109/tsmc.1979.4310076'. arXiv ids -> their DataCite DOI."""
    s = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", str(doi).strip(), flags=re.I)
    m = re.match(r"^(arxiv:\s*|https?://arxiv\.org/(abs|pdf)/)(\d{4}\.\d{4,5})(v\d+)?$", s, re.I)
    if m:
        s = f"10.48550/arxiv.{m.group(3)}"
    return s.rstrip(".,; ").lower()


# Words that mean the same feature. Applied before comparing, so "void fraction" matches "porosity".
SYNONYMS = {
    "void": "pore", "voids": "pore", "porosity": "pore fraction", "porous": "pore", "vacancy": "pore",
    "psd": "pore size distribution", "s2": "two point correlation", "autocorrelation": "two point correlation",
    "tpcf": "two point correlation", "glcm": "grey level cooccurrence", "haralick": "grey level cooccurrence",
    "gray": "grey", "co": "", "occurrence": "cooccurrence", "lbp": "local binary pattern",
    "grain": "particle", "flake": "particle", "flakes": "particle", "agglomerate": "particle",
    "diffusivity": "tortuosity", "mactmullin": "tortuosity", "taufactor": "tortuosity",
    "anisotropy": "orientation", "alignment": "orientation", "texture": "texture",
    "cbd": "carbon binder", "binder": "carbon binder", "additive": "bright phase",
    "boundary": "interface", "perimeter": "interface", "specific": "", "surface": "interface",
    "fissure": "crack", "fracture": "crack", "thickness": "thickness", "chord": "lineal path",
    "minkowski": "minkowski", "euler": "minkowski", "fft": "power spectrum", "fourier": "power spectrum",
    "spectral": "power spectrum", "size": "size", "diameter": "size",
}
STOPWORDS = {"the", "of", "a", "an", "in", "via", "from", "per", "and", "or", "to", "for", "by", "with", "on",
             "using", "based", "function", "feature", "features", "measure", "measured", "image", "images",
             "um", "um2", "frac", "fraction_of", "phase_of", "is", "how", "what", "this", "that", "its", "at"}


def norm_words(text):
    """Lower-case, split, apply SYNONYMS, crude plural stripping, drop stopwords -> one string."""
    out = []
    for w in re.findall(r"[a-z0-9]+", str(text).lower()):
        for v in SYNONYMS.get(w, w).split():
            if len(v) > 3 and v.endswith("s") and not v.endswith("ss"):
                v = v[:-1]
            if v and v not in STOPWORDS:
                out.append(v)
    return " ".join(out)


# ----------------------------------------------------------------------------------------------------
# LOOKING PAPERS UP  (OpenAlex first, Crossref as fallback; stdlib only)
# ----------------------------------------------------------------------------------------------------
def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def openalex_json(path, params=None):
    """OpenAlex GET. Without a key it shares a small daily budget per IP; set OPENALEX_API_KEY (free) to get your own."""
    params = dict(params or {})
    if os.environ.get("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    return http_json(f"https://api.openalex.org/{path}" + ("?" + urllib.parse.urlencode(params) if params else ""))


def crossref_work(m):
    """Crossref record -> the same shape as an OpenAlex work (fields cmd_search reads)."""
    return {"doi": m.get("DOI"), "title": (m.get("title") or [None])[0],
            "publication_year": (m.get("issued", {}).get("date-parts") or [[None]])[0][0],
            "primary_location": {"source": {"display_name": (m.get("container-title") or [None])[0]}},
            "cited_by_count": m.get("is-referenced-by-count"),
            "authorships": [{"author": {"display_name": f"{a.get('given', '')} {a.get('family', '')}".strip()}}
                            for a in m.get("author", [])],
            "abstract": re.sub(r"<[^>]+>", "", m.get("abstract") or "").strip()}


def short_authors(names):
    surnames = [n.split()[-1] for n in names if n]
    return ", ".join(surnames[:3]) + (" et al." if len(surnames) > 3 else "")


def lookup_doi(doi):
    """DOI -> {title, authors, year, venue} or None if neither OpenAlex nor Crossref knows it."""
    quoted = urllib.parse.quote(doi, safe="/")
    try:
        w = openalex_json(f"works/doi:{quoted}")
        source = (w.get("primary_location") or {}).get("source") or {}
        return {"title": w.get("title"), "year": w.get("publication_year"), "venue": source.get("display_name"),
                "authors": short_authors(a["author"]["display_name"] for a in w.get("authorships", []))}
    except urllib.error.HTTPError:
        pass                     # 404, or OpenAlex's daily budget is used up (429): ask Crossref instead
    try:
        m = http_json(f"https://api.crossref.org/works/{quoted}")["message"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    year = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
    return {"title": (m.get("title") or [None])[0], "year": year, "venue": (m.get("container-title") or [None])[0],
            "authors": short_authors(f"{a.get('given', '')} {a.get('family', '')}" for a in m.get("author", []))}


def abstract_text(inverted):
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inverted:
        return ""
    words = sorted((pos, w) for w, positions in inverted.items() for pos in positions)
    return " ".join(w for _, w in words)


def search_papers(query, n=10, since=None):
    """OpenAlex search; falls back to Crossref (no daily cap, weaker ranking) when OpenAlex refuses."""
    params = {"search": query, "per-page": n,
              "select": "doi,title,publication_year,primary_location,cited_by_count,authorships,abstract_inverted_index"}
    if since:
        params["filter"] = f"from_publication_date:{since}-01-01"
    try:
        return openalex_json("works", params)["results"]
    except urllib.error.HTTPError as e:
        if e.code not in (403, 429):
            raise
        print(f"(OpenAlex said {e.code}: free daily budget used up, set OPENALEX_API_KEY. Using Crossref.)")
    cr = {"query.bibliographic": query, "rows": n,
          "select": "DOI,title,author,issued,container-title,is-referenced-by-count,abstract"}
    if since:
        cr["filter"] = f"from-pub-date:{since}"
    return [crossref_work(m) for m in http_json("https://api.crossref.org/works?" + urllib.parse.urlencode(cr))["message"]["items"]]


# ----------------------------------------------------------------------------------------------------
# READING / WRITING ENTRIES
# ----------------------------------------------------------------------------------------------------
class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s,
                                                             style=">" if len(s) > 90 else None))


def load_entries():
    entries = []
    for path in sorted(LEDGER_DIR.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            entries.append((path, yaml.safe_load(f) or {}))
    return entries


def save_entry(entry):
    path = LEDGER_DIR / f"{entry['id']}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(entry, f, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)
    return path


def _list_literal(path, name):
    """The value of `name = [...]` in a source file (read, not imported: no torch / numpy needed)."""
    import ast
    for node in ast.parse((ROOT / path).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise ValueError(f"{path}: no list {name}")


def built_feature_folders():
    """{module: (features_table.csv columns it makes, first docstring line)} for every module in BUILT."""
    out = {}
    for mod, (sources, extra) in BUILT.items():
        doc = re.match(r'\s*"""(.*?)(\n|""")', (ROOT / mod).read_text(encoding="utf-8"), re.S)
        out[mod] = ([c for f, v in sources for c in _list_literal(f, v)] + extra, doc.group(1).strip() if doc else "")
    return out


def normalize_entry(entry, path, cache, online, built):
    """Tidy one entry in place; return a list of problems to print."""
    problems = []
    entry["id"] = slug(entry.get("id") or path.stem)
    entry["aliases"] = sorted({a.strip().lower() for a in entry.get("aliases") or [] if str(a).strip()})
    entry["detectors"] = sorted({DETECTORS.get(str(d).lower(), str(d)) for d in entry.get("detectors") or []})
    if entry.get("family") not in FAMILIES:
        problems.append(f"family {entry.get('family')!r} not one of {FAMILIES}")
    entry["status"] = entry.get("status") or "idea"
    if entry["status"] not in STATUSES:
        problems.append(f"status {entry['status']!r} not one of {STATUSES}")

    mod = entry.get("implemented_in")
    if mod:
        mod = entry["implemented_in"] = str(mod).replace("\\", "/")
        if mod not in built:
            problems.append(f"implemented_in {mod} is not a module that makes features_table.csv columns ({', '.join(built)})")
        else:
            cols = entry.get("columns") or []
            if not cols:
                problems.append(f"implemented_in {mod} but no columns listed")
            unknown = [c for c in cols if c not in built[mod][0]]
            if unknown:
                problems.append(f"columns not made by {mod}: {', '.join(unknown)}")
            if entry["status"] in ("idea", "in_progress"):
                entry["status"] = "implemented"
    elif entry["status"] == "implemented":
        problems.append("status is implemented but implemented_in is empty")
    if entry["status"] == "v1_only" and not entry.get("v1_implemented_in"):
        problems.append("status v1_only but v1_implemented_in is empty")

    refs = {}
    for ref in entry.get("refs") or []:
        ref = {"doi": ref} if isinstance(ref, str) else dict(ref)
        if not ref.get("doi"):
            problems.append(f"ref without a doi: {ref}")
            continue
        doi = norm_doi(ref["doi"])
        merged = {**refs.get(doi, {}), **{k: v for k, v in ref.items() if v not in (None, "")}, "doi": doi}
        if online and not merged.get("verified"):
            if doi not in cache:
                try:
                    cache[doi] = lookup_doi(doi)
                except (urllib.error.URLError, TimeoutError) as e:
                    problems.append(f"could not look up {doi}: {e}")
                    cache[doi] = "error"
            meta = cache[doi]
            if meta == "error":
                pass
            elif meta is None:
                merged["verified"] = False
                problems.append(f"DOI {doi} NOT FOUND in OpenAlex or Crossref: fix or remove it")
            else:
                merged.update({k: v for k, v in meta.items() if v}, verified=True)
        refs[doi] = {k: merged[k] for k in REF_FIELDS if k in merged} | {k: v for k, v in merged.items() if k not in REF_FIELDS}
    entry["refs"] = sorted(refs.values(), key=lambda r: r["doi"])
    if not entry["refs"]:
        problems.append("no citations")

    ordered = {k: entry.get(k) for k in FIELDS}
    ordered.update({k: v for k, v in entry.items() if k not in FIELDS})
    entry.clear()
    entry.update(ordered)
    return problems


# ----------------------------------------------------------------------------------------------------
# DUPLICATE CHECK
# ----------------------------------------------------------------------------------------------------
def candidates(entries, built):
    """Everything a new feature could duplicate: ledger entries, and built folders not in the ledger."""
    out, covered = [], set()
    for _, e in entries:
        names = [e.get("id", "").replace("_", " "), e.get("name") or "", *(e.get("aliases") or [])]
        out.append({"what": f"ledger/{e.get('id')}", "status": e.get("status"), "short": " ".join(names),
                    "long": " ".join(names) + " " + (e.get("description") or ""), "names": names})
        covered.update(e.get("columns") or [])
    for mod, (cols, doc) in built.items():
        for c in cols:
            if c not in covered:
                names = [c.replace("_", " ")]
                out.append({"what": f"{mod}:{c}", "status": "built, NOT in ledger", "short": names[0],
                            "long": f"{names[0]} {doc}", "names": names})
    return out


def uncovered_columns(entries, built):
    covered = {c for _, e in entries for c in e.get("columns") or []}
    return [f"{mod}:{c}" for mod, (cols, _) in built.items() for c in cols if c not in covered]


def similarity(query, docs):
    """Cosine similarity of the query to each doc, mixing word and character n-grams (robust to wording)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    texts = [norm_words(query)] + [norm_words(d) for d in docs]
    scores = 0
    for vec, weight in ((TfidfVectorizer(analyzer="word", ngram_range=(1, 2)), 0.5),
                        (TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)), 0.5)):
        m = vec.fit_transform(texts)
        scores = scores + weight * cosine_similarity(m[:1], m[1:])[0]
    return scores


def name_match(query, names):
    """1.0 if the query IS one of the names/aliases (after normalising), 0.7 if one mostly contains the other."""
    q = set(norm_words(query).split())
    best = 0.0
    for n in names:
        t = set(norm_words(n).split())
        if q and q == t:
            return 1.0
        small, big = sorted((q, t), key=len)
        if len(small) >= 2 and small <= big and len(small) / len(big) >= 0.5:
            best = 0.7
    return best


def check(query, entries, built, top=5, exclude=None):
    """[(score, candidate)] best first. Score = max(name/alias match, short-text match, 0.8 x description match)."""
    cands = [c for c in candidates(entries, built) if c["what"] != exclude]
    if not cands:
        return []
    short, long_ = similarity(query, [c["short"] for c in cands]), similarity(query, [c["long"] for c in cands])
    scores = [max(name_match(query, c["names"]), s, 0.8 * l) for c, s, l in zip(cands, short, long_)]
    return sorted(zip(scores, cands), key=lambda t: -t[0])[:top]


def print_check(query, results):
    print(f'check: "{query}"')
    for score, c in results:
        tag = "DUPLICATE?" if score >= DUPLICATE else "related" if score >= RELATED else ""
        print(f"  {score:.2f}  {tag:<10} {c['what']:<38} [{c['status']}]  {c['short'][:70]}")
    best = results[0][0] if results else 0
    verdict = ("LIKELY DUPLICATE: extend the existing entry instead (add a ref/alias) unless it is genuinely different"
               if best >= DUPLICATE else "related entries exist: say how yours differs in its description"
               if best >= RELATED else "new: go ahead")
    print(f"=> {verdict}")
    return best >= DUPLICATE


# ----------------------------------------------------------------------------------------------------
# LEDGER.md
# ----------------------------------------------------------------------------------------------------
def render(entries, built, problems):
    refs = {}
    for _, e in entries:
        for r in e.get("refs") or []:
            refs.setdefault(r["doi"], {**r, "used_by": []})["used_by"].append(e["id"])
    order = {doi: i + 1 for i, doi in enumerate(sorted(refs, key=lambda d: (str(refs[d].get("authors")), d)))}
    by_status = {s: sum(e.get("status") == s for _, e in entries) for s in STATUSES}

    lines = ["# Feature ledger", "",
             "Generated by `python ledger/ledger.py normalize` from `ledger/entries/*.yaml`. Don't edit by hand.", "",
             f"**{len(entries)} features** ({', '.join(f'{n} {s}' for s, n in by_status.items() if n)}), "
             f"**{len(refs)} papers** ({sum(1 for r in refs.values() if r.get('verified'))} DOI-verified).", "",
             "| Feature | Family | Status | Built in | Detectors | Papers |", "|---|---|---|---|---|---|"]
    for _, e in sorted(entries, key=lambda t: (STATUSES.index(t[1].get("status", "idea")) if t[1].get("status") in STATUSES else 9, t[1]["id"])):
        cites = " ".join(f"[{order[r['doi']]}](#ref-{order[r['doi']]})" for r in e.get("refs") or [])
        built_in = (f"`{e['implemented_in']}`" if e.get("implemented_in")
                    else f"v1: `{e['v1_implemented_in']}`" if e.get("v1_implemented_in") else "")
        lines.append(f"| [{e.get('name') or e['id']}](#{e['id']}) | {e.get('family') or ''} | {e.get('status')} "
                     f"| {built_in} | {', '.join(e.get('detectors') or [])} | {cites} |")

    uncited = uncovered_columns(entries, built)
    if uncited:
        lines += ["", "**Built but not in the ledger (no citation yet):** " + ", ".join(f"`{f}`" for f in uncited)]
    if problems:
        lines += ["", "**Problems found by normalize:**", ""] + [f"- `{eid}`: {p}" for eid, p in problems]

    lines += ["", "## Features", ""]
    for _, e in sorted(entries, key=lambda t: t[1]["id"]):
        lines += [f"### {e.get('name') or e['id']}", f'<a id="{e["id"]}"></a>', "",
                  f"`{e['id']}` · {e.get('family')} · {e.get('status')}"
                  + (f" · `{e['implemented_in']}`" if e.get("implemented_in") else "")
                  + (f" · first repo: `{e['v1_implemented_in']}`" if e.get("v1_implemented_in") else "")
                  + (f" · owner: {e['owner']}" if e.get("owner") else ""), ""]
        if e.get("columns"):
            lines += ["Columns: " + ", ".join(f"`{c}`" for c in e["columns"]), ""]
        if e.get("v1_columns"):
            lines += ["First-repo columns: " + ", ".join(f"`{c}`" for c in e["v1_columns"]), ""]
        if e.get("description"):
            lines += [f"**What:** {e['description'].strip()}", ""]
        if e.get("battery_relevance"):
            lines += [f"**Why it matters for the battery:** {e['battery_relevance'].strip()}", ""]
        if e.get("findings"):
            lines += [f"**Findings on our data:** {str(e['findings']).strip()}", ""]
        for r in e.get("refs") or []:
            lines.append(f"- [{order[r['doi']]}](#ref-{order[r['doi']]}) {r.get('authors') or '?'} ({r.get('year') or '?'})"
                         + (f": {r['note']}" if r.get("note") else ""))
        lines.append("")

    lines += ["## References", ""]
    for doi in sorted(refs, key=order.get):
        r = refs[doi]
        flag = "" if r.get("verified") else " **(UNVERIFIED DOI)**"
        lines.append(f'<a id="ref-{order[doi]}"></a>{order[doi]}. {r.get("authors") or "?"} ({r.get("year") or "?"}). '
                     f'*{r.get("title") or "?"}*. {r.get("venue") or ""}. [doi:{doi}](https://doi.org/{doi}){flag}  '
                     f'\n   Used by: {", ".join(f"[{u}](#{u})" for u in sorted(set(r["used_by"])))}')
    LEDGER_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------------------------------
# COMMANDS
# ----------------------------------------------------------------------------------------------------
def canonical(x):
    """Order- and whitespace-insensitive form, so reflowed text, sorted lists or reordered keys don't count as a change."""
    if isinstance(x, dict):
        return tuple(sorted((k, canonical(v)) for k, v in x.items() if v not in (None, "", [])))
    if isinstance(x, list):
        return tuple(sorted((canonical(v) for v in x), key=repr))
    return " ".join(x.split()) if isinstance(x, str) else x


def cmd_normalize(args):
    """Tidy entries, but only REWRITE a file whose content changed (comparing parsed YAML, not formatting), and with
    --only, only the named entries: other people's files keep their own layout and line wrapping."""
    entries, built, cache, problems = load_entries(), built_feature_folders(), {}, []
    seen = {}
    for path, entry in entries:
        before = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        mine = not args.only or slug(entry.get("id") or path.stem) in {slug(o) for o in args.only}
        for p in normalize_entry(entry, path, cache, not args.offline and mine, built):
            problems.append((entry["id"], p))
        if entry["id"] in seen:
            problems.append((entry["id"], f"same id as {seen[entry['id']].name}"))
            continue
        seen[entry["id"]] = path
        if not mine or (canonical(entry) == canonical(before) and path.stem == entry["id"]):
            continue
        new_path = save_entry(entry)
        if new_path != path:
            path.unlink()
            print(f"renamed {path.name} -> {new_path.name}")
        else:
            print(f"updated {path.name}")
    for path, entry in entries:   # near-duplicate entries
        for score, c in check(entry.get("name") or entry["id"], entries, built, top=1, exclude=f"ledger/{entry['id']}"):
            if score >= DUPLICATE:
                problems.append((entry["id"], f"looks like a duplicate of {c['what']} (similarity {score:.2f})"))
    render(entries, built, problems)
    for eid, p in problems:
        print(f"  [{eid}] {p}")
    print(f"normalized {len(entries)} entries -> {LEDGER_MD.relative_to(ROOT)}  ({len(problems)} problems)")


def cmd_check(args):
    sys.exit(1 if print_check(args.query, check(args.query, load_entries(), built_feature_folders())) else 0)


def search_amass(query, n=10, since=None):
    """TF-IDF search over Jude's local Amass set (ledger/papers/amass_papers.json, core + method tiers). Free, offline."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from papers import load_papers
    papers = [p for p in load_papers(source="amass") if p.get("relevance") in ("core", "method")
              and (not since or int(p.get("year") or 0) >= since)]
    docs = [f"{p.get('title') or ''} {p.get('title') or ''} {p.get('abstract') or ''}" for p in papers]
    vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, ngram_range=(1, 2), min_df=2)
    scores = linear_kernel(vec.fit_transform(docs), vec.transform([query])).ravel()
    return [{"doi": p.get("doi"), "title": p.get("title"), "publication_year": p.get("year"),
             "primary_location": {"source": {"display_name": f"{p.get('journal') or ''} [amass {p.get('relevance')}]"}},
             "cited_by_count": p.get("citations"), "authorships": [], "abstract": p.get("abstract") or ""}
            for p in (papers[i] for i in scores.argsort()[::-1][:n])]


def cmd_search(args):
    cited = {}
    for _, e in load_entries():
        for r in e.get("refs") or []:
            cited.setdefault(norm_doi(r["doi"]), []).append(e["id"])
    found = search_amass(args.query, args.n, args.since) if args.amass else search_papers(args.query, args.n, args.since)
    for i, w in enumerate(found, 1):
        doi = norm_doi(w["doi"]) if w.get("doi") else None
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        authors = short_authors(a["author"]["display_name"] for a in w.get("authorships", []))
        print(f"\n[{i}] {w.get('title')}\n    {authors} ({w.get('publication_year')}) {venue} · cited {w.get('cited_by_count')}x")
        print(f"    doi: {doi or '-'}" + (f"   ALREADY CITED by {', '.join(cited[doi])}" if doi in cited else ""))
        abstract = abstract_text(w.get("abstract_inverted_index")) or w.get("abstract") or ""
        if abstract:
            print("    " + (abstract[:args.chars] + ("..." if len(abstract) > args.chars else "")))


def separation(df, col, n_perm=2000, seed=0):
    """One column of the spot table, spot = unit. -> {means, auc3, p3, within signs + p, auc12, p12}.
    auc3/p3: Batch_3 vs rest, labels permuted across spots. within: Batch_3 minus the rest inside each session that
    holds both, labels permuted inside sessions (so the session cannot be the cue). auc12/p12: Batch_1 vs Batch_2."""
    import numpy as np
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(seed)
    d = df[df.batch.str.startswith("Batch_")].dropna(subset=[col])
    v, sess, y = d[col].to_numpy(float), d.session.to_numpy(), (d.batch == "Batch_3").to_numpy()
    groups = [np.flatnonzero(sess == s) for s in np.unique(sess)]
    groups = [g for g in groups if y[g].any() and (~y[g]).any()]

    def within(lab):
        return np.array([v[g][lab[g]].mean() - v[g][~lab[g]].mean() for g in groups])

    def perm_auc(lab, x):
        a = abs(roc_auc_score(lab, x) - 0.5)
        return (1 + sum(abs(roc_auc_score(rng.permutation(lab), x) - 0.5) >= a for _ in range(n_perm))) / (n_perm + 1)

    w = within(y)
    null = []
    for _ in range(n_perm):
        yy = y.copy()
        for g in groups:
            yy[g] = rng.permutation(yy[g])
        null.append(abs(within(yy).mean()))
    b12 = d.batch.isin(["Batch_1", "Batch_2"]).to_numpy()
    y12 = (d.batch[b12] == "Batch_2").to_numpy()
    return {"means": d.groupby("batch")[col].mean().to_dict(), "auc3": roc_auc_score(y, v), "p3": perm_auc(y, v),
            "within": "".join("+" if x > 0 else "-" for x in w),
            "p_within": (1 + sum(n >= abs(w.mean()) for n in null)) / (n_perm + 1) if groups else float("nan"),
            "auc12": roc_auc_score(y12, v[b12]), "p12": perm_auc(y12, v[b12])}


def cmd_report(args):
    """Every built column: how it separates the batches on qc/processed/features_table.csv, the verdict zones from
    qc/processed/verdicts.json, next to why it should matter and its papers."""
    import pandas as pd
    if not FEATURES_TABLE.exists():
        sys.exit(f"no {FEATURES_TABLE.relative_to(ROOT)} yet: run  python qc/depth_profile.py && python qc/features_table.py")
    df = pd.read_csv(FEATURES_TABLE)
    lots = json.loads(VERDICTS.read_text())["lots"] if VERDICTS.exists() else {}
    measured, unmeasured = [], []
    for _, e in load_entries():
        cols = [c for c in e.get("columns") or [] if c in df.columns and df[c].notna().any()]
        (measured if cols else unmeasured).append((e, cols))
    for e, cols in measured:
        print(f"\n=== {e.get('name')}  [{e['id']}, {e.get('family')}, {', '.join(e.get('detectors') or [])}]  {e.get('implemented_in')}")
        for c in cols:
            s = separation(df, c, args.n_perm)
            means = " / ".join(f"{s['means'].get(f'Batch_{i}', float('nan')):.4g}" for i in (1, 2, 3))
            zones = "  ".join(f"{b[-1]}: {k['delta_sd']:+.2f} SD {k['zone']}" for b, lot in lots.items()
                              if b.startswith("Batch_") and (k := lot["kpis"].get(c)) and "delta_sd" in k)
            print(f"  {c:<32} B1/B2/B3 {means}  | B3 vs rest AUC {s['auc3']:.2f} p {s['p3']:.3f}  within {s['within']} "
                  f"p {s['p_within']:.3f} | B1 vs B2 AUC {s['auc12']:.2f} p {s['p12']:.3f} | verdict {zones}")
        print(f"  why: {(e.get('battery_relevance') or '-').strip()}")
        for ref in e.get("refs") or []:
            print(f"  paper: {ref.get('authors') or '?'} ({ref.get('year') or '?'}) {str(ref.get('title') or '')[:80]}  doi:{ref['doi']}"
                  + ("" if ref.get("verified") else "  UNVERIFIED"))
        if not e.get("refs"):
            print("  paper: NONE (no citation yet)")
    print(f"\n{len(unmeasured)} ledger entries without a built column here: " + ", ".join(e["id"] for e, _ in unmeasured))
    print("Read: spot = unit (31 spots). B3 vs rest p = labels permuted across spots; within = Batch_3 minus the rest inside"
          "\n      each session holding both, labels permuted inside sessions (p < 0.1 = not just the imaging session);"
          "\n      columns tested together share a family: correct for how many you looked at before quoting a p."
          "\n      verdict = delta from the Batch_3 baseline in its SDs and the zone from qc/verdict.py.")


def cmd_add(args):
    entries, built = load_entries(), built_feature_folders()
    fid = slug(args.id)
    if (LEDGER_DIR / f"{fid}.yaml").exists():
        sys.exit(f"ledger/entries/{fid}.yaml already exists: edit it instead")
    query = " ".join([fid.replace("_", " "), args.name, *args.alias])
    if print_check(query, check(query, entries, built)) and not args.force:
        sys.exit("not added (looks like a duplicate). Re-run with --force if it really is different.")
    entry = {"id": fid, "name": args.name, "aliases": args.alias, "family": args.family, "detectors": args.detector,
             "status": args.status, "owner": args.owner, "implemented_in": args.implemented_in, "columns": args.column,
             "description": args.description, "battery_relevance": args.relevance, "refs": args.doi}
    problems = normalize_entry(entry, LEDGER_DIR / f"{fid}.yaml", {}, not args.offline, built)
    print(f"wrote {save_entry(entry).relative_to(ROOT)}")
    for p in problems:
        print(f"  [{fid}] {p}")
    print("now run:  python ledger/ledger.py normalize")


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows consoles default to cp1252
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("normalize", help="tidy every entry, verify DOIs, flag duplicates, rebuild LEDGER.md")
    p.add_argument("--offline", action="store_true", help="don't look DOIs up")
    p.add_argument("--only", nargs="+", metavar="ID", help="only update (and look up DOIs for) these entries")
    p.set_defaults(fn=cmd_normalize)

    p = sub.add_parser("check", help="is this feature already in the ledger or built? (exit 1 = likely duplicate)")
    p.add_argument("query", help='feature name or one-line description, e.g. "pore size distribution"')
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("search", help="search papers: OpenAlex (Crossref fallback), or --amass for the local Amass set")
    p.add_argument("query")
    p.add_argument("--amass", action="store_true", help="search ledger/papers/amass_papers.json offline instead")
    p.add_argument("-n", type=int, default=8, help="number of results (default 8)")
    p.add_argument("--since", type=int, help="only papers from this year on")
    p.add_argument("--chars", type=int, default=350, help="abstract characters to show (default 350)")
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("report", help="built columns: batch separation on features_table.csv + verdict + why + papers")
    p.add_argument("--n-perm", type=int, default=2000, help="permutations per test (default 2000)")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("add", help="add a feature to the ledger (runs check first)")
    p.add_argument("id", help="short snake_case id, e.g. local_thickness")
    p.add_argument("--name", required=True, help="human-readable name")
    p.add_argument("--family", required=True, choices=FAMILIES)
    p.add_argument("--doi", action="append", default=[], help="a paper behind it (repeatable; arxiv:XXXX.XXXXX works)")
    p.add_argument("--detector", action="append", default=[], help="BSE / SE / Inlens (repeatable)")
    p.add_argument("--alias", action="append", default=[], help="other names for the same thing (repeatable)")
    p.add_argument("--description", default="", help="what it measures, how")
    p.add_argument("--relevance", default="", help="why it matters for the battery")
    p.add_argument("--status", default="idea", choices=STATUSES)
    p.add_argument("--owner", help="who is building it")
    p.add_argument("--implemented-in", help=f"the module that makes its columns if it's built: {', '.join(BUILT)}")
    p.add_argument("--column", action="append", default=[], help="a features_table.csv column it makes (repeatable)")
    p.add_argument("--force", action="store_true", help="add even if check says duplicate")
    p.add_argument("--offline", action="store_true", help="don't look DOIs up")
    p.set_defaults(fn=cmd_add)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
