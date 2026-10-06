"""The pipeline on Modal: one cloud container per microscope spot, all spots at once.

Same code, same package versions and same files as the local commands, so the numbers match a local run. The
difference is wall time: every spot is computed in parallel (about a minute for all 31 spots instead of
10-15 minutes on a laptop). CPU only. See cloud/README.md for the first-time setup and the data upload.

Run from the repo root (`modal` is the Modal CLI; it needs nothing else from requirements.txt locally):
    modal run cloud/modal_app.py                                   # every batch on the Volume -> processed/features.csv
    modal run cloud/modal_app.py --batches Batch_4                 # only Batch_4; other batches' rows are kept
    modal run cloud/modal_app.py --train                           # retrain the trained features on the baseline first
    modal run cloud/modal_app.py --stage verdict --batches Batch_4 # certificate -> analysis/verdicts/Batch_4.*
    modal run cloud/modal_app.py --stage all --batches Batch_4     # features, then the verdict
    modal run cloud/modal_app.py --stage train                     # only retrain; models/ updated locally
    modal run cloud/modal_app.py --sites Batch_1/ffwubibz,Batch_3/cfe5vt7s --csv /tmp/check.csv   # a few spots only

Options (the local_entrypoint `main` below):
    --stage     features (default) | train | verdict | all
    --batches   comma-separated batch names (default: every batch on the Volume)
    --train     call train() of every trained feature on the baseline before computing (= run_features.py --train)
    --sites     comma-separated batch/sample_id pairs: compute only these, write only --csv (no merge, no Volume copy)
    --csv       local output CSV (default processed/features.csv; with --sites, processed/features_sites.csv)
    --out-dir   where verdict certificates go locally (default analysis/verdicts)

Where things live:
    Volume "losslarp-data", mounted at /vol:
        /vol/data/Batch_*/img_*.tif     the raw TIFs (upload: modal volume put losslarp-data data/Batch_4 /data/Batch_4)
        /vol/processed/full/            clean PNG cache (preprocessing.load_image writes it on first use)
        /vol/processed/harmonised/      harmonised-spot cache (features/_common/harmonise.py writes it on first use)
        /vol/processed/features.csv     a copy of the last full/--batches run
        /vol/models/                    mirror of the repo's models/ for every run (or the freshly trained models)
    Image: Python 3.11 + requirements.txt (versions pinned to the team's local ones) + the repo code at /root/losslarp
    (data/, processed/, .git and caches left out). The code is re-read from your working copy on every `modal run`.

Every function has a timeout; `modal run` is ephemeral, so nothing keeps running (or costs anything) after it exits.
"""
import re
import time
from pathlib import Path

import modal

APP_NAME = "losslarp"
VOLUME_NAME = "losslarp-data"
VOL = "/vol"                                    # the Volume's mount point inside every container
REMOTE_REPO = "/root/losslarp"                  # the repo code inside the image
# The repo root on this machine (cloud/ is one level down). Inside a container the file sits elsewhere, so use the image copy.
REPO = Path(__file__).resolve().parents[1] if modal.is_local() else Path(REMOTE_REPO)

# requirements.txt says WHICH packages; these pin WHICH versions, so Modal computes exactly what a local run computes
# (an unpinned image would install numpy 2.x, whose percentile/RNG/filter details can move thresholds slightly).
# The versions of the team's local Python 3.11. A package missing here (new in requirements.txt) installs unpinned.
PINNED = {"numpy": "1.26.4", "scipy": "1.16.3", "scikit-image": "0.26.0", "scikit-learn": "1.7.2",
          "pandas": "2.2.3", "matplotlib": "3.10.7", "pillow": "10.2.0", "pyyaml": "6.0.1"}

# Left out of the image: data and outputs live on the Volume; the rest is not needed to compute anything.
IGNORE = ["data", "processed", ".git", "**/__pycache__", "**/*.pyc", "**/.DS_Store", ".venv", "venv",
          ".claude", ".hyperresearch", "research", "literature/amass_papers.json"]


