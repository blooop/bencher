# Plan 23 — Constructive Data Modeling & Type Enforcement

**Goal:** Make illegal states unrepresentable in bencher's *internal* types — sum types
instead of tag-plus-parallel-fields, no sentinel values, exhaustive matching — and turn
the existing `ty` type-check gate from a de-facto no-op into a real, monotonically
tightening enforcement mechanism. Fix the live bugs the audit found along the way.

**Branch names:** one `plan/constructive-*` branch per phase (each phase is one PR).

**Citations pinned to:** `main` @ `4a13ab8e` (post plan 22 / PR #1021, 2026-07-31).
Per plans-README rule 7, confirm each `file:line` against the current tree before
relying on it; the symbol is the durable reference.

**⚠️ Amended by [plan 24](24-assert-never-boundary-discipline.md).** D2's `assert_never`
guarantee holds only where `ty` can establish the match subject's type, which it cannot
for `param`-descriptor reads (`pyproject.toml:281` documents them as `Unknown`) — and no
type checker, nor D1's strict-list ratchet, closes that gap. Plan 24 adds the missing
boundary-normalization precondition (D2 category three), scopes it to **P2** (`executor`)
and **P11** (`agg_fn`), and re-affirms §1's "`ty` only" non-goal with measurements. Read
plan 24 §3 before executing P1, P2 or P11.

**⚠️ Read first:** §1 Scope. Config-surface findings (regression method/thresholds,
`fail_on_sample_error`, `show`, `plot_size`, subsampling knobs) are **out of scope** —
they belong to A5's breaking-release train and are recorded here only as amendments
(§8). Do not refactor `BenchRunCfg`/`BenchCfg` fields in this plan.

**Note on provenance:** the audit behind this plan was first run against `e6b7d707`.
Plan 22 landed in between and **fixed one finding outright** (the `ResultDataSet`
missing-sentinel bug, §3.1 — the B-series was renumbered after dropping it) and
**changed the missing-value scheme** that D3 depends on. Every citation below has been
re-verified against `4a13ab8e`. Where plan 22 already solved something, this plan says
so rather than proposing it again.

---

## 1. Scope and non-goals

In scope:
- **Enforcement infrastructure** — tighten `[tool.ty.rules]`, add `assert_never`
  discipline, add tests that keep the gate honest.
- **Internal sum types** — types no external caller constructs directly: `JobFuture`,
  `VarRange`, `HistoryEvent`, `ComposeType` matching, `WorkerManager` state, the
  result-type classification tuples.
- **Live bug fixes** — defects that ship wrong behavior today (§3, B1–B5).

Out of scope (recorded as amendments in §8, do not implement here):
- Public config-surface sum types → **A5** (`plans/architecture/A5-config-surface-reduction.md`).
- `BenchResult` two-phase init / indistinguishable dry-run result → **A3**.
- The residual `dataset_list` / `object_index` dual read path → **plan 22 phase 3**.
- Switching or adding type checkers. Owner decision: **`ty` only** — already wired in,
  listed directly in the `ci` task (`pyproject.toml:170`; the `ty` and `lint` task
  definitions are at `:149-150`, and `lint` itself is reached via `style`/`ci-no-cover`,
  not by `ci`).

## 2. Measured facts (verified 2026-07-31 against `4a13ab8e`; do not re-litigate)

1. **The current gate is close to a no-op.** `[tool.ty.rules]`
   (`pyproject.toml:246-285`, running to EOF) sets **21** rules to `"ignore"`.
   `pixi run ty` passes trivially. Measured per-rule cost (whole tree, env resolved):

   | Tier | Rules | Errors |
   |---|---|---|
   | **A** — enable now | `call-non-callable` (6), `call-top-callable` (1), `inconsistent-mro` (0), `invalid-method-override` (2), `invalid-parameter-default` (1), `missing-argument` (1), `too-many-positional-arguments` (1), `unresolved-import` (5), `unresolved-reference` (0) | 17 |
   | **B** — ratchet in P12 | `invalid-return-type` (32), `not-iterable` (43), `possibly-missing-attribute` (16), `no-matching-overload` (21), `unsupported-operator` (14) | 126 |
   | **C** — strict-list only | `invalid-argument-type` (545), `unresolved-attribute` (256), `invalid-assignment` (110), `not-subscriptable` (79), `invalid-type-form` (78) | ~1068 |
   | **keep ignored by design** | `unused-ignore-comment`, `unused-type-ignore-comment` | — |

   9 + 5 + 5 + 2 = 21. Counts measured with
   `ty check --error <rule> --python .pixi/envs/default .` at `4a13ab8e`; they drift as
   code lands, so re-measure rather than trusting them to the digit. Tier C is dominated
   by `param` descriptor magic and by `test/` (315 of the 545 `invalid-argument-type`
   errors are in `test/`). The two `unused-*-ignore-comment` rules are ignored
   **deliberately** — the repo keeps 8 `# type: ignore` comments for other type checkers
   (`bencher/run.py:53`, six in `bencher/variables/inputs.py`, one in
   `test/test_plugins.py`; rationale comment at `pyproject.toml:283`). Do not "fix" them.
   The 5 `unresolved-import` errors are real: `playwright.sync_api`
   (`bencher/example/meta/generate_examples.py:330,877`,
   `test/test_docs_scrollbars.py:28`), `scoop` (`job.py:18`), `setuptools`
   (`setup.py`, dead per plan 03).

2. **ty 0.0.56** (resolved from the pin `ty>=0.0.13,<=0.0.64`, `pyproject.toml:80`)
   supports `[[tool.ty.overrides]]` blocks with `include=` globs that relax or
   re-enable rules per path. Verified in a scratch project. No checker change needed.

3. **Exhaustiveness enforcement — `assert_never` comes from the stdlib.** ty derives its
   target Python version from `requires-python`, which is now `>=3.11,<3.14`
   (`pyproject.toml:10`), so `from typing import assert_never` resolves and
   `error[type-assertion-failure]: Argument does not have asserted type 'Never'` fires on
   an incomplete match, with a clean pass on a complete one. Verified with stdlib `Enum`,
   the third-party `strenum.StrEnum` the repo uses, and frozen-dataclass unions.

   **History, because it explains why the floor moved.** This plan was originally written
   against a `>=3.10` floor, where the same probes measured:

   | Import form (py310 target) | Result |
   |---|---|
   | `from typing_extensions import assert_never` | ✅ works |
   | `from typing import assert_never` | ❌ `unresolved-import` — it is 3.11+ |
   | `TYPE_CHECKING`-guarded import with a runtime `def` fallback | ❌ **silently degrades** to `invalid-return-type` |

   That made a `typing_extensions` dependency unavoidable and put this plan in conflict
   with the repo's existing decision against one. **Raising the floor to 3.11 dissolved
   that conflict** — hence the floor change landed first, as a prerequisite. Retained here
   so nobody reintroduces the dependency thinking it is still required.

4. **`type-assertion-failure` is not in the ignore list**, so the discipline is enforced
   with no rules-config change. Note the degraded-fallback signal
   (`invalid-return-type`) *is* currently ignored — a second reason to land Tier B.

5. **Two 3.10-era workarounds are now removable** (both are P1 cleanups, not new work):
   - `bencher/result_collector.py:242-243` declines a `typing_extensions` dependency so
     that `__enter__` can avoid `typing.Self`. `Self` is stdlib at 3.11 — delete the
     comment, annotate `-> Self`, drop the `# noqa: PYI034`.
   - `strenum` (`>=0.4.0`) exists only because `enum.StrEnum` is 3.11+. Migration is now
     possible but is **explicitly not part of this plan** — see the hazard in D4.

## 3. Problem statement (with evidence)

### The gate enforces nothing

Every annotation in the repo is currently documentation: the 21 ignored rules include
`invalid-return-type`, `unresolved-reference`, `missing-argument`, and
`inconsistent-mro`. There are **zero** uses of `assert_never`; all 3 non-example
`case _:` arms defer partiality to runtime (`bench_result_base.py:353`,
`composable_container_base.py:25`, `composable_container_video.py:158`). Adding a new
enum member or `Result*` type breaks nothing at check time — every "silently" below is
literal.

### 3.1 Already fixed by plan 22 — do not re-propose

The original audit's most severe rendering finding was that `ds_to_container` indexed
`self.dataset_list[val]` where the `ResultDataSet` missing sentinel was `-1`, a valid
Python index, so a never-recorded sample silently rendered the **last** recorded
sample's payload. **Plan 22 fixed this.** `_dataset_sample_to_container`
(`bencher/results/bench_result_base.py:1173-1268`) now checks `result_is_missing`
first (`:1200`), and the legacy-int path is bounds-guarded by
`if not dataset_list or not 0 <= idx < len(dataset_list)` (`:1251`) → a labelled
Markdown placeholder. Plan 22 also added a guard this plan's author did not anticipate:
`legacy_trusted` (`:1105-1109`, `:1238-1245`) renders a placeholder for a legacy int at
a non-final `over_time` index rather than the final run's payload (plan 22 amendment
#2). New runs store blob-path strings; `-1` is now produced only for `ResultReference`.
Nothing to do here.

### Live bugs (B-series)

- **B1** `bencher/results/video_controls.py:30-35` — four button names (`:30`) are
  zipped (`:35`) with a two-element callback list (`:31`); `zip` truncates. Shipped
  behavior: "Pause Videos" is wired to `reset_vid` (which *unpauses*), and the Loop and
  Reset buttons are never created.
- **B2** `bencher/result_collector.py:463-471` — the `ResultVec` branch stores values
  only when `isinstance(result_value, (list, np.ndarray))` (`:465`) **and**
  `len(result_value) == rv.size` (`:466`); a wrong-length vector is **silently
  discarded**, leaving the NaN fill, indistinguishable from "never sampled". The
  sibling branch raises `TypeError` (`:473-474`) — this arm just lacks the `else`.
- **B3** `bencher/job.py:158-160` + `bencher/result_collector.py:424` — a worker
  returning `None` trips a bare `assert` on the SERIAL path (absent under `python -O`)
  but on MULTIPROCESSING/SCOOP passes the assert (the future is set), `result()`
  returns `None`, the entire `store_results` body is skipped by `if result is not
  None:` with no `else`, and the sweep completes green with an all-sentinel dataset and
  `n_failed == 0`. Same user error; loud or silent chosen by an unrelated config knob.
- **B4** `bencher/utils.py:477` — `publish_file` is declared `-> str` and documented to
  return a URL; the body ends at `:512` with `git("push", ...)` and returns `None`.
- **B5** `bencher/regression.py` — `RegressionResult.threshold` means percent,
  MAD-sigma, absolute delta, or an absolute limit depending on `method`, but the
  scorecard verdict `_verdict` (`bencher/report_export.py:189-191`, imported as
  `_core_verdict` at `bencher/scorecard/model.py:13`, called at `:82` where it also
  hardcodes `regressed=False`) compares `threshold` against `abs(change_percent)`
  regardless. **Scope this precisely:** `scorecard/model.py:77` already returns
  `"regressed"` straight from `reg["regressed"]` *before* reaching `_verdict`, and
  `_verdict`'s only threshold comparison is
  `if beneficial and abs(change_percent) >= threshold` (`report_export.py:205`). So
  regressions are still reported correctly; the unit mismatch corrupts only the
  **improved-vs-unchanged** distinction for non-percentage methods. Real, but narrower
  than "wrong verdicts".

### Nine hand-maintained result-type tuples (C1)

Adding one `Result*` class requires coordinated edits to nine registries, each with its
own failure mode, most silent:

| Registry | Location | Omission consequence |
|---|---|---|
| `PANEL_TYPES` | `variables/results.py:562` | `panel_cnt` undercounts → plot mis-selection (silent) |
| `SCALAR_RESULT_TYPES` | `variables/results.py:574` | dropped from every holoviews renderer (silent) |
| `XARRAY_MULTIDIM_RESULT_TYPES` | `variables/results.py:576` | `TypeError` far from cause |
| `ALL_RESULT_TYPES` | `variables/results.py:587` | classified as an **input** variable via the `else` at `parametrised_sweep.py:89` |
| `RESULT_KIND_ORDER` | `variables/results.py:604` | `result_kind()` returns `"unknown"` into the A2 signature (silent) |
| `_REFERENCE_MISSING_TYPES` | `variables/results.py:652` | wrong fill dtype → numpy cast error or silent corruption |
| `_OBJECT_MISSING_TYPES` | `variables/results.py:653` | as above |
| `DATA_VAR_RESULT_TYPES` | `variables/results.py:665` | derived from the three above; no dataset column → `KeyError` in `precompute_result_arrays` |
| `_MEDIA_RESULT_TYPES` | `result_collector.py:62` | media files leak on over_time aging (silent) |

Plan 22 added two more hand-maintained registries in adjacent domains —
`_NETCDF3_SAFE_DTYPES` (`blob_store.py:79`) and `_CONTENT_FOLDERS`
(`cache_management.py:65`). They are **not** result-type registries and are out of
scope; noted so a future reader does not mistake the count.

The repo already has the right enforcement mechanism for this shape:
`_discover_all_result_classes` (`test/test_hash_persistent.py:45`) auto-discovers
`Result*` classes and fails CI on an uncovered hash slot, and
`TestEveryResultTypeIsStorable` (`test/test_result_missing.py:116-141`) already pins
"member of `ALL_RESULT_TYPES` ⇒ the collector store loop has a branch". Nothing
equivalent guards the other eight tuples.

### Internal sum-type defects (C-series)

- **C2** `bencher/job.py:122-178` — `JobFuture` holds `res`/`future` as two optionals
  validated by a bare `assert` (`:158-160`), then *mutates* `res` on the first
  `result()` call, so `future is not None` stops meaning "pending". Both-set and
  neither-set are representable; neither is meaningful.
- **C3** `bencher/plotting/plot_filter.py:13-49` — `VarRange.upper_bound` has three
  meanings: `-1` = match nothing (the default, `:16`), `None` = unbounded (`:39`,
  `:44`), `>= 0` = real bound. Two sentinels on one field, the highest-severity smell.
  The class docstring has already drifted (claims both bounds default to `-1`;
  `lower_bound` defaults to `0`). Cost already paid twice: `match_all()` (`:84`) and
  `anything` (`:90`, `VarRange(0, None)`) exist purely because `PlotFilter()` matches
  nothing, and `plugins/plugin.py:72-73` documents the same default as "silently
  hiding the plugin forever".
- **C4** `bencher/plotting/plt_cnt_cfg.py:38-39` — `vector_len` and `result_vars`
  (the latter already marked `# todo remove`) are **never assigned anywhere**, yet gate
  every plot via `PlotFilter.vector_len`/`result_vars`
  (`plot_filter.py:77-78`, both `VarRange(1, 1)`) read at `plot_filter.py:141-142`.
  Both always equal their default `1`, so those gates can never fail — including
  `surface_result.py`'s "exactly one scalar result" intent. Only
  `test/test_plugins.py:415` sets them, so the tests assert machinery production never
  exercises.
- **C5** `bencher/history.py:66-85` — `HistoryEvent.kind: str` (`:77`) whose 7 legal
  values live in a trailing comment (`:77-78`); `lossy` (`:82-85`) is membership in
  `_LOSSY_KINDS` (`:66`, only 4 of the 7 kinds), so a typo'd kind is silently
  non-lossy — defeating the `on_history_reset="error"` CI gate. `load_history_cache`
  (`result_collector.py`) accepts any policy string; unknown values silently mean
  "ignore".
- **C6** `composable_container_base.py:19-26` — `ComposeType.flip()` raises at
  `:25-26` on 2 of its 4 members, reachable via
  `compose_method_list_for_dims(first_compose_method=...)` exposed at
  `video_summary.py:156`. `composable_container_panel.py` matches `compose_method` with
  no `case _:` (a 5th member → `UnboundLocalError` three frames from the cause),
  creates `_tabs` only on the `sequence` arm, and lets `horizontal: bool | None`
  silently overwrite `compose_method`. `composable_container_rerun.py` keeps two tables
  (`_shares_one_view`, `_LAYOUT_CLASS_NAMES`) that must stay exactly complementary
  with nothing checking it.
- **C7** `bencher/worker_manager.py:68` — `worker_class_instance:
  ParametrizedSweep | type[ParametrizedSweep] | None` holds an instance, a class, or
  nothing, with the mode inferred from `worker is None`; three
  `RuntimeError("Worker class instance not set")` sites (`:174`, `:187`, `:200`) and
  two `# noqa: TRY004` contortions carry the invariant.
- **C8** `bencher/worker_job.py:41-44` — four fields default `None`, filled by
  `setup_hashes()`; nothing prevents caching under `job_key=None`.
- **C9** `bencher/bench_report.py:203-235` — `bench_results` (appended `:204`) and
  `pane` (appended `:235`) are parallel lists correlated by index; `append_tab`
  (`:231`) skips `None` panes, after which `append_to_result` (`:215-221`) resolves
  `self.bench_results.index(bench_res)` → `self.pane[idx]`. Once the lists desync, an
  `idx` that is still in range silently writes into a **different result's tab**; an
  out-of-range one hits the `except (ValueError, IndexError)` fallback. So the guard
  does fire in the trailing case (e.g. one result whose `plot()` returned `None`:
  `bench_results=[r1]`, `pane=[]`) but cannot catch the misroute, which is the
  dangerous case. Same for `prepend_to_result` (`:222-229`).
- **C10** `bencher/plugins/bench_data.py:50-62` — capability dispatch on raw strings
  (`if capability ==` at `:54`, `:56`, …) with a `return False` fallthrough, consumed by
  `registry.py:241`. A misspelled capability in a plugin's `requires` (a hypothetical
  `frozenset({"legacy_resutl"})` — **no such typo exists in the tree today**; the real
  sites at `plugins/builtins.py:161,174` are spelled correctly) would yield a plugin
  that is permanently, silently never selected, indistinguishable from one whose
  capability is genuinely absent. This is a latent footgun on a public extension point,
  not a shipped defect. Note also that `bench_data.py:53`'s docstring misattributes
  `requires` to `PlotFilter`; it lives on `Plugin` (`plugin.py:25`).
