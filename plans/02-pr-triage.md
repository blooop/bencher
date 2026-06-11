# Plan 02 — Inflight PR Triage

**Goal:** Clear the backlog of 10 open PRs: merge what's ready, rebase what's salvageable,
close what's stale. Reviewed 2026-06-11; re-check each PR's state with
`gh pr view <N> --json state,mergeStateStatus,statusCheckRollup` before acting — anything
may have changed.

Use `gh` for all PR operations. Never force-push someone else's branch without checking
`gh pr view <N> --json author` first (all current PRs are by the repo owner, blooop).

---

## Step 0 — OWNER DECISION: Plotly port (#830) vs plugin system (#932)

These two draft/open PRs are architecturally incompatible:

- **#830** "Port visualizations from HoloViews/Panel to Plotly" removes the HoloViews
  rendering stack entirely (claims ~100x faster `report.save()`: 16s → 0.13s).
- **#932** "Plot plugin infrastructure (tier 0, additive)" builds a plugin registry **on
  top of** the existing HoloViews infrastructure.

Only one direction can proceed. **Ask the owner to choose:**

- **Option A (Plotly-first):** revive #830, then redesign #932's plugin protocol to emit
  Plotly figures. Closes the save-performance problem directly.
- **Option B (Plugin-first):** close #830, merge #932, and add Plotly later as a plugin
  backend. Lower risk, slower path to the performance win.

Do not merge or close either PR until the owner answers. Everything below can proceed
independently of this decision.

## Step 1 — #953 "Centralise result-variable missing-value representation": rebase & merge

- Its prerequisite (#952, NaN default flip) is already merged to main.
- Action: `gh pr checkout 953`, then `git merge origin/main` and resolve conflicts
  (expected to be small — the PR adds `result_missing_fill()` / `result_is_missing()`
  helpers that touch the same files as #952).
- Run `pixi run ci`. If green, push and merge the PR (squash).

## Step 2 — #760 "Replace diskcache with minimalkv (CVE-2025-69872)": fix CI & merge

This is a **security fix** — the pinned `diskcache<=5.6.3` is vulnerable to a pickle
deserialization CVE. Highest-priority merge after #953.

1. `gh pr checkout 760`, `git merge origin/main`, resolve conflicts.
2. Reproduce the CI failure locally: `pixi run ci`. The author reported all tests pass
   locally, so the failure is likely environment/lock-file drift — check whether
   `minimalkv` was added to `pyproject.toml` dependencies AND the pixi lock
   (`pixi list | grep minimalkv`). If the lock is stale, run `pixi install` to update
   `pixi.lock` and commit it.
3. Note the breaking change for users: existing `cachedir/` contents are incompatible.
   Make sure CHANGELOG.md has an entry telling users to delete their cache dir, and that
   the version bump is at least a minor bump.
4. Merge when CI is green.

## Step 3 — #850 "single scrollbar for RTD example pages": re-run checks & merge

- Only the `benchmark` check failed, on a JS/CSS-only change — likely transient.
- Action: `gh pr checkout 850`, merge main into it, push (this re-triggers CI).
- If all checks pass, merge. If `benchmark` fails again, read the failing log with
  `gh run view <run-id> --log-failed` and report findings instead of merging.

## Step 4 — #941 "bencher.ci module for CI regression gating" (draft): finish or park

1. `gh pr checkout 941`, merge main, run `pixi run format && pixi run lint` — the prek
   failure is a formatting/lint issue; fix what it reports.
2. **Restore removed exports**: the PR removed `render_report`, `save_result`, and others
   from `bencher/__init__.py`. Re-add them (imports from `.render`) so the PR is purely
   additive. The existing deprecation-alias mechanism (`__getattr__` at the bottom of
   `bencher/__init__.py`) is the pattern to use if any rename is truly intended.
3. Run `pixi run ci`. Push. Leave it as a draft for the owner to review — do not merge
   a draft without owner approval.

## Step 5 — #799 "netCDF-backed history_dir": diagnose RTD failure

1. Core CI is green; only the ReadTheDocs build failed, and the PR is ~3 months old.
2. `gh pr checkout 799`, merge main, push — this triggers a fresh RTD build.
3. If RTD passes now, mark ready and request owner review. If it fails, fetch the build
   log from the RTD link in `gh pr checks 799` output and report the first error.

## Step 6 — #908 "Fully auto-generate rerun examples": fix or recommend closing

1. `gh pr checkout 908`, merge main, `pixi run ci`.
2. The failure mode involves `inspect.getsource()` inlining of `ControlSystemSweep`.
   If the fix is not obvious within a reasonable effort (a few focused attempts),
   comment on the PR summarizing the failure and recommend closing; the idea can be
   re-done on top of current main more cheaply than rebasing 2 months of drift.

## Step 7 — #253 "Feature/dimension grid": close as stale

- Open since November 2023, no description, no CI runs.
- Action: `gh pr close 253 --comment "Closing as stale (open since 2023, no CI history). The branch is preserved; reopen if still relevant."`

## Step 8 — #923 "Plan to re-split bench_cfg.py": fold into plans/

- This PR only adds a planning document for splitting `BenchRunCfg` into nested
  sub-configs. That work is now tracked in `plans/08-core-refactors.md` of this repo.
- Action: ask the owner whether to merge it as documentation or close it with a comment
  pointing at `plans/08-core-refactors.md`. `OWNER DECISION` — default recommendation: close.

## Reporting

After executing, post (or print) a summary table: PR → action taken → resulting state,
plus the two owner decisions still pending (#830/#932 direction, #923 disposition).