def requirements():
    """requirements.txt as a pip list, each bare package name pinned to its PINNED version."""
    path = REPO / "requirements.txt"
    if not path.exists():        # only matters where the image is built (locally); a container never rebuilds it
        return []
    lines = [ln.split("#")[0].strip() for ln in path.read_text().splitlines()]
    return [f"{ln}=={PINNED[ln.lower()]}" if ln.lower() in PINNED else ln for ln in lines if ln]


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(*requirements())
    .env({
        "LOSSLARP_DATA_DIR": f"{VOL}/data",              # preprocessing/process_data.py reads these three
        "LOSSLARP_PROCESSED_DIR": f"{VOL}/processed",
        "LOSSLARP_MODELS_DIR": f"{VOL}/models",
        "PYTHONPATH": REMOTE_REPO,                       # so `import preprocessing, features` works from anywhere
        "MPLBACKEND": "Agg",
        "PYTHONUNBUFFERED": "1",                         # container prints stream to your terminal straight away
    })
    .add_local_dir(REPO, REMOTE_REPO, ignore=IGNORE)     # last: mounted at container start, no image rebuild per edit
)
volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
app = modal.App(APP_NAME, image=image)
VOLUMES = {VOL: volume}


# ----------------------------------------------------------------------------------------------------
# REMOTE: runs in the cloud containers
# ----------------------------------------------------------------------------------------------------
def _mirror_models():
    """Make /vol/models an exact copy of the repo's models/ (as uploaded with the code), so trained features read the
    same files a local run reads. Files not in the repo are removed: a model deleted locally must not live on here."""
    import shutil
    src, dst = Path(REMOTE_REPO) / "models", Path(VOL) / "models"
    dst.mkdir(parents=True, exist_ok=True)
    keep = {p.name for p in src.iterdir() if p.is_file()}
    for p in dst.iterdir():
        if p.is_file() and p.name not in keep:
            p.unlink()
    for name in sorted(keep):
        shutil.copyfile(src / name, dst / name)
    return sorted(keep)


@app.function(volumes=VOLUMES, cpu=0.5, memory=1024, timeout=120)
def prepare(batches: list, sites: list, mirror_models: bool) -> list:
    """The (batch, sample_id) pairs to compute, read from the Volume with preprocessing.list_samples; optionally
    mirrors models/ into the Volume first. Fails loudly when a batch or spot was never uploaded."""
    from preprocessing import DATA_DIR, list_batches, list_samples
    if not DATA_DIR.exists():
        raise FileNotFoundError(f"no {DATA_DIR} on the Volume. Upload the data first (cloud/README.md): "
                                f"modal volume put {VOLUME_NAME} data/Batch_1 /data/Batch_1   (and every other batch)")
    have = list_batches()
    wanted = batches or sorted({b for b, _ in sites}) or have
    unknown = sorted(set(wanted) - set(have))
    if unknown:
        raise ValueError(f"not on the Volume: {unknown} (it has {have}). Upload first: "
                         f"modal volume put {VOLUME_NAME} data/{unknown[0]} /data/{unknown[0]}")
    todo = list_samples(wanted)
    if sites:
        missing = sorted(set(map(tuple, sites)) - set(todo))
        if missing:
            raise ValueError(f"no such spot(s) on the Volume: {missing}")
        todo = [p for p in todo if p in set(map(tuple, sites))]
    if mirror_models:
        print(f"models/ mirrored into the Volume: {', '.join(_mirror_models())}")
        volume.commit()
    return [list(p) for p in todo]


@app.function(volumes=VOLUMES, cpu=2.0, memory=4096, timeout=600, max_containers=40, retries=1)
def features_for_site(batch: str, sample_id: str) -> dict:
    """Every registered feature on one spot -> the features.csv row (the same dict run_features.compute_rows makes).

    Mapped over all spots, one container each. The clean PNGs and the harmonised arrays this spot writes to
    /vol/processed are committed, so the next run (say, after adding a feature) skips the ~10 s harmonisation.
    Two containers never write the same file (one spot each); both caches write to a temp name and rename.
    """
    t0 = time.perf_counter()
    from features import REGISTRY, compute_all, load_feature_modules
    from preprocessing import load_sample
    if not REGISTRY:                     # a reused container keeps its imports
        load_feature_modules()
    sample = load_sample(batch, sample_id)
    t1 = time.perf_counter()
    row = {"batch": sample.batch, "sample_id": sample.sample_id, "split": sample.split, **compute_all(sample)}
    t2 = time.perf_counter()
    try:                                 # the caches only save time: a failed commit must not cost the row
        volume.commit()
    except Exception as e:
        print(f"{batch}/{sample_id}: cache not committed ({type(e).__name__}: {e}); the row is fine", flush=True)
    print(f"{batch}/{sample_id}: load {t1 - t0:.1f} s, features {t2 - t1:.1f} s, cache commit "
          f"{time.perf_counter() - t2:.1f} s  ({len(row) - 3} columns)", flush=True)
    return row