- **C11** the aggregation-function vocabulary exists in **four** independent spellings:
  the `Literal`s (`results/bench_result.py:175`; `bench_result_base.py:203`, `:266`,
  `:712`), `AGG_FN_MAP` (`utils.py:385-391`), the `ObjectSelector`
  (`bench_cfg.py:820-824`), and the if/elif ladder (`bench_result_base.py:373-399`)
  which does **not** consult `AGG_FN_MAP` and whose terminal `else` (`:397-399`,
  commented `# Fall back to mean if unknown string provided`) silently means `mean` on
  an unknown string rather than raising — while `optimize()` raises on the same bad
  input (`bencher.py:1370-1372`).
- **C12** `bencher/results/rerun_result.py` — missing values rendered as real data:
  `float(val) if val is not None else 0.0` (`:323`) and
  `np.nan_to_num(arr, nan=0.0)` (`:337`) turn never-sampled points into plotted zeros;
  the isinstance ladder (`:352`, `:358`, `:364`) has a `# Default:` numeric
  fallthrough (`:370-371`) that a `ResultPath` reaches as `float("/path/to/x.csv")`, and
  four `except (KeyError, ValueError, TypeError)` handlers log at **DEBUG** (`:312`,
  `:325`, `:343`, `:375`) so the rerun report is silently incomplete. The single oracle
  `result_is_missing` (`variables/results.py:698`) exists and is not consulted here.
