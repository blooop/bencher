"""Step 3 of the issue #1069 prototype: measurements that settle questions.

Measures, for both arms built by step2:
  1. GC visibility (A6): what the real reachability scan sees (cache_management.py).
  2. Dedup: physical media copies + sizes per arm.
  3. Round-trip: data.nc vs the pre-write dataset; manifest hashes vs bytes.
  4. Zip (A3's open owner decision): size + load-from-zip plausibility.
  5. Relocatability: shutil.move the run dirs elsewhere AND hide the blob
     cache dir (simulating another machine), then resolve every media cell.

Run AFTER step2:  pixi run python plans/prototypes/on_disk_form_1069/step3_measure.py
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
import shutil
import sys
import zipfile
from pathlib import Path

import xarray as xr

PROTO_DIR = Path(__file__).parent.resolve()
OUT_DIR = PROTO_DIR / "out"
WORK_DIR = OUT_DIR / "work"

sys.path.insert(0, str(PROTO_DIR))
os.chdir(WORK_DIR)
os.environ.pop("BENCHER_CACHE_DIR", None)

from bencher.blob_store import resolve_blob  # noqa: E402
from bencher.cache_management import blob_reachability, clean_orphaned_blobs  # noqa: E402

# Same __main__ shim as step2: the benchmark_inputs diskcache values are pickled
# BenchResults referencing __main__.DiskFormSweep; without this the GC scan
# reports those roots unreadable (itself a finding).
import step1_current  # noqa: E402

sys.modules["__main__"].DiskFormSweep = step1_current.DiskFormSweep

A3 = OUT_DIR / "run_A3_contained"
A6 = OUT_DIR / "run_A6_referenced"
R: list[str] = []


def log(line: str = "") -> None:
    R.append(line)
    print(line)


def dir_stats(root: Path) -> tuple[int, int]:
    files = [f for f in root.rglob("*") if f.is_file()]
    return len(files), sum(f.stat().st_size for f in files)


def media_cells(ds: xr.Dataset) -> list[str]:
    return [str(c) for var in ("disk", "points") for c in ds[var].values.ravel()]


def measure_gc() -> None:
    log("== 1. GC visibility (A6 arm) ==")
    reach = blob_reachability("cachedir")
    log(f"reachability roots complete: {reach.complete}")
    log(f"unreadable roots: {list(reach.unreadable)}")
    log(f"live blob names seen by GC: {sorted(reach.names)}")
    ds = xr.load_dataset(A6 / "data.nc", engine="scipy")
    run_blobs = {c for c in media_cells(ds) if c.endswith((".bin", ".parquet"))}
    log(f"blob names the A6 run dir needs: {sorted(run_blobs)}")
    invisible = run_blobs - reach.names
    log(f"needed by A6 run but INVISIBLE to GC: {sorted(invisible)}")
    orphans, orphan_bytes = clean_orphaned_blobs("cachedir", dry_run=True)
    log(f"clean_orphaned_blobs dry-run would delete: {[Path(o).name for o in orphans]}"
        f"  ({orphan_bytes} B)")
    would_strand = run_blobs & {Path(o).name for o in orphans}
    log(f"A6-run blobs the GC would delete: {sorted(would_strand)}")
    log()


def measure_dedup() -> None:
    log("== 2. Dedup ==")
    n, b = dir_stats(A3 / "artifacts")
    hashes = [hashlib.sha256(f.read_bytes()).hexdigest()
              for f in (A3 / "artifacts").rglob("*") if f.is_file()]
    log(f"A3 artifacts/: {n} physical files, {b} B, {len(set(hashes))} unique contents"
        f" -> {n - len(set(hashes))} duplicate copies")
    n3, b3 = dir_stats(A3)
    log(f"A3 run dir total: {n3} files, {b3} B (fully self-contained)")

    ds = xr.load_dataset(A6 / "data.nc", engine="scipy")
    blob_names = {c for c in media_cells(ds)}
    blob_files = [Path("cachedir/blobs") / name for name in blob_names]
    blob_bytes = sum(p.stat().st_size for p in blob_files)
    n6, b6 = dir_stats(A6)
    log(f"A6 run dir total: {n6} files, {b6} B (+ store dependency)")
    log(f"A6 store dependency: {len(blob_names)} blobs, {blob_bytes} B "
        f"(12 cells -> {len(blob_names)} physical files: content-addressing dedups"
        " identical repeats)")
    log()


def measure_roundtrip() -> None:
    log("== 3. Round-trip ==")
    for run_dir in (A3, A6):
        loaded = xr.load_dataset(run_dir / "data.nc", engine="scipy")
        with (run_dir / "expected_ds.pkl").open("rb") as fh:
            expected = pickle.load(fh)
        log(f"{run_dir.name}: values equal={loaded.equals(expected)} "
            f"identical(attrs too)={loaded.identical(expected)}")
        manifest = json.loads((run_dir / "manifest.json").read_text())
        checked = mismatched = 0
        for art in manifest["artifacts"]:
            actual = hashlib.sha256((run_dir / art["path"]).read_bytes()).hexdigest()
            checked += 1
            mismatched += actual != art["sha256"]
        for blob in manifest["requires_blobs"]:
            actual = hashlib.sha256((Path("cachedir/blobs") / blob["name"]).read_bytes()).hexdigest()
            checked += 1
            mismatched += actual != blob["sha256"]
        log(f"{run_dir.name}: manifest hashes checked={checked} mismatched={mismatched}")
    log()


def measure_zip() -> None:
    log("== 4. Zip check (A3 owner decision: dir vs single-file zip) ==")
    zip_path = shutil.make_archive(str(OUT_DIR / "run_A3_contained"), "zip",
                                   root_dir=A3.parent, base_dir=A3.name)
    _, dir_bytes = dir_stats(A3)
    log(f"zip size: {Path(zip_path).stat().st_size} B (dir was {dir_bytes} B)")
    with zipfile.ZipFile(zip_path) as zf:
        raw = zf.read(f"{A3.name}/data.nc")
    try:
        ds = xr.load_dataset(io.BytesIO(raw), engine="scipy")
        log(f"load data.nc from zip member bytes (no extraction): OK, dims={dict(ds.sizes)}")
    except Exception as exc:  # noqa: BLE001
        log(f"load data.nc from zip member bytes: FAILED ({type(exc).__name__}: {exc})")
    log("artifact cells resolve relative to the run dir -> a zip loader must read"
        " members by the same relative names (zipfile can; no extraction needed in principle)")
    log()


def measure_relocatability() -> None:
    log("== 5. Relocatability (move run dirs, hide the blob cache) ==")
    moved_root = OUT_DIR / "moved" / "another" / "machine"
    shutil.rmtree(OUT_DIR / "moved", ignore_errors=True)
    moved_root.mkdir(parents=True)
    a3_moved = Path(shutil.move(str(A3), str(moved_root / A3.name)))
    a6_moved = Path(shutil.move(str(A6), str(moved_root / A6.name)))
    cache_hidden = WORK_DIR / "cachedir_hidden"
    (WORK_DIR / "cachedir").rename(cache_hidden)
    os.chdir(moved_root)  # different cwd too: no ./cachedir anywhere in sight
    try:
        for run_dir, arm in ((a3_moved, "A3"), (a6_moved, "A6")):
            ds = xr.load_dataset(run_dir / "data.nc", engine="scipy")
            log(f"{arm}: data.nc loads after move: True")
            ok = missing = 0
            first_error = None
            for cell in media_cells(ds):
                if arm == "A3":
                    found = (run_dir / cell).is_file()
                else:
                    try:
                        resolve_blob(cell, fallback_cache_dirs=[ds.attrs.get("blob_cache_dir", "")])
                        found = True
                    except (FileNotFoundError, ValueError) as exc:
                        found = False
                        first_error = first_error or f"{type(exc).__name__}: {exc}"
                ok += found
                missing += not found
            log(f"{arm}: media cells resolved {ok}/{ok + missing}, missing {missing}")
            if first_error:
                log(f"{arm}: first failure: {first_error[:300]}")
    finally:
        os.chdir(WORK_DIR)
        cache_hidden.rename(WORK_DIR / "cachedir")
        shutil.move(str(a3_moved), str(A3))
        shutil.move(str(a6_moved), str(A6))
    log()


def main() -> None:
    measure_gc()
    measure_dedup()
    measure_roundtrip()
    measure_zip()
    measure_relocatability()
    (OUT_DIR / "step3_report.txt").write_text("\n".join(R))


if __name__ == "__main__":
    main()