@app.function(volumes=VOLUMES, cpu=2.0, memory=8192, timeout=1800)
def train_baseline() -> dict:
    """train() of every trained feature on the baseline batch only (= run_features.py --train), into /vol/models.

    Starts from the repo's models/ so the models of features without train() are there too. Returns every model
    file as bytes, so the local entrypoint can copy them into the repo's models/ (commit them from there).
    """
    from features import load_feature_modules, train_all
    from preprocessing import BASELINE, MODELS_DIR, load_samples
    _mirror_models()
    load_feature_modules()
    print(f"training on the baseline ({BASELINE}) only ...")
    train_all(load_samples(BASELINE))
    volume.commit()
    return {p.name: p.read_bytes() for p in sorted(MODELS_DIR.iterdir()) if p.is_file() and p.name != "README.md"}


@app.function(volumes=VOLUMES, cpu=1.0, memory=2048, timeout=300)
def assemble(rows: list, batches: list, existing_csv, write_volume: bool) -> str:
    """The rows -> features.csv text with run_features.py's rules: with --batches, the other batches' rows of the
    existing CSV are kept (merge_with_existing); columns META + features; sorted by batch, sample_id.

    existing_csv: the local CSV's text, or None to fall back to the Volume's copy. write_volume: also save the result
    as /vol/processed/features.csv.
    """
    import os
    import tempfile

    import pandas as pd
    from features.run_features import META, merge_with_existing, print_summary
    from preprocessing import PROCESSED_DIR
    volume.reload()
    vol_csv = PROCESSED_DIR / "features.csv"
    df = pd.DataFrame(rows)
    if batches:
        old = Path(tempfile.mkdtemp()) / "features.csv"     # fresh per call: a reused container keeps its /tmp
        if existing_csv is not None:
            old.write_text(existing_csv)
        elif vol_csv.exists():
            old.write_bytes(vol_csv.read_bytes())
        if old.exists():
            df = merge_with_existing(df, old, batches)
    feature_cols = [c for c in df.columns if c not in META]
    df = df[META + feature_cols].sort_values(["batch", "sample_id"]).reset_index(drop=True)
    text = df.to_csv(index=False)
    if write_volume:
        vol_csv.parent.mkdir(parents=True, exist_ok=True)
        tmp = vol_csv.with_name(vol_csv.name + ".tmp")
        tmp.write_text(text)
        os.replace(tmp, vol_csv)
        volume.commit()
    print(f"features.csv: {len(df)} rows x {len(feature_cols)} features")
    print_summary(df)
    return text