- **C13** `Executors` is compared four ways in three styles: `==` at
  `bencher/bencher.py:1180`, `!=` at `:1182`, `==` at `bencher/job.py:230`, and
  `is not` at `job.py:355`. **This is a latent smell, not a shipped bug** — an earlier
  draft of this plan claimed `BenchRunCfg(executor="serial")` diverged between the two
  branches; that was **false** and is corrected here per plans-README rule 7.
  `strenum.auto()` yields the *name*, so `Executors.SERIAL.value == "SERIAL"`;
  `executor="serial"` is rejected outright by `param.Selector`
  (`bench_cfg.py:241`) with `ValueError`, and even `executor="SERIAL"` behaves
  correctly because `Executors.factory("SERIAL")` returns `None` at `job.py:230` (it
  uses `==`), so `job.py:355-357` still falls to the serial path. Mixing `==` and `is`
  on a StrEnum is nonetheless a real hazard the moment a raw string reaches a site that
  uses `is` — normalize at the config boundary so it cannot become a bug later. No
  regression test is possible for C13; a test pinning "a raw-string executor resolves
  to the same branch everywhere" is the appropriate guard.

## 4. Proposed design

### D1 — Enforcement architecture: global-strict with two override blocks

Three layers in `pyproject.toml`, mechanism verified in §2.2:

1. **Global `[tool.ty.rules]`** — shrink the ignore list in two steps, per the §2.1
   tier table: **Tier A in P1** (~18 fixes), **Tier B in P12** (~126, fewer after
   P2–P11). **Tier C stays globally ignored**; the two `unused-*-ignore-comment` rules
   stay ignored permanently with their existing rationale comment preserved.
2. **Relaxed override block** — `include = ["test/**", "bencher/example/**",
   "docs/**", "setup.py", "scripts/**"]` keeping Tier B/C ignored there indefinitely.
3. **Strict override block (the ratchet)** — an explicit `include` file list where
   Tier C rules are `"error"`. Starts with the modules this plan refactors; **every
   subsequent phase adds its touched files to this list as part of its Definition of
   Done.** "Constructively modeled" is thereby coupled to "strictly checked", and the
   list only grows. `bench_cfg.py` (63 descriptor-noise errors) is the canonical file
   that never enters the list until A5 dismantles it.

### D2 — `assert_never` discipline

- Import `from typing import assert_never` — **stdlib, no new dependency.** This is the
  payoff of the 3.11 floor (§2.3); earlier revisions of this plan required
  `typing_extensions` and had to argue past the repo's decision against it. Both the
  dependency and that argument are now unnecessary. Do not reintroduce either.
