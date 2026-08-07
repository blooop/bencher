# Prototype: reconciled on-disk form of a saved run (issue #1069)

Throwaway prototype reconciling **A3 §2** (contained run dir: `data.nc` + `manifest.json`
+ `artifacts/` inside the run dir) with **A6 Law 1/9** (every non-numeric cell is a
content-addressed path into the blob store; `collect()` stores a Plan per view). Both
target forms were built **from the same real sweep output** (3 radii x 2 repeats, one
`ResultFloat`, one `ResultImage`, one `ResultDataSet`) and measured side by side.

Scripts (run in order, each `pixi run python plans/prototypes/on_disk_form_1069/<script>`):
`step1_current.py` (real sweep via `Bench.collect()` + `save_result`),
`step2_target.py` (converts the pickle+cachedir into both arms),
`step3_measure.py` (relocatability / dedup / GC / zip / round-trip).
Everything lands under `out/` (gitignored); the real `manifest_A3.json`,
`manifest_A6.json`, `plan.json` are committed beside this file.

## Step 1 — current truth (what `collect()` writes today)

`collect()` returns a live `BenchResult`; `bencher.save_result` writes **one pickle**
(`result.pkl`, 29,638 B for this 6-sample sweep). The pickle stream reconstructs (STACK_GLOBAL
opcodes): `BenchResult`, `BenchCfg`, `param.parameterized._InstancePrivate`,
`FloatSweep`/`ResultImage`/`ResultFloat`/`ResultDataSet` param objects, `xr.Dataset`, and
**`__main__.DiskFormSweep` — the user's sweep class**. Consequence measured twice below: the
pickle (and even the GC scan over `benchmark_inputs`) only works in a process where the
writer's class is importable.

Two different media-cell conventions coexist today:

- `ResultImage` cell = **absolute** per-job-key path (from `utils.py:gen_path`, line 268):
  `/…/out/work/cachedir/img/disk/37f7436f2bb1aed9…/disk.png`
