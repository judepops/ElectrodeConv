"""The QA pass: what is done, do the tests pass, what is blocked. Writes processed/bank/STATUS.md.

    python -m bank.qa            # status + the local tests
    python -m bank.qa --no-tests # status only (fast)

Free: it never touches Modal.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bank import core, families   # noqa: E402


def table():
    perts = (core.P0,) + core.IMAGING_PERTS + core.MATERIAL_INJECTS
    lines = ["| family | " + " | ".join(perts) + " | scalars | blocks | s/crop |", "|---|" + "---|" * (len(perts) + 3)]
    timings = {}
    if core.STATUS_LOG.exists():
        for line in core.STATUS_LOG.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("seconds") is not None:
                timings.setdefault(r["family"], []).append(r["seconds"])
    counts = {p: len(list((core.VIEWS_DIR / p).glob("*.npz"))) for p in perts}
    lines.append("| (views) | " + " | ".join(str(counts[p]) for p in perts) + " | | | |")
    for family in families.family_names():
        done = {p: len(list((core.FEAT_DIR / family / p).glob("*.done"))) for p in perts}
        n_s = n_b = ""
        cat = core.FEAT_DIR / family / "catalog.parquet"
        if cat.exists():
            c = core.load_catalog(family)
            n_s, n_b = int((c.kind == "scalar").sum()), int((c.kind != "scalar").sum())
        t = timings.get(family)
        lines.append(f"| {family} | " + " | ".join(str(done[p]) for p in perts) + f" | {n_s} | {n_b} | {sorted(t)[len(t) // 2]:.0f} |" if t
                     else f"| {family} | " + " | ".join(str(done[p]) for p in perts) + f" | {n_s} | {n_b} | |")
    return "\n".join(lines)


def run_tests():
    out = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
                         cwd=core.ROOT, capture_output=True, text=True, timeout=3600)
    tail = [line for line in out.stdout.strip().splitlines() if line.strip()][-12:]
    return out.returncode, "\n".join(tail)


def main():
    parts = [f"# Feature bank status\n\nWritten {time.strftime('%Y-%m-%d %H:%M')} by `python -m bank.qa`. Expected per column: 31 crops "
             f"(injection columns: {len(core.INJECT_CROPS)}).\n", table()]
    ready = sorted(p.stem for p in (core.BANK_DIR / "ready").glob("*.json")) if (core.BANK_DIR / "ready").exists() else []
    parts.append(f"\nPassed review: {', '.join(ready) or 'none yet'}")
    blocked = core.BANK_DIR / "BLOCKED.md"
    if blocked.exists():
        parts.append("\n## Blocked\n\n" + blocked.read_text().strip())
    if "--no-tests" not in sys.argv:
        code, tail = run_tests()
        parts.append(f"\n## Tests: {'PASS' if code == 0 else 'FAIL'}\n\n```\n{tail}\n```")
    text = "\n".join(parts) + "\n"
    (core.BANK_DIR / "STATUS.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