- **Convention (applies to all future code):** every `match` over a closed enum or
  union ends in `case _ as unreachable: assert_never(unreachable)` — **unless** the
  match subject crosses a trust boundary (deserialized cache/user input), where a
  runtime `raise` is the correct price. `composable_container_video.py:158` is the
  named example of a correct boundary raise; keep it.
- Never add `type-assertion-failure` to the ignore list; P1's meta-test pins this.

### D3 — Result-type registry (replaces the nine tuples)

One ordered mapping in `bencher/variables/results.py`:

```python
@dataclass(frozen=True)
class ResultSpec:
    kind: ResultKind              # StrEnum, replaces RESULT_KIND_ORDER's implicit order
    missing_fill: Any             # np.nan | "NAN" | -1
    fill_dtype: type              # float | object | int
    missing_sentinels: frozenset  # values that mean "missing" on READ (see below)
    is_panel: bool
    is_media: bool
    is_data_var: bool
    multidim: bool                # XARRAY_MULTIDIM family
    reference_backed: bool        # object_index-backed (ResultReference only)

RESULT_SPECS: dict[type, ResultSpec] = {...}  # insertion order = isinstance-resolution order
```

**Post-plan-22 fills — get these right, they changed:**
- `_REFERENCE_MISSING_TYPES` is now **`(ResultReference,)` alone** (`results.py:652`);
  fill `(-1, int)`, still an `object_index` index.
- `ResultDataSet` **moved into `_OBJECT_MISSING_TYPES`** (`results.py:653-661`,
  `ResultDataSet` at `:660`); fill `("NAN", object)` — it stores a blob path now.
- Everything else (Float/Bool/Vec): `(nan, float)`.
- `missing_sentinels` is a **set**, not a single value, because missingness is no
  longer a pure function of the fill: `_dataset_cell_is_missing`
  (`results.py:678-696`) accepts `"NAN"`, `-1`, `-1.0`, NaN and `None` permanently, to
  read both cell generations. Model that as a per-spec frozenset, or keep the
  `ResultDataSet` branch as a documented exception — **do not collapse it**, it is
  dual-generation compatibility, not redundancy.

Other design points:
- All nine existing names become **derived values under their existing names** — zero
  call-site churn. `result_collector.py:62` imports instead of redeclaring.
- Why a central mapping rather than per-class declarations: the `Result*` classes share
  no common base (they subclass `param.Number`/`param.String`/`param.List`/... directly)
  and use `__slots__` with a hash-stability contract (`ruff.toml` RUF023 note), so
  per-class attributes would still need central discovery to produce *ordered*
  isinstance-tuples. The mapping lives exactly where the tuples live today.
- Subclass-before-base ordering matters for isinstance dispatch — add a test asserting
  no key precedes one of its own subclasses.
- `result_missing_fill` (`results.py:668-675`) and `result_is_missing` (`:698`) read
  from the spec; external behavior unchanged.
- **Completeness test — extend, do not duplicate.** Build on
  `TestEveryResultTypeIsStorable` (`test/test_result_missing.py:116-141`) and fold in
  the hand-written truth table `TestResultIsMissingTruthTable`
  (`test/test_grammar_data_model.py:468`) so it becomes registry-driven. Reuse
  `_discover_all_result_classes` (`test/test_hash_persistent.py:45`): every discovered
  `Result*` class must be a `RESULT_SPECS` key **or appear on an explicit, documented
  exemption list**. **Any test that instantiates every class must suppress
  `DeprecationWarning`** — both `ResultHmap` (`results.py:268-277`) and `ResultVar`
  (`:730-735`) emit one; the existing tests already do this via
  `warnings.catch_warnings()` (`test_hash_persistent.py:58-66`,
  `test_result_missing.py:39-44`).
- **Two deprecated classes need explicit handling — a naive completeness test fails on
  day one:**
  - `ResultHmap` is deprecated but still in `ALL_RESULT_TYPES` and `RESULT_KIND_ORDER`
    and still absent from `DATA_VAR_RESULT_TYPES`. The registry must reproduce that
    exactly, not "tidy" it.
  - `ResultVar` (`class ResultVar(ResultFloat)`, `results.py:727`) is deprecated and
    absent from **every** registry, yet `_discover_all_result_classes` finds it because
    it lives in `bencher.variables.results`. It therefore needs either a spec that
    mirrors `ResultFloat` or a place on the exemption list — decide in P4 and state
    which in the PR.
- Close the misclassification hole: the `else` arm at `parametrised_sweep.py:89` gains
  a guard — a parameter whose class is defined in `bencher.variables.results` but
  absent from the registry **raises** instead of becoming an input variable.

### D4 — Sum-type conventions (py311 + param constraints)

- Sum types = small frozen dataclasses joined by `|`, destructured with exhaustive
  `match` + `assert_never`. **No new dependencies at all** (§2.3).
- Closed string vocabularies = `strenum.StrEnum`, i.e. **keep using the existing
  package** for now, matching every enum already in the tree.
- **Do not opportunistically migrate `strenum` → stdlib `enum.StrEnum` as part of this
  plan.** The 3.11 floor makes it possible, but the two are *not* drop-in equivalents and
  the difference is silent:

  ```
  strenum.StrEnum + auto()  ->  member name verbatim   ('SERIAL')
  enum.StrEnum    + auto()  ->  lowercased name        ('serial')
  ```

  Measured across the seven StrEnums in `bencher/`: five have lowercase member names and
  are unaffected (`ComposeType`, `PaneLayout`, `RerunViewKind`, `OptDir`, `ShowMode`).
  **Two would silently change value** — `Executors` (`SERIAL`/`MULTIPROCESSING`/`SCOOP`)
  and `SampleOrder` (`INORDER`/`REVERSED`). Because `executor` is a
  `param.Selector(objects=list(Executors))` (`bench_cfg.py:241`), that flips which string
  callers may pass: `executor="SERIAL"` is valid today and would start raising. Verified
  *not* a cache-invalidation risk — neither enum feeds `hash_persistent`, and
  `sample_order` is in `EXCLUDED_FIELDS` (`identity.py:49`) — so this is a narrow public
  API break, not data corruption. If the migration is ever wanted, it belongs in its own
  PR that gives those two enums **explicit string values** rather than `auto()`, and it
  is A5's call whether the accepted-string change ships in a breaking release.
- Normalize enum-typed param fields at the config boundary so `==` vs `is` can never
  diverge (C13). Note plan 24 §2.2–2.3: a `match` on a raw `param`-descriptor read is
  *not* a type ty can establish, so boundary normalization is a precondition for
  `assert_never` there, not merely tidiness.

## 5. Phases

Each phase is one PR on a `plan/*` branch; `pixi run ci` must pass. **Ordering
rationale:** enforcement floor first so every later PR is checked by the tightened
gate; live bugs second (user-visible correctness, tiny diffs, and they establish the
loud-failure tests the refactors inherit); the registry third (highest leverage —
later phases and A6 phase 2 consume it); subsystem refactors after; the Tier-B ratchet
last, when earlier phases have shrunk its counts. **P5–P11 are mutually independent**
and may be reordered or dropped individually.

### P1 — Enforcement floor

- **Prerequisite (landed separately):** the `>=3.11` floor. No dependency to add —
  `assert_never` is stdlib (§2.3).
- Clear the two 3.10-era workarounds (§2.5): annotate `ResultCollector.__enter__` as
  `-> Self` and delete the now-false comment at `result_collector.py:242-243` plus its
  `# noqa: PYI034`. Leave `strenum` alone (D4).
