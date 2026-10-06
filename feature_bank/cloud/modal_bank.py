"""The feature bank on Modal: the same jobs as `python -m bank.run`, one container per crop version.

PAID. Only the lead runs this, after stating the cost. Every job skips itself if its result is already on the Volume.

    modal run cloud/modal_bank.py --stage views  --sites all --perts all                   # 247 crop versions
    modal run cloud/modal_bank.py --stage fam    --fam phase --sites all --perts all
    modal run --detach cloud/modal_bank.py --stage fam --fam emb --sites all --perts all   # keeps going if you disconnect
    modal run cloud/modal_bank.py --stage parity --fam phase                               # 2 smoke crops -> PARITY_JSON=...
    modal run cloud/modal_bank.py --stage status
    modal volume get losslarp-data /processed/bank/feat processed/bank/ --force            # copy results down (free)

--sites: all | smoke | inject | a comma list.   --perts: P0 | imaging | inject | all | a comma list.

What runs where
    views        2 CPU, 8 GB    one per crop version: perturb the raw image, harmonise, store the window and phase maps
    cpu_small    2 CPU, 8 GB    a CPU family that sets nothing (the default)
    cpu_large    8 CPU, 32 GB   a CPU family whose module sets MODAL = "large"
    GpuFamily    one GPU        a family with RUNS_ON = "gpu"; weights load once per container in warmup(cfg).
                                 Only registered when BANK_GPU names a type, e.g. BANK_GPU=H100 modal run ...
    orchestrate  0.25 CPU       fans the jobs out from inside the cloud, so a detached run survives a closed laptop

Prices (modal.com/pricing, 3 Oct 2026): CPU $0.0000131 per core-second, memory $0.00000222 per GiB-second,
H100 $0.001097 per second. So small = $0.16/h, large = $0.63/h, H100 = $3.95/h per container.

Code: this working copy is uploaded on every run to /root/losslarp (data/, processed/, .git, .venv left out).
Data: the Volume `losslarp-data`, mounted at /vol. Raw TIFs at /vol/data/Batch_*; everything the bank writes at
/vol/processed/bank/, the same layout as processed/bank/ locally. Never put a key or token in this file.
"""
import json
import os
import sys
import time
from pathlib import Path

import modal

APP_NAME = "losslarp-bank"
VOLUME_NAME = "losslarp-data"
VOL = "/vol"
REMOTE_REPO = "/root/losslarp"
REPO = Path(__file__).resolve().parents[1]
IGNORE = ["data", "processed", ".git", ".venv", "**/__pycache__", "**/.pytest_cache", ".secrets", "QUESTIONS_FOR_POLARON.md",
          "dashboard/site", "research", "notes", "ledger", "literature/*.json", "results/figures"]
ENV = {"LOSSLARP_DATA_DIR": f"{VOL}/data", "LOSSLARP_PROCESSED_DIR": f"{VOL}/processed", "PYTHONPATH": REMOTE_REPO,
       "HF_HOME": f"{VOL}/hf_cache", "TORCH_HOME": f"{VOL}/torch_cache", "MPLBACKEND": "Agg"}

# GPU functions exist only when BANK_GPU names a type (H100, L40S, A10G, ...). Every GPU type needs a payment method on
# the Modal account, and registering one without it stops the whole app, CPU stages included. So the default is none.
GPU = os.environ.get("BANK_GPU", "")
if GPU:
    ENV["BANK_GPU"] = GPU

# Pinned to the versions in the local .venv on 3 Oct 2026, so local and cloud numbers agree.
CPU_PINS = ["numpy==2.5.3", "scipy==1.18.1", "scikit-image==0.26.0", "scikit-learn==1.9.1", "pandas==3.0.6", "pyarrow==25.0.1",
            "pillow==12.3.0", "pyyaml==6.0.3", "imagecodecs==2026.8.16", "matplotlib==3.11.2", "porespy==3.1.1",
            "cripser==0.0.36", "gudhi==3.13.0", "mahotas==1.4.19"]