- `ResultDataSet` cell = **bare content-addressed blob name** (from
  `blob_store.py:materialize_blob`): `fb0ce1afcb4dbfe8.parquet`, resolved against
  `<cachedir>/blobs/` with the collect-time cache dir recorded once in
  `ds.attrs["blob_cache_dir"]` (commit cfd551a3's `--cachedir` machinery).

Cachedir layout: `cachedir/{CACHE_VERSION, benchmark_inputs/ (diskcache),
blobs/ (3 parquet), img/disk/<job_key>/disk.png x6}` — 147,993 B total. The 6 PNGs contain
only 3 unique images (repeats are deterministic) but exist as 6 physical files: the
per-job-key media tree does not dedup; the blob store does (3 parquet for 6 cells).

## Step 2 — both target arms

```
run_A3_contained/                     run_A6_referenced/
  data.nc          1,240 B              data.nc          1,220 B
  manifest.json    2,792 B              manifest.json    2,400 B
  plan.json          825 B              plan.json          825 B   (byte-identical to A3's)
  artifacts/                            (no artifacts/ — needs 6 blobs
    img/37f7436f2b_disk.png   172 B      from <cachedir>/blobs/, listed
    img/69f7e70fd6_disk.png   172 B      with sha256 in manifest.json
    img/7d6ddd24ec_disk.png   328 B      "requires_blobs")
    img/6dbfa5f9fe_disk.png   328 B
    img/3d5189ff3d_disk.png   422 B
    img/32b4bd1bac_disk.png   422 B
    data/fb0ce1afcb4dbfe8.parquet 2,140 B
    data/45987ab7f576351e.parquet 2,140 B
    data/3bb689ff30010cee.parquet 2,140 B
```
(`expected_ds.pkl` in each dir is measurement scaffolding, not part of the format.)

Cell contents: A3 `disk` = `artifacts/img/37f7436f2b_disk.png` (relative),
A3 `points` = `artifacts/data/fb0ce1afcb4dbfe8.parquet`; A6 `disk` =
`a01463ec32a6319d.bin` (real `materialize_blob` output — bytes get `.bin`; the blob
store has **no media extensions**, see Exposed), A6 `points` = `fb0ce1afcb4dbfe8.parquet`
(unchanged — already store-form today). `data.nc` written netCDF3/scipy (this env's only
backend) after object→str and int64→int32 sanitization.

### The real manifest.json (A3 arm; A6 differs only in `form`, empty `artifacts`, and a populated `requires_blobs`)

```json
{
  "run_meta": {
    "schema_version": "1",
    "name": "disk_form_1069",
    "bencher_version": "1.119.1",
    "timestamp": "2026-08-07T15:19:48+00:00",
    "sweep_hash": "f526fe23dd02e465e691273186ef95ab9400d369",
    "form": "contained"
  },
  "input_vars": [
    {"name": "radius", "type": "FloatSweep", "kind": "input", "units": "ul",
     "bounds": [0.2, 1.0], "samples": 3, "level": null},
    {"name": "repeat", "type": "repeat", "kind": "input", "units": null,
     "bounds": null, "samples": 2, "level": null}
  ],
  "result_vars": [
    {"name": "disk",   "type": "ResultImage",   "kind": "image",   "units": "path"},
    {"name": "area",   "type": "ResultFloat",   "kind": "float",   "units": "m^2"},
    {"name": "points", "type": "ResultDataSet", "kind": "dataset", "units": "dataset"}
  ],
  "plot_specs": [],
  "plans": ["plan.json"],
  "artifacts": [
    {"path": "artifacts/img/37f7436f2b_disk.png", "sha256": "a01463ec32a6319d954c…", "bytes": 172},
    {"path": "artifacts/img/69f7e70fd6_disk.png", "sha256": "a01463ec32a6319d954c…", "bytes": 172},
    {"path": "artifacts/img/7d6ddd24ec_disk.png", "sha256": "ca471bff3d0eebadbee7…", "bytes": 328},
    {"path": "artifacts/img/6dbfa5f9fe_disk.png", "sha256": "ca471bff3d0eebadbee7…", "bytes": 328},
    {"path": "artifacts/img/3d5189ff3d_disk.png", "sha256": "514e32f23953a420da50…", "bytes": 422},
    {"path": "artifacts/img/32b4bd1bac_disk.png", "sha256": "514e32f23953a420da50…", "bytes": 422},
    {"path": "artifacts/data/fb0ce1afcb4dbfe8.parquet", "sha256": "fb0ce1afcb4dbfe8c9fe…", "bytes": 2140},
    {"path": "artifacts/data/45987ab7f576351e.parquet", "sha256": "45987ab7f576351e8526…", "bytes": 2140},
    {"path": "artifacts/data/3bb689ff30010cee.parquet", "sha256": "3bb689ff30010ceeb28f…", "bytes": 2140}
  ],
  "requires_blobs": []
}
```
(Full-length hashes in the committed `manifest_A3.json` / `manifest_A6.json`. Note the
sha256 columns already reveal the A3 duplication: three hash values across six PNG rows.
Result-var rows abbreviated here; the committed files carry all VarSpec fields.)

### The real plan.json (identical bytes in both arms)

Serialized from the real grammar package (`bencher/grammar`): `Channel` values are the
stored channel names, the outer node is a real `Compose` (Law 4/5: one view per result
var, composed along a layout channel).

```json
{
  "plan_schema_version": "1",
  "grammar_version": "1",
  "policy_version": null,
  "dataset_dims": {"radius": 3, "repeat": 2},
  "views": [
    {"result_var": "disk", "result_kind": "image", "mark": "image",
     "channels": {"radius": "facet_col", "repeat": "facet_row"}},
    {"result_var": "area", "result_kind": "float", "mark": "line",
     "channels": {"radius": "x", "repeat": "spread"}},
    {"result_var": "points", "result_kind": "dataset", "mark": "scatter",
     "channels": {"radius": "facet_col", "repeat": "overlay"}}
  ],
  "compose": {"along": "facet_row", "items": ["view:disk", "view:area", "view:points"]}
}
```

**Where the plan lives — concrete choice: a sibling `plan.json` per view-set, referenced
from `manifest.json` (`"plans": ["plan.json"]`).** Why not dataset attrs: (a) this env's
only netCDF backend is netCDF3/scipy, whose attrs are flat strings — a plan would be an
opaque JSON-in-a-string invisible to `ncdump` readers; (b) Law 9 says a stored plan is a
default, never a lock — `replan=True` must be able to rewrite the plan without touching
`data.nc` (and without invalidating the data file's checksum/mtime); (c) plan and
dataset need **separate** schema_version discipline (grammar/policy version vs data
schema version), which one file with two half-owned attrs muddles.

## Step 3 — measurements

| # | Question | A3 contained | A6 store-referenced |
|---|---|---|---|
| 1 | Relocatability (run dir `shutil.move`d, blob cache renamed away, cwd changed) | `data.nc` loads; **12/12 media cells resolve** relative to the run dir | `data.nc` loads; **0/12 cells resolve** — `FileNotFoundError: blob store: no readable file for blob 'a01463ec32a6319d.bin' (tried 'cachedir/blobs/…', '/…/out/work/cachedir/blobs/…')` (both the cwd-relative store and the recorded `blob_cache_dir` hint are gone) |
| 2 | Dedup (repeats=2, deterministic payloads) | `artifacts/`: **9 physical files, 6 unique contents → 3 duplicate PNG copies**; run dir 16,189 B | run dir 4 files, 6,983 B; store dependency **6 blobs, 7,342 B for 12 cells** — content addressing dedups the repeats for free |
| 3 | GC visibility (reads real `cache_management.py`) | n/a (no store dependency) | Parquet blobs reachable only via the `benchmark_inputs` diskcache; the run dir itself is **never a GC root**. The 3 image blobs the A6 run needs are invisible: `clean_orphaned_blobs(dry_run=True)` lists exactly those 3 for deletion (922 B) |
| 4 | Zip (A3 open owner decision) | zip = **10,392 B** (dir 16,189 B); `data.nc` loads straight from the zip member bytes via `xr.load_dataset(BytesIO, engine="scipy")` — no extraction; artifact members are addressable by the same relative names, so load-from-zip is plausible with the current stack | n/a |
| 5 | Round-trip | `xr.load_dataset(data.nc)` `.equals` **and** `.identical` (attrs incl.) = True; 9/9 manifest sha256 match artifact bytes | same: identical=True; 6/6 `requires_blobs` sha256 match store bytes |

GC evidence (cited from code, verified live):

- Roots are only the `benchmark_inputs` + `history` diskcaches under the cachedir —
  `cache_management.py:453` (`_BLOB_REFERENCE_CACHES = ("benchmark_inputs", "history")`)
  — plus `extra_roots`, which accepts **only `*.pkl` files** (`_extra_root_files`,
  `cache_management.py:583-602`: a directory contributes `path.rglob("*.pkl")`). A run
  dir with `data.nc` can never be a root today, moved or not; its blobs get collected as
  soon as the diskcache entry that happens to share them is evicted. The module already
  documents the same hole for pickles ("Results saved outside the cache are invisible",
  `cache_management.py:734-739`).
- Worse: with the writer's sweep class not importable, the reachability scan itself
  aborts — measured: `complete=False`, `unreadable: benchmark_inputs[…]: cannot
  deserialize (AttributeError: Can't get attribute 'DiskFormSweep' on <module
  '__main__'>)` — GC then deletes nothing at all (`cache_management.py:780-783`). The
  pickle-based roots make GC hostage to the user's import graph.

## Settled vs Exposed

**Settled by this artifact** (evidence line in the table above):

1. **Relocatability requires the contained form.** A3 moved to a "different machine"
   resolves 12/12 cells; A6 resolves 0/12 (measurement 1). A6 Law 1 alone does not give
   an emailable run.
2. **Dedup requires the store form.** A3 physically duplicates identical repeat payloads
   (9 files / 6 unique); the store holds 6 blobs for 12 cells (measurement 2). Neither
   arm wins both 1 and 2 — the reconciliation must be a hybrid (below).
3. **netCDF + JSON round-trips this dataset exactly** — `.identical()` = True including
   attrs, via netCDF3/scipy after object→str sanitization; manifest sha256s verify
   bytes (measurement 5). The A3 §5 "netCDF fidelity" risk did not bite for
   image/float/dataset cells at this scale.
4. **Zip is viable as an export encoding** of the contained form: 36% smaller here, and
   `data.nc` loads from member bytes without extraction (measurement 4). The owner
   decision can be "directory canonical, zip = export", not either/or.
5. **The stored Plan serializes naturally from the landed grammar vocabulary** — channel
   names, `Compose`, `GRAMMAR_VERSION` — and is byte-identical in both arms, i.e. the
   plan is orthogonal to the artifact-location question (Law 9 composes with either A3
   or A6).
6. **A run dir is invisible to today's blob GC by construction** (roots:
   `cache_management.py:453`; `*.pkl`-only extra roots: `:583-602`) — verified live:
   dry-run GC deletes exactly the A6 run's image blobs. Shipping A6-referenced run dirs
   without adding run dirs as GC roots loses data.

**Exposed — needs the A3 disposition discussion:**

1. **Hybrid form** (the actual reconciliation): store-backed cells at collect (A6, dedup +
   `over_time` sharing) with an **export-to-contained** operation (A3, relocatable) that
   copies `requires_blobs` into `artifacts/` and rewrites cells to relative paths — this
   prototype's step2 *is* that export, run in both directions; ~60 lines. Decide: is the
   contained dir a *view* produced on export, or the canonical save format?
2. **Two media conventions today** (absolute gen_path image paths vs bare blob names).
   Any target form must first unify them; A6 Law 1 says blob store, but the blob store
   currently has **no media extensions** — image bytes become `<hash>.bin`
   (`blob_store.py` `_BLOB_FORMATS`: parquet/nc/da.nc/bin/pkl only), which loses the
   file-type signal renderers key on. Needs `.png`/`.mp4`/`.rrd` in the format table
   (single-entry change by design) before Law 1 covers images.
3. **Should manifest.json carry the plan inline?** This prototype says no (sibling file,
   reasons above), but the counter-position — one fewer file, atomic manifest+plan —
   deserves the owner call, especially if `plans` grows to per-view files
   (`plan_<view>.json`).
4. **schema_version discipline**: `run_meta.schema_version` (writer-version-in-band,
   issue #1107's RRF2 analog) vs `plan_schema_version` + `grammar_version` +
   `policy_version` in plan.json. Three version fields in two files — who bumps what,
   and does the loader's refuse-on-unknown-major rule apply to plans (Law 9 says no:
   fall back to replan)?
5. **GC contract for A6-form runs**: run dirs as first-class GC roots (scan `data.nc`
   for blob names — cheap, no pickle) vs manifest-registered runs vs "contained-on-save
   makes GC irrelevant". The `*.pkl`-only `extra_roots` and the
   import-graph-hostage scan (measured above) both argue for scanning `data.nc` +
   `manifest.json` instead of pickles.
6. **`artifacts/data/` for dataset payloads**: A3 §2 names only `img/, vid/, rrd/`;
   ResultDataSet parquet blobs needed a home in the contained form. Bless
   `artifacts/data/` (this prototype's choice) or fold everything into one
   content-named `artifacts/` pool (which would also dedup the contained form — at the
   cost of A3's human-readable relative names).

Rulings honored, not re-made: rerun recordings stay merged single `.rrd` (#1113 — rrd
not exercised here; image was the required blob type); writer version travels in-band
(#1107 → `run_meta.schema_version`).