- Re-enable Tier-A rules globally; fix the 17 resulting errors (guard the
  `scoop`/`playwright` imports; carve `setup.py` into the relaxed block or delete per
  plan 03). Preserve the `unused-*-ignore-comment` rationale comment. **Note the
  interaction:** 3 of the 5 `unresolved-import` errors live in
  `bencher/example/meta/generate_examples.py` and `test/test_docs_scrollbars.py` —
  the relaxed override block exempts those paths from Tier B/C only, so Tier A still
  fires there and those three edits land in code this plan otherwise treats as exempt.
- Add the relaxed override block and an initially-small strict override block (D1).
- Convert `bench_result_base.py:353` (`match reduce:` over `ReduceType`) to
  `assert_never` if the arm is genuinely unreachable after `_resolve_auto`.
- New `test/test_ty_gate.py`: (a) parse `pyproject.toml` and assert
  `type-assertion-failure` is never ignored and that the strict list is non-empty from
  P4 onward; (b) subprocess-run `ty check` against a seeded file containing one
  non-exhaustive match and one Tier-A violation in a tmp dir with a minimal config,
  asserting both diagnostics fire (skip if the `ty` binary is absent). **Use a minimal
  standalone config for the seeded file** — running under the repo config suppresses
  Tier-C rules and the probe silently passes (this bit the author; see §2.3).
- **DoD:** gate demonstrably fails on a seeded violation; `pixi run ci` green on py311
  and py313 (the CI matrix after the floor raise).

### P2 — Collection-path live bugs (B2, B3) + executor normalization (C13)

- `result_collector.py:463-471`: add the missing `else` → `TypeError` naming the
  variable, expected size and actual length. Match the wording style of the ladder's
  terminal `else` at `:473-474` (`Unsupported result type`) — note that is the whole
  `if/elif` chain's fallback, not a sibling of this branch's length check.
- Worker-returns-`None`: one boundary check raising `TypeError` with the current
  assert's helpful message ("return a dict or `super().__call__(**kwargs)`…") on
  **both** serial and parallel paths; delete the bare `assert` (`job.py:158-160`) and
  the silent `if result is not None:` skip (`result_collector.py:424`).
- C13: normalize `executor` to the `Executors` enum where `BenchRunCfg` is accepted so
  all four comparison sites (`bencher.py:1180`, `:1182`, `job.py:230`, `:355`) agree
  regardless of `==`/`is` style. This is hardening, not a bug fix — see C13.
- **Tests:** wrong-length `ResultVec` raises; `None` worker result raises under SERIAL
  *and* MULTIPROCESSING; a raw-string `executor` (the exact-case `"SERIAL"`, since
  lowercase is rejected by the `Selector`) resolves to the same branch at all four
  comparison sites.

### P3 — Reporting/rendering live bugs (B1, B4, B5)

- `video_controls.py:30-35`: replace the two parallel lists with one
  `list[tuple[str, Callable]]`; implement all four callbacks (play, pause, loop, reset)
  correctly — pause must pause, and Loop/Reset must exist.
- `utils.py:477` `publish_file`: make the annotation truthful — decide in-phase from
  the call sites whether to return the constructed URL or annotate `-> None`.
- B5: thread `method` through to the verdict so the beneficial-change comparison at
  `report_export.py:205` only measures `threshold` against `abs(change_percent)` for the
  percentage method; other methods get a correct or explicitly-abstaining verdict. Also
  revisit the hardcoded `regressed=False` at `scorecard/model.py:82`. Minimal change;
  A5's `RegressionCfg` sum type subsumes it later (§8).
- **Tests:** four correctly-wired buttons; for a MAD-method result, an improvement is
  not misclassified as unchanged (or vice versa) by a percent-vs-sigma comparison.

### P4 — Result-type registry (C1, D3)

- Implement `ResultSpec` / `RESULT_SPECS` with the post-plan-22 fills; derive the nine
  names; import in `result_collector.py`; add the `parametrised_sweep.py:89` guard.
- **Tests:** extend `test/test_result_missing.py:116` and
  `test/test_grammar_data_model.py:468` to be registry-driven (suppressing
  `DeprecationWarning`); add a transitional test asserting each derived tuple is
  **value-identical** to the pre-migration literal (delete after one release); add the
  subclass-order test.
- Add `variables/results.py` to the strict ty list.
- **DoD:** adding a `Result*` class without a spec fails CI with one clear message.

### P5 — Job state (C2 + C8; completes B3)

- `JobFuture` → a single field holding `Ready(res: dict) | Pending(future: Future)`
  (frozen dataclasses); the worker-`None` check from P2 moves into the factory that
  constructs `Ready`; `result()` becomes total; the order-dependent
  `job_future.future is not None` test in `bencher.py` reads the variant instead.
- `WorkerJob`: the four `None`-default fields (`worker_job.py:41-44`) become a factory
  classmethod or `cached_property`s so no object with unset hashes exists.
- **DoD:** `job.py`/`worker_job.py` in the strict ty list; existing cache tests green;
  P2's None-result tests pass through the new type.

### P6 — Plot filter bounds (C3 + C4)

- `VarRange`: named constructors (`VarRange.none()`, `.at_least(n)`, `.between(lo, hi)`,
  `.exactly(n)`, `.unbounded()`) or an equivalent Bounds sum type; kill the `-1`/`None`
  sentinel pair; fix the drifted docstring; `PlotFilter()`'s default must no longer
  silently match nothing (retire `match_all()` at `:84` and `anything` at `:90`, and
  the `plugin.py:72-73` footgun).
- C4 per owner decision (§6.1): delete `vector_len`/`result_vars` from `PltCntCfg` and
  `PlotFilter`, or populate them — **first report what plot selections would change if
  populated**, so the decision is informed.
- Blast radius: `plot_filter.py`, `plt_cnt_cfg.py`, ~20 `VarRange(...)` sites across
  `results/holoview_results/*`, `bench_result_base.py`, `plugins/`,
  `surface_result.py`, `test/test_plugins.py` (~18 files, mechanical).
- **DoD:** plot-selection output unchanged on the gallery-driving tests
  (`pixi run generate-docs` diff-clean); a default-constructed filter can no longer
  hide a plugin.

### P7 — History enums (C5)

- `HistoryEventKind(StrEnum)` with the 7 members from the comment at
  `history.py:77-78`; `lossy` computed by exhaustive match (replaces `_LOSSY_KINDS`,
  `:66`); an `OnHistoryReset` policy enum; unknown policy at `load_history_cache`
  **raises** instead of silently meaning "ignore".
- **Cache-safety check:** verify `HistoryEvent` is runtime-only (no `kind` string
  persisted) before enum-ifying; state the finding in the PR.
- **Tests:** unknown policy raises; every kind exercised through `apply_policy` under
  `on_history_reset="error"`.

### P8 — Composition types (C6)

- Two-member `Axis` type (`right | down`) owns `flip()`; `ComposeType` keeps its four
  members but partial `flip` becomes unrepresentable
  (`compose_method_list_for_dims(first_compose_method=sequence)` can no longer reach a
  runtime flip error).
- Exhaustive `assert_never` matches in `composable_container_panel.py` (declare
  `_tabs` unconditionally; remove the `horizontal: bool | None` overwrite of
  `compose_method`) and `composable_container_dataframe.py`.