# The GPU image: kymatio 0.3.0 needs the older scipy (see cloud/requirements-gpu.txt). Views are made on the CPU image.
GPU_PINS = ["torch==2.14.1", "torchvision==0.29.1", "timm==1.0.30", "huggingface_hub==2.1.1", "scipy==1.16.3", "kymatio==0.3.0",
            "taufactor==1.2.1", "scikit-image==0.26.0", "scikit-learn==1.9.1", "pandas==3.0.6", "pyarrow==25.0.1",
            "pillow==12.3.0", "pyyaml==6.0.3"]

base = modal.Image.debian_slim(python_version="3.12").apt_install("libgl1", "libglib2.0-0", "libxrender1", "git")
cpu_image = base.pip_install(*CPU_PINS).env(ENV).add_local_dir(REPO, REMOTE_REPO, ignore=IGNORE)
gpu_image = base.pip_install(*GPU_PINS).env(ENV).add_local_dir(REPO, REMOTE_REPO, ignore=IGNORE)

volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
app = modal.App(APP_NAME)
VOLUMES = {VOL: volume}
GPU_PRICE_PER_S = {"T4": 0.000164, "L4": 0.000222, "A10G": 0.000306, "L40S": 0.000542, "A100-40GB": 0.000583,
                   "A100-80GB": 0.000694, "H100": 0.001097}


def _commit():
    try:
        volume.commit()
    except Exception as e:                                # a failed commit loses only this job's files; it will rerun
        print(f"volume commit failed: {type(e).__name__}: {e}", flush=True)


def _family_job(family, crop_id, pert, force):
    """One (family, crop version): skip if done, else extract, validate, save on the Volume. Returns a status dict."""
    import traceback

    from bank import core, families
    t0 = time.time()
    record = dict(family=family, crop=crop_id, pert=pert)
    try:
        volume.reload()
        if core.is_done(family, crop_id, pert) and not force:
            return dict(record, skipped=True, seconds=0.0)
        module = families.load(family)
        res = module.extract(core.load_crop(crop_id, pert), dict(module.DEFAULT_CFG))
        core.save_result(res, crop_id, pert, seconds=time.time() - t0)
        _commit()
        return dict(record, seconds=round(time.time() - t0, 1), n_scalars=len(res.scalars), n_blocks=len(res.blocks) + len(res.tiles))
    except Exception:
        return dict(record, seconds=round(time.time() - t0, 1), error=traceback.format_exc()[-1500:])


@app.function(image=cpu_image, volumes=VOLUMES, cpu=2.0, memory=8192, timeout=900, max_containers=60, retries=1)
def views(job):
    import traceback

    from bank import core
    crop_id, pert, force = job
    t0 = time.time()
    try:
        volume.reload()
        if core.views_path(crop_id, pert).exists() and not force:
            return dict(family="views", crop=crop_id, pert=pert, skipped=True, seconds=0.0)
        core.build_views(crop_id, pert, force)
        _commit()
        return dict(family="views", crop=crop_id, pert=pert, seconds=round(time.time() - t0, 1))
    except Exception:
        return dict(family="views", crop=crop_id, pert=pert, seconds=round(time.time() - t0, 1), error=traceback.format_exc()[-1500:])


@app.function(image=cpu_image, volumes=VOLUMES, cpu=2.0, memory=8192, timeout=3600, max_containers=60, retries=1)
def cpu_small(job):
    return _family_job(*job)


@app.function(image=cpu_image, volumes=VOLUMES, cpu=8.0, memory=32768, timeout=7200, max_containers=40, retries=1)
def cpu_large(job):
    return _family_job(*job)


if GPU:
    @app.cls(image=gpu_image, gpu=GPU, volumes=VOLUMES, timeout=7200, max_containers=4, scaledown_window=60)
    class GpuFamily:
        family: str = modal.parameter()

        @modal.enter()
        def load(self):
            from bank import families
            module = families.load(self.family)
            if hasattr(module, "warmup"):                       # download / load the weights once per container
                module.warmup(dict(module.DEFAULT_CFG))
                _commit()                                       # keep downloaded weights on the Volume for the next container

        @modal.method()
        def run(self, job):
            return _family_job(*job)


