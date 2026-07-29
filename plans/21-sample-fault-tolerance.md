# Plan 21 — Per-Sample Fault Tolerance in Sweeps

**Goal:** Stop one failing sample from discarding an entire sweep, and make
failed samples visible in the result. `Bench.optimize()` already has the knob for
this; `plot_sweep()` does not, so the same benchmark is fault-tolerant when driven
by Optuna and all-or-nothing when swept.

**Branch name:** `feat/sweep-catch-sample-errors`

**⚠️ Read first:** the default must stay fail-fast. This plan adds an opt-in, and
the opt-in is only safe if a caught sample is kept out of the sample cache — see
D4 and the precedent in PR #962.

---

## Problem statement (with evidence)

### P1 — One raising sample aborts the whole sweep

The exception propagates unhandled: `store_results` calls `job_result.result()`
(`bencher/result_collector.py:334`), which re-raises whatever the future holds
(`bencher/job.py:119`), and nothing between the worker and `bn.run` catches it —
`_execute_bench_fn` invokes the benchmark function bare
(`bencher/bench_runner.py:276-286`).

Verified on v1.116.0: a `ParametrizedSweep` whose `__call__` raises
`RuntimeError` propagates straight out of `bn.run`. Every sample already
collected in that sweep is lost — no dataset, no report, no history entry, and
nothing written for the samples that did succeed.

For a sweep whose samples are individually expensive, this is the difference
between losing one measurement and losing an entire run.

### P2 — The optimize path already solved this

`Bench.optimize(catch=...)` exists precisely so that one bad trial does not kill a
study (`bencher/bencher.py:1152`, forwarded to Optuna at `:1273`), with the
default `()` preserving fail-fast. `to_optimize()` forwards it through `**kwargs`.

So bencher already holds the position that a long, expensive run should be able to
tolerate an individual sample failure — it just holds it for one of the two ways
of driving a benchmark. The sweep path, which is the common one, has no equivalent
spelling.

### P3 — The dataset can already represent a failed sample; nothing produces one

The pieces are in place. Result variables have a missing-value fill
(`result_missing_fill`, imported by `bencher/history.py:52`), and the history layer
already distinguishes "did not exist yet" from "was not recorded" using each
column's birth coordinate (`bencher/history.py:1-35`), with regression gating that
holds fire while a baseline is young.

So a caught sample has a well-defined representation: fill every result variable
with the missing sentinel at that coordinate. No new data model is needed.

### P4 — And the converse: a failed run must not look clean

Tolerance without accounting is worse than fail-fast. Today nothing anywhere
counts failed samples: `BenchResult` has no failure list, the report has no
failure summary, and `bn.run` returns `list[BenchCfg]`
(`bencher/run.py:67`) with no signal. If `catch=` were added without D3, a run in
which *every* sample failed would produce an all-NaN dataset, a valid-looking
report, a fresh history entry, and a successful exit — the worst possible outcome
for an unattended or scheduled run.

---

## Proposed design

### D1 — `catch=` on the sweep path, spelled as on `optimize()`

`plot_sweep(catch: tuple[type[Exception], ...] = ())`, threaded to the sampling
loop and honored in both executor paths (`bencher/bencher.py:1015-1029`), plus the
same argument on `bn.run` for callers who never touch `plot_sweep` directly.
Default `()` — identical behavior to today. Reuse the exact name, type, and
default from `optimize()` so the two paths read the same.

### D2 — What a caught sample records

- Every result variable at that coordinate gets the missing-value fill (P3), so
  the dataset shape is unchanged and downstream consumers need no special case.
- The exception is recorded: sample index, the input values, the exception
  `repr`, and the formatted traceback.
- It is logged at WARNING with the input values, so a tolerated failure is visible
  in the run log rather than only in the artifact.

### D3 — Accounting, which is not optional

- `BenchResult.failed_samples: list[SampleFailure]` and `n_failed`.
- A report section listing failures when `n_failed > 0`, placed where it cannot be
  missed rather than at the bottom.
- The count in the exported result JSON — plan 10's verdict export is the natural
  carrier, so coordinate the field name with it rather than inventing a parallel
  artifact.
