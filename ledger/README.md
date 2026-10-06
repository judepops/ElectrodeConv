# ledger/ — every feature idea, the papers behind it, and how it did on our data

Carried over from the first repo (`a-rune/losslarp`), with its 38 entries and its paper index. One YAML file per
feature in `entries/` (one each, so two people adding features don't conflict). `LEDGER.md` is generated from them:
read it, don't edit it.

```bash
python ledger/ledger.py check "pore size from local thickness"   # already in the ledger or built? exit 1 = likely duplicate
python ledger/ledger.py search "binder migration drying anode"   # papers from OpenAlex (Crossref if OpenAlex refuses), marks DOIs we already cite
python ledger/ledger.py search "binder migration drying anode" --amass   # same, offline, over papers/amass_papers.json
python ledger/ledger.py add my_feature --name "..." --family morphology --doi 10.xxxx/yyyy --detector BSE \
    --description "what it measures, how" --relevance "why it matters for the battery"
python ledger/ledger.py normalize --only my_feature              # tidy that entry, verify its DOIs, rebuild LEDGER.md
python ledger/ledger.py report                                   # every built column vs the batches (needs qc/processed/)
```

A feature here is a set of columns of `qc/processed/features_table.csv`. An entry links to its code with
`implemented_in: <module>` (one of `BUILT` in `ledger.py`: `cnn/tile_features.py`, `qc/depth_profile.py`) and lists
its `columns`; `normalize` checks that the module makes them and lists any built column no entry covers. Put the
numbers of `report` in `findings:`. Claim an idea you're building with `owner:` and `status: in_progress`.

`report`, per column (spot = unit, 31 spots): batch means; Batch_3 vs rest AUC with a spot-permutation p; `within` =
Batch_3 minus the rest inside each imaging session that holds both, with labels permuted inside sessions (small p =
not just the session); Batch_1 vs Batch_2 AUC and p; and the verdict's delta from the Batch_3 baseline in its SDs with
its zone (`qc/verdict.py`). Correct for how many columns you looked at before quoting a p.

Families: `morphology`, `spatial_statistics`, `texture`, `transport`, `composition`, `orientation`, `depth_profile`,
`learned`, `acquisition`. Statuses: `idea`, `in_progress`, `implemented`, `v1_only` (built in the first repo, path in
`v1_implemented_in`, not ported yet: a port candidate with its first-repo `findings`), `rejected` (keep rejected ones:
a negative result stops someone re-trying it).

Only use DOIs a search tool printed; `normalize` flags any it can't find in OpenAlex or Crossref.

## papers/

The paper index behind the entries, the same files as the first repo's `literature/` (moved here because
`literature/` in this repo is the GXL evidence layer): `amass_papers.json` (Jude's Amass search, ~11k papers),
`paperclip_papers.json` (the same searches through GXL Paperclip), `topics.yaml` (the searches), the two fetch
scripts, and `RESIDUAL_*.md` (what each source covers and misses). Read with
`sys.path.insert(0, "ledger"); from papers import load_papers`. `literature/evidence.py` is the step after: for a built
feature, which way the papers say it moves each battery outcome.

OpenAlex without a key shares a small free daily budget per IP address (search costs 10 of 1000 credits), so a busy
network runs out. Lookups then fall back to Crossref automatically. For your own budget, get a free key at
openalex.org and `set OPENALEX_API_KEY=...`.