@app.function(image=cpu_image, volumes=VOLUMES, cpu=0.25, memory=1024, timeout=6 * 3600)
def orchestrate(stage, family, versions, force):
    """Fan the jobs out from inside the cloud and write one consolidated status file. Returns the status records."""
    from bank import core, families
    t0 = time.time()
    if stage == "views":
        calls = views.map([(c, p, force) for c, p in versions], order_outputs=False, return_exceptions=True)
        cost_per_s = 2 * 0.0000131 + 8 * 0.00000222
    else:
        module = families.load(family)
        jobs = [(family, c, p, force) for c, p in versions]
        if module.RUNS_ON == "gpu":
            if not GPU:
                raise RuntimeError("GPU family requested but BANK_GPU is not set (needs a payment method on the Modal account)")
            calls = GpuFamily(family=family).run.map(jobs, order_outputs=False, return_exceptions=True)
            cost_per_s = GPU_PRICE_PER_S.get(GPU, 0.001097)
        elif getattr(module, "MODAL", "small") == "large":
            calls = cpu_large.map(jobs, order_outputs=False, return_exceptions=True)
            cost_per_s = 8 * 0.0000131 + 32 * 0.00000222
        else:
            calls = cpu_small.map(jobs, order_outputs=False, return_exceptions=True)
            cost_per_s = 2 * 0.0000131 + 8 * 0.00000222
    records = []
    for i, r in enumerate(calls, 1):
        r = r if isinstance(r, dict) else dict(family=family or "views", error=repr(r))
        records.append(r)
        state = "FAILED" if "error" in r else "skipped" if r.get("skipped") else f"{r.get('seconds', 0):.0f} s"
        print(f"  [{i}/{len(versions)}] {r.get('family')} {r.get('pert', ''):<13} {r.get('crop', '')}  {state}", flush=True)
        if "error" in r:
            print(r["error"], flush=True)
    busy = sum(r.get("seconds", 0.0) for r in records)
    summary = dict(stage=stage, family=family, jobs=len(records), failed=sum("error" in r for r in records),
                   skipped=sum(bool(r.get("skipped")) for r in records), container_seconds=round(busy),
                   wall_seconds=round(time.time() - t0), est_cost_usd=round(busy * cost_per_s, 2))
    out = core.BANK_DIR / "modal_status" / f"{stage}_{family or 'views'}_{time.strftime('%H%M%S')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in [summary] + records) + "\n")
    _commit()
    print("SUMMARY_JSON=" + json.dumps(summary), flush=True)
    return summary


@app.function(image=cpu_image, volumes=VOLUMES, cpu=2.0, memory=8192, timeout=1800)
def parity(family):
    """The scalars of one family on the smoke crops, computed in the cloud, for the local-vs-Modal test."""
    from bank import core, families
    volume.reload()
    module = families.load(family)
    out = {}
    for crop_id in core.SMOKE_CROPS:
        core.build_views(crop_id)
        out[crop_id] = module.extract(core.load_crop(crop_id), dict(module.DEFAULT_CFG)).scalars
    _commit()
    return out


@app.function(image=cpu_image, volumes=VOLUMES, cpu=0.25, memory=1024, timeout=300)
def status():
    from bank import core, families
    volume.reload()
    perts = (core.P0,) + core.IMAGING_PERTS + core.MATERIAL_INJECTS
    rows = {"views": {p: len(list((core.VIEWS_DIR / p).glob("*.npz"))) for p in perts}}
    for family in families.family_names():
        rows[family] = {p: len(list((core.FEAT_DIR / family / p).glob("*.done"))) for p in perts}
    return rows


@app.local_entrypoint()
def main(stage: str = "status", fam: str = "", sites: str = "smoke", perts: str = "P0", force: bool = False):
    sys.path.insert(0, str(REPO))
    if stage == "status":
        rows = status.remote()
        width = max(len(k) for k in rows)
        for name, counts in rows.items():
            print(f"{name:<{width}}  " + "  ".join(f"{p}={n}" for p, n in counts.items()))
        return
    if stage == "parity":
        print("PARITY_JSON=" + json.dumps(parity.remote(fam)))
        return
    from bank import core
    versions = core.crop_versions(sites, perts)
    print(f"{stage} {fam}: {len(versions)} crop versions")
    summary = orchestrate.remote(stage, fam, versions, force)
    print(json.dumps(summary, indent=1))