- Merge `composable_container_rerun.py`'s two must-stay-complementary tables into one
  `dict[ComposeType, spec]` with a completeness assertion.
- **DoD:** a hypothetical 5th `ComposeType` member fails `ty` at every match site.

### P9 — Worker lifecycle (C7)

- Internal `WorkerState = Unbound | Declared(cls) | Runnable(fn, instance)` in
  `WorkerManager`; the three `RuntimeError("Worker class instance not set")` sites
  (`:174`, `:187`, `:200`) and both `# noqa: TRY004` collapse into exhaustive matches.
  Public `set_worker*` API unchanged.
- **Coordinate with plan 11** (same subsystem): whichever lands second rebases.

### P10 — Small constructive fixes (C9, C10, C12)

- `bench_report.py`: store `(bench_res, tab)` pairs so `append_to_result` /
  `prepend_to_result` cannot write into a different result's tab when `plot()` returns
  `None`.
- `plugins/bench_data.py`: `Capability` StrEnum; an unknown capability in `requires`
  raises at registration instead of yielding a permanently-unselectable plugin.
- `rerun_result.py`: route every value read through `result_is_missing`; replace the
  `0.0`/`nan_to_num` fills (`:323`, `:337`) with genuine gaps; replace the isinstance
  ladder's numeric fallthrough (`:370-371`) with explicit dispatch and raise the four
  DEBUG-swallowed handlers (`:312`, `:325`, `:343`, `:375`) to WARNING with context.
- **Tests:** None-plot result no longer misroutes panes; typo'd capability raises;
  a missing rerun value is not rendered as `0.0`.

### P11 — Aggregation single source (C11)

- One `AggFn` enum sourcing all four spellings (the `Literal`s at
  `bench_result.py:175` and `bench_result_base.py:203`/`:266`/`:712`, `AGG_FN_MAP` at
  `utils.py:385-391`, the `ObjectSelector` at `bench_cfg.py:820-824`) and the ladder at
  `bench_result_base.py:373-392`; unknown agg **raises**, matching `optimize()`'s
  existing behavior (`bencher.py:1370-1372`). Internal only — the knob's *home* is
  A5's business.
- **Test:** unknown `agg_fn` raises instead of silently meaning `mean`.

### P12 — Tier-B ratchet

- Re-enable the five Tier-B rules globally (~126 diagnostics at `4a13ab8e`, fewer
  after P2–P11). Note `invalid-return-type` doubles as the fallback exhaustiveness
  signal (§2.4), so this phase also hardens D2. Final strict-list review; record the
  Tier-C endgame decision (§6.6) as an open item for a future plan.

## 6. OWNER DECISIONS

1. **C4 (P6): populate vs delete `vector_len`/`result_vars`.** Recommendation:
   **delete** — `result_vars` already carries `# todo remove`; only a test writes them;
   their gates have never fired. The phase must first report what would start being
   filtered if populated.
2. **B2/B3 (P2): raise vs warn.** Recommendation: **raise `TypeError`**, and *not*
   routed through plan 21's `catch=` — a `None` return or wrong-length vector is a
   harness-contract error, not a sample fault. Alternative (warn + skip) preserves the
   current silent behavior for parallel users.
3. ~~**D2: take the `typing_extensions` dependency**~~ — **RESOLVED, no longer a
   decision.** The owner raised the floor to `>=3.11`, so `assert_never` is stdlib and no
   dependency is needed (§2.3). Kept as a numbered entry so later references to
   "decision 3" still resolve. The follow-on question — migrate `strenum` → stdlib
   `enum.StrEnum` — is deliberately **not** opened here; D4 records why and hands the
   accepted-string break to A5.
4. **P1 meta-test: subprocess ty-on-seeded-violation in CI.** Recommendation: **yes**
   (~1–2 s, skip when the binary is absent). Fallback: config-parsing assertion only.
5. **B5 (P3): fix now vs wait for A5's `RegressionCfg`.** Recommendation: **now** —
   wrong scorecard verdicts ship today; the fix is small and A5 subsumes it.
6. **Tier-C endgame:** whether `invalid-argument-type` (531) / `unresolved-attribute`
   (251) ever go global, or the strict-list ratchet is the permanent mechanism. Out of
   scope here; record as an open question.
7. **`pandas-stubs`.** Recommendation: **defer** — holoviews/hvplot/plotly/diskcache
   have no stubs anyway, so marginal signal is small.

## 7. Cache safety

- **P2 (B4):** executor normalization must not perturb any persisted hash (`executor`
  lives on `BenchRunCfg`; the plan 09/16 key split should exclude it — confirm in-phase
  and state the finding in the PR).
