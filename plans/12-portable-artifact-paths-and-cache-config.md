# Plan 12 — Portable Artifact Paths & Public Cache Configuration

**Goal:** Give bencher one authoritative resolution point for the `cachedir/` root
(explicit setter > env var > current CWD-relative default) and a supported cache-size
knob — so benchmarks stop scattering `cachedir/` litter across working directories,
the collect/render split stops silently dropping media when processes disagree on
CWD, and downstream users stop monkey-patching module globals.

**⚠️ Read first:** `plans/architecture/A3-benchdata-contract.md` and
`plans/architecture/A4-caching-architecture.md`. This plan is a deliberately small,
independently-shippable **precursor** to both:

- A4 Phase C1 replaces diskcache with a `BencherStore` interface. This plan does
  NOT touch the storage engine, keys, or values — it only centralizes *where the
  root directory comes from*. When C1 lands, `BencherStore` construction consumes
  this plan's resolver as its base path; nothing here is thrown away.
- A4 §3.3 / A3 Phase D2 make saved runs truly relocatable (artifacts copied into a
  run directory, referenced by relative path + content hash in a manifest). That is
  the *cross-machine* fix. This plan only guarantees *same-machine* agreement on
  the cache root regardless of CWD — do not implement manifests or relative
  artifact references here; that would conflict with A3/A4.
- No cache key or value format changes; no `CACHE_VERSION` bump is needed.

**Rules:** always use the pixi environment (`pixi run ...`); `pixi run ci` must
pass before committing; feature branch only, never `main` (version bump on `main`
auto-publishes); if a step fails in a way this plan does not cover, stop and report.

---

## 1. Current behavior (verified)

### 1.1 Media paths: CWD-relative at creation, absolute in results

`gen_path` (`bencher/utils.py:247-279`) builds
`Path(f"cachedir/{folder}/{filename}/{job_key}/")` (`utils.py:264`; UUID fallback at
`utils.py:277`) — **relative to the process CWD at call time** — then returns
`path.absolute().as_posix()` (`utils.py:275`). So the string stored in the result
dataset is *absolute against the collect process's CWD*. Wrappers:
`gen_video_path` (`utils.py:282`), `gen_image_path` (`utils.py:295`),
`gen_rerun_data_path` (`utils.py:308`). Callers include `VideoWriter`
(`bencher/video_writer.py:15`), regression plots (`bencher/regression.py:871`),
and rerun capture (`bencher/utils_rerun.py:25`).

### 1.2 The rrd pipeline re-relativizes against a CWD-relative constant

`_RRD_CACHE_DIR = Path("cachedir/rrd")` (`bencher/utils_rrd.py:27`) is resolved
against the CWD of whichever process happens to be running, at four stages:

1. **Pane construction** — `rrd_file_to_pane` requires
   `rrd_path.relative_to(_RRD_CACHE_DIR.resolve())` (`utils_rrd.py:115-121`) and
   emits a root-relative `/rrd_static/...` URL (`utils_rrd.py:250-251`), discarding
   the absolute path.
2. **Static save rewrite** — `inline_rrd_iframes` re-derives
   `cache_root = _RRD_CACHE_DIR.resolve()` in the *save* process
   (`utils_rrd.py:378`) and reconstructs each `.rrd`'s absolute path from the
   `/rrd_static/` URL (`utils_rrd.py:395`).
3. **Live serving** — the Panel server mounts `Path("cachedir/rrd").resolve()` at
   `/rrd_static/` (`bencher/bench_plot_server.py:190`).
4. **over_time panes** — `_over_time_filepath`
   (`bencher/results/bench_result_base.py:951-965`) drops any stored path that
   fails `os.path.isfile`.

### 1.3 Diskcache and management paths are also CWD-relative

- Sample cache: `Cache(f"cachedir/{cache_name}", ...)` (`bencher/job.py:225`).
- Result + history caches: `Cache("cachedir/benchmark_inputs", ...)` /
  `Cache("cachedir/history", ...)` (`bencher/result_collector.py:157,163`); the
  plot server opens the same relative path (`bench_plot_server.py:95`).
- `ensure_cache_version(cachedir="cachedir")` (`bencher/cache_management.py:79`)
  runs on every `Bench` construction (`bencher/bencher.py:106`) — it *creates*
  `cachedir/` in whatever directory you launched from.
- Every management helper defaults to the relative literal: `cache_stats`
  (`cache_management.py:180`), `cleanup_job_media` (`:222`), `clear_all` (`:257`),
  `clear_media` (`:267`), `clean_orphaned_media` (`:311`).
- `BenchReport.save(directory="cachedir", ...)` (`bencher/bench_report.py:244`) and
  `run_file_server` (`bencher/file_server.py:46`) default to the CWD `cachedir/`.

