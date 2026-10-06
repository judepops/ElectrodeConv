# Residual: Amass literature search

A "residual" is something added to the pipeline from outside the main path, written down so its contribution can be traced, measured and switched off. This file is the record for one of them: the papers pulled from the Amass literature search.

| | |
|---|---|
| What was added | 11,091 papers on battery electrodes, of which 2,776 are directly about electrode structure or manufacturing |
| Source | Amass BiomedCore literature search, `https://api.amass.tech/api/v1/cores/biomedcore/records` |
| Added | Sat 3 Oct 2026. First pull 17:07 BST (390 papers, 13 searches); deep pull 17:22 BST (184 searches) |
| Added by | Jude |
| Lives in | `literature/amass_papers.json` (13 MB, committed), made by `literature/fetch_amass.py` from `literature/topics.yaml` |
| Cost | 13,855 Amass credits (75 per search of 300 papers) |

## What it adds to the pipeline

The papers are used at two points, and removing them breaks neither the feature code nor the comparison.

```
            papers (Amass)
             |          |
   1. which features    2. what a difference
      to compute           means for the battery
             v          v
images -> features -> between-batch differences -> report
```

1. **Feature selection, before any batch comparison.** The papers say which properties of an electrode are known to matter, so the feature list is pegged to published mechanisms instead of chosen after seeing which features separate the batches.
2. **Structure to function, after the comparison.** For a feature that does separate the batches, the papers give the mechanism linking it to cell behaviour and the direction that is harmful.

Without the papers, the report states the differences with no functional interpretation and the feature list has no stated justification. That is the comparison to make when asking what this residual contributed.

## What was searched

184 searches, each returning the maximum of 300 papers. The full list of search strings is `literature/topics.yaml`.

- **144 topic searches across 38 topics**, written from the Track 4 brief, the Polaron engineer's notes and the feature map. Every term in those documents that could describe an electrode has at least one search.
- **40 sweep searches**: four broad queries, each repeated over ten publication-date windows, to reach past the 300-paper cap.

Polaron has not confirmed the material is a graphite anode, so the searches are not limited to graphite. Most topics have a chemistry-neutral search next to the graphite one, and cathodes, silicon, hard carbon and metal contamination have their own topics.

| Group | Topics |
|---|---|
| The problem as set | batch-to-batch variability, process-structure-property, manufacturing QC, defects that show up later |
| Process steps | slurry mixing, bubbles and voids, drying and binder migration, calendering |
| Features | porosity, pore size, tortuosity, flake orientation, particle size, particle morphology, interface density, particle cracking, carbon-binder domain, porosity gradient, coating thickness, adhesion, homogeneity descriptors |
| What the bright phase could be | silicon / SiOx, metal contamination, phase identification by BSE and EDS |
| If it is not a graphite anode | cathode microstructure, other anodes, graphite supply |
| Function | rate and lithium plating, SEI and first-cycle loss, capacity fade, resistance |
| Sample preparation and imaging | cross-section preparation, SEM acquisition |
| Methods | SEM image analysis, 3D generation from 2D, representation learning, acquisition shift, microstructure modelling |

## What is in it

Amass's search always returns 300 papers, drifting off topic when it runs out of relevant ones, and its corpus is mostly biomedical. So each paper is given a tier by keyword rules (in `fetch_amass.py`) and papers with no battery or materials-imaging content are dropped: 44,109 of the 55,200 results returned were duplicates or dropped.

| Tier | Papers | Meaning |
|---|---|---|
| `core` | 2,776 | A battery paper about electrode structure or manufacturing. 1,399 have full text in Amass; 1,939 are from 2020 or later. |
| `method` | 1,737 | Not a battery paper; a materials microstructure or imaging method. Noisy: a sample still contained concrete, alloys and biosensors. |
| `peripheral` | 6,578 | A battery paper about something else (new-material synthesis, electrolytes, recycling). Stored without abstracts. |

The tiers are a coarse filter, not a judgement of each paper: a random sample of `core` still contained nano-material synthesis papers. The reliable ordering is the search rank within a topic, so read topics from the top. The best 50 papers of every topic together come to 1,388 unique papers, and that is the realistic size of the directly useful set.

Each entry carries title, abstract, journal, year, DOI, PubMed id, citation count, tier, what it is useful for, how many searches found it, and its rank within each topic.

## How the harness reads it

```python
from literature import load_papers

load_papers(topic="binder_migration", top=10)            # ten most relevant papers on a topic
load_papers(feature_column="porosity_frac", top=10)      # papers behind one features.csv column
load_papers(use="feature_selection", relevance="core")   # everything usable for choosing features
```

No API key is needed to read. The key is only needed to re-fetch, and is read from `AMASS_API_KEY` or `.secrets`. Raw search answers are cached in `processed/amass_cache/` (not committed), so a re-run costs credits only for new searches.

## Known gaps

- **Core electrochemistry journals are nearly absent.** The corpus follows PubMed's journal list. Among the 2,776 core papers there are 3 from Journal of Power Sources and Journal of the Electrochemical Society together, and none from Electrochimica Acta, Energy Storage Materials or Joule. Coverage is strong in Nature Communications, ACS Applied Materials & Interfaces, Advanced Science, Small, ACS Nano and Scientific Reports. Claims that rest on the missing journals need a web search as well.
- **Some of the track judge's own papers are missing.** Sam Cooper's ImageRep paper is in; TauFactor, the original SliceGAN paper and the Kintsugi imaging paper were not found.
- **Patents were tested and left out.** Amass's patent database holds battery patents only where they are also classified as organic chemistry or medical devices (64 in the main lithium-ion class).

## Where it is used

Add a row here each time something starts using it, so the claim "the Amass papers were used in production" points at specific code and outputs.

| Date | Used by | What it changed in the output |
|---|---|---|
| 3 Oct 2026 | `python ledger/ledger.py search "<topic>" --amass` (Adarsh, commit `918c9ee`) | The feature ledger can find papers for a feature idea offline from this file, and the feature template accepts DOIs from `literature.load_papers`. No ledger entry cites an Amass-found paper yet; add a row when one does. |

## To change or remove it

- New search: add it to `literature/topics.yaml`, then `python literature/fetch_amass.py`. `--dry-run` shows the cost first.
- Remove: delete `literature/amass_papers.json`. Nothing in `preprocessing/`, `features/` or `analysis/` depends on it.

## Credit

Amass (https://amass.tech) — BiomedCore literature search API, used with hackathon credits. This needs a line in the main README's credits when that section is written.
