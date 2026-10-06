# <feature name>

One-line summary: what it measures and the columns it adds to `processed/features.csv`.

| Column | Unit | Meaning |
|---|---|---|
| `<name>_<unit>` | | |

## Battery impact at a glance

| If it goes … | What it means in the cell | Good, bad or neither? | Confidence |
|---|---|---|---|
| up | mechanism in one line (e.g. "more Si phase: more capacity now, more swelling and faster fade later") | good / bad / neither / trade-off | strong / moderate / low |
| down | | | |

**Best value:** "as close to the approved baseline as possible" for most features (any shift means the supplier's
process changed), or a direction where one exists ("lower is better"). **Our batches:** where Batch_1 and Batch_2
sit against the baseline right now, in one line each, with the uncertainty.

## What it measures

The quantity in plain words, on which detector, at what scale. A materials expert should be able to picture it.

## Why it matters for the battery

The mechanism linking this microstructure to cell behaviour (transport, conductivity, adhesion, SEI growth,
swelling, …) and which direction of change is harmful. Each claim gets a citation from the References.

## Industry / Polaron use

Who measures this today (powder CoA item, cell-maker patent, imaging-vendor KPI, Polaron product) and which
supplier or process change would move it. Say "academic only" if that is the honest answer.

## How it is computed

Detector(s), the harmonisation used (`features/_common`), the algorithm step by step, and every tuning number
with its name in `config.yaml`.

## Evidence on our data

How it does on the 31 spots: per-batch means, separation and q from `analysis/rank_features.py`, the
within-session batch test, session R², perturbation ratio and split-half reliability. Say plainly when the
evidence is thin; a negative result is a result.

## Uncertainty and pitfalls

Error bars (sampling, segmentation, session), what can fool it (acquisition, pore-back, noise, curtaining),
and whether the 2D value is valid in 3D.

## References

Numbered list; DOIs only from `python ledger/ledger.py search` or `literature.load_papers`. Mark anything
unverified.
