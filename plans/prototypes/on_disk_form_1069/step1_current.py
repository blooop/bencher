"""Step 1 of the issue #1069 prototype: capture the CURRENT on-disk truth.

Runs a real, tiny sweep through the collect() path (bencher/render.py's collect
half) with one float result var, one image result var, and one ResultDataSet var
(so we see both media-cell conventions that exist today: absolute gen_path media
paths AND content-addressed blob names). Then dumps what actually lands on disk.

Run:  pixi run python plans/prototypes/on_disk_form_1069/step1_current.py
Output: plans/prototypes/on_disk_form_1069/out/work/  (cachedir + result.pkl)
        plans/prototypes/on_disk_form_1069/out/step1_report.txt
"""

from __future__ import annotations

import os
import pickletools
import subprocess
import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

PROTO_DIR = Path(__file__).parent.resolve()
OUT_DIR = PROTO_DIR / "out"
WORK_DIR = OUT_DIR / "work"


def make_workdir() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    # cachedir is resolved relative to cwd everywhere in bencher (gen_path,
    # blob_store.DEFAULT_CACHE_DIR), so the sweep must run FROM the workdir.
    os.chdir(WORK_DIR)


make_workdir()

import bencher as bn  # noqa: E402  (chdir must happen before Bench touches cachedir)


class DiskFormSweep(bn.ParametrizedSweep):
    """Tiny deterministic sweep: image + float + dataset results.

    The image and the dataframe depend ONLY on radius, so repeats produce
    byte-identical payloads -- exactly the dedup case step 3 measures.
    """

    radius = bn.FloatSweep(default=0.5, bounds=(0.2, 1.0), samples=3)
    disk = bn.ResultImage()
    area = bn.ResultFloat(units="m^2")
    points = bn.ResultDataSet()

    def benchmark(self):
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r = self.radius * size / 2
        c = size / 2
        draw.ellipse([c - r, c - r, c + r, c + r], outline="red", width=2)
        filepath = bn.gen_image_path("disk")
        img.save(filepath, "PNG")
        self.disk = str(filepath)
        self.area = 3.14159265 * self.radius**2
        self.points = bn.ResultDataSet(
            pd.DataFrame({"angle": [0.0, 90.0, 180.0], "r": [self.radius] * 3})
        )


def tree(root: Path, max_files_per_dir: int = 8) -> str:
    lines = []
    for dirpath, dirnames, filenames in sorted(os.walk(root)):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        lines.append("  " * depth + (root.name if rel == "." else os.path.basename(dirpath)) + "/")
        dirnames.sort()
        for fname in sorted(filenames)[:max_files_per_dir]:
            fsize = (Path(dirpath) / fname).stat().st_size
            lines.append("  " * (depth + 1) + f"{fname}  ({fsize} B)")
        if len(filenames) > max_files_per_dir:
            lines.append("  " * (depth + 1) + f"... {len(filenames) - max_files_per_dir} more")
    return "\n".join(lines)


def pickle_top_level_types(pkl_path: Path, limit: int = 40) -> list[str]:
    """Classes the pickle reconstructs (GLOBAL / STACK_GLOBAL opcodes).

    Protocol 4+ pushes module and qualname as strings then STACK_GLOBAL, so we
    track the last two string pushes to recover the dotted name.
    """
    seen: list[str] = []
    last_strings: list[str] = ["", ""]
    with pkl_path.open("rb") as fh:
        for opcode, arg, _pos in pickletools.genops(fh):
            if opcode.name in ("SHORT_BINUNICODE", "BINUNICODE", "UNICODE") and isinstance(
                arg, str
            ):
                last_strings = [last_strings[1], arg]
            elif opcode.name == "STACK_GLOBAL":
                name = f"{last_strings[0]}.{last_strings[1]}"
                if name not in seen:
                    seen.append(name)
            elif opcode.name == "GLOBAL" and isinstance(arg, str):
                name = arg.replace(" ", ".")
                if name not in seen:
                    seen.append(name)
            if len(seen) >= limit:
                break
    return seen


def main() -> None:
    run_cfg = bn.BenchRunCfg(repeats=2)
    bench = DiskFormSweep().to_bench(run_cfg)
    res = bench.collect(
        "disk_form_1069",
        input_vars=["radius"],
        result_vars=["disk", "area", "points"],
    )
    pkl_path = bn.save_result(res, WORK_DIR / "result.pkl")

    ds = res.ds
    report: list[str] = []
    report.append("== STEP 1: current on-disk truth (collect() path) ==\n")
    report.append(f"cwd (cachedir root): {WORK_DIR}")
    report.append(f"collect() returned: {type(res).__module__}.{type(res).__name__}")
    report.append(f"save_result() wrote: {pkl_path}  ({pkl_path.stat().st_size} B)")
    report.append("")
    report.append("-- top-level classes reconstructed by the pickle (GLOBAL opcodes) --")
    for name in pickle_top_level_types(pkl_path):
        report.append(f"  {name}")
    report.append("")
    report.append("-- dataset --")
    report.append(f"dims: {dict(ds.sizes)}")
    for name, var in ds.data_vars.items():
        report.append(f"var {name!r}: dtype={var.dtype}")
    report.append(f"dataset attrs: {dict(ds.attrs)}")
    report.append("")
    report.append("-- literal cell contents --")
    for name in ("disk", "points"):
        vals = ds[name].values.ravel()
        for i, v in enumerate(vals):
            report.append(f"  {name}[{i}] = {v!r}")
    report.append(f"  area = {ds['area'].values.ravel().tolist()}")
    report.append("")
    report.append("-- cachedir layout --")
    report.append(tree(WORK_DIR / "cachedir"))
    report.append("")
    du = subprocess.run(
        ["du", "-sb", str(WORK_DIR / "cachedir"), str(pkl_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    report.append("-- sizes (du -sb) --")
    report.append(du.stdout.strip())

    out = "\n".join(report)
    (OUT_DIR / "step1_report.txt").write_text(out)
    print(out)


if __name__ == "__main__":
    sys.exit(main())
