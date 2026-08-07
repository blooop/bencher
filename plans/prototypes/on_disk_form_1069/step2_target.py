"""Step 2 of the issue #1069 prototype: build BOTH target on-disk arms.

Converts the real step-1 output (result.pkl + cachedir) into:

  out/run_A3_contained/    A3 form: data.nc + manifest.json + plan.json +
                           artifacts/{img,data}/ with media copied IN, cells
                           hold relative paths ("artifacts/img/<name>.png").
  out/run_A6_referenced/   A6 form: same data.nc + manifest.json + plan.json,
                           but every media cell is a content-addressed blob
                           name per today's blob-store convention (bencher/
                           blob_store.py: sha256[:16] + extension, file lives
                           under <cachedir>/blobs/). NO artifacts/ dir; the
                           manifest lists the blob names the run needs.

plan.json (both arms): the stored Plan for the default view (A6 Law 9),
serialized from the real grammar vocabulary (bencher/grammar). It lives as a
SIBLING FILE referenced from manifest.json — see RESULTS.md for why.

Run AFTER step1:  pixi run python plans/prototypes/on_disk_form_1069/step2_target.py
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version
from pathlib import Path

import numpy as np
import xarray as xr

PROTO_DIR = Path(__file__).parent.resolve()
OUT_DIR = PROTO_DIR / "out"
WORK_DIR = OUT_DIR / "work"

sys.path.insert(0, str(PROTO_DIR))
os.chdir(WORK_DIR)

import bencher as bn  # noqa: E402
from bencher.blob_store import materialize_blob, resolve_blob  # noqa: E402
from bencher.grammar.channels import GRAMMAR_VERSION, Channel  # noqa: E402
from bencher.grammar.compose import Compose  # noqa: E402
from bencher.variables.results import result_kind  # noqa: E402

# The step-1 pickle references __main__.DiskFormSweep (it was defined in the
# script that ran the sweep), so it only loads in a process that has that name
# in __main__. This shim IS a finding: the current save format is bound to the
# writer's import graph. See RESULTS.md.
import step1_current  # noqa: E402  (chdirs to WORK_DIR as a side effect)

sys.modules["__main__"].DiskFormSweep = step1_current.DiskFormSweep

SCHEMA_VERSION = "1"  # run_meta.schema_version (A3 rule 3, issue #1107 analog)
PLAN_SCHEMA_VERSION = "1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def var_spec(v, is_result: bool) -> dict:
    """A3's VarSpec: plain data extracted from the live param object."""
    # FloatSweep redirects user bounds -> softbounds (inputs.py:620-622)
    bounds = getattr(v, "bounds", None) or getattr(v, "softbounds", None)
    return {
        "name": v.name,
        "type": type(v).__name__,
        "kind": result_kind(v) if is_result else "input",
        "units": getattr(v, "units", None),
        "bounds": list(bounds) if bounds is not None else None,
        "samples": getattr(v, "samples", None),
        "level": getattr(v, "level", None),
    }


def sanitize_for_netcdf(ds: xr.Dataset) -> xr.Dataset:
    """Make every variable/coord netCDF3-safe (scipy engine is this env's only
    backend — see bencher/blob_store.py _NETCDF3_SAFE_DTYPES)."""
    out = ds.copy(deep=True)
    for name in list(out.variables):
        var = out[name]
        if var.dtype.kind == "O":
            out[name] = var.astype(str)
        elif var.dtype == np.int64:
            out[name] = var.astype(np.int32)
    return out


