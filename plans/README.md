# Bencher Improvement Plans

This directory contains self-contained improvement plans for the bencher repository.
Each plan is written so it can be executed independently by an AI agent or developer
without additional context. **Read the whole plan before starting it.**

## Ground rules for every plan

1. **Always use the pixi environment**: prefix every command with `pixi run`
   (e.g. `pixi run pytest`, `pixi run python ...`). Never run tools directly.
2. **Run `pixi run ci` before committing.** It must pass (format, lint, type check, tests).
3. Work on a feature branch, never directly on `main`. Merging to `main` with a version
   bump auto-publishes to PyPI (until plan 01 is done), so be careful.
4. Do not bump the version in `pyproject.toml` unless the plan says to.
5. The PyPI package name is **`holobench`** (intentional — `bencher` was taken).
   The import name is `bencher`. Do NOT "fix" this mismatch.
6. If a step fails in a way the plan doesn't cover, stop and report rather than improvising.

## Plan index and recommended order

| # | Plan | Risk | Effort | Do first? |
|---|------|------|--------|-----------|
| 01 | [Release & CI safety](01-release-safety.md) | Low | Small | **Yes — highest impact/effort ratio** |
| 02 | [Inflight PR triage](02-pr-triage.md) | Low–Med | Medium | Yes — unblocks everything else |
| 03 | [Repo hygiene](03-repo-hygiene.md) | Low | Small | Yes |
| 04 | [Dependencies & import time](04-dependencies.md) | Medium | Medium | After 02 (depends on PR #760 decision) |
| 05 | [Test coverage gaps](05-test-coverage.md) | Low | Large | Anytime |
| 06 | [Docs & onboarding](06-docs-onboarding.md) | Low | Medium | Anytime |
| 07 | [Low-risk core cleanup](07-core-cleanup.md) | Low | Small | Anytime |
| 08 | [Larger core refactors](08-core-refactors.md) | Med–High | Large | Last — needs owner sign-off |

Plans 01–03 are quick wins. Plan 02 contains decisions only the repo owner can make
(notably the Plotly-vs-plugin-system direction for PRs #830/#932); those steps are
clearly marked `OWNER DECISION`.

## Architecture plans (`plans/architecture/`)

Higher-level redesigns. These are written as architecture decision documents with
phased, independently-shippable migrations — read the proposal and decision sections
before executing any phase. **A3 is the keystone — read it first.**

| Doc | Subject | Resolves |
|-----|---------|----------|
| [A1 — Rendering backend unification](architecture/A1-rendering-backend-unification.md) | Plugin registry as the skeleton; Plotly renderers and the fast save path land as plugins; HoloViews deprecated gradually | The #830-vs-#932 conflict, the 17-class `BenchResult` MRO, 16s saves |
| [A2 — Plot selection redesign](architecture/A2-plot-selection-redesign.md) | Centralized, explainable, *ranked* selection; serializable plot specs instead of callables | Render-everything noise, scattered match logic, unpicklable `plot_callbacks` |
| [A3 — BenchData contract](architecture/A3-benchdata-contract.md) | One frozen, pickle-free data type (netCDF + JSON manifest) used by rendering, the collect/render split, result cache, and history | Pickled god-object at four boundaries; load-time code execution |
| [A4 — Caching architecture](architecture/A4-caching-architecture.md) | One storage interface (absorbs PR #760), one key module, worker source-code hashing, artifact manifests, netCDF history (absorbs PR #799) | Stale-results footgun, media orphans, pickle CVE class, scattered key logic |

Sequencing: A1 Phase 0–1 and A4 Phase C1–C2 can start immediately; A3 Phase D2 gates
A4 Phase C4 and A1's split-render convergence; A2's ranking phases come last.

## State of the repo (review summary, 2026-06-11)

### What is good

- **Sophisticated, intentional architecture**: the collect/render split (`bencher/render.py`)
  isolates C-extension state and is guarded by a three-layer test defense (parity tests,
  per-result-type round-trips, and a full `BENCHER_FORCE_SPLIT_RENDER=1` CI job).
- **Strong test suite**: ~79 test files / ~1,479 tests / ~90% line coverage, including
  hypothesis property-based tests and a disciplined `hash_persistent()` determinism contract.
- **Good composition in the core**: `Bench` delegates to `WorkerManager`, `SweepExecutor`,
  `ResultCollector`; no circular imports; clean `__getattr__`-based deprecation aliases.
- **Healthy process**: maintained CHANGELOG, dual-Python CI matrix, pre-commit hooks,
  codespell, shellcheck, RTD builds per PR, ~209 auto-generated gallery examples.

### What needs improvement

- **Release safety**: PyPI auto-publish is NOT gated on CI passing (plan 01).
- **PR backlog**: 10 open PRs, several stale or mutually conflicting — especially
  #830 (Plotly port) vs #932 (plugin system), and #760 (diskcache CVE fix) is unmerged (plan 02).
- **Repo clutter**: stale root-level plan files (PLAN.md, PROMPT.md, RENAME_PLAN.md, ...),
  dead `setup.py`/`setup.cfg`/`MANIFEST.in` (plan 03).
- **Dependencies**: vulnerable `diskcache<=5.6.3` (CVE-2025-69872), `numpy>=1.0` floor,
  no core/viz extras split, heavy eager imports (panel/optuna/xarray) (plan 04).
- **Test gaps**: ~27 modules under `bencher/results/` have no direct unit tests;
  no coverage threshold; a few sleeps/skips (plans 01, 05).
- **Onboarding**: README doesn't sell the project or link the gallery; caching and
  over_time docs are scattered; some public classes lack docstrings (plan 06).
- **Core debt**: `bencher.py` 1,516 lines / 46 methods, `bench_cfg.py` 1,060 lines /
  100+ params, `regression.py` mixes detection + rendering, dead commented-out code
  (plans 07, 08).
