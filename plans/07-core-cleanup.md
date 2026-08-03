# Plan 07 — Low-Risk Core Cleanup

**Goal:** Mechanical, behavior-preserving cleanups in `bencher/`: delete dead code,
narrow exception handlers at internal boundaries, replace stray prints with logging.
Every task must leave `pixi run ci` green; none changes public API.

**Branch name:** `chore/core-cleanup`
**One commit per task.** If any step's "verify" fails, revert that task and report.

---

## Task 1: Delete commented-out dead code

Known locations (re-verify line numbers before editing — they drift):

1. `bencher/bencher.py` — a fully commented-out `show()` method (~lines 821–843 region).
   Delete the whole commented block.
2. `bencher/results/bench_result_base.py` — commented assignments
   (`# self.width`, `# self.height`, `# bench_res.reference_index`, ~lines 113–117).
3. `bencher/variables/parametrised_sweep.py` — commented hash-debug lines (~46–47).
4. `bencher/results/video_summary.py` — commented print (~line 207).

Sweep for more: `grep -rn "^\s*# *def \|^\s*# *self\." bencher/ --include="*.py" | grep -v example` —
delete only blocks that are clearly disabled code (not explanatory comments). When in
doubt, leave it.

Verify: `pixi run ci`.

## Task 2: Replace print with logging in library code

**DONE/moot (2026-07-06):** the print — which lived in `to_auto()`, not `to_pane()` —
was removed by the plugin-registry rewrite (commit 95d1ebf); render failures now go
through `logging.error`. If new prints appear, the rule stands: replace with logging,
but do NOT touch prints in CLI entry points
(`bencher/render.py` main path), `bencher/plotting/file_server.py` startup messages, or
example files — those are intentional user-facing output.

Verify: `pixi run pytest test/test_render.py -q && pixi run ci`.

## Task 3: Narrow the broad exception handler in optuna_conversions

In `bencher/optuna_conversions.py`, `_append_safe` (~lines 170–190) catches bare
`Exception`. Change it to catch `(RuntimeError, ValueError, TypeError, AttributeError)`
for the "render an error pane" path, and keep a final `except Exception` that logs at
`logging.error` level *and still appends the error pane* (do not re-raise — this runs
inside report building and a crash there loses the whole report). Keep the existing
`# pylint: disable=broad-except` on the final handler.

Verify: `pixi run pytest -q -k "optuna or optimize"` then `pixi run ci`.

## Task 4: Document BenchCfg parameter interactions

In `bencher/bench_cfg.py`, extend the `BenchCfg` class docstring with a short
"Parameter interactions" section covering the cache-flag combinations and
over_time/max_time_events eviction. **Derive each statement from the code** (read the
flag usage in `bencher/job.py` / `bencher/result_collector.py`); if you cannot confirm a
behavior from code, leave it out.

Verify: `pixi run ci`.

## Task 5: Resolve trivially-resolvable TODOs

1. `bencher/__init__.py` warning-filter line for "Unable to import Axes3D": add a
   one-line comment above it explaining it silences a holoviews/matplotlib import-order
   warning irrelevant to bencher.
2. Grep all markers: `grep -rn "TODO\|FIXME\|HACK" bencher/ --include="*.py" | grep -v example`.
   For each, classify: (a) deletable (refers to already-done work — verify, then delete
   the comment), (b) real debt (leave the comment, add it to a list in your PR
   description), (c) needs a decision (list separately). Do not attempt to *implement*
   any TODO in this plan.

## Final verification

```bash
pixi run ci
pixi run test-split
```

PR description must include: the dead-code blocks removed, the TODO triage list from
task 5, and a statement that no public API changed.
