# Residual: GXL Paperclip literature search

Second literature residual, added to fill the gap the first one left. Read `RESIDUAL_AMASS.md` first: it explains what a residual is and where the papers enter the pipeline. This file records only what is different.

| | |
|---|---|
| What was added | 9,478 papers on battery electrodes, of which 2,600 are directly about electrode structure or manufacturing |
| Source | GXL Paperclip, abstracts corpus: OpenAlex, Crossref, arXiv and PubMed Central (`https://paperclip.gxl.ai`) |
| Added | Sat 3 Oct 2026, 18:30 BST |
| Added by | Jude |
| Lives in | `literature/paperclip_papers.json` (committed), made by `literature/fetch_paperclip.py` from the same `literature/topics.yaml` |
| Cost | None. GXL gives hackathon teams unlimited Paperclip credits |

## Why it was added

Amass's corpus follows PubMed's journal list, so the field's own journals were nearly absent from it, and two of the track judge's papers were missing. Before a full run, both tools were compared on three searches (`literature/paperclip_test.json`):

| | Amass | Paperclip |
|---|---|---|
| Binder migration: top 20 about battery electrodes | 20 | 20 by keyword, about 16 by eye |
| Tortuosity, graphite anode: top 20 | 13 | 20 |
| Calendering and porosity: top 20 | 20 | 20 |
| Papers from the five core electrochemistry journals, top 100 of all three searches | 0 | 47 |
| TauFactor paper (Cooper et al., SoftwareX 2016) | not found | found |
| SliceGAN paper (Kench and Cooper, Nature Machine Intelligence 2021) | not found | found |
| Kintsugi imaging paper | not found | not found |

The Amass column uses the closest searches already cached, not the identical search strings, so the table is an indication and not a controlled test.

## What was searched

The same 144 topic searches as Amass, 300 papers each, plus the four broad sweep queries repeated for every publication year from 2012 to 2026 (60 searches). 204 searches in total.

## What is in it

Same layout and the same keyword tiers as the Amass file (`core`, `method`, `peripheral`), with the same warning: the tiers are a coarse filter, and the reliable ordering is the rank within a topic.

- 2,600 core papers. 223 of them are from the five core electrochemistry journals (Journal of The Electrochemical Society 168, Journal of Power Sources 35, Energy Storage Materials 14, Electrochimica Acta 4, Joule 2). The Amass core set has 3.
- Each paper also carries Paperclip's own relevance score for its best-matching search (`score`, 0 to 1).

## Both sources together

`load_papers()` merges the two files on DOI by default.

| | Papers |
|---|---|
| Amass only | 7,571 |
| Paperclip only | 5,960 |
| In both | 3,519 |
| Total unique | 17,050, of which 4,233 are core |

```python
from literature import load_papers

load_papers(topic="tortuosity", top=10)                       # both sources, merged
load_papers(topic="tortuosity", top=10, source="paperclip")   # one source
```

## Known gaps

- **Abstract only for the paywalled journals.** Paperclip holds full text for arXiv and PubMed Central papers. For the electrochemistry journals it has title and abstract.
- **Short abstracts.** For 918 of the 2,600 core papers the file holds only the first 200 or so characters of the abstract (`abstract_is_snippet: true`). The full abstract is one call away: `paperclip cat /papers/<paperclip_id>/meta.json`.
- **Journal names are partly missing.** Paperclip returns no journal for OpenAlex and Crossref records. The fetcher fills in the main journals from the DOI prefix; 379 core papers have no journal name. The DOI is always there to look it up.
- **Kintsugi imaging paper** is in neither source.

## Where it is used

Nothing reads `paperclip_papers.json` yet. Add a row each time something starts using it.

| Date | Used by | What it changed in the output |
|---|---|---|
| | | |

## To change or remove it

- Re-fetch or add a search: edit `literature/topics.yaml`, then run `python literature/fetch_paperclip.py` with Python 3.10 or newer and the Paperclip CLI logged in. Answers are cached in `processed/paperclip_cache/`.
- Remove: delete `literature/paperclip_papers.json`. `load_papers()` then returns the Amass papers alone.

## Credit

GXL Paperclip (https://paperclip.gxl.ai) — literature search, used with hackathon credits. This needs a line in the main README's credits when that section is written.