def build_manifest(res, artifacts: list[dict], requires_blobs: list[dict], form: str) -> dict:
    bench_cfg = res.bench_cfg
    return {
        "run_meta": {
            "schema_version": SCHEMA_VERSION,
            "name": bench_cfg.title,
            "bencher_version": pkg_version("holobench"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sweep_hash": bench_cfg.hash_persistent(True),
            "form": form,  # "contained" (A3) | "store-referenced" (A6)
        },
        "input_vars": [var_spec(v, False) for v in bench_cfg.input_vars]
        + [
            {
                "name": "repeat",
                "type": "repeat",
                "kind": "input",
                "units": None,
                "bounds": None,
                "samples": bench_cfg.repeats,
                "level": None,
            }
        ],
        "result_vars": [var_spec(v, True) for v in bench_cfg.result_vars],
        "plot_specs": [],  # stub — A2's serializable name+kwargs specs land later
        "plans": ["plan.json"],  # sibling file per view; see RESULTS.md for why
        "artifacts": artifacts,
        "requires_blobs": requires_blobs,
    }


def build_plan(ds: xr.Dataset, res) -> dict:
    """The stored Plan for the default view, in the real grammar vocabulary.

    Channel assignments follow A6 Law 7 (v1.1): float input -> X, repeat ->
    SPREAD where the mark accepts it (numeric line), FACET fallback for blob
    marks (an image cannot render a spread band), first float -> FACET_COL for
    blob result vars. Multiple result vars compose via an outer layout node
    along FACET_ROW (Law 5: one plan per result var + outer Compose).
    """
    views = []
    for rv in res.bench_cfg.result_vars:
        kind = result_kind(rv)
        if kind == "float":
            channels = {"radius": Channel.X.value, "repeat": Channel.SPREAD.value}
            mark = "line"
        elif kind == "image":
            channels = {"radius": Channel.FACET_COL.value, "repeat": Channel.FACET_ROW.value}
            mark = "image"
        else:  # dataset payload
            channels = {"radius": Channel.FACET_COL.value, "repeat": Channel.OVERLAY.value}
            mark = "scatter"
        views.append(
            {
                "result_var": rv.name,
                "result_kind": kind,
                "mark": mark,
                "channels": channels,
            }
        )
    outer = Compose(items=tuple(f"view:{v['result_var']}" for v in views), along=Channel.FACET_ROW)
    return {
        "plan_schema_version": PLAN_SCHEMA_VERSION,
        "grammar_version": GRAMMAR_VERSION,
        "policy_version": None,  # planner policy arrives with A6 phase 3
        "dataset_dims": {k: int(v) for k, v in ds.sizes.items()},
        "views": views,
        "compose": {"along": asdict(outer)["along"], "items": list(outer.items)},
    }


def write_arm(run_dir: Path, ds: xr.Dataset, manifest: dict, plan: dict) -> None:
    nc = sanitize_for_netcdf(ds)
    nc.to_netcdf(run_dir / "data.nc", engine="scipy")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (run_dir / "plan.json").write_text(json.dumps(plan, indent=2))
    # step3 round-trip baseline: the exact pre-write dataset.
    with (run_dir / "expected_ds.pkl").open("wb") as fh:
        pickle.dump(nc, fh)


def main() -> None:
    res = bn.load_result(WORK_DIR / "result.pkl")
    ds = res.ds

    # ---------------- Arm A3: contained ----------------
    a3 = OUT_DIR / "run_A3_contained"
    shutil.rmtree(a3, ignore_errors=True)
    (a3 / "artifacts" / "img").mkdir(parents=True)
    (a3 / "artifacts" / "data").mkdir(parents=True)

    ds_a3 = ds.copy(deep=True)
    artifacts: list[dict] = []

    # Image cells: absolute per-job-key paths -> copy INTO the run dir, cell
    # becomes a relative path. One copy per cell (that is what "contained with
    # no store" means — dedup is the store's job), disambiguated by job key.
    disk_vals = ds_a3["disk"].values
    flat = disk_vals.ravel()
    for i, cell in enumerate(flat):
        src = Path(str(cell))
        dest_name = f"{src.parent.name[:10]}_{src.name}"  # job-key prefix + name
        rel = f"artifacts/img/{dest_name}"
        shutil.copy2(src, a3 / rel)
        artifacts.append({"path": rel, "sha256": sha256_file(a3 / rel), "bytes": src.stat().st_size})
        flat[i] = rel
    ds_a3["disk"].values = disk_vals

    # Blob cells (ResultDataSet): resolve out of the store, copy in.
    pts_vals = ds_a3["points"].values
    flat = pts_vals.ravel()
    copied: dict[str, str] = {}
    for i, cell in enumerate(flat):
        name = str(cell)
        if name not in copied:
            src = resolve_blob(name)
            rel = f"artifacts/data/{name}"
            shutil.copy2(src, a3 / rel)
            artifacts.append({"path": rel, "sha256": sha256_file(a3 / rel), "bytes": src.stat().st_size})
            copied[name] = rel
        flat[i] = copied[name]
    ds_a3["points"].values = pts_vals

    ds_a3.attrs.pop("blob_cache_dir", None)  # self-contained: no store hint
    ds_a3.attrs["schema_version"] = SCHEMA_VERSION
    manifest_a3 = build_manifest(res, artifacts, [], form="contained")
    plan = build_plan(ds, res)
    write_arm(a3, ds_a3, manifest_a3, plan)

    # ---------------- Arm A6: store-referenced ----------------
    a6 = OUT_DIR / "run_A6_referenced"
    shutil.rmtree(a6, ignore_errors=True)
    a6.mkdir(parents=True)

    ds_a6 = ds.copy(deep=True)
    requires: dict[str, dict] = {}

    # Image cells: push the PNG bytes through the REAL blob store (today's
    # convention: bytes -> sha256[:16] + ".bin"; there is no media extension in
    # _BLOB_FORMATS — a finding, see RESULTS.md). Cell becomes the bare name.
    disk_vals = ds_a6["disk"].values
    flat = disk_vals.ravel()
    for i, cell in enumerate(flat):
        src = Path(str(cell))
        name = materialize_blob(src.read_bytes(), "cachedir")
        blob_path = Path("cachedir/blobs") / name
        requires[name] = {
            "name": name,
            "sha256": sha256_file(blob_path),
            "bytes": blob_path.stat().st_size,
            "source_kind": "image",
        }
        flat[i] = name
    ds_a6["disk"].values = disk_vals

    # ResultDataSet cells already ARE store references — unchanged.
    for cell in ds_a6["points"].values.ravel():
        name = str(cell)
        blob_path = resolve_blob(name)
        requires[name] = {
            "name": name,
            "sha256": sha256_file(blob_path),
            "bytes": blob_path.stat().st_size,
            "source_kind": "dataset",
        }

    ds_a6.attrs["schema_version"] = SCHEMA_VERSION  # keeps blob_cache_dir hint
    manifest_a6 = build_manifest(res, [], sorted(requires.values(), key=lambda d: d["name"]),
                                 form="store-referenced")
    write_arm(a6, ds_a6, manifest_a6, plan)

    # ---------------- immediate round-trip sanity ----------------
    report = ["== STEP 2: target arms written =="]
    for run_dir, pre in ((a3, ds_a3), (a6, ds_a6)):
        loaded = xr.load_dataset(run_dir / "data.nc", engine="scipy")
        pre_nc = sanitize_for_netcdf(pre)
        report.append(f"{run_dir.name}:")
        report.append(f"  data.nc bytes: {(run_dir / 'data.nc').stat().st_size}")
        report.append(f"  values equal after round-trip: {loaded.equals(pre_nc)}")
        report.append(f"  identical (incl. attrs/names): {loaded.identical(pre_nc)}")
        report.append(f"  dtypes after load: {[str(loaded[v].dtype) for v in loaded.data_vars]}")
        report.append(f"  attrs after load: {dict(loaded.attrs)}")
    out = "\n".join(report)
    (OUT_DIR / "step2_report.txt").write_text(out)
    print(out)


if __name__ == "__main__":
    main()