@app.function(volumes=VOLUMES, cpu=1.0, memory=2048, timeout=300)
def verdict(batch: str, features_csv, robustness_csv, csv_path: str = "", robustness_path: str = "") -> dict:
    """analysis/verdict.py <batch> --json on the given features.csv text (None: the Volume's copy). Sessions come from
    the raw TIF headers on the Volume. robustness_csv: the text of processed/robustness.csv for the R2 gate (None: no
    R2 gate, as locally; with the Volume's features.csv, the Volume's robustness.csv if there is one).

    csv_path / robustness_path: the local paths the texts came from. The texts are written to those same paths inside
    the container, so the certificate names your files, as a local run does, not a temporary copy.
    Returns the certificate files as bytes."""
    import subprocess
    import sys
    import tempfile

    from preprocessing import BASELINE, PROCESSED_DIR
    if batch == BASELINE:
        print(f"{batch} is the baseline: no verdict")
        return {}
    volume.reload()

    def where(path, default):                         # never inside the mounted Volume
        p = Path(path or default)
        return Path(default) if p.is_relative_to(VOL) else p

    def put(path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    out = Path(tempfile.mkdtemp(prefix="verdict_"))   # fresh per call: a reused container must not hand back the last batch's files
    if features_csv is None:
        csv = PROCESSED_DIR / "features.csv"
    else:
        csv = put(where(csv_path, "/tmp/features.csv"), features_csv)
    if robustness_csv is not None:
        rob = put(where(robustness_path, "/tmp/robustness.csv"), robustness_csv)
    elif features_csv is None:
        rob = PROCESSED_DIR / "robustness.csv"        # next to the Volume's features.csv, if there is one
    else:
        rob = where(robustness_path, "/tmp/robustness.csv")
        rob.unlink(missing_ok=True)                   # an earlier call in this container may have written one
    cmd = [sys.executable, "analysis/verdict.py", batch, "--json", "--csv", str(csv), "--out-dir", str(out),
           "--robustness", str(rob)]                  # a missing file: verdict.py notes "R2 cannot fire", as locally
    result = subprocess.run(cmd, cwd=REMOTE_REPO)
    if result.returncode != 0:
        raise RuntimeError(f"analysis/verdict.py {batch} exited with {result.returncode} (its output is above)")
    return {p.name: p.read_bytes() for p in sorted(out.iterdir()) if p.is_file()}


# ----------------------------------------------------------------------------------------------------
# LOCAL: runs on your machine (modal run cloud/modal_app.py ...)
# ----------------------------------------------------------------------------------------------------
def _names(text):
    return [t for t in re.split(r"[,\s]+", text.strip()) if t]


def _write(path, data):
    """Write bytes/text next to the target, then rename (a reader never sees half a file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data if isinstance(data, bytes) else data.encode())
    tmp.replace(path)


def _local_path(text, default):
    p = Path(text) if text else REPO / default
    return p if p.is_absolute() else Path.cwd() / p


def _read_text(path):
    return path.read_text() if path.exists() else None


def stage_train():
    t0 = time.time()
    files = train_baseline.remote()
    changed = []
    for name, data in files.items():
        target = REPO / "models" / name
        if not target.exists() or target.read_bytes() != data:
            _write(target, data)
            changed.append(name)
    print(f"trained in {time.time() - t0:.0f} s; models/ updated: {', '.join(changed) or 'nothing changed'}"
          + ("  (commit them)" if changed else ""))


def stage_features(batches, sites, train, csv_path):
    """List the spots, train (optional), map features_for_site over the spots, assemble and write the CSV.
    Returns the batches done."""
    t0 = time.time()
    todo = prepare.remote(batches, sites, mirror_models=not train)   # first: a typo in --batches fails before training
    if train:
        stage_train()                                                # mirrors models/, then trains into the Volume
    print(f"computing {len(todo)} spots on Modal (one container each, at most 40 at once) ...")
    t1 = time.time()
    rows, failed = [], []
    results = list(features_for_site.map([b for b, _ in todo], [s for _, s in todo], return_exceptions=True))
    for (b, sid), result in zip(todo, results):     # .map keeps the input order
        if isinstance(result, BaseException):
            failed.append(f"{b}/{sid}: {type(result).__name__}: {result}")
        else:
            rows.append(result)
    print(f"{len(rows)} spots done in {time.time() - t1:.0f} s wall time")
    if failed:   # a CSV with a spot missing would quietly change a verdict: write nothing
        raise SystemExit("spots that failed (no CSV written):\n  " + "\n  ".join(failed))
    existing = None if sites else _read_text(csv_path)
    text = assemble.remote(rows, [] if sites else batches, existing, write_volume=not sites)
    _write(csv_path, text)
    print(f"wrote {csv_path}" + ("" if sites else f" (and {VOL}/processed/features.csv on the Volume)")
          + f"  total {time.time() - t0:.0f} s")
    return sorted({b for b, _ in todo})


def stage_verdict(batches, csv_path, out_dir):
    if not batches:
        raise SystemExit("--stage verdict needs --batches (the incoming batch(es) to judge)")
    features_csv = _read_text(csv_path)
    rob_path = REPO / "processed" / "robustness.csv"     # verdict.py's default (analysis/verdict_config.yaml)
    robustness = _read_text(rob_path)
    print(f"verdict on {csv_path if features_csv is not None else 'the Volume copy of features.csv'}")
    for batch in batches:
        for name, data in verdict.remote(batch, features_csv, robustness, str(csv_path), str(rob_path)).items():
            _write(out_dir / name, data)
            print(f"wrote {out_dir / name}")


@app.local_entrypoint()
def main(stage: str = "features", batches: str = "", train: bool = False, sites: str = "", csv: str = "",
         out_dir: str = ""):
    stage = stage.lower()
    if stage not in ("features", "train", "verdict", "all"):
        raise SystemExit(f"--stage must be features, train, verdict or all, not {stage!r}")
    batch_list = _names(batches)
    site_list = [s.split("/", 1) for s in _names(sites)]
    if any(len(s) != 2 for s in site_list):
        raise SystemExit("--sites takes batch/sample_id pairs, e.g. Batch_1/ffwubibz,Batch_3/cfe5vt7s")
    if site_list and stage != "features":
        raise SystemExit("--sites is a quick feature check on a few spots; a verdict needs every spot of the batch")
    csv_path = _local_path(csv, "processed/features_sites.csv" if site_list else "processed/features.csv")
    if stage == "train":
        stage_train()
    if stage in ("features", "all"):
        done = stage_features(batch_list, site_list, train, csv_path)
        batch_list = batch_list or done          # --stage all without --batches: a verdict for every batch
    if stage in ("verdict", "all"):
        stage_verdict(batch_list, csv_path, _local_path(out_dir, "analysis/verdicts"))
