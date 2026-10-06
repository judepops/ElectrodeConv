"""Keep every GPU busy: a job queue that starts the next training run wherever there is room.

    python cnn/gpu_queue.py jobs.txt                 # runs forever; add lines to jobs.txt at any time
    cat cnn/processed/supcon/queue_status.txt        # what runs where, what waits

jobs.txt: one job per line, `<name> <fold> <flags...>` (fold -1 = the full model); names starting with j_ run
cnn/joint.py, all others `cnn/supcon.py train`. A job is skipped
when its embeddings.npz exists, so the file can be re-run safely. Every 15 s, for each GPU: if its free memory (from
nvidia-smi, so other people's jobs count) is above --need-gb and fewer than --per-gpu of our jobs run there, the next
waiting job starts on it. Lines starting with # are ignored.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDIR = REPO / "cnn" / "processed" / "supcon"


def free_gb():
    out = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.total,memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return {int(i): (float(t) - float(u)) / 1024 for i, t, u in (l.split(",") for l in out)}


def run_dir(name, fold):
    return SDIR / name / ("full" if int(fold) < 0 else f"fold{int(fold):02d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("--need-gb", type=float, default=24.0, help="free memory a GPU needs before the next job starts there")
    ap.add_argument("--per-gpu", type=int, default=6)
    ap.add_argument("--gpus", default="0,1")
    a = ap.parse_args()
    gpus = [int(g) for g in a.gpus.split(",")]
    running = {}                                   # key -> (Popen, gpu, t0)
    failed = set()
    while True:
        jobs = []
        for line in Path(a.jobs).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                name, fold, *flags = line.split()
                jobs.append((name, fold, " ".join(flags)))
        for key, (p, g, t0) in list(running.items()):
            if p.poll() is not None:
                if p.returncode != 0:
                    failed.add(key)
                del running[key]
        def busy_elsewhere(name, fold):           # started by an earlier queue instance and still writing its log
            log = run_dir(name, fold).parent / f"{run_dir(name, fold).name}.log"
            return log.exists() and time.time() - log.stat().st_mtime < 120 and "done in" not in log.read_text()[-300:]
        waiting = [j for j in jobs if (j[0], j[1]) not in running and (j[0], j[1]) not in failed
                   and not (run_dir(j[0], j[1]) / "embeddings.npz").exists() and not busy_elsewhere(j[0], j[1])]
        free = free_gb()
        for g in gpus:
            mine = sum(1 for _, gg, _ in running.values() if gg == g)
            if waiting and free.get(g, 0) >= a.need_gb and mine < a.per_gpu:
                name, fold, flags = waiting.pop(0)
                d = run_dir(name, fold)
                d.mkdir(parents=True, exist_ok=True)
                env = {**os.environ, "CUDA_VISIBLE_DEVICES": str(g), "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "4"}
                log = open(d.parent / f"{d.name}.log", "w")
                script = "cnn/joint.py" if name.startswith("j_") else "cnn/supcon.py train"     # j_* = V1 + V2 trained together
                p = subprocess.Popen(f"{sys.executable} {script} --name {name} --fold {fold} {flags} --preload",
                                     shell=True, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
                running[(name, fold)] = (p, g, time.time())
                free[g] -= a.need_gb                       # memory is claimed gradually; do not double-book this round
        lines = [time.strftime("%H:%M:%S") + f"  running {len(running)}, waiting {len(waiting)}, failed {len(failed)}  free GB " +
                 " ".join(f"gpu{g}={free_gb().get(g, 0):.0f}" for g in gpus)]
        for (name, fold), (p, g, t0) in sorted(running.items()):
            prog = run_dir(name, fold) / "progress.txt"
            lines.append(f"  gpu{g} {name} fold {fold}: " + (prog.read_text().split("  ")[0] if prog.exists() else "starting") + f"  ({(time.time() - t0) / 60:.0f} min)")
        lines += [f"  waiting {n} fold {f}" for n, f, _ in waiting] + [f"  FAILED {n} fold {f}" for n, f in sorted(failed)]
        (SDIR / "queue_status.txt").write_text("\n".join(lines) + "\n")
        time.sleep(15)


if __name__ == "__main__":
    main()
