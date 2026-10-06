# cloud/

The feature pipeline on [Modal](https://modal.com/docs): the same code as `features/run_features.py`, but with one cloud container per microscope spot, all running at once. A full run takes about a minute instead of 10-15 minutes on a laptop, and gives the same numbers. CPU only. One file: `modal_app.py`.

```bash
modal run cloud/modal_app.py                                    # every batch -> processed/features.csv
modal run cloud/modal_app.py --train                            # retrain the trained features on Batch_3 first (= run_features.py --train)
modal run cloud/modal_app.py --batches Batch_4                  # only Batch_4; the other batches' rows are kept
modal run cloud/modal_app.py --stage verdict --batches Batch_4  # certificate -> analysis/verdicts/Batch_4.{md,json} + forest plot
modal run cloud/modal_app.py --stage all --batches Batch_4      # features, then the verdict
modal run cloud/modal_app.py --stage train                      # only retrain; models/ updated locally
modal run cloud/modal_app.py --sites Batch_1/ffwubibz,Batch_3/cfe5vt7s --csv /tmp/check.csv   # a few spots, for a quick check
```

Run from the repo root. Locally you only need the Modal CLI (`pip install modal`), not the packages in `requirements.txt`: everything that needs numpy or pandas runs in the cloud. `modal run` is ephemeral: the app stops when the command returns, so nothing keeps running or costing money afterwards.

## First time

1. Log in once: `modal setup` (or `modal token new`). The token goes to `~/.modal.toml` in your home folder. Never put it, or any other key, in the repo.
2. Upload the raw images to the shared Volume `losslarp-data` (1.6 GB; about 70 s on a fast connection). `modal volume put` does not create the Volume, so create it once per Modal workspace first. The folder name after `/data/` must be the batch name:

   ```bash
   modal volume create losslarp-data                # once per workspace ("already exists" is fine)
   modal volume put losslarp-data data/Batch_1 /data/Batch_1
   modal volume put losslarp-data data/Batch_2 /data/Batch_2
   modal volume put losslarp-data data/Batch_3 /data/Batch_3
   modal volume ls losslarp-data /data              # check: Batch_1  Batch_2  Batch_3
   ```

   Check `modal volume ls losslarp-data /data` first: a teammate in the same workspace may have uploaded it already. Add `--force` to overwrite files that are already there.
3. `modal run cloud/modal_app.py --train`. The first run also builds the image (about 30 s, then cached).

## When the new batch arrives

Put it at `data/Batch_4/` with the same file names as the other batches, then:

```bash
modal volume put losslarp-data data/Batch_4 /data/Batch_4
modal run cloud/modal_app.py --stage all --batches Batch_4
```

This writes `processed/features.csv` (your local file, with Batch_4's rows replaced or added and the other batches' rows kept), a copy of it on the Volume, and `analysis/verdicts/Batch_4.md`, `Batch_4.json` and `Batch_4_forest.png`. Do not pass `--train` here: the trained features learn the baseline (Batch_3) only, and that has not changed.

## What runs where

| Function | Runs | Size | Timeout | Does |
|---|---|---|---|---|
| `prepare` | 1 container | 0.5 CPU, 1 GB | 2 min | lists the spots on the Volume (`preprocessing.list_samples`), copies the repo's `models/` into the Volume |
| `features_for_site` | one container per spot (at most 40 at once), retried once if a container dies | 2 CPU, 4 GB | 10 min | `load_sample` + `compute_all` on one spot, returns its `features.csv` row |
| `train_baseline` | 1 container (only with `--train`) | 2 CPU, 8 GB | 30 min | `train_all` on the Batch_3 samples, into the Volume's `models/`. Returns the model files, and the local side copies them into `models/` (commit them from there) |
| `assemble` | 1 container | 1 CPU, 2 GB | 5 min | builds `features.csv` with `run_features.py`'s own rules (`merge_with_existing`, column order, sorting, summary) |
| `verdict` | 1 container, one call per batch | 1 CPU, 2 GB | 5 min | `analysis/verdict.py <batch> --json` on your local `features.csv` (and your `processed/robustness.csv` if you have one, for the R2 gate). Sessions come from the TIF headers on the Volume. Both files are written to their local paths inside the container, so the certificate names your files exactly as a local run does |

Each container gets:
- **Code:** your working copy of the repo, uploaded on every `modal run` to `/root/losslarp`. Uncommitted edits are included. `data/`, `processed/`, `.git`, `__pycache__` and `literature/amass_papers.json` are left out.
- **Packages:** `requirements.txt` on Python 3.11, with each version pinned to the team's local one (`PINNED` in `modal_app.py`: numpy 1.26.4, scipy 1.16.3, scikit-image 0.26.0, ...). An unpinned image would pull numpy 2.x. If you upgrade a package locally, update `PINNED`. A package added to `requirements.txt` but not to `PINNED` installs at its latest version.
- **Folders:** `LOSSLARP_DATA_DIR`, `LOSSLARP_PROCESSED_DIR` and `LOSSLARP_MODELS_DIR` point `preprocessing` at the Volume (mounted at `/vol`), so no feature code changes.

## The Volume

| Path on the Volume | What | Written by |
|---|---|---|
| `/data/Batch_*/img_*.tif` | raw images | you (`modal volume put`) |
| `/processed/full/{batch}/{sample_id}_{detector}.png` | clean images, about 30 MB per spot | `preprocessing.load_image`, on first use |
| `/processed/harmonised/{batch}/{sample_id}_{hash}.npz` | the shared harmonised spot, about 80 MB per spot | `features/_common/harmonise.py`, on first use |
| `/processed/features.csv` | copy of the last full or `--batches` run (not `--sites`) | `assemble` |
| `/models/` | mirror of the repo's `models/` (or the freshly trained files) | `prepare` / `train_baseline` |

- **Caches.** Each spot's container commits the clean PNGs and harmonised arrays it made, so the next run (after you add a feature, say) skips the PNG cleaning and the harmonisation, about 5-10 s per spot. The commit is best-effort: if it fails, the row still counts and only the cache is lost. Containers never write the same file (one spot each), and both caches write to a temporary name and then rename. The harmonised file name includes a hash of `features/_common/harmonise.py` and `config.yaml`, so changing the recipe never reuses stale arrays. Old hashes are left behind, though, at about 2.5 GB per recipe version for all 31 spots. Clean them with `modal volume rm -r losslarp-data /processed/harmonised`. The PNG cache is not hashed: after changing `preprocessing`'s cleaning steps, run `modal volume rm -r losslarp-data /processed/full`, the same as `process_data.py --force` locally.
- **Models.** Every run first makes `/models` an exact copy of your local `models/`, including deleting files that are not in the repo, so trained features read what a local run would read. With `--train`, the fresh models are written to the Volume and copied back into your `models/`. The Volume is shared by the whole Modal workspace: if two people run at once with different `models/` folders, the last mirror wins.
- **A failed spot writes nothing.** If any spot raises an error (a missing image, or a container out of memory twice), no CSV is written and the failed spots are listed. A CSV with a spot missing would quietly change a verdict. A single feature that fails still gives NaN in its column, the same as locally.

## Same numbers as a local run

Checked twice against a local run of the same code snapshot with a fresh `processed/` folder:

- **Builder check.** 3 spots from the mixed session 2080: Batch_1/ffwubibz, Batch_2/r17byphk, Batch_3/cfe5vt7s.
- **Review re-check.** 7 spots, one from each mixed session plus the two odd sessions: rxax5ozo (2068), ffwubibz (2080), f1vzngrs (2148), b3esycq1 (2156), pl8uabbv (2272), 71vgq3fw (2060, lifted black level) and 4ih2ggld (2316, the Si-phase lead).

Results:

- **Clean PNGs** are byte-identical (checked for all 3 detectors of 4ih2ggld and the BSE of b3esycq1).
- **Harmonised arrays.** The masks (`void`, `bright`, `bright_fixed`, `dim`), the `acq` dict, Inlens and SE are identical. Anchored BSE differs by at most 1.2e-7 on 7 of 9.3 M pixels of 4ih2ggld, about one float32 rounding step (x86 vs Apple ARM).
- **Feature values.** The re-check covers all 69 columns on 7 spots, 483 values. Fresh spots were compared with a fresh local run, and spots already cached on the Volume with a local run from its own cache:
  - 461 values are bit-identical.
  - 13 are NaN in both. `interface_density_resid_z` is NaN on all 7 spots because its model was not in `models/` yet. `carbon_domain_boundary_on_particle_frac` is NaN on 6 spots, the same as locally.
  - 9 differ, with the largest relative difference 1.3e-11 (`bright_core_cv`).
  - The cited columns are all bit-identical on every spot: `porosity_frac`, `bright_phase_frac`, `porosity_open_frac`, `bright_frac`, `acq_bse_black_level` and `histogram_anomaly_z`.
  - Compare CSVs with `pd.read_csv(..., float_precision="round_trip")`, because pandas' default parser drops the last digit itself.
- **Training.** `train_baseline` on Modal gives a `histogram_anomaly.npz` with the same arrays as the committed `models/` file. Its `minkowski_functionals.npz` has the same arrays as a local computation on the 17 baseline spots.
- **Verdict.** This is `analysis/verdict.py` for Batch_1 and Batch_2 on a 31-spot `features.csv`, run with and without a robustness CSV.
  - Certificate (`.md`) and forest plot are byte-identical to a local run, file paths included.
  - In the `.json`, the verdicts and every non-float field are identical. 50 floats differ in the last digit, by at most a relative 4e-15.
  - The `--batches` merge in `assemble` gives the same rows, columns and order as `run_features.merge_with_existing` run locally.
- **Fresh vs cached.** A spot computed from scratch and the same spot read from the harmonised cache match except `acq_curtain_index`, which differs by a relative 2e-6 to 3e-5. This is because the cache stores Inlens/SE as float16, so it happens locally too. A spot cached on the Volume therefore matches a local run that reads its own cache.

## Time and cost

Measured on the 3-spot check (3 containers) and the 7-spot re-check (7 containers):

| Run | Whole `modal run` | Spot map | Per spot, inside its container |
|---|---|---|---|
| First ever: image build (about 22 s, once) + cold cache, 3 spots | 82 s | 41 s | load 7-11 s + features 20-27 s |
| Warm cache (PNGs + harmonised already on the Volume), 3 spots | 36 s | 21 s | load 3.4 s + features 14-16 s |
| 7 spots, 4 uncached + 3 cached, image already built | 47 s | 34 s | load 2.7-8.8 s + features 15.6-22.2 s |
| `--stage verdict` (1 container) | 12-15 s per batch | | |
| `train_baseline` alone (1 container, 17 baseline spots, 16 not yet cached) | 242 s | | |

A full 31-spot run uses 31 containers in parallel. Expect about a minute of wall time and roughly 0.4-0.7 core-hours in total (31 spots x 2 cores x 25-40 s), which is a few cents at Modal's CPU rates. `--train` adds the single training container before the map (about 4 minutes on a cold cache, less once the baseline spots are cached). The exact bill for each run is on the app page linked in the `modal run` output.

## When something goes wrong

| Message | Cause and fix |
|---|---|
| `modal volume put` says the Volume `losslarp-data` is not found | it does not exist in this workspace yet: `modal volume create losslarp-data`, then upload |
| `not on the Volume: ['Batch_4']` / `no /vol/data on the Volume` | the images were never uploaded: `modal volume put losslarp-data data/Batch_4 /data/Batch_4` |
| `<file> was modified during build process` | a file in the repo was saved while `modal run` was uploading the code (a teammate or an agent editing). Run the command again |
| `[interface_density_resid_z] failed ... minkowski_functionals.npz is missing` | that feature's model is not in `models/` yet. Run once with `--train`, then commit `models/` |
| `spots that failed (no CSV written)` | listed per spot with the error. The container log above it has the traceback |

When you are done, check that nothing is left: `modal app list` should show no `losslarp` app as running. To stop one, use its App ID from the list: `modal app stop ap-...`. `modal app stop losslarp` does not work here, because the CLI looks names up among deployed apps only and `modal run` apps are ephemeral. Nothing here is deployed, so there is nothing to tear down.