- **P4 (C1):** pure module-level reorganization; derived tuples asserted
  value-identical; the dual-generation `missing_sentinels` sets must keep reading old
  cells (plan 22's `-1`/`"NAN"` compatibility is **not** to be simplified away); no
  pickle or cache format change; **no `CACHE_VERSION` bump**.
- **P6 (C4-delete):** cached `BenchResult` pickles may hold `PltCntCfg` state for the
  deleted params — verify old pickles load cleanly after param-class attribute removal
  (the `getattr` posture of plan 22 / PR #994); if not, deprecate-in-place for one
  release.
- **P7 (C5):** verify `HistoryEvent` is never persisted before enum-ifying.
- **General rule:** no phase changes stored cell values or sentinels.

## 8. Amendments to other plans (recorded here, implemented there)

- **A5 (config surface):** when Phase 1/2 builds `RegressionCfg`, model method +
  threshold as a **sum type** — one variant per detection method carrying its own
  threshold with its own unit semantics (`PercentThreshold`, `MadSigma`, `DeltaLimit`,
  `AbsoluteLimit`) — not a method string plus one overloaded `threshold: float`. P3's
  B5 fix is a stopgap this design subsumes. Apply the same discipline to
  `fail_on_sample_error` (`bool | float` today, with a hand-written ambiguity guard
  rejecting `1`), `show` (7 objects for 4 modes), `plot_size`/`plot_width`/
  `plot_height` (documented precedence), and the subsampling knobs
  (`subsampling_divisions == 0` as a sentinel beside `samples_per_var`): enums and sum
  types, not `str | bool | None` unions.
- **A3 (BenchData contract):** `BenchResult`'s two-phase init (`post_setup`) and the
  dry-run path returning an empty result type-indistinguishable from a real one are
  A3's to fix — "no samples collected" should be a distinct, represented state.
- **Plan 22 (landed):** its D2/D5 already fixed the `ResultDataSet` sentinel bug and
  unified the oracle (§3.1); this plan consumes that rather than duplicating it. The
  residual `dataset_list`/`object_index` dual read path stays plan 22 phase 3's
  business. P4 must preserve the dual-generation sentinel acceptance.
- **Plan 11 (worker lifecycle):** P9 touches the same subsystem; whichever lands
  second rebases on the other's shape.
- **A6 phase 2:** the phase-2 plan should be written against the post-P4 registry —
  a closed channel vocabulary is much easier to derive from `RESULT_SPECS` than from
  nine tuples.

## 9. Definition of done (plan-level)

- All twelve phases merged (or explicitly dropped with a note in this file).
- `pixi run ci` enforces: Tier A+B rules globally, Tier C on every module this plan
  touched, `assert_never` exhaustiveness (`type-assertion-failure` never ignored), and
  the registry completeness test.
- Bugs B1–B5 each have a regression test that fails on the pre-fix code. C13 gets a
  branch-agreement test instead — it is a latent smell with no failing pre-fix case.
- Grep-level checks: no `_LOSSY_KINDS`, no `match_all(`, no bare
  `assert self.res is not None`, no `zip(button_names`, no `nan_to_num(arr, nan=0.0)`
  in `rerun_result.py`, and exactly one definition of the agg-fn vocabulary.

## 10. Amendments discovered during implementation

Recorded per the plans-README rule that claims which stopped holding are stated rather
than silently worked around.

### P1 (implemented)

1. **The gate was worse than "21 rules ignored" — it ran with no dependency
   resolution.** The `ty` task was `ty check --respect-ignore-files .` with no
   `--python`, so *every* third-party import was unresolved (`param`, `panel`, `numpy`,
   `xarray`, …). That is why `unresolved-import` had to be ignored globally, and it
   silently degraded every rule that needs a third-party type. The task now passes
   `--python "$CONDA_PREFIX"`, which resolves the *active* pixi environment so `-e py311`
   and `-e py313` each check against their own interpreter. **All per-rule counts in §2.1
   are only reproducible with `--python`**; measured without it they are meaningless. A
   meta-test now pins the flag.
2. **Tier A is 17 diagnostics, and all 17 are fixed rather than suppressed except two.**
   Genuine fixes: `hv_dataset: hv.Dataset = None` → `| None` (annotation contradicted its
   own default); `plot_callback: Callable | None` narrowed to `Callable` in `_to_panes_da`
   and `_to_video_panes_ds` (both call it unguarded, so `None` was unanswerable — all four
   call sites already pass a real callable); `options(self, *_args)` → `*_args, **_kwargs`
   to match tornado's `RequestHandler.options`; `ExampleEnum.to_class`'s parameter widened
   to `ClassEnum` (it narrowed a base-class parameter, an LSP violation). Two scoped
   `# ty: ignore` comments remain, each with its reason inline: the optional `scoop`
   import (the `try/except ImportError` *is* the handling) and the `signal.getsignal`
   result in `run.py` (ty cannot narrow an `IntEnum` by identity against specific members).
3. **`extra_panels`' `callable()` check cannot exclude the `Viewable` arm**, so the
   predicate is now `callable(ep) and not isinstance(ep, pn.viewable.Viewable)`.
   **Corrected during review:** the first attempt used `isinstance(...)` alone with the
   branches swapped, which *introduced* a regression — the two predicates are not
   complementary, and an object that is neither callable nor `Viewable` (a `str`, an
   `hv.Curve`, a `DataFrame`) used to reach `append`, where `Column.append` coerces it.
   Under the swapped form it was called instead, raising `TypeError` into the surrounding
   `except Exception` and **silently dropping the panel**. `test_extra_panels.py` only
   covers `pn.pane.Markdown`, so nothing caught it. Note also that the "latent bug" the
   change was originally justified by is hypothetical: no panel `Viewable` is callable
   (`Viewable` has no `__call__` in its MRO). The guard is cheap and kept, but it defends
   a possibility, not an observed defect.
4. **`Benchable` is discriminated by `inspect.signature` parameter count**, which no
   checker can narrow. The two call sites now `cast()` to the arm the introspection
   established, so the assumption is stated rather than blanket-ignored. This is the
   shape plan 24 warns about; the `cast` is honest about being unverified.
5. **`_resolve_auto` now returns `ResolvedReduceType`** — a `Literal` over the four
   non-`AUTO` members — so `to_dataset`'s `match` is exhaustive over those members and the
   `assert_never` arm is not a catch-all. Deleting one arm produces
   `error[type-assertion-failure] … Inferred type of argument is Literal[ReduceType.MINMAX]`,
   naming the forgotten variant.
   **Scope corrected during review — this is not yet a compile-time guarantee.** The
   proof rests on `_resolve_auto` really returning a member of that `Literal`, and the only
   rule that checks it, `invalid-return-type`, is Tier B and still globally ignored.
   Measured: seeding `return ReduceType.AUTO` into `_resolve_auto` passes `pixi run ty`
   (it is caught only with `--error invalid-return-type`), and adding a `ReduceType` member
   without updating the alias or the match also passes ty, then fails at runtime in
   `assert_never`. So for that scenario P1 moves "silently degrades to NONE" to "crashes,
   still statically undetected". P12 closes it; a caveat comment records this at the alias.
6. **Plan 24's warning was confirmed empirically, by this plan breaking on it.**
   Converting the catch-all to `assert_never` turned two green tests red with
   `AssertionError: Expected code to be unreachable, but got: None` — `map_plot_panes`
   declares `reduce: ReduceType | None = None` and passed that `None` into `to_dataset`,
   whose annotation says `ReduceType`. The old `case _:` had been absorbing it. This is
   exactly plan 24 §2.1: a *complete* match is type-clean while raising at runtime,
   because the subject's type was never established.

   **Where the sentinel is normalized matters, and the first attempt got it wrong.**
   Mapping `None` → `ReduceType.NONE` in `map_plot_panes` (the obvious place) was **not**
   behaviour-preserving, and review caught it: `to_hv_dataset` branches on
   `reduce == ReduceType.NONE` *before* delegating, and `None` deliberately did not match
   that, so it took the generic arm where holoviews infers kdims from the xarray variables
   **with their units**. Normalizing early flipped it onto the arm that passes bare
   strings as `kdims`, silently dropping unit metadata:

   ```
   reduce=None       -> [('theta', 'rad'), ('repeat', 'repeats')]
   ReduceType.NONE   -> [('theta', None),  ('repeat', None)]
   ```

   The normalization therefore lives in **`_resolve_auto`** — the single funnel, reached
   after every `== ReduceType.NONE` branch has already been decided on the raw value. That
   preserves behaviour on every path *and* fixes the wider problem: `to_dataset`,
   `to_hv_dataset`, `to_hv_type`, `to_points` and `filter` all forward `reduce` unchanged,
   so an early fix in one caller would have left `reduce=None` crashing on all the others.
   `to_dataset`/`to_hv_dataset` are now annotated `ReduceType | None`, which is the domain
   they have always accepted.

   **The behaviour discrepancy this exposed is recorded, not fixed:** `map_plot_panes`
   defaulting to `None` means it has always skipped reduction, whereas `to_hv_dataset`'s own
   default is `AUTO` (mean/std over repeats). Changing that alters rendering output and
   needs a phase that can own it. Compare `BenchResult.to()`, which handles the same
   sentinel correctly by omitting the argument.

7. **`identity.py` was pulled back off the strict list.** It is not clean: it passes
   `list | dict | None` to `plot_sweep`, annotated `list[ParametrizedSweep] | None`. The
   annotation is the wrong one — `convert_vars_to_params` accepts
   `param.Parameter | str | dict | tuple` — but widening a public entry point's signature
   is A5's business, not P1's. The strict list's rule ("a file is added only once it is
   clean") is honoured instead of loosening the block. Initial strict members are
   therefore `sample_order.py`, `sweep_timings.py` and `blob_store.py`.
8. **Two rules stay ignored permanently and are labelled as such**, so a future reader
   does not mistake them for debt: `unused-ignore-comment` and
   `unused-type-ignore-comment`, because the repo deliberately carries 8 `# type: ignore`
   comments for other checkers.
9. **D1's relaxed override block was dropped entirely, and D1 should be read as amended.**
   As first written it exempted `test/**`, `bencher/example/**`, `scripts/**`, `docs/**`
   and `setup.py` from twelve rules. Review measured what actually fires in those paths
   with nothing silenced: **6 diagnostics**, all addressable inline — 4
   `unresolved-import` (optional `playwright` ×3, vestigial `setuptools` in `setup.py`) and
   2 `call-non-callable` in `scripts/benchmark_save.py:190` (a heterogeneous dict literal
   widens `fdef["cls"]` past `type`). Five of the twelve rules were also **no-ops**, being
   Tier C and already globally ignored. So the block's real effect was disabling seven
   Tier-A rules over the largest trees in the repo — including `missing-argument` across
   `bencher/example/**`, the corpus that doubles as integration tests and doc source, and
   the very rule that catches a call site omitting a newly-required argument like this
   phase's `plot_callback`. It is replaced by the two narrowest things that work: one
   scoped `# ty: ignore[call-non-callable]` in `scripts/benchmark_save.py`, and a
   **file-precise** override silencing only `unresolved-import` for exactly three files
   (`generate_examples.py`, `test_docs_scrollbars.py`, `setup.py`). Those three cannot take
   an inline comment: ruff reflows the import past the line limit and the comment lands on
   the inner line, where pylint's own `import-error` pragma stops applying — attempting it
   dropped `pixi run pylint` from 10.00/10. Verified afterwards that `missing-argument`
   still fires in both `test/` and `bencher/example/`, so **Tier A is now enforced in those
   trees**. A future phase enabling Tier B/C may need a broader relaxed block; it should
   size it from measured evidence and list paths explicitly rather than by subtree glob.
10. **The meta-tests could not detect the bypass they exist to prevent.** Asserting only
   on `[tool.ty.rules]` missed the override route: review demonstrated adding
   `"bencher/**"` to a relaxed `include` turned the whole Tier-A gate off for the package
   with `test_ty_gate.py` still green. There is now a parametrized assertion that no
   override block silences a protected rule for first-party package code, verified to fail
   on exactly that seeded bypass. The probe tests also assert ty's **exit code**, not just
   its output text, so a rule demoted to warning level cannot pass; and their class
   docstring no longer claims to prove the repo's gate, only the mechanism.

### P2 (implemented)

1. **B2 and B3 both landed as `raise TypeError`, per decision 2 — and the "not routed
   through `catch=`" half of that decision turned out to be the load-bearing half.**
   Seeding the pre-fix code back to measure what the new tests catch produced this, from a
   run with `catch=Exception`:

   ```
   WARNING sample failed and was caught (x=0, repeat=1): AssertionError('old assert')
   ```

   So the old serial `assert` was not merely absent under `python -O`; with `catch=` set it
   was **downgraded to a tolerated sample failure**, which is the same silent-empty-dataset
   outcome as the parallel path. Both checks are therefore raised *outside*
   `store_results`'s `except catch` block, and `TestCatchDoesNotAbsorbContractErrors` pins
   it — without that test the fix would have looked complete while the obvious user
   response (`catch=Exception`) restored the old behaviour.
2. **The B3 check could not go where it naturally belongs.** `JobFuture.result()` is the
   one place both executors converge, but it is called *inside* that same `except catch`
   block (and `FutureCache.submit` is inside the caller's), so raising from either would be
   absorbed. The check is `require_worker_result(result, job_id)` at the two points where a
   result is *consumed* — `store_results` and the optimize path (`bencher.py`, which calls
   `.result()` directly and would otherwise fail as a downstream subscript error).
   Consequently `JobFuture.result()` is now annotated `-> dict | None`: honest rather than
   narrow, since `JobFuture` really can hold neither a result nor a future. **P5 removes
   the `| None`** by making that state unrepresentable; until then the widening is the
   truthful option, not a regression.
3. **C13's `assert_never` works on a `strenum.StrEnum` — verified, not assumed.**
   `Executors.factory` now parses with `normalize_executor` and matches exhaustively.
   Deleting the SCOOP arm yields
   `error[type-assertion-failure] … Inferred type of argument is Literal[Executors.SCOOP]`,
   naming the missing member. This is the first place in the repo where plan 24 A2's claim
   is realised end to end: the parse is what makes the subject typed, and
   `test_factory_rejects_an_unknown_value_before_matching` pins that bad input raises
   `ValueError` at the parse rather than `AssertionError` at the match.
4. **No pre-fix regression test exists for C13, and the plan was right that none could.**
   What is testable is the *reason* the normalization exists, so it is pinned as an
   executable fact: `"SERIAL" == Executors.SERIAL` while `"SERIAL" is not Executors.SERIAL`.
   That assertion doubles as a tripwire for the stdlib-`StrEnum` migration (D4 / handover
   §5.4), which would change the vocabulary rather than just the representation.
5. **Normalization is not visible on the caller's own config, and that is intended.**
   `to_bench(cfg)` deepcopies, so `plot_sweep` normalizes the copy — asserted via
   `bench.last_run_cfg`. A config passed directly as `plot_sweep(run_cfg=cfg)` is not
   copied and *is* normalized in place. A first draft of the test asserted the wrong one of
   these and failed; both paths are now pinned explicitly so the asymmetry is documented
   rather than rediscovered.
6. **`Executors.factory` was annotated `-> Future | None`, the one type it never
   returns.** A `Future` is what `submit()` hands back. Found by putting `job.py` on the
   strict list to measure it: `Object of type Future[Unknown] has no attribute submit`. The
   concrete values are a `ProcessPoolExecutor` and, for SCOOP, a *module*, so naming
   `concurrent.futures.Executor` would be a second smaller lie; the fix is a two-method
   `SupportsSubmit` Protocol, which both satisfy.
7. **Neither reworked file could join the strict ratchet, and the block's rule is honoured
   rather than loosened** (as in P1 item 7). Measured with `job.py` and
   `result_collector.py` added to it: 6 diagnostics, 2 of which the Protocol above fixed.
   The remaining 4 are pre-existing and out of P2's scope:
   - `job.py` `clear_tag` calls `self.cache.evict(tag)` on `Cache | None` with no guard —
     a live latent `AttributeError`.
   - `job.py` `Job.__init__` argument type; `result_collector.py`
     `record_caught_sample` argument type.
   - `result_collector.py` iterates `worker_job.function_input.items()` where the field is
     `dict | None`. The last two are the *same* defect: `WorkerJob.function_input` is
     `None` until `setup_hashes()` runs, i.e. two-phase init. **That is P5/P9 territory**
     (`WorkerJob`/`JobFuture` state), and fixing it there should let both files onto the
     strict list in one step.
8. **P1's Tier-A gate caught this phase's own test fixture**, which is worth recording as
   evidence the gate earns its keep: `ReturnsNothing.__call__` is annotated `-> None` and
   `invalid-method-override` flagged it against `ParametrizedSweep.__call__ -> dict`. It
   carries a scoped `# ty: ignore` with a reason, because the invalid override *is* the
   subject under test. The useful implication: for a worker whose return type is
   annotated, B3 is already a **static** error; `require_worker_result` is what covers the
   unannotated case, which is the common one.
9. **Cache safety confirmed for the C13 normalization** (§7's requirement). `executor`
   reaches no persistent hash — it appears in neither `identity.py` nor `worker_job.py` —
   and for the one place it is stringified (`bench_cfg.py`'s sampling summary) a member and
   the raw string are indistinguishable: `str(Executors.SERIAL) == str("SERIAL")` and
   `hash(Executors.SERIAL) == hash("SERIAL")`, both True, since `StrEnum` inherits `str`.
   No `CACHE_VERSION` bump.