- `fail_on_sample_error: bool | float = False` on `bn.run`: `True` raises if any
  sample failed; a float in `(0, 1]` raises if the failed *fraction* meets or
  exceeds it. This is what makes `catch=` safe to use unattended — tolerate a
  flake, fail the run if the flakes are the story.

The raise happens **after** the dataset and report are assembled, so the partial
results are still on disk when it fires. Losing the artifact would defeat the
purpose of catching in the first place.

### D4 — A caught sample must not be cached

`JobFuture.result()` writes to the cache after retrieving a result
(`bencher/job.py:119-122`). A failed sample must commit nothing, or the failure
becomes permanent for every later run with the same key — turning a transient
flake into a poisoned cache entry. PR #962 established this behavior for the
optimize path; verify it holds for both the serial and the process-pool paths and
add a test that pins it.

### D5 — History interaction

A tolerated failure writes the missing sentinel, which is indistinguishable in the
stored dataset from "not recorded". That is acceptable — it is already the
sentinel's meaning — but regression detection must not read a filled failure as a
measured improvement or regression. Confirm the existing gating treats the fill as
absent, and add a test at the boundary; if it does not, that is a bug this plan
must fix, not defer.

---

## Phased steps

1. `catch=` plumbed through the sampling loop for both executor paths, with the
   fill behavior (D1, D2). Default unchanged.
2. The no-cache-on-failure guarantee and its test (D4). Ship before advertising
   `catch=`.
3. Accounting: `failed_samples`, `n_failed`, the report section (D3).
4. `fail_on_sample_error` on `bn.run`, and the result-JSON field (coordinate with
   plan 10).
5. History/regression boundary check (D5), docs, `CHANGELOG.md`.

Phases 1–2 are one reviewable unit; do not release `catch=` without phase 2.

## Tests / acceptance criteria

- Default behavior is byte-identical to today: an uncaught exception propagates
  out of `bn.run` (the P1 case, pinned as a regression test).
- With `catch=(RuntimeError,)` and one raising sample out of N: the sweep
  completes, the dataset has N coordinates, the failed one carries the missing
  fill, `n_failed == 1`, and the successful samples' values are correct.
- An exception type *not* listed in `catch` still aborts the sweep.
- **No cache entry** is written for a caught sample: a second run with the same
  key re-executes it. Assert for the serial and the process-pool executor
  separately — they take different paths at `bencher/bencher.py:1015-1029`.
- `fail_on_sample_error=True` raises after the report is written; the report file
  exists and contains the failure section.
- `fail_on_sample_error=0.5` with 1 of 4 failed does not raise; with 2 of 4 it
  does.
- All-samples-failed with `catch=` and no `fail_on_sample_error`: run succeeds
  (documented), `n_failed == N`, and the report leads with the failure section —
  the guard against P4's silent success.
- Regression detection over a history containing a filled failure treats it as
  absent (D5).

## Migration & compatibility

Fully backward compatible: every new argument defaults to today's behavior. The
only unconditional change is the report gaining a section that is empty unless
failures occurred.

## Risks

- **Turning real breakage into a warning.** A user who sets
  `catch=(Exception,)` and ignores `n_failed` gets a green run over garbage. This
  is why D3 is part of the same plan and why the docs must present `catch=` and
  `fail_on_sample_error` as a pair, not as independent knobs.
- **Cache poisoning** (D4) — the highest-severity risk, since a cached failure is
  durable and silent. Phase 2 gates the feature for that reason.
- **Partial datasets reaching history.** A sweep that completes with failures
  appends a history event containing filled columns. Acceptable given the
  sentinel's existing meaning, but D5 must confirm the regression path agrees.
- **Non-exception failures.** A worker that segfaults or is killed takes the
  process with it; `catch=` cannot help, and the docs should say so rather than
  implying general robustness.

## Coordination

- **PR #962** — the `catch=` precedent on `optimize()`, including the
  no-cache-on-failure behavior. Match its spelling exactly.
- **Plan 10** — owns the result-JSON verdict export; `n_failed` belongs there
  rather than in a new artifact.
- **Plan 11** — worker lifecycle hooks; a `teardown_sample` hook must still run
  for a caught sample, or a tolerated failure leaks resources.
- **Plans 09/14** — the history and regression boundary in D5.