### 1.4 Cache size: a constant threaded through import-time bindings

`DEFAULT_CACHE_SIZE_BYTES = int(100e9)` (`bencher/cache_management.py:45`) — 100 GB
(≈93 GiB), far above what a CI runner can absorb before eviction ever triggers.
`bencher.py:48` imports it **by value**; `Bench.__init__` reads it at construction
time (`bencher.py:109-112`) and passes it to `SweepExecutor` and `ResultCollector`;
the sample cache inherits it via `init_sample_cache`
(`bencher/sweep_executor.py:188-195`). `ResultCollector.__init__` and
`SweepExecutor.__init__` also bind it as a **default argument** at import time
(`result_collector.py:143`, `sweep_executor.py:80`). Standalone `FutureCache` and
`JobFunctionCache` carry separate literals (`job.py:209` = 20 GB, `job.py:386` =
10 GB), unconnected to the constant.

A per-run knob exists — `BenchRunCfg.cache_size` in **megabytes**
(`bencher/bench_cfg.py:255-260`), converted at `bencher.py:646-655` — but it must
be set on every run config and cannot change the process default. Consequently the
only way to change the default is monkey-patching, and only one spelling works:
patching `bencher.bencher.DEFAULT_CACHE_SIZE_BYTES` affects future `Bench` objects
(name looked up at call time), while patching `bencher.cache_management.…` or the
re-export in `bencher/__init__.py:149` does nothing after import. Users have found
and depend on the one working spelling; that is an accident, not an API.

## 2. The defects

**D1 — cachedir litter.** Running the same benchmark from three directories creates
three independent `cachedir/` trees (three cold caches, three version files, up to
3×100 GB before any eviction), because every path in §1.1–1.3 resolves against CWD.

**D2 — collect/render CWD coupling.** The split (`bencher/render.py`) pickles in
one process and renders in another. The dataset's media paths are absolute (§1.1),
but the rrd stages in §1.2 each re-resolve `cachedir/rrd` against their *own* CWD.
When CWDs disagree, in decreasing loudness:
- Direct rerun pane: `ValueError` from `utils_rrd.py:117-121`; the render CLI's
  broad guard converts it to exit 1 (`render.py:253-256`) — report not produced.
- Saved report: `inline_rrd_iframes` can't find the file, logs a warning, and
  **leaves the dead `/rrd_static/` URL in place** (`utils_rrd.py:395-398`) — the
  report renders with blank embedded viewers and no error surfaced to the user.
- Live serving from the wrong CWD: iframe 404s, blank viewer, silent.
- over_time panes: silently replaced by "No data for this time point"
  (`bench_result_base.py:951-965`).

**D3 — no supported configuration.** No env var or public setter exists for either
the cache root (grep: the only `BENCHER_*` env var is `BENCHER_FORCE_SPLIT_RENDER`,
`bencher.py:761`) or the default cache size (§1.4).

## 3. Design

### 3.1 One root resolver: `bencher/paths.py` (new, zero bencher imports)

```python
def set_cache_dir(path: str | Path | None) -> None:
    """Process-wide override; None clears it. Call before creating a Bench."""

def cache_dir() -> Path:
    """Absolute cache root. Precedence:
    set_cache_dir(...) > $BENCHER_CACHE_DIR > Path("cachedir") (CWD-relative)."""

def rrd_dir() -> Path:
    """cache_dir() / 'rrd' — replaces the _RRD_CACHE_DIR constant."""
```

`cache_dir()` resolves lazily at each call and returns an absolute path. The
default remains `Path("cachedir")` resolved against the current CWD — byte-for-byte
compatible with today. Export `set_cache_dir` / `get_cache_dir` from
`bencher/__init__.py`. Every literal in §1.2–1.3 routes through it: `gen_path`,
`_RRD_CACHE_DIR` (becomes the `rrd_dir()` call), both `Cache(...)` constructors,
`job.py:225`, `ensure_cache_version`, all `cache_management.py` defaults
(`cachedir: str | Path | None = None` → resolve in body), `bench_plot_server.py:95`
and `:190`, `file_server.py:46`, and `BenchReport.save`'s default directory.
(Leave `manim_cartesian/cartesian_product_scene.py:600` for a follow-up; it is a
leaf default, not on the render path.)

With every stage resolving the same root, D2's same-machine case is fixed without
touching the stored-path format: with `BENCHER_CACHE_DIR=/data/b`, collect,
render, save, and serve agree on `/data/b/rrd` regardless of each process's CWD.

### 3.2 Cache size as configuration, not a patchable global

In `cache_management.py`, add:

```python
def default_cache_size_bytes() -> int:
    """set_default_cache_size(...) > $BENCHER_CACHE_SIZE_MB (MB, matching
    BenchRunCfg.cache_size units) > DEFAULT_CACHE_SIZE_BYTES (100 GB)."""
```

Call sites switch from the constant / import-time default args to lazy resolution:
`bencher.py:109` calls the function; `result_collector.py:143` and
`sweep_executor.py:80` take `cache_size: int | None = None` and resolve in-body.
`BenchRunCfg.cache_size` keeps highest precedence per run (`bencher.py:646-655`,
unchanged). Keep `DEFAULT_CACHE_SIZE_BYTES` exported as the documented fallback
constant; add a CHANGELOG + docstring note that patching module attributes is
unsupported and now ineffective by design (the accidental
`bencher.bencher.DEFAULT_CACHE_SIZE_BYTES` patch point disappears — see §6).

**OWNER DECISIONS:** (a) lower the 100 GB default? Recommend **no** for now — a
lower `size_limit` culls existing warm caches on next open; the env var gives CI
the small cache it needs. Revisit alongside A4 C1's eviction work. (b) Env var
names `BENCHER_CACHE_DIR` / `BENCHER_CACHE_SIZE_MB` (matching the existing
`BENCHER_FORCE_SPLIT_RENDER` prefix).

## 4. Implementation phases

**P1 — resolver + path call sites.** Add `paths.py` with unit tests (precedence,
absolute result, override clearing). Mechanically route §3.1's call sites through
it. No behavior change with no env var set — the full suite must pass unchanged.

**P2 — cache-size resolution.** §3.2, plus docs for `BenchRunCfg.cache_size` (the
MB units are easy to miss). Unit tests: env var respected; run-cfg wins; constant
fallback.

**P3 — cross-CWD regression tests + docs.** See §5. Document both env vars in the
README caching section (plan 06 territory — coordinate, don't duplicate).

## 5. Tests / acceptance criteria

1. **Collect in A, render in B** (the D2 regression test, in `test/test_render.py`):
   run a sweep with a file-backed result var (image is enough; rerun if the SDK is
   in the test env) with `BENCHER_CACHE_DIR` pointing at a tmp dir; `save_result`;
   `os.chdir` to a second tmp dir; `render_report`; assert exit success, media
   sidecars present next to the HTML, and **no `/rrd_static/` references remain**
   in the saved HTML (the current silent-blank signature).
2. Same scenario *without* the env var must reproduce today's behavior (documents
   the compat default; marks the trap).
3. `cachedir/` litter: with `set_cache_dir(tmp)`, `Bench(...)` construction and a
   small sweep create nothing under CWD (assert directory listing unchanged).
4. Precedence unit tests for `cache_dir()` and `default_cache_size_bytes()`.
5. `pixi run ci` green, including `test/test_rrd_inline.py`,
   `test/test_cache_management.py`, and the untouched
   `test/test_split_render_examples.py` split-render harness.

## 6. Migration & compatibility

- **Default behavior is unchanged** (CWD-relative `cachedir/`): no cache is
  invalidated, no key changes, no `CACHE_VERSION` bump.
- First run with `BENCHER_CACHE_DIR` set starts a cold cache at the new location —
  expected; note in the CHANGELOG. Old absolute paths inside previously cached
  results still point at the old tree and keep working until evicted.
- The working monkey-patch spelling (`bencher.bencher.DEFAULT_CACHE_SIZE_BYTES`)
  stops having an effect once `bencher.py:109` calls `default_cache_size_bytes()`.
  **Breaking for patch users** — headline it in the CHANGELOG with the one-line
  replacement (`BENCHER_CACHE_SIZE_MB` or `set_default_cache_size(...)`).
- `set_cache_dir` is process-wide and must be called before the first `Bench` /
  `gen_path`; changing it mid-run is unsupported (document, and log a warning if
  caches are already open).

## 7. Risks

- **Missed call site**: a leftover `"cachedir"` literal splits the tree in two when
  the env var is set. Mitigate with a CI grep gate allowlisted to `paths.py`.
- **Windows separators**: `gen_path` returns `as_posix()` strings today; keep that
  contract when routing through the resolver.
- **A4 drift**: if A4 Phase C1 lands first, implement §3.1 anyway (C1's store still
  needs a base path) but hand §3.2's size setting to `BencherStore`'s eviction
  config instead of diskcache `size_limit`.

## 8. What NOT to do (deferred to A3/A4)

- No artifact manifests, content hashes, or relative stored paths — A4 §3.3 / A3
  Phase D2 own relocatability across machines and into run directories.
- No storage-engine or key/`hash_persistent` changes (A4 C1/C2; plan 09 owns the
  key-ordering defects). No per-`Bench` or per-thread cache roots — one process,
  one root, until A4's store interface gives a natural scoping point.
