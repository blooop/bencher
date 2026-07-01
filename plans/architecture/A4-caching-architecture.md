# A4 — Caching Architecture Redesign

**Status:** Proposal. Independent of A1/A2 except where marked; converges with A3's
serialization format in Phase C4. Supersedes-and-absorbs open PRs #760 (minimalkv
store) and #799 (netCDF history) — coordinate with plans/02-pr-triage.md.

---

## 1. Current architecture (verified, with file refs)

Four layers, three diskcache databases plus loose media directories, all under `cachedir/`:

| Layer | Store | Key | Value | Flags |
|---|---|---|---|---|
| **A: sample cache** | `cachedir/sample_cache` via `FutureCache` (`job.py:184-366`) | `hash_sha1((sorted(fn_inputs), tag))` (`worker_job.py:63`) | pickled worker result dict | `cache_samples`, `clear_sample_cache`, `overwrite_sample_cache`, `only_hash_tag`, `cache_size` |
| **B: result cache** | `cachedir/benchmark_inputs` (`result_collector.py:387-415`) | `bench_cfg.hash_persistent(include_repeats=True)` (`bench_cfg.py:731-777`) | pickled `BenchResult` | `cache_results`, `clear_cache` |
| **C: over_time history** | `cachedir/history` (`result_collector.py:416-508`) | `hash_persistent(include_repeats=False)` | pickled `xr.Dataset` | `over_time`, `clear_history`, `max_time_events` |
| **D: media artifacts** | `cachedir/{img,vid,rrd,generic}/{name}/{job_key}/` (`cache_management.py`) | path convention keyed by job_key | raw files | cleaned by `cleanup_job_media` / `clean_orphaned_media` |

The good parts, to preserve: the `hash_persistent()` contract is documented, test-
enforced (auto-discovering determinism tests), and deliberately excludes display-only
fields like `title`; `CACHE_VERSION` gives atomic global invalidation; `prefetch()`
batches lookups; tag-based eviction exists; `ContextVar`-based job keys make media
paths parallel-safe.

## 2. The architectural weaknesses

| # | Weakness | Consequence |
|---|---|---|
| W1 | **Worker source code is not in the sample key** (`worker_job.py:63` hashes inputs+tag only) | Edit your benchmark function, rerun, silently get *old* results. The single worst footgun in the system — it undermines trust in every cached number. |
| W2 | **Media orphaning**: `clear_tag` → `cache.evict(tag)` removes entries but not their media dirs (`job.py:332-344`); reconciliation is a manual `clean_orphaned_media()` walk | unbounded disk growth, stale images silently shown if paths collide |
| W3 | **Pickle at every layer** (job.py:116, result_collector.py:408, bench_plot_server.py) | CVE-class load-time code execution (the diskcache CVE is one instance); cache format coupled to internal class layout, so refactors corrupt/invalidate Layer B |
| W4 | **Key logic scattered** across `worker_job.py`, `bench_cfg.py`, `bencher.py:678-682` | nobody can answer "what invalidates what?"; the include_repeats=True/False subtlety between Layers B and C lives in two distant call sites |
| W5 | **History concat fragility**: Layer C key excludes repeats; dtype-mismatch history is silently discarded (`result_collector.py:473-480`); NaN-vs-0 sentinel mixing after the v1.105 default flip | over_time data quietly disappears or mixes regimes |
| W6 | **`only_hash_tag` cross-contamination is a global boolean** rather than a scoped, named decision | one flag flips the meaning of every key in the run |
| W7 | **Storage engine hard-coded** to diskcache (4 import sites) | the CVE response (#760) had to touch every call site; no cloud/shared-cache option for CI |

## 3. Target architecture

### 3.1 One storage interface, three namespaces (absorbs PR #760)

PR #760's `BencherStore` (dict-like API, tag index, pluggable minimalkv backends,
LRU-by-mtime eviction) is the right interface. Adopt it as **the only storage API**;
diskcache disappears behind it. Layers A/B/C become namespaces of one store rather
than three ad-hoc databases. CI/shared-cache backends (S3/GCS) come free via minimalkv.

### 3.2 One key module (fixes W4, W1, W6)

Create `bencher/caching/keys.py` — the *only* place hashes are composed:

```python
@dataclass(frozen=True)
class SampleKey:
    inputs_hash: str        # hash_sha1(sorted(fn_inputs))
    code_hash: str          # NEW — see below
    tag: str
    scope: str              # "run" (default) | "tag-only" (replaces only_hash_tag)

@dataclass(frozen=True)
class RunKey:
    cfg_hash: str           # hash_persistent(...)
    include_repeats: bool   # explicit, documented, in ONE place
    cache_version: int
```

`code_hash` policy (the W1 fix): default = `hash_sha1(inspect.getsource(worker))`,
falling back to the worker's `__qualname__` + module mtime when source is unavailable
(lambdas, C extensions). Opt-out flag `hash_worker_source=False` for users whose
workers call out to unhashable external systems and who manage invalidation by tag.
**This is a deliberate cache-busting change**: on upgrade, everyone's sample cache
misses once. Bump `CACHE_VERSION` in the same release and put it in the changelog as
a headline item.

### 3.3 Artifact manifests, not path conventions (fixes W2)

Every sample-cache value gains an explicit manifest of the media files it produced
(relative path + content hash) — the same `ArtifactManifest` as A3. Eviction deletes
through the manifest; `clean_orphaned_media` becomes a paranoid backstop instead of
the mechanism. Content hashes also enable dedup (identical frames across repeats
stored once) — optional, later.

### 3.4 Pickle-free values (fixes W3, converges with A3)

- Layer A values: worker results are dicts of primitives + artifact references —
  serialize as JSON/msgpack (validate: grep tests for workers returning exotic types;
  anything non-primitive should already be an artifact).
- Layer B values: store the A3 run directory format (netCDF + manifest) instead of
  pickled `BenchResult`. Cache survives refactors via `schema_version`.
- Layer C values: netCDF append along `over_time` — this **is** PR #799's
  `history_dir` design, generalized: history becomes ordinary, inspectable,
  git-committable files. #799's pandas-3.0 sanitization code is reusable directly.

### 3.5 History robustness (fixes W5)

With history as netCDF + manifest: store `repeats`, sentinel convention, and bencher
version per time-slice in attrs; on load, *report* incompatibilities (markdown pane in
the report: "2 historical snapshots skipped: repeats changed 5→10 on 2026-05-01")
instead of silently discarding. The silent-discard branch at
`result_collector.py:473-480` becomes a user-visible event.

## 4. Migration phases

**Phase C1 — storage interface.** Finish/merge PR #760 (`BencherStore`), then route
the remaining diskcache call sites (`cache_management.py`, `bench_plot_server.py`,
tests' `unique_names` cache) through it. Verify: full `ci` + the cache-specific tests;
manual check that `clear_cache`/`clear_sample_cache`/`evict(tag)` behave identically.

**Phase C2 — key module.** Mechanical extraction of all hash composition into
`caching/keys.py` with **zero key changes** (assert: golden-key tests pinning the
exact hash for fixed inputs before refactor, still passing after). Then add
`code_hash` + `CACHE_VERSION` bump as its own PR with the changelog headline.

**Phase C3 — artifact manifests.** Add manifest to new cache writes; eviction uses it
when present, falls back to the directory walk for old entries. No invalidation needed.
Verify: a test that runs an image sweep, evicts by tag, asserts the media dir is gone.

**Phase C4 — pickle-free values.** Requires A3 Phase D2 (the directory format).
Layer B first (lowest risk: it's a pure cache, regenerable), then Layer C with the
#799 convergence, Layer A last (highest traffic). Each layer keeps a read-only legacy
loader for one release.

**OWNER DECISIONS:** (a) the `code_hash` default-on choice and its one-time cache bust
(recommend: yes — correctness beats warm caches); (b) whether Layer C history should
default to in-cachedir or to a user-visible `history_dir` as #799 proposes (recommend:
`history_dir`, it makes regression tracking auditable and CI-committable); (c) dedup
in 3.3 (recommend: defer).

## 5. What NOT to do

- Don't redesign `hash_persistent()` semantics (what's excluded, e.g. `title`) — it's
  documented, tested, and correct. This plan moves *where* keys are composed and *what
  feeds them* (code hash), not the contract style.
- Don't make Layer A async/streaming or add TTLs — nothing in the workload needs it.
- Don't attempt cross-version cache compatibility for pickled legacy entries beyond
  one release of read-only support; they are caches, regeneration is the recovery path.
