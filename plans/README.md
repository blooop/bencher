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
7. **Cite code as `file:line` and name the symbol there.** The symbol is the durable
   reference; the line number is a convenience pinned to the commit the plan was written
   against, so it goes stale — confirm each citation against the current tree before relying
   on it. If a plan's evidence no longer matches the code, say so in the PR rather than
   silently working around it: a moved line is harmless, but a claim that no longer holds may
   invalidate the plan's reasoning. When writing a plan, state the commit or version its
   citations were taken against.

## Plan index and recommended order

| # | Plan | Risk | Effort | Do first? |
|---|------|------|--------|-----------|
| 01 | [Release & CI safety](01-release-safety.md) | Low | Small | **DONE** — executed verbatim in PR #982 |
| 02 | [Inflight PR triage](02-pr-triage.md) | Low–Med | Medium | Partially done — see status note in the plan |
| 03 | [Repo hygiene](03-repo-hygiene.md) | Low | Small | Yes |
| 04 | [Dependencies & import time](04-dependencies.md) | Medium | Medium | After 02 (depends on PR #760 decision) |
| 05 | [Test coverage gaps](05-test-coverage.md) | Low | Large | **Mostly done** — see status note in the plan |
| 06 | [Docs & onboarding](06-docs-onboarding.md) | Low | Medium | Anytime |
| 07 | [Low-risk core cleanup](07-core-cleanup.md) | Low | Small | Anytime |
| 08 | [Larger core refactors](08-core-refactors.md) | Med–High | Large | Last — needs owner sign-off |
| 09 | [Cache & history invalidation correctness](09-result-cache-invalidation.md) | Medium | Medium | **Implemented** (with 14, v1.116.0) |
| 10 | [Regression policy on result vars & verdict export](10-regression-policy-and-verdict-export.md) | Low–Med | Medium | After 02; builds on #974 |
| 11 | [Worker lifecycle & resource injection](11-worker-lifecycle-and-resource-injection.md) | Medium | Medium–Large | Coordinate with A3/A4 |
| 12 | [Portable artifact paths & cache config](12-portable-artifact-paths-and-cache-config.md) | Low | Small–Medium | Precursor to A3/A4 |
| 13 | [Benchmark declaration bundle & run defaults](13-benchmark-declaration-and-run-defaults.md) | Low | Medium | Coordinate with 09 |
| 14 | [Schema-evolving over_time history](14-history-schema-reconciliation.md) | — | — | **Implemented** (design record, v1.116.0) |
| 15 | [Stable benchmark series identity](15-benchmark-series-identity.md) | Medium | Medium | **Implemented** in #1012 (stack 3/5) |
| 16 | [Inspectable, pinnable benchmark identity](16-inspectable-benchmark-identity.md) | Low | Small | **Implemented** in #1010 (stack 1/5) |
| 17 | [Single-point sweep ranges](17-single-point-sweep-ranges.md) | Low | Small | **Implemented** in the plan PR |
| 18 | [Reusable sweep declarations](18-reusable-sweep-declarations.md) | Low–Med | Medium | **Implemented** in #1014 (stack 5/5) |
| 19 | [Reject unnamed parameters](19-unnamed-parameter-detection.md) | Low | Small | **Implemented** in the plan PR |
| 20 | [Duplicate declared variables](20-duplicate-declared-variables.md) | Low–Med | Small | **Implemented** in #1011 (stack 2/5) |
| 21 | [Per-sample fault tolerance in sweeps](21-sample-fault-tolerance.md) | Medium | Medium | **Implemented** in #1013 (stack 4/5) |

Plans 01–03 are quick wins (01 is done). Plan 02's headline owner decision — the
Plotly-vs-plugin-system direction for PRs #830/#932 — was resolved plugin-first on
2026-07-01 (see the A1 addendum); its remaining steps are still live and the other
`OWNER DECISION` markers still apply.

Plans 15–21 came out of an audit of how a large external project drives bencher,
and of the workarounds it had accumulated; all seven cite code as of `main` @
`7dad0cd4` (v1.116.0). Three of them (17, 19, 20) are small correctness fixes
worth doing first; 15 and 16 concern benchmark *identity* and build directly on
the landed 09/14; 18 complements 13's declaration bundle; 21 extends
`optimize()`'s existing `catch=` to the sweep path.

## Architecture plans (`plans/architecture/`)

Higher-level redesigns. These are written as architecture decision documents with
phased, independently-shippable migrations — read the proposal and decision sections
before executing any phase. **A3 is the keystone — read it first.**

| Doc | Subject | Resolves |
|-----|---------|----------|
| [A1 — Rendering backend unification](architecture/A1-rendering-backend-unification.md) | Plugin registry as the skeleton (Phases 0, 2, and 3 landed); backends swap under stable plot names; the Plotly port and fast-save path were dropped per owner decision — see the addendum | The #830-vs-#932 conflict (resolved plugin-first), the 17-class `BenchResult` MRO |
| [A2 — Plot selection redesign](architecture/A2-plot-selection-redesign.md) | Centralized, explainable, *ranked* selection (S1 signature enrichment landed via PR #983; S2's `explain_selection()` shipped in v1.115.0); serializable plot specs instead of callables | Render-everything noise, scattered match logic, unpicklable `plot_callbacks` |
| [A3 — BenchData contract](architecture/A3-benchdata-contract.md) | One frozen, pickle-free data type (netCDF + JSON manifest) used by rendering, the collect/render split, result cache, and history | Pickled god-object at four boundaries; load-time code execution |
| [A4 — Caching architecture](architecture/A4-caching-architecture.md) | One storage interface (absorbs PR #760), one key module, worker source-code hashing, artifact manifests, netCDF history (absorbs PR #799) | Stale-results footgun, media orphans, pickle CVE class, scattered key logic |

Sequencing: A1 Phases 0, 2, and 3 have landed (#932, #970, #973/v1.114.0; Phase 1 is
dropped — see the A1 addendum); A4 Phase C1–C2 can start immediately; A3 Phase D2
gates A4 Phase C4; A2's ranking phases (S3–S4) come last.

## State of the repo (review summary, 2026-06-11)

> **Update (2026-07-06):** the snapshot below is preserved as written. Since then:
> plan 01 executed (PR #982); most of plan 05 executed (all listed result modules now
> have dedicated tests; the suite is now ~101 files / ~1,500 tests); #830 closed while
> #932, #953, and #850 merged (7 PRs remain open, including the #760 CVE fix); A1
> Phases 0 and 2 landed.
>
> **Update (2026-07-11):** A1 Phase 3 landed (#973, v1.114.0); A2 Phase S2's
> `explain_selection()` shipped in v1.115.0 and Phase S1 is in review as PR #983;
> plans 09 and 14 were implemented in v1.116.0 (cache re-key, `CACHE_VERSION` 5),
> so A4 §1's cache-layer table now describes the post-1.116 key split.

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
