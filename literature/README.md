# literature

The link from a measured feature to a battery outcome, backed by papers that were read, and from there to which
how Batch_1 and Batch_2 differ from the baseline in what a customer would care about. It is section 08 of the team page.

```bash
python literature/evidence.py         # feature x outcome -> what the papers say   (GXL Paperclip, ~15 min, free)
python literature/batch_outlook.py    # measured shifts x paper directions -> which batch, and why   (seconds, offline)
```

| File | What it is |
|---|---|
| `EVIDENCE.md` / `evidence.json` | For every feature and battery outcome: how many papers say higher means more, less, an optimum or no effect; the sentence each paper says it in, with its DOI; and whether that agrees with the sign in `qc/impact_rules.yaml` |
| `BATCH_OUTLOOK.md` / `batch_outlook.json` | Batch_1 and Batch_2 against Batch_3 on six outcomes, how the ranking changes under different assumptions, and the features and sentences behind every number |
| `../dashboard/site/literature.js` | The same numbers for section 08 of the team page, written by `batch_outlook.py` |
| `feature_cards.py` / `feature_cards.json` | What each feature looks like: the tile at the 5th, 50th and 95th percentile with the measured phase tinted, where the three batches sit between them, and what the papers say more of it does. Pictures go to `dashboard/site/img/lit_*.jpg`; run it before `batch_outlook.py` |
| `evidence_terms.yaml` | The questions: which feature columns measure which concept, and how each outcome is worded. Add a feature here when one is built |
| `web_references.yaml` | Seven extra papers from an ordinary web search, for the questions the reader left unsettled. Shown, never counted |

## Where each item comes from

Every item in `EVIDENCE.md` and on the page carries one of these tags.

| Tag | Source | Read in full? | Counted? | How many |
|---|---|---|---|---|
| `GXL read` | GXL Paperclip: search of PubMed Central and arXiv, then its paper reader | Yes, by the reader; the quoted sentence was found in the paper | Yes | 228 answers from 138 papers |
| `GXL abstract` | GXL Paperclip search, papers it holds as abstract only (mostly the paywalled electrochemistry journals) | No | No | up to 8 listed per question |
| `web` | An ordinary web search, not GXL | No, search summaries and abstracts only | No | 7 |
| (none) | The citations inside `qc/impact_rules.yaml` | They are the team's own, carried over from the first repo's research report | n/a | 16 |

Amass was not used for this layer. It was used in the first repo (`losslarp/literature/`), where an Amass search
and then a Paperclip search built the paper index behind the feature ledger; the comparison of the two tools is
recorded there.

## How the evidence is made

1. **One question per pair**, for example *when electrode porosity is higher, is charging faster or slower?* There
   are 13 concepts (porosity, silicon fraction, silicon particle size, ..., thin ligaments and current-collector
   porosity from `qc/depth_profile.py`) and the 6 outcomes of `qc/impact_rules.yaml`. `evidence.py` keeps the pairs
   already in `evidence.json` that have no local cache (the cache is git-ignored), so `--only <concept>` on another
   machine adds to the table instead of replacing it. On Windows run with `PYTHONUTF8=1`.
2. **Paperclip searches its full-text papers** and its reader opens the top 25, answering in a fixed schema: does
   the paper address the question, which direction, experiment or simulation or review, and one sentence copied
   from the paper.
3. **Every quoted sentence is looked up in the paper's text.** An answer whose sentence is not found is dropped
   (44 were).
4. **The directions are counted.** "More" or "less" needs at least two papers and twice as many as the other side.

`evidence.py` holds no model. It counts the reader's answers.

## How the batch outlook is made

It reads two things that already exist: the feature shifts from `qc/verdict.py` and `cnn/explain.py` (through
`dashboard/site/pipeline.js`), and `evidence.json`. For each batch and outcome it multiplies each feature's shift
from Batch_3 by the direction the papers agree on, weights by the number of papers, and sums. The intervals come
from redrawing every shift from its own interval. The full recipe is in the docstring of `batch_outlook.py`.

Batch_3 is the baseline: Polaron describes it as what the supplier promised, with Batch_1 and Batch_2 arriving afterwards. 
Baseline does not mean defect-free, and its score is 0 because the other two are measured against it.

**Read the sensitivity table before quoting a ranking.** Batch_2 leads because of one clear measurement, a lower
silicon fraction, which counts towards three outcomes. Without that feature no batch leads.

## Limits

- **Silicon is confirmed, silicon oxide is not.** Polaron says the bright particles are silicon and the dark ones graphite.
  Several papers read are about silicon oxide, which swells less than silicon.
- **The batches are constructed groups.** Polaron made them by cutting about 20 large images into crops and grouping the crops on features it extracted.
  So neighbouring crops of one strip can sit in different batches, and a batch is a kind of microstructure, not a production lot.
- **Only open-access papers are read.** The reader cannot open the paywalled electrochemistry journals.
- **A machine read the papers.** Each sentence is in its paper, but nobody checked that the paper's material and
  setting match this electrode. Read the sentence before citing it.
- **No cycling data.** Every outcome here is an expectation from the literature, not a measurement on these batches.
- **After `dashboard/build.py`, run `python literature/batch_outlook.py` again**, or section 08 keeps the old numbers.

## Credit

GXL Paperclip (https://paperclip.gxl.ai), literature search and paper reader, used with hackathon credits.
