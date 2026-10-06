"""Write demo/results.js from the committed result files, so the deck opens from disk.
usage: python3.11 demo/make_data.py   (run from the repo root after a new model is scored and committed)"""
import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def committed(path):                       # HEAD's copy, so half-written files from a running job are ignored
    try:
        return json.loads(subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=ROOT, stderr=subprocess.DEVNULL))
    except subprocess.CalledProcessError:
        return None


keep = ("bacc", "ci90", "recall", "delta_vs_v1")
compare = committed("cnn/results/compare_extra.json")
out = {
    "folds": compare["folds"],
    "models": {k: {kk: v.get(kk) for kk in keep} for k, v in compare["models"].items()},
    "v2_seeds": {f: (committed(f"cnn/results/{f}_score.json") or {}).get("ci90") for f in ("v2", "v2s1", "v2s2")},
    "test": committed("cnn/results/classify_Hackathon-Polaron-test.json"),
    "eval": committed("cnn/results/classify_Hackathon-Polaron-eval.json"),
}
(ROOT / "demo" / "results.js").write_text("window.DEMO_RESULTS = " + json.dumps(out, indent=1) + ";\n")
print("wrote demo/results.js:", ", ".join(out["models"]))
