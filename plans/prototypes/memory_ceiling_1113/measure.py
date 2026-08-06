"""Orchestrator for the #1113 memory-ceiling measurements.

Generates four synthetic report-scale item sets (constant per-item size,
varying item count, so the RSS trend across scales reveals the scaling law:
proportional growth => scales with TOTAL report size, flat => bounded by the
LARGEST item / a constant working set), then runs every strategy in a fresh
subprocess (``reps`` times each) and prints a Markdown table of medians.

Peak RSS metric: VmHWM from ``/proc/self/status``, read at process end.
``ru_maxrss`` is also recorded but is NOT trustworthy here: on Linux the
rusage high-water mark survives fork+exec, so every child inherits the
orchestrator's peak. VmHWM is reset at execve and is per-strategy-process.

Usage:
    pixi run python plans/prototypes/memory_ceiling_1113/measure.py \
        --workdir /path/to/tmp [--reps 3]
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SCALES = {"tiny": 6, "small": 12, "large": 24, "xlarge": 48}
STRATEGIES = ["a", "b", "c", "cf", "d", "df", "d2", "d2s"]
GENERATED_STRATEGIES = ("c", "cf")  # log data themselves; need the item count


def run_one(strategy: str, items_dir: Path | None, out: Path | None, n_items: int) -> dict:
    cmd = [sys.executable, str(HERE / "run_one.py"), strategy]
    if items_dir is not None:
        cmd += ["--items-dir", str(items_dir)]
    if out is not None:
        cmd += ["--out", str(out)]
    if n_items:
        cmd += ["--n-items", str(n_items)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--reps", type=int, default=3)
    args = parser.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)

    from itemgen import generate_items

    item_dirs = {}
    for scale, n_items in SCALES.items():
        item_dir = args.workdir / f"items_{scale}"
        paths = generate_items(item_dir, n_items)
        total = sum(p.stat().st_size for p in paths)
        print(f"[gen] {scale}: {n_items} items, {total / 2**20:.1f} MB total", file=sys.stderr)
        item_dirs[scale] = (item_dir, n_items)

    rows = []
    null_runs = [run_one("null", None, None, 0) for _ in range(args.reps)]
    null_mb = statistics.median(r["vmhwm_mb"] for r in null_runs)
    rows.append({"strategy": "null", "scale": "-", "runs": null_runs})
    for scale, (item_dir, n_items) in item_dirs.items():
        for strategy in STRATEGIES:
            out = args.workdir / f"merged_{strategy}_{scale}.rrd"
            wanted = n_items if strategy in GENERATED_STRATEGIES else 0
            runs = [run_one(strategy, item_dir, out, wanted) for _ in range(args.reps)]
            rows.append({"strategy": strategy, "scale": scale, "runs": runs})
            print(f"[run] {strategy}/{scale}: {[r['vmhwm_mb'] for r in runs]}", file=sys.stderr)

    (args.workdir / "results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    header = (
        "| strategy | scale | items | input MB | out MB | wall s (med) "
        "| VmHWM MB (med) | VmHWM min..max | ΔRSS MB | ΔRSS/input |"
    )
    print("\n" + header)
    print("|---|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        runs = row["runs"]
        med = statistics.median(r["vmhwm_mb"] for r in runs)
        lo, hi = min(r["vmhwm_mb"] for r in runs), max(r["vmhwm_mb"] for r in runs)
        wall = statistics.median(r["wall_s"] for r in runs)
        input_mb = runs[0].get("input_mb", 0)
        delta = med - null_mb
        ratio = f"{delta / input_mb:.2f}x" if input_mb else "-"
        print(
            f"| {row['strategy']} | {row['scale']} | {runs[0]['n_items']} | {input_mb} "
            f"| {runs[0].get('out_mb', 0)} | {wall} | {med} | {lo}..{hi} "
            f"| {delta:.1f} | {ratio} |"
        )


if __name__ == "__main__":
    main()
