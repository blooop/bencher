# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Scorecard and A/B verdicts now measure an improvement in the units the detector
  actually used** (plan 23 P3, B5). `RegressionResult.threshold` means a percent for
  `regression_method="percentage"`, but **MAD-sigma** for `"adaptive"`, an **absolute
  delta** for `"delta"`, and an **absolute limit** for `"absolute"` — and the verdict
  helper compared it against `abs(change_percent)` regardless. Regressions were never
  affected (both call sites resolve `regressed` from the detector before the comparison
  is reached); what was corrupted is the **improved-vs-unchanged** split for the three
  non-percentage methods: a tiny but real improvement on a quiet metric read as
  "unchanged", and a beneficial move well inside the acceptance band read as "improved"
  because its percent number happened to exceed a sigma count. Each method is now judged
  on its own terms — `delta` on `|current - baseline|`, `adaptive` against the MAD
  acceptance band (plus the percent band when the dual-band gate is configured),
  `absolute` abstaining because a fixed limit has no baseline to improve on — and a
  record missing the fields a method needs abstains instead of guessing.

  **This recolours existing scorecards.** `schema_version` is a *structural* version and
  the discovery pass has no version gate, so every `*.summary.json` already on disk is
  re-read with the corrected rules on the next scorecard build: cells from `adaptive`,
  `delta`, and `absolute` gates can move between `improved` and `passed` with no file
  changing and no benchmark re-running. `regressed` and `trend` cells are unaffected. See
  `docs/scorecard.md` for the versioning policy this follows.

- **All four video-control buttons exist and each does what its label says** (plan 23 P3,
  B1). Four button labels were zipped against a two-element callback list, so `zip`
  truncated the row: only two buttons were ever built, "Pause Videos" was wired to the
  callback that *unpauses*, and the Loop and Reset buttons did not exist. All four are now
  built from a single list of `(label, callback)` pairs. Looping is driven by one shared
  flag so a click moves every video pane to the same state instead of inverting each
  independently, and the button is labelled "Toggle Looping" because videos start out
  looping — a button reading "Loop Videos" would have turned looping *off* when first
  pressed. Note that Reset's rewind is a request panel's client-side model can drop while
  a video is playing (its `set_time` handler returns without seeking when a recent
  `timeupdate` armed its internal guard); the docstring records this rather than promising
  a rewind bencher cannot deliver.

- **`publish_file` no longer claims to return a URL it never returned** (plan 23 P3, B4).
  It was annotated `-> str` and documented as returning the published file's URL, but the
  body ends at the `git push` and falls off the end returning `None` — so a caller
  following the signature got `None`. The annotation and docstring now state that, and
  document `remote` as the string it is (it was described as a callable returning a pair
  of URLs, from a signature that no longer exists). Behaviour is unchanged: the viewable
  URL is provider-specific and not derivable from the arguments, so callers still build it
  themselves, as `publish_and_view_rrd` already did.

- **A malformed or foreign `*.summary.json` no longer aborts a scorecard build.** JSON
  integers are arbitrary-precision, so an oversized integer where a metric value was
  expected raised `OverflowError` (not caught by the `TypeError`/`ValueError` guard) out of
  the verdict pass and out of the page render; it now degrades to an abstaining verdict.
  The same gap is closed in the writer (`RegressionResult.to_dict`), which now emits `null`
  for such a value rather than raising.

- **Fail-loud, not fail-fatal: a benchmark that returns `None` no longer produces a
  silently empty sweep — and no longer aborts the run either** (plan 23 P2, B3; amended
  per owner decision before release). A worker that forgot to `return
  super().__call__(**kwargs)` used to trip a bare `assert` on the serial executor — and
  nothing at all on `MULTIPROCESSING`/`SCOOP`, where the future resolved to `None`,
  `store_results` skipped its entire body behind `if result is not None:` with no `else`,
  and the sweep finished green with an all-sentinel dataset and `n_failed == 0`. The same
  user error was loud or silent depending on an unrelated config knob, and the assert
  vanished entirely under `python -O`. Both paths now funnel through one check
  (`require_worker_result`, raising `WorkerContractError`), which `store_results`
  consumes: the sample is recorded in `failed_samples` (so `n_failed` counts it and
  `fail_on_sample_error` can gate the run at the end), logged at ERROR, announced with a
  `WorkerContractWarning`, and shown in the report's failed-samples summary — while the
  sweep continues, because crashing mid-run loses the expensive samples already
  collected. Strict pipelines can promote the warning:
  `warnings.filterwarnings("error", category=bn.WorkerContractWarning)`.

- **A `ResultVec` set to the wrong number of elements is recorded and warned, not
  silently dropped** (plan 23 P2, B2; same amended disposition as B3). The store was
  guarded by `isinstance(value, (list, np.ndarray)) and len(value) == rv.size` with no
  `else`, so a length mismatch was silently discarded and the cell kept its NaN fill —
  indistinguishable downstream from "never sampled". `param.List` validates that the
  value is a list but not how long it is, so this was reachable from ordinary benchmark
  code. The warning names the variable, the declared size and the actual length. A
  raw-dict worker omitting a declared result variable (previously a mid-sweep
  `KeyError`) is handled the same way.

  Contract violations are handled **outside** `store_results`'s `except catch` block on
  purpose: a bad return shape is a harness-contract error, not a sample fault, so
  `catch=` plays no part in it (plan 23 decision 2) — the violation is recorded
  identically with and without `catch=Exception`, so neither setting nor omitting it
  restores the old silent skip. The `Bench.optimize` path is the documented exception —
  its objective runs under `study.optimize(..., catch=catch)`, so a `catch=` there still
  absorbs the error. That is pre-existing rather than new: the old code was absorbed at
  the same point, as an `AssertionError` on serial and a `None` subscript `TypeError` on
  the pool.

- **The report now shows failed samples.** `n_failed`/`failed_samples` existed since
  plan 21 but never surfaced anywhere a reader would look: a run with failures produced
  a normal-looking report and only log lines. `to_auto_plots` now auto-inserts a
  failed-samples summary (inputs + first error line per failure) whenever
  `n_failed > 0`, in the same way the regression report is auto-inserted.

### Changed
- **`VarRange` is built with named constructors; the `-1`/`None` sentinel pair is gone**
  (plan 23 P6, C3). `VarRange.upper_bound` carried three meanings on one field — `-1`
  meant "match nothing" (and was the default), `None` meant "no upper bound", and any
  other value was a real bound — while `lower_bound` accepted `None` as a fourth
  spelling of `0`. The class docstring had already drifted away from the code (it claimed
  both bounds defaulted to `-1`; `lower_bound` defaulted to `0`). A `VarRange` is now a
  frozen wrapper over a three-variant sum — no counts, a closed `low..high` interval, or
  an open `low..` interval — built through `VarRange.none()`, `.exactly(n)`,
  `.between(lo, hi)`, `.at_most(n)`, `.at_least(n)` and `.unbounded()`. Nonsense that the
  old constructor accepted silently (`VarRange(2, 1)`, a negative bound) now raises at
  construction, and `matches()` dispatches over the variants with `assert_never`.

  **`PlotFilter()` no longer matches nothing.** Every field now defaults to
  `VarRange.unbounded()`, so an omitted range never narrows a filter and a plugin
  declared with the obvious `match=PlotFilter()` — or with no match rule at all — is
  eligible for every sweep shape instead of being hidden forever. `PlotFilter.match_all()`
  existed only to work around the old default and has been **removed**; use `PlotFilter()`.
  `BenchResultBase.filter()`'s five `*_range` parameters lose their `None` defaults for
  the real ranges they always stood in for, and its long-dead `plot_filter=` parameter
  (unconditionally overwritten two lines later) is gone.

  **Plot selection is unchanged.** Every production filter now states all five ranges
  explicitly, so the new permissive default cannot widen anything: the three direct
  `PlotFilter(...)` sites that previously inherited a restrictive default
  (`surface_result`'s `panel_range`, plus `repeats_range` in `video_summary` and
  `rerun_summary`) spell those values out. No production filter had ever inherited the
  match-nothing `float_range`/`cat_range` default. `volume_result`'s `cat_range` was
  written `VarRange(-1, 0)`, whose negative lower bound was inert because `matches()`
  rejects negative counts — it is now the `VarRange.exactly(0)` it always meant.
  `pixi run generate-docs` produces a byte-identical output tree.

- **`WorkerManager` holds one `WorkerState` instead of a not-set invariant** (plan 23 P9,
  C7). `worker_class_instance: ParametrizedSweep | type[ParametrizedSweep] | None` carried
  three different situations in one field — an instance, a declaration-only class, or
  nothing — with "declaration only" inferred from `worker is None`, and three
  `RuntimeError("Worker class instance not set")` sites plus two `# noqa: TRY004`
  suppressions standing in for the type the field did not have. The state is now a single
  `Unbound | Declared(cls) | RunnableFunction(fn) | RunnableInstance(instance)` sum of
  frozen dataclasses, parsed once in `set_worker` / `set_worker_class`; `worker` and
  `worker_class_instance` remain as read-only views over it, so **the public
  `set_worker` / `set_worker_class` API, the attributes `Bench` mirrors, and the
  `RuntimeError` contract for a class-vs-instance mix-up are all unchanged**. The three
  raise sites collapse into one total `_declaring()` accessor, and all three matches over
  the union end in `assert_never` — verified by seeding a fifth variant and measuring
  `error[type-assertion-failure]` at each site. The messages are now actionable: reading
  variables with nothing attached names `set_worker()` and `set_worker_class()`, and doing
  it with a plain-function worker says so and points at `input_vars`/`result_vars`/
  `const_vars` rather than repeating "Worker class instance not set". These are all
  setup-time errors, raised before any sample exists, so no in-progress sweep can lose
  collected data to them. `bencher/worker_manager.py` joins the strict `ty` list.

  Note the sum has **four** variants where the plan sketched three: callability and
  "declares the sweep's variables" are independent axes, and folding them together would
  have needed a nullable `instance` field inside `Runnable` — the same sentinel, one level
  down. Also corrected while putting the module under strict typing:
  `worker_input_cfg` is annotated `type[ParametrizedSweep]`, the class every caller has
  always passed and the body has always instantiated (the annotation said instance while
  the docstring said class). `bencher.py` and `sweep_executor.py` still carry the old
  annotation on their pass-through parameters.
- **BREAKING (small): one `AggFn` vocabulary, and an unknown `agg_fn` now raises instead
  of silently meaning `mean`** (plan 23 P11, C11). The aggregation-function vocabulary
  existed in four independent spellings — the `Literal`s on `to`/`to_dataset`/
  `to_hv_dataset`/`filter`, `AGG_FN_MAP`, `BenchCfg.agg_fn`'s `ObjectSelector`, and an
  if/elif ladder in `to_dataset` that consulted none of the others. `AggFn`
  (`bencher/utils.py`) is now the single definition and the other three derive from it;
  the ladder normalizes at the boundary (`normalize_agg_fn`) and then matches
  exhaustively under `assert_never`.

  Two user-visible changes, both on the plotting path:

  1. **An unrecognised `agg_fn` raises `ValueError`.** The ladder's terminal `else` was
     commented "Fall back to mean if unknown string provided", so `agg_fn="meen"`
     silently produced a mean-aggregated plot — while `optimize()` raised on the very
     same input. The two agree now. The raise lands at plot/aggregation time, never
     mid-sweep: via `plot_sweep`, `BenchCfg`'s `ObjectSelector` rejects the value before
     any sample is collected; via `to_dataset`/`filter`, results are already collected
     and cached. Validation is also unconditional now — previously an unknown value was
     only checked when `agg_over_dims` was non-empty, so whether you got an error
     depended on the data.

  2. **Uppercase is no longer accepted.** The ladder did `(agg_fn or "mean").lower()`,
     so `agg_fn="MEAN"` worked in `to`/`to_dataset`/`to_hv_dataset`/`filter` — and
     nowhere else: `plot_sweep(agg_fn="MEAN")` and `optimize(agg_fn="MEAN")` already
     raised, because the `ObjectSelector`'s objects are lowercase. That leniency was
     undocumented, unused anywhere in the tree, and asymmetric across the API, i.e. a
     fifth partial spelling of the vocabulary rather than a feature. Preserving it
     inside `normalize_agg_fn` would have recreated exactly the divergence this change
     deletes; honouring it everywhere would mean widening the accepted set, which is a
     public-API decision that does not belong in an internal single-sourcing change.
     The error message names the lowercase spelling
     (`... (the vocabulary is lowercase; did you mean 'mean'?)`), so the fix is
     mechanical. Lowercase the string, or pass an `AggFn` member.

  No cache, hash or `CACHE_VERSION` impact: `agg_fn` feeds no persistent hash (it is in
  `identity.py`'s `EXCLUDED_FIELDS`), the accepted string set is byte-identical, and all
  five aggregations are numerically unchanged.

- **`BenchRunCfg.executor` is normalized to an `Executors` member at the sweep boundary**
  (plan 23 P2, C13). Because `Executors` is a `StrEnum`,
  `param.Selector(objects=list(Executors))` accepts the bare string `"SERIAL"` and stores a
  `str` in a field compared with `==`/`!=` in `Bench` and with `is not` in
  `FutureCache.submit` — styles that disagree on a raw string. The four sites happened to
  agree, because `Executors.factory` also used `==`; that was luck, not design. `executor`
  is now parsed once in `plot_sweep` and in `FutureCache.__init__`, `factory` matches
  exhaustively via `assert_never`, and an out-of-vocabulary value raises at the parse
  rather than at a match site. No cache impact: `executor` feeds no persistent hash, and a
  member's `str()` and `hash()` are identical to the raw string's.

- `Executors.factory` is annotated `-> SupportsSubmit | None` rather than `-> Future |
  None`, which was the one thing it never returns — a `Future` is what `submit()` hands
  back. The new `Protocol` (`submit`, `shutdown`) is satisfied by both
  `ProcessPoolExecutor` and scoop's module.

- `JobFuture.result()` was annotated `-> dict | None` by P2 (the `None` was not new
  behaviour, only newly admitted: `JobFuture` could represent "no result and no future").
  **Superseded before release by P5 below**, which makes that state unrepresentable and
  the method total.

- **`JobFuture` holds one state field instead of two optionals** (plan 23 P5, C2). `res`
  and `future` were independent optionals that `result()` *mutated* — it assigned to
  `self.res` and left `self.future` set — so `future is not None` stopped meaning
  "pending" after the first call, and both-set and neither-set were both representable
  while neither was meaningful. The field is now a single
  `Ready(res) | Pending(future) | Broken(error)` sum of frozen dataclasses, parsed once in
  the constructor (whose keyword signature is unchanged, so every construction site and
  hand-built test object reads as before); passing both a result and a future now raises
  `ValueError`. `result()` matches exhaustively with `assert_never` — verified by deleting
  an arm and measuring `error[type-assertion-failure] … Inferred type of argument is
  'Broken & ~Ready & ~Pending'` — and is **total**: the `| None` return is gone. The
  order-dependent `job_future.future is not None` dispatch in `Bench.calculate_benchmark_results`
  reads the variant instead.

  `Broken` is the constructive replacement for the one meaningful half of "neither set": a
  job that yielded no result. The error is *stored* rather than raised at construction,
  because the serial site is inside the caller's `except catch` block — raising there is
  exactly the original B3 failure mode where `catch=Exception` absorbed a contract
  violation. It is supplied by whichever caller *knows* the cause (the serial site in
  `FutureCache.submit`, having just watched `run_job` return `None`) rather than inferred
  from the shape of the constructor call, which cannot tell a `None`-returning worker from
  a cache entry holding `None`. **The record-and-continue disposition is unchanged** (plan
  23 §6.2 as amended): `result()` raises at the consume point on *either* executor path,
  `store_results` records a `SampleFailure`, logs at ERROR, emits
  `WorkerContractWarning`, and the sweep continues. A `None` return never aborts a run.
  Caching semantics are also unchanged: the pre-P5 `res is not None` guard on `cache.set`
  is now enforced by construction — a worker that returned nothing cannot reach the cache.

- **`WorkerJob`'s derived inputs and hashes are `cached_property`s, not two-phase init**
  (plan 23 P5, C8). `function_input`, `canonical_input`, `fn_inputs_sorted` and
  `function_input_signature_pure` defaulted to `None` and were filled by a `setup_hashes()`
  call every construction site had to remember, so nothing prevented caching a sample under
  `job_key=None`. `setup_hashes()` is gone; the four values are computed on demand from the
  constructor fields, so a `WorkerJob` with unset hashes no longer exists. The unused
  `found_in_cache` and `msgs` fields (written nowhere in the package) are removed. Hash
  values are byte-identical — the same `hash_sha1((sorted_inputs, tag))` over the same
  inputs — so no cached sample is invalidated, and pickling across a process boundary still
  works (computed values travel in `__dict__`; unaccessed ones recompute deterministically).

- `FutureCache.clear_tag` no longer raises `AttributeError` on `None` when the cache is
  disabled (`cache_samples=False`), and `JobFunctionCache.call` passes its counter as a
  `str`, matching `Job.job_id`'s declared type. Both were latent defects surfaced by putting
  `job.py` on the strict `ty` list (recorded as out-of-scope in plan 23 P2 item 7).
  `bencher/job.py`, `bencher/worker_job.py` and `bencher/result_collector.py` are all on
  that list now — the last one because C8 removed the `function_input`-is-`None` diagnostics
  that were holding it off, exactly as P2 predicted.

  Both fixes go past what the type checker asked for, because in both cases satisfying it
  would have hidden the defect it pointed at. `FutureCache.call_count` was initialised to 0
  and incremented **nowhere**, so every `JobFunctionCache.call()` produced the same job id —
  the string every log line and contract message identifies a sample by; it is now
  incremented, and ids read `call 1`, `call 2`, …. And `clear_tag` on a cache-less
  `FutureCache` now logs a WARNING rather than returning silently: not crashing is right, but
  on a public path (`Bench.clear_tag_from_sample_cache`) "nothing happened" must not read as
  "the tag was cleared".

- **Flipping a composition direction lives on a two-member `Axis` type, so a partial flip
  is unrepresentable** (plan 23 P8, C6). `ComposeType.flip()` raised
  `RuntimeError("cannot flip this type")` on 2 of its 4 members, and that arm was reachable
  from the public `compose_method_list_for_dims(first_compose_method=...)` /
  `VideoSummaryResult.dataset_to_compose_list(first_compose_method=...)` — so a
  `sequence`/`overlay` seed aborted a 2+-dimensional video or rerun composition part-way
  through rendering, after the samples had already been collected. The new
  `bencher.Axis` (`right | down`) owns `flip()`, which is total over its two members;
  `ComposeType` keeps its four members and answers `as_axis() -> Axis | None`, so "has no
  opposite" is a value rather than an exception. `compose_method_list_for_dims` accepts
  either type and, for a seed with no axis, repeats it on every spatial level instead of
  failing. Every input the old implementation answered returns a byte-identical list — the
  test suite pins that against the pre-refactor algorithm.

- **Composition `match` statements over `ComposeType` are exhaustively checked**
  (plan 23 P8, C6). `ComposableContainerPanel.__post_init__` and
  `ComposableContainerDataset.render` had no final arm, so a fifth `ComposeType` member
  would have produced an `UnboundLocalError` three frames from the cause and a silent
  `None` composition respectively. Both now end in `assert_never`; verified empirically by
  seeding a fifth member and measuring `error[type-assertion-failure]` at all four match
  sites. `ComposableContainerRerun`'s two tables that had to stay exactly complementary
  (`_shares_one_view` and `_LAYOUT_CLASS_NAMES`) are merged into one exhaustive mapping
  onto a `_SharedViewLayout | _StackedViewLayout` sum, which makes "shares one view" and
  "has a stacking layout class" mutually exclusive by construction and retires the
  `Unsupported Rerun compose type` raise as unreachable. The four
  `bencher/results/composable_container/*` modules this touches join the strict `ty` list.

- `ComposableContainerPanel._tabs` is declared on the class instead of being created only
  by the `sequence` arm, and `append`/`render` read that one field rather than each
  re-deriving "am I a tab strip?" from `compose_method`.
  `ComposableContainerBase.label_formatter` is annotated `-> str | None` over
  `str | None` inputs, which is what it has always accepted and returned.

### Removed
- **Deleted the two plot-selection gates that could never fire: `vector_len` and
  `result_vars`** (plan 23 P6, C4; owner decision §6.1 resolved as *delete*). Both were
  declared on `PltCntCfg` *and* on `PlotFilter`, and both were read on every
  plot-selection pass (`PlotMatchesResult`) — but nothing in the package ever assigned
  the `PltCntCfg` side, so both always held their default `1` while every filter
  defaulted to `VarRange(1, 1)`. The gates therefore always passed and could not filter
  anything, including `surface_result`'s "exactly one scalar result" intent, which never
  actually held. `result_vars` had carried a `# todo remove` for some time.

  **What populating them instead would have done** (the analysis §6.1 required before
  deleting): with every filter left at the `VarRange(1, 1)` default, a correctly
  populated `vector_len` would have made *every* plot reject any sweep containing a
  `ResultVec(size > 1)`, and a correctly populated `result_vars` would have made every
  plot reject any sweep with more than one result variable — which describes most of the
  example corpus. Populating was the breaking option; deleting is the inert one, and
  `pixi run generate-examples` confirms the generated gallery is byte-identical.

  `BenchResultBase.filter()`'s `vector_len=` and `result_vars=` keyword parameters are
  removed with them. No caller in the tree passed either; a caller who did could only
  ever have used them to unconditionally *disable* a plot, since the counts they were
  compared against were frozen at `1`.

- **Deleted the dead setuptools files `setup.py`, `setup.cfg`, and `MANIFEST.in`** (plan
  03). The build has been hatchling via `pyproject.toml` for a long time, and
  `[tool.hatch.build] include` never shipped these three in the wheel or the sdist, so
  `pip install holobench` and `pip install -e .` are unaffected. They were leftovers from a
  ROS-era layout and actively misleading: `setup.py` declared the package name as `bencher`
  rather than `holobench` and listed a `package.xml` in `data_files` that does not exist in
  the repo. The only workflow this breaks is the legacy `python setup.py <cmd>` invocation,
  which has been unsupported since the move to hatchling. Verified by diffing a wheel built
  before and after the removal: the two contain an identical set of 400 files.
  `resource/bencher` (the empty ROS ament index marker that `setup.py` pointed at) is
  deliberately kept, and still ships in the wheel exactly as before.
- **`ComposableContainerPanel(horizontal=...)`**, which silently overwrote
  `compose_method` — and did so *inverted* relative to the rest of the codebase
  (`horizontal=True` meant a `pn.Column` here, while the same flag in
  `BenchResultBase._to_panes_da` selects a row). Two spellings of one concept that
  disagreed; only `compose_method` remains. No caller in the package used the kwarg
  (plan 23 P8, C6).

- **`ComposeType.flip()`** — superseded by `Axis.flip()`, see above. `ComposeType.as_axis()`
  converts, and `Axis.to_compose_type()` converts back.

- **BREAKING: dropped Python 3.10 support.** `requires-python` is now `>=3.11,<3.14`, and
  the CI matrix runs py311 + py313 (was py310 + py313). The `py310` pixi feature and
  environment are gone.

  The motivation is type-checking, not any runtime feature: `typing.assert_never` — the
  mechanism plan 23 uses to make `match` statements exhaustively checked by `ty` — is
  stdlib only from 3.11. On a 3.10 floor it required a `typing_extensions` dependency the
  repo had explicitly declined (`result_collector.py`), and the dependency-free
  workarounds were measured to silently degrade the check to a rule the repo ignores,
  giving false confidence. Raising the floor removes the dependency and the conflict.

  Two 3.10-era workarounds are now removable and are queued as plan 23 P1 cleanups:
  `typing.Self` in `ResultCollector.__enter__`, and the third-party `strenum` package.
  **`strenum` is deliberately retained for now** — stdlib `enum.StrEnum` is not a drop-in
  replacement, because `auto()` lowercases member names where `strenum` preserves them,
  which would silently change the values of `Executors` and `SampleOrder` and therefore
  which strings `BenchRunCfg(executor=...)` accepts. See plan 23 D4.

### Added
- **`bencher.WorkerReturnedNothingError`**, a narrow subclass of `WorkerContractError`
  meaning *the harness itself* determined a job produced no result (plan 23 P5). Only this
  subclass is exempt from `catch=`; a `WorkerContractError` raised by a **worker** — the
  class is public, so a worker or plugin can raise it, e.g. to signal a hard config error
  and abort with `catch=()` — is an ordinary sample fault and is routed through `catch=` as
  before. Without the split, a worker-raised `WorkerContractError` was silently tolerated on
  MULTIPROCESSING even with `catch=()` while still aborting on SERIAL: loud or silent chosen
  by the executor, which is the defect shape plan 23 B3 exists to eliminate. Existing
  `except WorkerContractError` handlers keep matching, by subclassing.

- **Single result-type registry: `RESULT_SPECS` in `bencher/variables/results.py`**
  (plan 23 P4). One ordered `{Result* class: ResultSpec}` mapping now declares each
  result type's kind, missing fill/sentinels, and family memberships (panel, media,
  data-var, multidim, scalar, reference-backed). The nine previously hand-maintained
  registries — `PANEL_TYPES`, `SCALAR_RESULT_TYPES`, `XARRAY_MULTIDIM_RESULT_TYPES`,
  `ALL_RESULT_TYPES`, `RESULT_KIND_ORDER`, `_REFERENCE_MISSING_TYPES`,
  `_OBJECT_MISSING_TYPES`, `DATA_VAR_RESULT_TYPES`, and `result_collector`'s
  `_MEDIA_RESULT_TYPES` — are derived from it under their existing names, so call
  sites are unchanged and no stored cell value or sentinel changes (no
  `CACHE_VERSION` bump). Adding a `Result*` class without a spec now fails CI with
  one clear message, and a parameter class defined in the results module but absent
  from the registry is refused at sweep-declaration time instead of silently
  classifying as an *input* variable. A6 phase 2 (the generalized rendering plan)
  is intended to derive its channel vocabulary from this registry. The deprecated
  `ResultVar` is exempt by declaration (`RESULT_SPEC_EXEMPT`) and resolves to
  `ResultFloat`'s spec; `ResultHmap` keeps its historical quirks (registered, but
  neither a data-var nor a panel type) rather than being "tidied". Membership of
  every derived tuple is unchanged, but iteration *order* now follows the registry's
  most-derived-first order (e.g. `SCALAR_RESULT_TYPES` is now `(ResultBool,
  ResultFloat)`); every in-repo consumer is an `isinstance()` check, so this is
  observable only to external code that indexes or orders on the re-exported tuples.
- **Content-addressed blob store: `bencher/blob_store.py`** (plan 22, phase 1 of the A6
  grammar-of-ND-data migration, #1021). Result payloads that cannot live directly in a
  dataset cell are serialized under `cachedir/blobs/` and named by the sha256 of their
  bytes, so identical payloads across repeats and time points deduplicate to one file.
  Dispatch is by payload type: `DataFrame` → `.parquet`, `Dataset` → `.nc`, `DataArray` →
  `.da.nc` (name preserved), `bytes` → `.bin`, anything else picklable → `.pkl`. The
  environment is netCDF3-only (scipy is the sole engine), which silently narrows int64 →
  int32 and raises on other dtypes, so an empirically-derived whitelist
  (`_NETCDF3_SAFE_DTYPES`) diverts unsafe payloads to pickle rather than let them
  round-trip with changed values. Every structured-format failure falls back to pickle with
  a logged warning: a payload inside the documented contract can never abort a sweep. The
  `.pkl` branch is the pickle surface plan A3 wants gone and is flagged as such in the
  module docstring.
- **`ResultDataSet` renders its full `over_time` history.** Because a cell is now
  meaningful in any process (see below), the pre-existing `isel(over_time=-1)` restriction
  is gone: the report shows a labelled per-time grid, one pane per snapshot under its
  timestamp, instead of only the latest run. Practical effect: a report over a long history
  gets *N* times wider — bound it with `max_time_events` on the result variable if that
  matters. Note that unlike an image or video, aging a dataset cell out of the history does
  not itself delete the payload: blobs are content-addressed, so the same file may still
  back a cell elsewhere in the cache. `max_time_events` bounds the *report*; reclaiming
  blob storage is a cache-management operation. Cells cached before this release render
  real content at the final time event and an explicit labelled placeholder at earlier
  ones, because the legacy payload list only ever held the final run's samples.
- **New gallery example `example_result_dataset_1d_over_time`** under
  `reference/meta/result_types/result_dataset/`; no existing example combined
  `ResultDataSet` with `over_time`.
- **Garbage collection for the blob store: `bn.clean_orphaned_blobs()`.** `cachedir/blobs/`
  previously grew until an explicit `clear_media()`/`clear_all()` wiped it whole; a nightly
  sweep whose payloads drift accumulated a file per distinct payload forever, since content
  addressing only deduplicates byte-identical ones. The new call reclaims exactly the files
  nothing references any more, and `dry_run=True` is the default:

  ```python
  bn.clean_orphaned_blobs()                                    # report only
  bn.clean_orphaned_blobs(dry_run=False)                        # reclaim
  bn.clean_orphaned_blobs(dry_run=False, extra_roots=["runs/"])  # protect saved results
  ```

  It returns `(orphan_paths, total_bytes)` like `clean_orphaned_media`, and
  `bn.print_orphaned_blobs()` prints the same report the way `print_cache_stats` does. Two
  pixi tasks wrap it: `pixi run cache-blob-orphans` (report) and `pixi run cache-blob-gc`
  (reclaim). `bn.blob_reachability()` exposes the live set on its own for auditing.

  The model is **reachability, not ownership**. A blob is content-addressed, so one file may
  back cells from many job keys, sweeps and `over_time` events at once — which is precisely
  why `cleanup_job_media`/`clean_orphaned_media` must never touch it and why their per-job
  model could not be reused. Instead, every blob name referenced from any dataset in the
  `benchmark_inputs` and `history` diskcaches is collected first, and only files outside
  that set are deleted. The `history` scan reads the *stored* record rather than the served
  projection, so a reference held only by an old `over_time` event, or by a dormant or
  retired column, still counts as live. Matching is on the blob's filename (which *is* its
  content hash), so a stored absolute path from a cachedir that has since moved still
  protects its payload. `sample_cache` is deliberately not a root: it holds what the worker
  returned, before materialization, so it cannot name a blob — and a payload still in it
  re-materializes to the same path on the next hit.

  Two limitations are explicit rather than papered over. **Results saved outside the cache
  are invisible**: nothing records where `bencher.render.save_result` wrote, so GC can strand
  a saved result's payloads (it still loads; its dataset cells render as placeholders). Pass
  the archive as `extra_roots=` to protect it. **A blob is primary storage, not a cache**:
  `cache_results` and `cache_samples` both default to `False`, so with the defaults nothing
  on disk references the blobs of a plain (non-`over_time`) sweep, and a stored history
  holds paths rather than payload copies. GC is therefore an offline maintenance step, as
  `clean_orphaned_media` already is. `min_age_seconds=` adds a grace period, and it covers
  both ways a concurrent sweep gains a reference: a blob it *wrote*, and an old blob it
  *deduplicated onto* — a content hit in `materialize_blob` refreshes the blob's mtime, so
  **a blob's mtime means "last referenced", not "created"** (pinned by
  `test_min_age_protects_a_new_reference_to_an_old_deduplicated_blob`; the bytes are still
  never rewritten on a hit). Size the window honestly: the guard holds when
  `min_age_seconds` exceeds the gap between a sweep materializing a payload and persisting
  the record that references it — in practice, your longest sweep's runtime — and the
  default `0` gives no protection at all. The deletion loop stats each blob immediately
  before its unlink, leaving only the syscall-instant between stat and unlink uncovered,
  so running GC with no sweep in flight remains the zero-assumption choice. There is
  deliberately no size- or age-based eviction of *referenced* blobs, because nothing could
  restore them. An unreadable cache entry makes
  absence-of-reference unprovable, so a corrupt cache collects **nothing** in either mode
  and warns with the offending entries named.

  Practical note on where the garbage actually comes from: a per-variable `max_time_events`
  limit ages an old `over_time` cell out by overwriting it with the missing-value sentinel,
  and `_null_old_entries` deliberately does *not* delete the file (a deduplicated blob may
  still back a live cell), so every aged-out payload was an immediate permanent leak before
  this change.

### Changed
- **A plot that fails to render now leaves a visible mark instead of vanishing.** Report
  building stays best-effort — one bad plot still never aborts a whole report — but the
  failure was previously recorded with `logger.exception` and nothing else. Loggers are off
  by default in library use, so a report could be written *missing whole plots* while every
  caller-visible signal still said success: no warning, a zero exit code, and an HTML file
  that looks complete unless you already know which plot should have been there.

  Each swallowed failure now leaves two marks: a `bencher.RenderFailedWarning`, so an
  embedding test runner (pytest's warnings summary, `-W error`) sees it without configuring
  logging; and a pane in the report naming what failed and why, so the gap is legible to
  whoever opens the HTML. The `logger` call is kept for callers already capturing it, though
  render-failure records now come from the `bencher.results.render_failure` logger rather
  than from each calling module's logger — code filtering on
  `bencher.results.bench_result` to catch plot failures should filter on the new name.

  Applied to every best-effort render site: plot plugins, legacy plot callbacks, and
  user-injected `extra_panels` in `to_auto`/`to_auto_plots`; regression overlays; and the
  optuna analysis plots, which previously hand-rolled their own differently-formatted
  failure pane and are now unified on the shared helper.

  Reports that were silently short will now show these panes. That is the point — but a
  caller whose test run cannot tolerate the new warning can silence that half of it (the
  report pane is not affected):

  ```python
  import warnings
  import bencher as bn
  warnings.filterwarnings("ignore", category=bn.RenderFailedWarning)
  ```

- **BREAKING: a `ResultDataSet` dataset cell holds a blob path string, not an index.**
  Cells were `int` indices into `BenchResult.dataset_list`, valid only inside the process
  that produced them; they are now absolute `str` paths into the blob store, so any process
  sharing the cache filesystem can render any sample. Code that introspects a result
  directly is affected — `res.to_dataset()["var"].values` and `res.to_pandas()` now yield
  `/…/cachedir/blobs/a1b2c3.parquet` where they yielded `0, 1, 2`. To recover the payload:

  ```python
  from bencher.blob_store import load_blob
  cell = res.to_dataset()["my_dataset_var"].sel(x=1.0).values.item()
  payload = load_blob(cell)   # was: res.dataset_list[int(cell)].obj
  ```

  Rendering is unaffected — every built-in render path goes through
  `BenchResultBase.ds_to_container`, which accepts both generations. `result_is_missing`
  accepts both sentinels (`"NAN"` and the legacy `-1`) permanently, since one mixed
  `over_time` history contains cells of each kind.
- **BREAKING: `BenchResult.dataset_list` is now always empty.** It survives as the read
  path for results collected before this release and is scheduled for removal with phase 3.
  Nothing in bencher's own examples, docs, or exports used it, but code that did
  (`res.dataset_list[i].obj`) now sees an empty list rather than an error at the point of
  change — use `load_blob` on the cell as shown above.
- **`clear_media()` now also clears `cachedir/blobs/`, and `cache_stats()` counts it.**
  The blob store is tracked as a third cache category (`_CONTENT_FOLDERS`) rather than as
  media, because `_MEDIA_FOLDERS` means "contains per-job-key subdirectories" and that
  layout is what makes per-job and orphan cleanup safe — a deduplicated blob may back cells
  belonging to many job keys, so `cleanup_job_media` and `clean_orphaned_media` must never
  touch it, and they don't. A cell whose blob was cleared renders as a placeholder, exactly
  as a cell whose image was cleared does. `CacheStats` gained a `content` field (defaulted,
  so existing construction is unaffected) and `cache_stats().total_bytes` now includes
  blobs, so totals are not comparable across this release.
- **A `plot_callback` may now be offered a `legacy_trusted=` keyword.** The `over_time`
  dataset path needs to tell the render layer "a legacy index at this time point cannot be
  trusted". Since `plot_callback` is a public extension point that a caller may satisfy with
  a plain `(dataset, result_var)` function, the keyword is passed *only* to callbacks that
  declare it or carry `**kwargs`; a stricter callback is called exactly as before instead of
  raising `TypeError`. Every callback in bencher declares `**kwargs`, so nothing internal
  changes. `ds_to_container` gained the parameter with a default, so overrides written
  against the old signature keep working.
- **No `CACHE_VERSION` bump** (stays `5`), so an existing `cachedir` is *not* wiped by this
  release. Pre-existing sample-cache entries re-materialize into blobs on a cache hit;
  stored `over_time` histories merge (the int64 column and the new object column concat to
  object, and legacy cells survive intact); results saved with `save_result` still load.
  Old data degrades honestly where it cannot support the new capability rather than failing.

### Deprecated
- **`ResultHmap` is deprecated** and now emits a `DeprecationWarning` on instantiation;
  removal is scheduled for a later phase of the A6 migration. Its data lives out-of-band in
  `bench_res.hmaps` rather than in the canonical result dataset, so it cannot participate in
  the grammar-of-ND-data model. Use `ResultContainer`, or `ResultReference` with a declared
  `container=`, instead. Behavior and `hash_persistent()` are unchanged until removal. Note
  for downstream code: this breaks builds that run with `-W error::DeprecationWarning` or
  pytest `filterwarnings = error`. **Known follow-up:** bencher's own
  `bencher/example/meta/example_meta.py` still declares a `ResultHmap`, so the flagship
  meta example warns about itself; migrating it changes generated gallery output and was
  deliberately left out of #1021.

### Notes
- **`cachedir/blobs/` is garbage-collected by reachability, never per job key.** Reclaiming
  it per job key is impossible by design (one blob, many owners), so `clean_orphaned_blobs()`
  above deletes only what no live reference names — see that entry for the roots it scans and
  the two cases it cannot see. What it does *not* do is bound the store's size: blobs that
  are still referenced are never evicted, because with `cache_results`/`cache_samples`
  defaulting to `False` and a stored history holding paths rather than payloads, there is
  nothing to restore them from. Capping growth still means `max_time_events` plus a GC run,
  or the artifact manifest A4 owns.
- Blob filenames use the first 16 hex chars (64 bits) of the sha256, so two *different*
  payloads sharing that prefix would collide and the second would load back as the first.
  The birthday bound puts even odds at ~2^32 blobs in one cache directory, so the risk is
  accepted rather than mitigated; `_HASH_CHARS` can be raised without invalidating existing
  blobs, since `load_blob` dispatches on extension rather than name length.

## [1.117.0] - 2026-07-31

### Added
- **Stable benchmark series identity: `plot_sweep(series_id=...)`** (plan 15, #1012).
  Names the over_time *trend* a benchmark appends to, independently of what identifies its
  configuration: `tag` partitions storage, `series_id` names the trend. Deliberately not
  part of `hash_persistent`, so declaring one re-keys nothing — it exists so a trend
  survives a worker rename or a move between modules.
- **Inspectable, pinnable benchmark identity: `bn.sweep_identity()`, `bn.identity_of()`,
  `bn.diff_identities()`** (plan 16, #1010). Returns the exact cache/history keys a
  declaration resolves to *without running it*, taking `plot_sweep`'s declarative arguments
  with the same spellings; diff two identities to see precisely which field moved a key.
  Pairs with `SweepSpec`: `bn.sweep_identity(**spec.bind(W), worker=W)`.
- **`bn.ComposableContainerRerun` — compose rerun recordings** (#1007). Combines complete
  `.rrd` recordings right/down/sequence/overlay into one recording plus a generated
  Blueprint, from inside `benchmark()`; the composition itself renders to a `.rrd`, so
  nesting is plain recursion.
- **`rerun_summary` / `rerun_grid` — merge a whole sweep's rerun recordings into one
  viewer** (#1017). Sweeping a `ResultRerun` previously embedded one wasm web viewer per
  sample (blank past ~16 due to browser WebGL context limits, nothing comparable across
  iframes). These walk the result dataset and merge every sample's cached `.rrd` into a
  single recording — `rerun_summary` on one shared timeline, `rerun_grid` laid out in
  space with `compose_method_list=` control. Named-only (opt-in) like `video_summary`.
  The dimension-ordering policy is extracted to `compose_method_list_for_dims()` so the
  video and rerun summary renderers share it.
- **Single-point sweep ranges** (plan 17, #1001). `with_bounds` and `bn.sweep` accept
  `low == high`, yielding exactly one sample (previously: a raise, or N linspace copies /
  an empty arange if the guard had simply been relaxed). `samples > 1` over a zero-width
  range raises at declaration, and `bn.sweep` validates an inverted range at construction
  instead of mid-run. `bounds=(x, x)` and `values=[x]` keep deliberately distinct
  identities.
- **Unnamed parameters are rejected at resolution time** (plan 19, #1003). A variable
  declared on a plain (non-`Parameterized`) mixin registers with `param.name=None` and
  used to fail far from the declaration (a `KeyError` in result storage, or a bare
  `ValueError` from param, depending on param version). Resolution now raises a
  `TypeError` naming the metaclass cause and the remedy; parameter objects built by
  `bn.box()`/`bn.sweep()` are unaffected.
- **`bn.SweepSpec` — a sweep declaration as a value (plan 18, phase 1).** A frozen record
  of `plot_sweep`'s seven declarative arguments (title, descriptions, input/result/const
  vars, tag) that can be built once, composed (`with_`, `plus_input_vars`,
  `plus_result_vars`, `merge`), compared (`bn.diff_specs`), pickled, and bound to any
  worker: `bench.plot_sweep(**spec.bind(Worker))`. `bind(worker)` checks every by-name
  variable up front and runs the duplicate-variable validation at bind time, where the
  composition that caused a duplicate is in view. Run configuration (`repeats`, `run_cfg`,
  `plot_callbacks`, …) is deliberately absent — a spec states what is measured, not how the
  run is driven — and a callable in any field is rejected at construction. Purely additive:
  every existing `plot_sweep` call is unchanged.
- **Per-sample fault tolerance on the sweep path: `catch=` and `fail_on_sample_error`.**
  `Bench.optimize(catch=...)` has had this knob since #962, so the same benchmark was
  fault-tolerant when driven by Optuna and all-or-nothing when swept. `catch` lives on
  `BenchRunCfg` (so `bn.run(catch=...)` works, and it reaches `plot_sweep` via `run_cfg` —
  its one home); a bare exception type is accepted and wrapped. A caught sample leaves the missing-value sentinel
  at its coordinate — `setup_dataset` already fills every result variable, so the dataset
  shape is unchanged and reductions skip it — is logged at WARNING with its inputs, and
  writes **nothing** to the sample cache, so a transient flake cannot become a permanent
  cached failure. Default `()` is fail-fast, exactly as before, and tolerating a failure
  moves no cache key.

  `fail_on_sample_error: bool | float` is the other half, and the two are a pair rather than
  independent knobs: `catch` alone turns real breakage into a green run over an all-sentinel
  dataset. `True` fails the run if any sample was caught; a float in (0, 1] fails when the
  failed *fraction* reaches it, measured over samples the run actually **executed** — a cache
  hit never reached the worker, so counting it would make one threshold mean different things
  on a cold and a warm cache. The raise happens after the dataset and report are assembled,
  so the partial results survive it, and only for a run that actually sampled: on a
  benchmark-result cache hit the loaded result carries a *previous* run's counts, which are
  not this run's errors. Both knobs are validated before sampling starts, so a typo'd
  threshold costs milliseconds rather than a whole sweep.

  Inspect failures via `BenchResult.failed_samples` (a `SampleFailure` per caught sample:
  job id, inputs, exception repr, traceback), `n_failed`, and `failed_fraction`.

### Removed
- **`ResultVolume` is gone.** It was declarable but not usable: exported from
  `bencher/__init__.py` and listed in `ALL_RESULT_TYPES`/`RESULT_KIND_ORDER`, but absent
  from every registry that decides how a sample is *stored*. Putting one in `result_vars`
  raised `KeyError: No variable named '<name>'` in `precompute_result_arrays` — the type
  got no data variable, yet the collector indexed one anyway — and had it survived that,
  the store loop's `else` raised `TypeError: Unsupported result type`. Since no working
  code could have used it, removal is only nominally an API break. Note that
  `VolumeResult` (`bencher/results/volume_result.py`), the 3-float-input volume *plot*, is
  unrelated and unaffected — it renders `ResultFloat`.

  A new `TestEveryResultTypeIsStorable` pins the invariant that made this a trap:
  membership in `ALL_RESULT_TYPES` now implies the collector has a branch to store the
  type, and that `result_kind` classifies it as something other than `"unknown"`.
  `ResultHmap` is the one exemption, collected out-of-band via `result_hmaps`.

### Changed
- **A `ResultReference` container is now called with the object alone.** It was called as
  `container(obj, **kwargs)`, so the render kwargs every path adds (`override`,
  `agg_over_dims`, `pane_layout`, and the `width`/`height` that `set_plot_size` injects from
  `bench_cfg.plot_size`) leaked into a callback that
  only ever wanted the object, and a single-argument renderer raised `TypeError`. It now
  matches the `ResultDataSet` contract, so one renderer works for both. Breaking only for a
  callback that *relied* on receiving those keywords; nothing in bencher did. The
  `container=` a renderer passes to `to_panes` is a separate contract — a panel pane
  constructor, still called with `styles=` and the layout keywords — and is unchanged.
- **Intra-sample chart gallery examples now declare their container** rather than appending
  a report-level plot. `res.to(XYCurveResult, ...)` and friends *add* a plot below whatever
  `plot_sweep` already rendered, which for a `ResultDataSet` with no declared container is
  the raw table — so the example showed the rows and the chart. Declaring
  `container=bn.xy_curve(...)` puts the chart in the result's own position instead, which is
  what `example_plot_xy_scatter` already did. Affects `example_plot_xy_curve`,
  `example_plot_xy_histogram` and `example_plot_xy_hexbin`; the chart-type route is
  unchanged and still covered by tests.
- **`DataSetResult` now renders `ResultDataSet` results only.** It previously claimed every
  pane-type result, which made `bench.add(bn.DataSetResult)` / `plot_list=["dataset"]` a
  second name for the `panes` view on a sweep with no stored payload. Now that
  `ResultDataSet` is a generic payload store, a `container=` written for a payload must not
  be handed an unrelated result's value, so the view returns `None` for such a sweep instead
  of falling back. Use the `panes` view (`res.to_panes()`, or the default report) for
  image/video/string/reference results — it is unchanged, and both views share one render
  path (`BenchResultBase.map_sample_panes`).
- **Logging now goes through per-module loggers.** Every module logs via
  `logging.getLogger(__name__)` instead of calling `logging.info()` and friends on the
  root logger, so bencher's output can be configured and filtered per module (e.g.
  `logging.getLogger("bencher.job").setLevel(logging.DEBUG)`) without touching root.
  Records now carry their originating `bencher.*` logger name; anything that filtered
  bencher output by root-handler side effects should key off the logger name instead.
- **Dev toolchain: ruff 0.16.** Bumped the ruff pin to `<=0.16.0` (and the ruff-format
  prek hook to `v0.16.0`), which expands ruff's default rule set from `E4/E7/E9/F` to
  roughly 413 rules. Lint debt surfaced by the wider defaults is fixed; `DTZ001`/`DTZ005`
  (naive datetimes) and `RUF023` (unsorted `__slots__`) are ignored in `ruff.toml` with
  rationale — the `over_time` axis is a timezone-naive `datetime64` coordinate, and
  `__slots__` order feeds `hash_persistent()`. The formatter is scoped away from markdown,
  which 0.16 newly formats. Example generation now runs `ruff check --fix-only` alongside
  `ruff format`, so regenerated examples stay lint-clean. No runtime behavior change.

### Fixed
- **A container declared on a `ResultRerun` now applies with `over_time` history too.**
  With history off, a rerun result renders through `ds_to_container`, where a declared
  container wins over the type's built-in viewer. With history on and more than one time
  point, rendering is routed to `_pane_over_time_grid` instead — a separate path that
  hardcoded `rrd_file_to_pane`, so the same benchmark honoured its declared renderer on
  the first run and silently fell back to the rerun viewer on every run after. The grid
  now resolves the declared container the same way, and only imports the rerun viewer
  stack when it is the renderer actually being used. `ResultVideo`/`ResultImage` take the
  matching `_pane_over_time_slider` path but have no container slot to honour, so they are
  unaffected.
- **A variable declared twice in one sweep is now rejected or normalised, instead of quietly
  moving the cache and history key.** ⚠️ *This moves the key for affected benchmarks — see
  below.* `plot_sweep` converted each list positionally with no uniqueness check, and the
  three kinds of variable each misbehaved differently:

  `result_vars=["y", "y"]` was the damaging one. It produced a dataset **byte-identical** to
  `result_vars=["y"]` under a **different** key: `ResultCollector.setup_dataset` builds
  `data_vars` as a dict keyed by name and `bencher.history` keys its per-column metadata the
  same way, so the repeat collapsed in the data, while `BenchCfg.hash_persistent` folded the
  per-variable digests as a sorted *tuple* and so hashed it twice. The benchmark ran,
  reported correct numbers, and appended to a different trend line than the one it appeared
  to belong to — with nothing in the run saying so. The duplicate is now dropped (first
  occurrence kept) with a `UserWarning` naming the variable and both positions.

  `input_vars=["x", "x"]` was accepted and then either collapsed to a single dimension or
  died inside xarray with `broadcasting cannot handle duplicate dimensions`, depending on
  the sweep's shape — after the whole sweep had run. It now raises a `ValueError` at
  declaration time, naming the variable and every position.

  `const_vars` behaved differently depending on spelling: the dict form collapsed duplicates
  before bencher saw them, while the list-of-pairs form accepted a repeat with two
  *different* values and let iteration order pick the winner. Repeats with equal values are
  now deduped silently; conflicting values raise, naming both.

  Validation happens once, in `validate_declared_vars`, called from `plot_sweep` after
  conversion so comparison is on resolved names and every declaration form — string, spec
  dict, param object, and mixtures — is covered by the same code.

  Separately, `hash_persistent` now folds result and const digests as **sets** rather than
  sorted tuples. Its docstring already promised they contribute as an "unordered set", but a
  sorted tuple delivered only the ordering half of that; uniqueness was missing, which is
  the mechanism behind the bug above. This keeps identity correct on paths that never reach
  the validator, such as a `BenchCfg` built or deserialized directly.

  **Migration:** only benchmarks that *currently declare an overlapping result variable* are
  affected, and they are exactly the ones now emitting the new warning. Their key moves onto
  the key it would have had if declared correctly, so in the common case the benchmark
  rejoins the trend it should have been on all along; in the worst case it starts a fresh
  series, and `on_history_reset` controls how loudly that surfaces. Configurations without a
  duplicate are bit-identical: every golden hash in `test/test_hash_persistent.py` is
  unchanged, since `sorted(set(xs)) == sorted(xs)` when `xs` is already unique.
- **`hover=False` on an intra-sample chart now actually disables hover.** `set_default_opts`
  registers `tools=["hover"]` as a global holoviews default for most element types, so a
  spec that merely omitted the key got hover back and the option was a silent no-op.
  `tools` is now set in both directions (`[]` when off). Passing `tools=` through `**opts`
  still wins, as it is applied last.
- **A `ResultDataSet` renders on every run, not only the first.** With `over_time` and
  more than one event in the history, a stored payload reached `ds_to_container` with
  `over_time` still a live dimension: `_to_panes_da` drops `over_time` from the pane
  recursion so hvplot can use groupby, and the branch that rebuilds it for pane-type
  results only covered `ResultVideo`/`ResultImage`/`ResultRerun`. The render then died in
  `zero_dim_da_to_val` with `ValueError: Dimension over_time already exists` (no input
  vars) or, once another dimension was consumed first, in the `dataset_list` lookup with
  `TypeError: only integer scalar arrays can be converted to a scalar index` — one cause,
  two signatures, and via `to_auto` the traceback was swallowed and the plot silently
  vanished from the report. A `ResultDataSet` now renders the current event: its cells
  hold indices into `dataset_list`, which is rebuilt from the samples of the run doing the
  rendering, so the indices merged in from history address *this* run's list and a slider
  across the events would show the current payload under every past run's label. Scalar
  results keep their full `over_time` series. Two supporting hardenings: a length-1
  dimension on a point now collapses to a value instead of a one-element array, and
  `ds_to_container` names the result variable and the dimension that was not reduced
  rather than indexing a list with an array several frames later.

### Added
- **`container=` extended to the remaining renderable result types.** `ResultString`,
  `ResultPath` and `ResultContainer` (and so `ResultRerun`, which subclasses it) now take
  the same declared-renderer slot `ResultDataSet` and `ResultReference` have, and a
  declared container **beats the type's built-in `to_container()`**. A `ResultPath` can
  therefore render a file's *contents* — a CSV as a chart, a JSON as a tree — where before
  it was always a download widget, and a `ResultString` can render as Markdown or
  highlighted code instead of plain text. `ResultReference` also honours a container
  declared on the class, not just one attached to a sample; previously a class-level one
  was silently ignored because only the stored sample was consulted. Precedence is uniform:
  renderer-supplied, then the sample's, then the class's, then the type's default. Every new
  slot is in `_hash_exclude`, so declaring a renderer leaves cache keys and `over_time`
  history series byte-identical. The resolution itself is now one helper,
  `BenchResultBase.declared_container`, rather than being open-coded per type.

  Not extended to `ResultVolume`: it has no render path at all (nothing dispatches on it —
  `VolumeResult` plots `ResultFloat` over three float inputs, and `ResultVolume` is absent
  from `PANEL_TYPES`), so a container slot there would be an option that never fires.
- **`xy_histogram` chart type** — bins one or more measured columns of a `ResultDataSet`,
  showing the distribution a single sample measured. Distinct from the existing
  `histogram`, which bins a `ResultFloat` across the sweep and so shows the spread of the
  repeats. `column=` takes a list to overlay several distributions, binned over a *shared*
  range so they are actually comparable, and drawn translucent so the one underneath stays
  readable; it defaults to every numeric column. `density=True` normalises instead of
  counting, and the y axis is labelled accordingly. An empty or all-NaN column produces
  empty bins rather than raising — numpy cannot pick a range for an empty array, and NaN is
  how bencher marks a sample missing, so NaN rows are dropped rather than poisoning the
  range. Gallery example: `example_plot_xy_histogram`.
- **`xy_hexbin` chart type** — the density counterpart to `xy_scatter`, taking the same
  axes and binning them into hexagonal tiles. For a cloud of tens of thousands of points
  the markers saturate and where the mass actually is becomes the thing a scatter cannot
  show. `gridsize=` sets the resolution, `min_count=1` drops empty tiles, and the colourbar
  is on by default since a density plot without one shows shape but no magnitude. Gallery
  example: `example_plot_xy_hexbin`.
- **`hv.HexTiles` now carries the shared default figure size.** It was absent from
  `HoloviewResult.DEFAULT_SIZED_ELEMENTS`, so a hexbin would have fallen back to the
  holoviews default rather than bencher's 600x600 — the same gap Histogram/Area/ErrorBars
  were fixed for previously.
- **`xy_curve` chart type** — draws one or more *measured* columns of a `ResultDataSet`
  against an x column, for a benchmark that collects a whole series as one sample. The
  gap it fills: `curve` and `line` plot *across* the sweep, with one value per sample, so
  they cannot show a series that lives inside one. Available the same two ways as
  `xy_scatter`: `bn.xy_curve(x="time", y="signal")` returns a picklable spec usable as a
  `ResultDataSet(container=...)`, and `XYCurveResult` is registered as a **named-only**
  chart type. `y=` takes a list to overlay several series with a legend, `markers=True`
  adds a marker per row for a sparse series, and `sort=False` keeps the frame's row order
  so a trajectory that doubles back in x is drawn as travelled rather than sorted into a
  function of x. Gallery example: `example_plot_xy_curve`.
- **A named DataFrame index is now plottable as a column.** `Dataset.to_pandas()` — the
  idiomatic way to build a `ResultDataSet` from xarray — leaves the dimension coordinate
  in the index and only the data variables in the columns, so the x axis was unreachable
  by any chart and inference saw a single-column frame. `to_dataframe` now promotes named
  index levels to columns, at the front so inference finds the x axis first. An unnamed
  `RangeIndex` is row position rather than data and is left alone; a level whose name is
  already a column keeps its values and loses its name, since pandas rejects a label that
  is both an index level and a column as ambiguous. The `ResultDataSet` gallery examples
  (`example_result_dataset_1d`/`_2d`) and `BenchableDataSetResult` now declare an
  `xy_curve` container, so they show the collected series as a curve rather than as a
  table of raw rows.
- **Generic per-sample data rendering, with tabular handling kept at the edge.**
  `BenchResultBase.map_sample_panes` is the single operation that retrieves each stored
  sample and optionally maps a renderer over it; it neither checks nor converts the payload
  type, and takes the result types it claims as a parameter. Both per-sample views now go
  through it — `PaneResult.to_panes` (every pane type, and the path the default report
  takes) and `render_data_samples` (`ResultDataSet` only) — so a fix to the render path
  reaches the report and the chart types alike. `XYScatterResult` composes
  `render_data_samples` instead of introducing a parallel result hierarchy. The opt-in
  `holoview_results/tabular_spec.py` module only contains renderer-side concerns:
  `TabularSpec`, a frozen (therefore picklable) dataclass whose `__call__` coerces
  supported table-like data to a DataFrame, shared HoloViews options, and column helpers
  (`to_dataframe`, `check_column`, `resolve_axes`, `plot_frame`, `value_columns`).
  `TabularSpec` is exported as `bn.TabularSpec`, since writing a new chart type is what it
  is for. Column-validation errors name the chart that rejected the column, for every
  column a chart plots — including the ones a chart *option* implies (`color=`), which
  `value_columns` validates rather than letting them reach pandas as a bare `KeyError`.
  Chart types keep
  naming their options explicitly rather than accepting `**kwargs`: `**kwargs` belongs
  to `map_plot_panes`, and a signature-based split could not tell a pane-sizing `width`
  from a HoloViews style `width`.
- **`xy_scatter` chart type** — scatters two *measured* columns of a `ResultDataSet`
  against each other, for results whose rows are the measurement (landing points, hit
  locations, a phase-space cloud). Distinct from the existing `scatter`, which puts an
  input variable on x and a result variable on y; here both axes come from inside one
  sample and the sweep dimensions separate one plot from the next. Available two ways
  from one implementation: `bn.xy_scatter(x=..., y=..., color=..., data_aspect=1)`
  returns a picklable spec usable as a `ResultDataSet(container=...)`, so the cloud
  renders in `result_vars` order with the other results; and `XYScatterResult` is
  registered as a **named-only** chart type (`bench.add(bn.XYScatterResult, x=..., y=...)`
  or `to_auto(plot_list=["xy_scatter"], ...)`), so no existing report gains a plot it
  did not ask for. Columns are validated against the frame — a typo names the available
  columns instead of rendering nothing — x/y are inferred from the numeric columns when
  omitted, `data_aspect=1` gives the equal-aspect scaling a position cloud needs, and
  DataFrame / xarray / `hv.Dataset` objects are all accepted. The
  `example_plot_xy_scatter` gallery declares this renderer on its result, so the default
  report contains the scatter in place of the raw table rather than appending both.
- **`ResultDataSet(container=...)`** — `ResultDataSet` is a generic per-sample store for
  any picklable Python payload, with no DataFrame/xarray requirement. It can declare how
  the payload renders, the way `ResultReference` already could. The callback takes the
  stored object and returns anything Panel can display, so domain data shows up as the
  view it means, *in `result_vars` order* with the rest of the results.
  Precedence: a container passed to a renderer wins, then one attached to the stored
  sample (`ResultDataSet(data, container=...)` inside `benchmark()`), then the one declared
  on the class. The callback is invoked with the object alone (no plot kwargs), so
  single-argument callables are safe. An explicit
  `bench.add(bn.DataSetResult, container=...)` view still appends to the end of the report
  and cannot sit among the other result variables. `container` is in
  `_hash_exclude`, so declaring one does not change any cache key. A declared container
  rides in `BenchCfg` into the result cache and the collect/render split, so it must be
  picklable — a module-level function or a callable object, not a lambda.
- **Plot-selection signature enrichment** (A2 Phase S1): `PltCntCfg` gains additive, cheaply-computed facts alongside the existing counts — `has_time`/`time_steps` (temporal axis presence and length), `result_kinds` (result-variable name → coarse serializable kind, via the new `result_kind` / `RESULT_KIND_ORDER` in `bencher.variables.results`), `cat_levels` (levels per categorical input), and `samples_per_point` (min repeat count actually present at the latest time step, missing-sentinel-aware per result type, vs the configured `repeats`). `generate_plt_cnt_cfg` takes an optional dataset for the data-derived facts, `PltCntCfg.__str__` includes the new fields, and the aggregation plotting path carries them through. No selection behavior changes.

## [1.116.0] - 2026-07-11

### Changed — cache-busting release (`CACHE_VERSION` 4 → 5)

Every benchmark-level and `over_time` history cache key changes in this
release: expect a one-time cache miss and a fresh history series per the
standing cache policy (no migration of old entries). Implements plans 09 and
14 (`plans/09-result-cache-invalidation.md`,
`plans/14-history-schema-reconciliation.md`).

- **`BenchCfg.hash_persistent` composition** (plan 09):
  - `result_vars` and `const_vars` now contribute as an *unordered set* —
    reordering either no longer resets caches or history (D1).
  - Every per-variable identity (input, result, const) now includes the
    variable's **name** — renaming a variable is a detected identity change
    instead of a silent history split or phantom-dimension broadcast (D2).
- **`over_time` history survives result-variable changes** (plan 14): the
  history cache is keyed *without* result vars
  (`hash_persistent(True, include_result_vars=False)`) and stores a superset
  record of every column ever measured. At load time, columns are reconciled
  per identity `(name, class, units, meaning_version)` — added columns are
  NaN-backfilled and birth-stamped, removed columns go dormant (retained,
  invisible, resumed on return), redefined columns are retired under a mangled
  name and restart — and consumers receive a projection onto exactly the
  current config's columns. The benchmark-level result cache stays strict.

### Added

- **`meaning_version`** on `ResultFloat`/`ResultBool` — bump it when a metric
  keeps its name but changes meaning; that column's history and regression
  baseline restart cleanly while every other column continues.
- **`BenchRunCfg.on_history_reset`** (`"warn"` default / `"error"` /
  `"ignore"`) — loss-y history events (full reset with a named diff and
  orphaned-event count via a per-benchmark last-seen index, column dormant,
  column retired, incompatible history discarded) are logged, raised
  (`bencher.HistoryResetError`, before any state is persisted), or suppressed.
  Pre-record (bare-dataset) history entries participate in the same lifecycle:
  a column they carry that leaves the config is reported dormant, and it
  resumes rather than restarts when it returns.
- **`BenchRunCfg.regression_min_history`** (default 1 = previous behavior) —
  regressions on a baseline younger than N points since the column's birth are
  reported and exported (`young_baseline: true` in `result.json`,
  `RegressionReport.has_blocking_regressions`) but never trigger
  `regression_fail`; history-free `absolute` checks still gate. Per-variable
  override via a `min_history` key in `regression_overrides`. Young rows are
  marked notify-only (†) in the rendered regression report, the scorecard
  shows them as uncolored trend cells, and the exported report JSON carries a
  top-level `has_blocking_regressions`.

## [1.115.0] - 2026-07-11

### Added
- **`BenchResult.explain_selection()` / `PluginRegistry.explain()`** (A2 Phase S2): the full plot-selection decision table — one row per registered plugin, chosen entries first, each rejected entry carrying the first gate that dropped it (named-only, not in `plot_list`, excluded, missing capability, shape-filter mismatch, superseded backend resolution). `select()` is now exactly the chosen subset of `explain()`, so the table is the authoritative record of why a plot did or did not appear.
- **Scorecard orientation toggle** — each category's table can now be read two ways, switched by a control in the page header (the choice persists via `localStorage`). The default *metric across benchmarks* view is unchanged (one column per metric, one row per benchmark); the new *metrics within benchmark* view transposes it (one column per benchmark, one row per metric) so a benchmark's metrics stack with their sparkline time axes aligned. Both orientations are rendered from a single set of per-benchmark cells through one shared cell macro; the switch is pure show/hide of the pre-rendered tables, so it needs no data round-trip.

## [1.114.0] - 2026-07-06

### Added
- **Every result type is now addressable by name in `to_auto`** (A1 Phase 3). New *named-only* plugin concept: plugins with `auto=False` never appear in automatic selection but are selected when explicitly named via `plot_list`/`include`/`only` (`@bencher.plot_plugin(..., auto=False)`; the attribute is optional on the `PlotPlugin` protocol, read with a `getattr` default, so existing plugins are unaffected). The non-default built-ins register this way: `violin`, `scatter_jitter`, `scatter`, `band`, `table` (holoviews); `tabulator`, `dataset`, `video_summary` (panel); `surface` (plotly — only where a plot already required it, like `volume`); and `rerun` as its own first-class backend (the rerun SDK is imported lazily inside the renderer, so registration is safe without it installed). **Default report output is unchanged** (parity tests unaffected); e.g. `res.to_auto(plot_list=["violin"])` now works by name.
- `LegacyResultPlugin.render` filters the ride-along kwargs (`override`, plot size) to the callback's signature when the renderer has no `**kwargs` (e.g. `RerunResult.to_rerun`), instead of failing with a `TypeError`.
- `TableResult` and `TabulatorResult` joined `BenchResult`'s base list: named-only callbacks are unbound methods invoked on the live `BenchResult`, and `TabulatorResult.to_plot` (via `self.to_tabulator`) crashed with `AttributeError` without it.

## [1.113.1] - 2026-07-06

### Dependencies
- Bumped `rerun-sdk` and `rerun-notebook` upper bounds to `0.34.0`.
- Bumped upper bounds on `holoviews` (`1.23.1`), `numpy` (`2.5.1`), `scikit-learn` (`1.9.0`), and `matplotlib` (`3.11.0`).
- Bumped dev/test upper bounds on `hypothesis` (`6.156.1`), `coverage` (`7.15.0`), and `ty` (`0.0.56`).

## [1.113.0] - 2026-07-04

### Added
- **Benchmark health scorecard** (`bencher.scorecard`) — renders a set of benchmark result summaries into a single grouped HTML page where every scalar metric shows a regression verdict and a noise sparkline, so run-to-run trends are visible without opening each benchmark's full report.
  - `generate_scorecard(reports_dir, config, *, chrome, output_name)` walks `<reports_dir>/<layout.root>/<tag>/*.summary.json`, groups benchmarks by category, builds one row per benchmark and one column per (aliased) scalar metric, and writes the page. Benchmarks with only image reports are listed as plain links so they stay reachable.
  - Everything project-specific is injected via `ScorecardConfig`: the `tag -> (category, name, description)` registry, metric-name `aliases` (so equivalent metrics from different benchmarks share a column), `percent_metrics` (0..1 fractions shown as percentages), and the on-disk `ReportLayout`. Every field defaults, so the zero-config path still renders. Optional `Chrome` supplies page title, provenance, and CI nav links.
  - Cell verdicts reuse the core 3-state regression verdict and add a presentation-level split: a gated metric that didn't move renders `passed`, an ungated metric renders `trend` (uncolored, with a self-computed latest-vs-previous delta). Each cell also shows the μ mean of its series.
- **`sparkline_svg(means, stds)`** (`bencher.sparkline`) — a responsive inline-SVG sparkline: a ±std noise band, a mean line, a node per run, and a right-margin distribution column (one alpha-blended dot per run collapsed onto the value axis, so run-to-run spread and bimodality the line hides read as density). Pure-numeric input (safe to embed unescaped); `preserveAspectRatio="none"` + non-scaling strokes let CSS stretch it to any width. Uncolored — the caller (e.g. a verdict-colored cell background) owns any color.
- **`result_to_dict(bench_res, *, include_series=True)`** (and `result_to_json`, plus the new public `series_for_var`) — attaches a per-time-event `mean`/`std`/`n` series to each scalar metric when the result carries an `over_time` axis. Off by default, so the base contract stays byte-stable; this is the trend the scorecard sparklines render.
- **Scorecard example + docs page** — `bencher.example.example_scorecard` fabricates benchmark summaries across distribution archetypes (stable, low/high noise, improving, regressing, ungated trend, step change, converging/expanding noise, outlier spike, first run) plus a config-options showcase (aliases, percent metrics, chrome), so the rendering can be evaluated in isolation. Rendered into the docs (`docs/scorecard.md`) with the live page embedded.

### Dependencies
- Added `jinja2` (already present transitively via panel/bokeh) — used to render the scorecard template shipped as package data.

## [1.112.0] - 2026-07-02

### Added
- **`BenchRunCfg.regression_overrides`** — per-variable regression specs. Maps result-variable name → a `{method: threshold}` dict drawn from `percentage` / `adaptive` / `delta` / `absolute`, or a bare number as shorthand for `{'absolute': value}` (a hard directional limit: minimize = ceiling, maximize = floor).
  - A listed variable is checked by exactly the methods in its spec **instead of** the benchmark-wide `regression_method`, so a threshold can be loosened *or* tightened per variable; an explicit `{}` opts a variable out of detection. Unlisted variables keep the benchmark-wide method, and names matching no result variable are skipped, so one override map can be shared across benchmarks.
  - Multiple entries run as independent checks — `{'percentage': 15.0, 'absolute': 1.0}` tracks the trend and holds a hard floor. `absolute` checks need no history and fire from the very first recording; the other methods skip until history exists.
  - Adaptive overrides: the threshold is the MAD limit (the dual-band percent gate still comes from `regression_percentage`); while history is too sparse for MAD the check skips instead of falling back to a percentage check, so a listed variable is never judged by a knob outside its spec.
  - Malformed specs never crash a run: unknown method keys and non-finite/bool thresholds are dropped with a warning, and a spec left with no valid checks keeps the benchmark-wide method (a typo can't silently disable detection). Bare-number shorthand accepts numpy scalars.
  - Motivating use case: CI tracking of flat health metrics (a success rate that must hold 1.0, an orphan-process count that must hold 0) next to per-metric trend thresholds on the same benchmark. Breaches flow through the existing machinery unchanged (`has_regressions`, `regression_fail`/`RegressionError`, report markdown, JSON, `render_png`).
  - First mutable (`param.Dict`) field on `BenchRunCfg`: every `BenchRunner` copy point deepcopies and the default is `None`; recorded in the copy-guard test's `REVIEWED_MUTABLE_FIELDS` allowlist with nested-dict isolation tests.

### Changed
- `detect_absolute` with `OptDir.none` now warns and returns `None` instead of recording a non-regressed "checked" result — a guard with no direction never ran, so it no longer appears to have passed.

## [1.111.0] - 2026-07-01

### Changed
- **`to_auto` dispatches through the plot plugin registry** (A1 Phase 2). The built-in chart types (bar, box_whisker, curve, line, heatmap, histogram, volume, panes) are registered as thin wrappers (`bencher/plugins/builtins.py`) that delegate to the existing renderer methods — renderer logic and report output are unchanged (priorities encode the legacy callback order; parity covered in `test/test_plugins_builtins.py`). What changes: user plugins registered with `@bencher.plot_plugin` / `bencher.register_plugin` or shipped via the `bencher.plot_plugins` entry-point group now appear in reports automatically; built-ins can be overridden by registering the same (name, backend); `plot_list`/`remove_plots` accept plugin names (`"line"`, `"heatmap"`, ...) alongside the legacy callables (which keep working, unknown callables via direct call); and `to_auto(backend=...)` states a preferred rendering backend — chart types the preferred backend implements swap to it, the rest keep their best other implementation.
- New `BenchResult.to_bench_data()` builds the frozen `BenchData` contract from a live result (first step of the A3 data-contract migration). Transitional `BenchData.legacy_result`/`render_kwargs` fields carry the live result and plot kwargs for the wrapped built-ins; they are not part of the stable plugin contract and disappear when renderers consume `BenchData` directly.

## [1.110.0] - 2026-07-01

### Added
- **Plot plugin infrastructure (tier 0, purely additive)** — the first piece of the plan to replace the inheritance-based rendering system in `bencher/results/` with a plugin registry (see `plans/architecture/A1-rendering-backend-unification.md` and `docs/plot_plugin_design.md`). New `bencher.plugins` package exposing, at the top level: `BenchData` (frozen value type: dataset, input/result vars, `plt_cnt_cfg`, `RunMeta`, optional `optimizer_study`/`baseline_runs`/`cache`), the `PlotPlugin` protocol and `@plot_plugin` decorator, and `PluginRegistry` with `get_registry()`/`register_plugin()`/`unregister_plugin()`. Plugins are `(chart-type × backend)` pairs with a `PlotFilter` match rule, priority, capability gating via `requires`, lazy entry-point discovery (`bencher.plot_plugins` group), and error-pane substitution on render failure (`strict=True` re-raises). **No existing code path queries the registry yet**; built-in chart types migrate onto it in subsequent PRs. Coverage in `test/test_plugins.py`.

## [1.108.0] - 2026-06-21

### Added
- `bencher` console-script entry point (`[project.scripts]` → `bencher.render:main`), so the render/compare CLI can be invoked as `bencher <result.pkl> <out_dir> [--json PATH]` and `bencher compare <a.pkl> <b.pkl> --json PATH` instead of only `python -m bencher.render …`. **Non-breaking**: the existing `python -m bencher.render` invocation is unchanged and keeps working; this is purely an additional way to reach the same `main()`. Usage/`--help` text is now invocation-aware via a small `_prog()` helper — it shows `bencher` under the console script and `python -m bencher.render` from a source checkout — so the displayed command always matches how the tool was run. Coverage in `test/test_render.py`.

## [1.107.0] - 2026-06-12

### Changed
- Centralised the representation of *missing*/unrecorded result-variable entries. The dtype-specific sentinels (`NaN` for numeric types, `-1` for `ResultReference`/`ResultDataSet`, `"NAN"` for object/file types) were duplicated across `ResultCollector.setup_dataset` (initial fill) and `_sentinel_for_result_var` (over_time aging), and consumers hardcoded the check per call site (`== "NAN"` for file panes). New helpers in `bencher.variables.results` — `result_missing_fill(rv)` and `result_is_missing(rv, value)` — are now the single source of truth; the two `isinstance` ladders collapse into one polymorphic call and the hardcoded `== "NAN"` file checks in `bench_result_base.py` use the shared predicate. **No behaviour change**: the stored fill values and dtypes are identical, so the on-disk cache format, `BenchCfg` hashes, and every reduction are unchanged (`CACHE_VERSION` stays at `4`). Direct coverage in `test/test_result_missing.py`.

## [1.106.2] - 2026-06-12

### Added
- `catch` parameter on `Bench.optimize()`, forwarded to `optuna.Study.optimize()`: a trial whose worker raises one of the given exception types is recorded as `FAILED` and the study continues with the remaining trials, instead of one raising trial aborting the entire study. The default `()` mirrors Optuna's own default and preserves the existing fail-fast behaviour exactly. `ParametrizedSweep.to_optimize()` already forwards `**kwargs`, so it picks up `catch` with no change. A raising worker leaves no committed sample-cache entry (both the serial and parallel paths raise before `cache.set`), so `FAILED` trials cannot poison the cache. Coverage in `test/test_optimize.py::TestCatch`.

## [1.106.1] - 2026-06-12

### Changed
- Version-only re-release of 1.106.0; no code changes.

## [1.106.0] - 2026-06-12

### Fixed
- `Bench.optimize()` never passed `const_vars` to the worker: `_run_optuna_job` folded the constants into the **cache key** but submitted only the trial-suggested values as `job_args`, so every Optuna trial silently ran with the worker class's parameter *defaults* for all `const_vars`. Constants are now merged into the submitted `job_args` (mirroring the sweep path's `WorkerJob.setup_hashes`); trial-suggested values keep precedence since `_resolve_optimize_vars` already strips colliding const entries. Regression coverage in `test/test_optimize.py::TestConstVars` for both the plain and `aggregate`/`repeats>1` branches.
- `CACHE_VERSION` bumped to `"4"`: because the old cache key already included the constants, any cached `optimize()` entries produced with non-default `const_vars` hold values actually computed with worker defaults — wrong data under a correct-looking key, indistinguishable on disk from good entries. The bump wipes the cache tree on first use of the new version so the fixed code can never warm-start from poisoned entries.

## [1.105.0] - 2026-06-11

### Changed
- The default value for `ResultFloat`, `ResultVec`, and `ResultBool` is now `NaN` instead of `0`. An *unrecorded* sample — a run that aborts before measuring, or a result var the worker never sets — is now treated as missing and dropped by the nan-aware regression/aggregation reductions, instead of masquerading as a real `0`/`False` measurement and dragging means toward zero. This matches the storage layer, which already initialises result arrays with `NaN`. Callers who want unrecorded samples to read as `0` can opt out with `default=0`.
- For `ResultBool`, this means **missing ≠ failure**: an unrecorded repeat is dropped from the success proportion rather than counted as `False`. A worker that wants a crash/abort to count as a failure must explicitly record `False` on its failure path. The binomial standard error already divides by the per-cell count of valid (non-NaN) repeats (see 1.104.2), so missing repeats no longer understate the SE.
- `CACHE_VERSION` is **not** bumped: the result-var `default` is not part of `BenchCfg.hash_persistent()`, so existing benchmark and `over_time` history caches are preserved. The new `NaN` default only applies to cache *misses* (newly computed cells); already-cached cells keep whatever sentinel they were stored with, so a benchmark with missing samples may transiently hold a mix of `0` (old) and `NaN` (new) until those cells are recomputed.

## [1.104.2] - 2026-06-10

### Fixed
- `ResultBool` rejected NaN as a default or value even though NaN is the documented "missing"/unrecorded sentinel for result variables (see `ResultFloat.__init__`). `ResultBool` locks its bounds to `[0, 1]`, and param validates a Parameter's default against its bounds whenever a subclass *overrides* it (and validates every value assignment). So `ResultBool(default=float("nan"))` raised `must be at most 1, not nan` the moment a subclass overrode the inherited Parameter, and assigning `float("nan")` at runtime to mark a sample missing raised the same — making the NaN "missing" sentinel that already works for `ResultFloat` unusable for `ResultBool`. `ResultBool._validate_bounds` now treats NaN as in-bounds, so result bools can use the same missing sentinel as `ResultFloat` while genuinely out-of-range values (e.g. `2.0`) are still rejected. Added coverage in `test/test_result_nan_default.py`.
- The `ResultBool` binomial standard error (`REDUCE` path in `bench_result_base.py`) divided `p*(1-p)` by the full repeat-dimension size while computing `p` with a `skipna=True` mean. Now that NaN is a valid "missing" repeat for `ResultBool`, those diverged and the SE was understated whenever a repeat was missing. The SE now divides by the per-cell count of valid (non-NaN) repeats. Added coverage in `test/test_result_bool.py`.

## [1.104.1] - 2026-06-09

### Fixed
- 30° x-axis label rotation (and `title`/`ylabel`) were silently dropped on plots that hvplot returns as a panel layout — specifically over_time time-series lines that pair `widget_location="bottom"` with an extra categorical `by` widget, which come back as a `pn.Column([HoloViews pane, WidgetBox])`. `HoloviewResult._apply_opts` only handled bare HoloViews elements (`.opts`) and `pn.pane.HoloViews` wrappers (`.object`); the layout container has neither, so the options never reached the nested pane and long x-axis labels (e.g. `over_time` datetime/`TimeEvent` ticks) rendered horizontally and unreadable. `_apply_opts` now recurses into panel layout containers to apply options to the nested pane. hv elements never expose `.objects`, so the new branch only catches panel layouts. Added unit coverage in `test/test_holoview_result.py` for all three input shapes (bare element, pane wrapper, layout container).

## [1.104.0] - 2026-06-08

### Changed
- Sped up `import bencher` (~19s → ~4s warm) by lazy-loading two heavy plotting dependencies that were imported eagerly at module load but only needed when a plot is rendered. `holoview_result.py` no longer registers the holoviews plotly backend (`hv.extension("bokeh", "plotly")` → `hv.extension("bokeh")`) — nothing in bencher renders through it, since `SurfaceResult`/`VolumeResult` build `plotly.graph_objs` figures directly and wrap them in `pn.pane.Plotly`. The `optuna.visualization` imports (which pull in sklearn's fANOVA evaluator) were moved into the functions that use them (`param_importance()`, `collect_optuna_plots()`). No public API changes.

## [1.103.1] - 2026-06-08

### Fixed
- Histograms rendered at hvplot's default 700×300 instead of the shared 600×600 used by every other plot type. `HoloviewResult.set_default_opts()` registered the default figure size for `Curve`, `Points`, `Bars`, `Scatter`, `BoxWhisker`, `Violin`, and `HeatMap`, but `Histogram` was missing so it escaped to hvplot's own default. Also registered `Area` and `ErrorBars` for consistency (`ErrorBars` would likewise escape when returned standalone from `to_error_bar()`; `Area` previously inherited the size only by virtue of being overlaid). The default-sized element list is now centralized in `HoloviewResult.DEFAULT_SIZED_ELEMENTS` and reused by both `set_default_opts()` and `test_default_opts_cover_all_element_types`, so the coverage guard stays in sync as new element types are added.

## [1.102.0] - 2026-06-02

### Added
- Optional `default=` argument on `ResultFloat` and `ResultVec` (defaults to `0`, so no behaviour change). The hardcoded `0` default meant an *unrecorded* sample — a run that aborts before measuring, or a result var the worker never sets — was indistinguishable from a real `0` measurement, dragging nan-aware regression/aggregation means toward zero. Callers can now opt in with `default=float("nan")` so unrecorded samples are treated as missing and dropped by the existing `np.nanmean`/`np.nansum` reductions. `default` is not a hashed slot, so opting in does not invalidate `over_time` history for an otherwise-identical result var.
- `test/test_result_nan_default.py`: backward-compat (default still `0`), NaN/explicit-default opt-in, hash stability, end-to-end unrecorded-sample handling, plus serialization coverage — a pickle `save_result`/`load_result` round-trip and a HoloViews→bokeh `render_report` HTML render both preserve/handle the NaN default.

## [1.101.1] - 2026-06-01

### Fixed
- Pylint failures introduced by the `param` 2.4.0 / `panel` 1.9.2 dependency bumps: the deeper class hierarchy pushed several sweep classes (`BoolSweep`, `StringSweep`, `EnumSweep`, `YamlSweep`, `IntSweep`, time sweeps) over the `too-many-ancestors` threshold, so that check is now disabled alongside the other `too-many-*` checks.
- Renamed the `IntSweep._validate_value` parameter from `val` to `value` to match param 2.x's signature and silence `arguments-renamed` (W0237).

- Cleared the three pre-existing `ty` warnings: corrected the `_InputResult` namedtuple's first argument to match its variable name, explicitly imported `moviepy.video.VideoClip` for the `write_video_raw` annotation, and suppressed the `unsupported-base` false positive on `BenchResult`'s optional `RerunResult` base.

### Changed
- Raised the minimum `param` requirement from `>=1.13.0` to `>=2.0`. The validation override now matches param 2.x's `_validate_value(self, value, allow_None)` signature.
- Dependency audit: raised upper bounds to the latest releases — `numpy` `<=2.4.6`, `xarray` `<=2026.4.0`, `pandas` `<=3.0.3`, `scikit-learn` `<=1.8.0`. Full test suite passes against all bumped versions.
- Migrated panel widget construction from the deprecated `name=` to `label=` (`Button`, `DiscreteSlider`, and example sliders) ahead of its removal in panel 2.0, and raised the panel floor to `>=1.9.0` (the release that introduced `Widget.label`).

## [1.101.0] - 2026-06-01

### Added
- Collect/render split for out-of-process report rendering. Building a report allocates large holoviews/panel/bokeh object graphs; when CPython's cyclic GC traverses them alongside foreign live C-extension state (e.g. ROS 2 `rclpy`/DDS), the process can segfault. The split lets rendering happen in a clean process that never imported the foreign extension:
  - `plot_sweep(auto_plot=...)` — new parameter (defaults to `None`, deferring to `run_cfg.auto_plot`, itself `True`). When `False`, the sweep runs and regression detection is computed but no plotting objects are constructed.
  - `Bench.collect(...)` — thin wrapper for `plot_sweep(auto_plot=False)`; returns a fully-populated, picklable `BenchResult` (dataset + regression report).
  - `bencher.save_result()` / `load_result()` / `render_report()` (new `bencher.render` module) — persist a collected result and render the HTML report from it, optionally in a separate process via `python -m bencher.render <result> <out_dir>`.
- Three test layers guarding the split against divergence from the normal `plot_sweep` path: parity tests (`collect()` computes the same dataset/regression as `plot_sweep()`), a breadth round-trip over every generated result type (save → load → render to HTML, plus a real-subprocess media test), and the `BENCHER_FORCE_SPLIT_RENDER=1` switch that reroutes every auto-plot report build through serialize/render-from-loaded so `pixi run test-split` re-runs the whole suite over the split pipeline (own parallel py313-only `ci-split` job).

### Changed
- `BenchReport.append_result()` gained an optional `render_from=` argument so a caller can register one result for identity-based tab routing while building the tab pane from another (used by the forced-split path).

## [1.100.0] - 2026-05-15

### Added
- Overlay controls on each embedded rerun recording: a fullscreen button (⛶) that calls `iframe.requestFullscreen()` and an open-in-new-tab link (↗) that opens the same chromeless viewer in a new browser tab. Useful when comparing multiple recordings side-by-side and you want to expand one. Controls are positioned top-center to avoid the viewer's own corner UI.

## [1.99.0] - 2026-05-15

### Changed
- Renamed `level` API to `subsampling_divisions` across the entire public interface (`BenchRunCfg.subsampling_divisions`, `subsampling_divisions_to_samples()`, `with_subsampling_divisions()`, `SUBSAMPLING_DIVISIONS_SAMPLES`, `max_subsampling_divisions`, `select_subsampling_divisions()`).
- Added `UNSET` sentinel for default detection so that `run(subsampling_divisions=2, level=3)` correctly raises `TypeError`.
- Extracted shared `normalize_subsampling_divisions_kwargs()` helper to centralize deprecation logic.
- Bumped `rerun-sdk` and `rerun-notebook` from 0.31.3 to 0.32.0.
- Updated fallback rerun version in `utils_rrd.py` to 0.32.0.

### Deprecated
- `level`, `max_level`, `min_level` parameters — use `subsampling_divisions`, `max_subsampling_divisions` instead. Old names still work with `DeprecationWarning`.
- `LEVEL_SAMPLES` constant — use `SUBSAMPLING_DIVISIONS_SAMPLES`.
- `with_level()` function — use `with_subsampling_divisions()`.
- `level_to_samples()` method — use `subsampling_divisions_to_samples()`.
- `select_level()` function — use `select_subsampling_divisions()`.

## [1.98.0] - 2026-04-27

### Added
- `aggregate`, `agg_fn`, and `repeats` parameters for `optimize()`, matching the `plot_sweep()` API. Aggregated dimensions are looped inside the Optuna objective so the optimizer sees robust metrics (e.g. mean loss across seeds or repeated boolean outcomes).
- `AGG_FN_MAP` in `bencher/utils.py` — NaN-safe numpy aggregation functions for objective-level aggregation.
- Example `example_optimize_aggregate.py` demonstrating sweep-then-optimize with dimension aggregation and repeats.

### Fixed
- Missing `skipna=True` on `REDUCE` and `MINMAX` repeat aggregation in `bench_result_base.py`.
- `np.mean` → `np.nanmean` in `optuna_result.py` aggregation to match xarray's NaN-safe behavior.

## [1.97.0] - 2026-04-27

### Fixed
- `aggregate=True` no longer duplicates pane-type results (rerun, image, video). Pane results store file paths that cannot be numerically aggregated, so they now only render in the non-aggregated view.
- Line plotter crash when aggregating: `plt_cnt_cfg` still referenced collapsed dimensions, causing holoviews `DataError` on missing dimension names. Swapped to post-aggregation config during `map_plot_panes` calls.
- `remove_plots` no longer raises `ValueError` when combined with `numeric_only`.

### Changed
- Renamed `VideoResult` to `PaneResult` to reflect that it handles all pane types (rerun, image, video), not just video.

### Added
- Image and video aggregate examples (`example_result_image_aggregate`, `example_result_video_aggregate`) to exercise and demonstrate pane-result aggregation.
- `omega_n` sweep added to `ControlSystemSweep` for multi-input rerun testing.

## [1.94.0] - 2026-04-25

### Fixed
- Rerun viewer panes now work in saved HTML reports (`show="html"` / `ShowMode.HTML`). Previously the viewer failed because browsers block `fetch()` from `file://` origins. The `.rrd` data is now base64-encoded directly into the viewer HTML page and loaded via the rerun `open_channel()` / `send_rrd()` API, bypassing the fetch entirely.
- Multi-tab reports with rerun panes: tab files in `_tabs/` now correctly reference `../_rrd/` instead of `_rrd/`, fixing broken relative paths.

## [1.93.0] - 2026-04-25

### Added
- `ShowMode` StrEnum (`live`, `html`, `published`, `none`) exported from the top-level `bencher` package. `bn.run(show=bn.ShowMode.HTML)` gives autocomplete and typo detection while plain strings (`show="html"`) and booleans (`show=True`) keep working. The old `"static"` spelling is accepted as an alias for `ShowMode.HTML`.

### Changed
- The `show` parameter on `bn.run()`, `BenchRunner.run()`, `BenchRunner.show()`, and `BenchPlotSrvCfg` now accepts `ShowMode` in addition to `bool | str`.
- Renamed the `"static"` display mode to `"html"` (`"static"` remains supported via alias).

## [1.92.0] - 2026-04-22

### Added
- `show` parameter on `bn.run()`, `BenchRunner.run()`, and `BenchRunner.show()` now accepts string display modes in addition to `bool`: `"live"` (start Panel server, blocks — same as `True`), `"static"` (save an embedded HTML file and open in the browser, returns immediately), `"published"` (open the published URL — requires `publish=True`), and `"none"` (display nothing — same as `False`).
- Public `MethodCells` dataclass and `method_cells(result)` helper in `bencher.regression`, re-exported from the top-level `bencher` package. Downstream report builders can now call `method_cells(r)` to get pre-rendered, method-aware display strings (change, baseline, threshold, summary lead) for a `RegressionResult` and embed them in a custom layout — custom columns, non-markdown output, CI comments with status decoration, etc. — without reimplementing per-method dispatch (and drifting when new detection methods are added).

### Removed
- The private names `_MethodCells` / `_method_cells` are gone. Update callers to the public `MethodCells` / `method_cells`.

## [1.91.0] - 2026-04-22

### Added
- Regression report is now auto-embedded as a Markdown panel at the top of `to_auto_plots()` whenever `regression_report.has_regressions` is true. Previously only the per-variable overlay plots were injected, so absolute-method fires (which have no history/overlay) were silent in the report.

### Changed
- Regression report rendering (`RegressionReport.summary()` and `to_markdown()`) now dispatches per method so each row describes its actual gate:
  - `percentage`: threshold shown as `±T%`.
  - `adaptive`: threshold shown as `Tσ` (change remains in percent).
  - `delta`: Change column shows the raw Δ (not percent, since the gate is in absolute units); threshold rendered as `±T`.
  - `absolute`: Change and Baseline cells rendered as em-dash (no historical baseline); Threshold cell carries the direction-aware inequality (`≤ L` for `OptDir.minimize`, `≥ L` for `OptDir.maximize`). Summary line phrased as `current=X vs ceiling|floor=Y`.

### Fixed
- `RegressionResult.summary()` / `RegressionReport.to_markdown()` no longer render `+nan%` or mislabel the hard limit as `Baseline` for `regression_method="absolute"` results.

## [1.90.0] - 2026-04-22

### Added
- `sampling_context` parameter on `bn.run()`: an optional context manager that wraps only the sampling phase. Its `__exit__` is guaranteed to run before the Panel/Bokeh server starts, so external resources (DB pools, GPU handles, simulators) are released while nothing blocks. `save` and `publish` still execute inside the context. Defaults to `None` (fully backward-compatible).

## [1.89.0] - 2026-04-21

### Added
- Two new values for `BenchRunCfg.regression_method`: `"delta"` and `"absolute"`. Each selects a dedicated detector and its threshold comes from a new `BenchRunCfg` field:
  - `"delta"` uses `regression_delta`: largest acceptable absolute-unit change of the current run's mean from the mean of all historical per-time means, respecting the result variable's `OptDir`. Useful when a percent threshold obscures sensitivity at tiny baselines or when CI wants a flat unit ceiling on drift.
  - `"absolute"` uses `regression_absolute`: hard directional threshold (ceiling for `OptDir.minimize`, floor for `OptDir.maximize`) against the current run's mean. No history required — fires on the very first recording.
- `detect_delta()` and `detect_absolute()` public detectors in `bencher.regression`, mirroring the `detect_percentage` / `detect_adaptive` shape so they participate in the shared plot/report pipeline.
- `detect_regressions()` now runs with a single `over_time` point when `regression_method="absolute"`, so contractual limits can gate even the initial benchmark run.
- Gallery examples `example_regression_delta` and `example_regression_absolute` demonstrating the new methods.

### Changed
- Regression diagnostic plot: when the adaptive detector produces both a MAD band and a percent band, they are now merged into a single combined acceptance band (the union of both — matching the adaptive gate, which flags a regression only when both tests fail). Previously the plot layered two separately-coloured bands.

## [1.87.0] - 2026-04-19

### Added
- PNG/bokeh regression diagnostic plot via `render_regression_png` (matplotlib) and `build_regression_overlay` (holoviews/bokeh) sharing a single plot spec, so the same diagnostic can be posted as a PR-comment PNG or embedded in the HTML report. `RegressionResult` now stores history/current samples and their `over_time` coordinates so plots use real datetimes when available.
- HTML report auto-inserts the regression overlay per regressed variable; bare over_time line/band plots are suppressed for any variable with a regression overlay to avoid duplicate graphs.
- Categorical x-axis support in regression plots (e.g. `git_time_event` string labels like `"2024-06-15 abc1234d"`), surfaced via xticks overrides.
- Dotted connector from the last history point to the current marker in regression overlays so the jump that triggered a regression is visually obvious.
- `matplotlib` added as a dependency for PNG rendering.

### Fixed
- `over_time` bar plot crash on duplicate coord values (e.g. two runs at the same `git_time_event` string) that caused `HoloMap must only contain one type of object, not both Bars and DynamicMap`. Switched `_build_time_holomap` and `_pane_over_time_{slider,grid}` to positional `isel(over_time=idx)` and deduped identical coord values.
- Holoviews `UFuncNoLoopError` with `git_time_event` string x-axes by replacing `HSpan`/`HLine` with `Area`/`Curve` primitives that carry explicit x coords, so the regression band and baseline always render regardless of x dtype.
- Regression plot dtype mismatch between `hist_x` and `current_x` (e.g. datetime64 vs int64) that raised in holoviews' range computation; `current_x` now only replaces the extrapolated tick when its dtype matches the history.
- Single-datetime-point regression overlays now nudge the current marker forward by a small timedelta so it doesn't overlap the sole history point.

## [1.86.0] - 2026-04-19

### Changed
- `BenchRunCfg.regression_method` default changed from `"percentage"` to `"adaptive"`. The adaptive method (robust MAD-based step + drift test) is more resilient to noisy metrics and is a better default for most benchmarks. Users can still opt into `"percentage"`, `"iqr"`, or `"ttest"` explicitly.

## [1.85.1] - 2026-04-19

### Fixed
- Rerun regression over-time line plots crashing when an acceptance band was overlaid on a `widget_location`-wrapped hvplot (panel pane), by composing the band onto `plot.object` when the plot is a pane wrapper.

## [1.85.0] - 2026-04-18

### Fixed
- **Benchmark-level cache identity for reshaped sweeps**: `SweepBase.hash_persistent` previously hashed only `(units, samples)`, so reshaping a `FloatSweep`/`IntSweep`/`SweepSelector` (changing bounds, step, `sample_values`, or `objects`) silently left the benchmark-level cache and `over_time` history keyed by the old shape, returning stale coordinates. Fixed by introducing an explicit `_sweep_identity` whitelist (bounds, sample_values, step, objects) with a slot-coverage test that catches future "added a slot, forgot the hash" regressions.
- `CACHE_VERSION` bumped to `"3"` and folded directly into `BenchCfg.hash_persistent` so version bumps atomically invalidate every benchmark-level and over_time key.

### Changed
- `ResultFloat.direction` and `ResultRerun.width`/`height` moved to `_hash_exclude`: these are interpretive/cosmetic fields that should not invalidate history when changed.
- New `TestGoldenBenchCfgHash` regression pins byte-exact values for a canonical `BenchCfg`; any future change to what contributes to the hash fails CI loudly and forces a deliberate `CACHE_VERSION` bump.

## [1.84.0] - 2026-04-12

### Changed
- Decouple benchmark title from cache hash so renaming a title no longer invalidates cached results or loses over_time history

## [1.83.0] - 2026-04-12

### Fixed
- `.rrd` filename collision in saved reports by using subdirectory structure for rrd sidecar files (#909)
- Guard `rrd_file_to_pane` against None/empty file paths
- Start over_time film-strip labels from t=1 instead of t=0 (#907)
- Skip rerun over-time entries with no data instead of showing placeholder (#905, #906)

### Changed
- Track all generated examples and remove duplicate cartesian animation
- Gitignore `bencher/example/generated/` to stop dirty working tree

## [1.81.0] - 2026-04-08

### Added
- Per-variable `max_time_events` support for fine-grained control over rerun time-series density (#899)
- Regression markdown output for result reporting

### Changed
- Pinned rerun-sdk to 0.31.1 for stability
- Rewritten rerun examples with improved over_time handling and result rendering

### Fixed
- Histogram rendering fixes
- Rerun over_time slider crash (#900)
- Cache management: cleanup timing, gen_path collisions, error handling, and type annotations (#899)
- Accidental generated file deletion during cache cleanup

## [1.80.1] - 2026-04-06

### Fixed
- Recover gracefully from stale history cache entries after dependency upgrades (#898)

## [1.79.0] - 2026-04-05

### Added
- **Rerun visualization backend** with seamless backend switching between holoviews and rerun (#755)
- `ResultRerun` type for dedicated `.rrd` result handling (#882)
- `extra_panels` parameter in `to_auto_plots()` for composability (#846)
- `LEVEL_SAMPLES` constant and `BenchRunCfg.level_to_samples()` for transparent level-to-sample lookups (#834)
- `samples_per_var` parameter on `BenchRunCfg` — explicit sample count that overrides `level` (#834)
- Improved `BenchRunCfg` docstring with quick-start examples and level-to-samples table (#834)
- Mermaid architecture diagram in concepts docs (#852)

### Changed
- `cache_samples` is now opt-in, with auto-enable for progressive runs (#889)
- Refactored holoviews backend: unified tap logic, time HoloMaps, and filter usage (#754)
- All generated example filenames now prefixed with `example_` (#890)
- Improved error messages, result validation, and example modernization (#895)
- Improved validation, error messages, and onboarding docs (#887)

### Fixed
- Type hints and error handling for `extra_panels` (#896)
- Use random port instead of `port=0` to avoid `EADDRINUSE` on Linux 6.x (#894)
- Save report synchronously before serving to prevent Bokeh race condition (#893)
- Coerce sweep bounds/values to declared type (#888)
- Use CDN viewer for rerun and eagerly init recording (#884)

### Performance
- `as_completed()` for parallel result streaming (#891)
- Hoist shared allocations and pre-cache numpy arrays (#886)
- Bypass xarray indexing and cache `get_input_and_results` (#885)
- Batch cache lookups to reduce SQLite round-trips (#883)
- Memoize `to_dataset()` results (#877)
- Speed up RTD docs build (#892)

## [1.78.0] - 2026-04-02

### Added
- `share_axis` parameter on `ResultFloat` for independent y-axis scaling (#881)
- Automatic axiswise scaling when result variables have different units

### Fixed
- pylint E0606: initialize `axiswise_cb` before conditional

## [1.77.0] - 2026-04-02

### Changed
- **Renamed `ResultVar` to `ResultFloat`** with deprecation shim (#880)
- Extract `SCALAR_RESULT_TYPES` constant to DRY up repeated type tuples

### Docs
- Improve `ResultBool` discoverability in docs and docstrings (#879)

## [1.76.0] - 2026-04-01

### Added
- `PaneLayout` option for tab-based multi-dimensional container display (#878)
- Auto-generated examples for container tab layouts
- Bump rerun-sdk and rerun-notebook to 0.31.x (#867)

### Performance
- Eliminate redundant deepcopy in `BenchRunner.run()` (#876)

## [1.75.2] - 2026-03-31

### Fixed
- `.rrd` iframe URLs no longer hardcode `localhost:8051` — CDN viewer uses relative URLs, local/hosted viewer resolves `window.location.origin` at render time via JavaScript, so reports work behind container port mappings and on any Panel server port (#866)
- Panel server uses `port=0` (OS-assigned) when no explicit port is given, preventing `OSError: Address already in use` when other services occupy the default port (#866)
- `_cdn_viewer_versions` cache collision between `_cdn_viewer_url` (filenames) and `_get_cdn_viewer_html` (HTML strings) — split into separate caches (#866)
- Film strip labels now render at constant pixel size regardless of strip dimensions, with horizontal clipping and right-alignment for wide strips (#865)

### Changed
- `show=True` in `BenchRunner.run()` now auto-saves a static HTML report to `reports/` in a background thread (non-blocking), with the path logged for offline viewing. Explicit `save=True` still saves synchronously. (#866)
- **Deprecated `__call__()` in favor of `benchmark()`**: `ParametrizedSweep` subclasses should now override `benchmark()` instead of `__call__()`. The new method removes the need for `self.update_params_from_kwargs(**kwargs)` and `return super().__call__()` boilerplate. The old `__call__()` pattern still works but emits a `DeprecationWarning`. (#864)

### Removed
- `PANEL_PORT` constant from `utils_rrd` — no longer needed since iframe URLs are resolved dynamically (#866)

## [1.74.0] - 2026-03-28

### Added
- **Cartesian Product Animations**: New PIL-based animation system that visualizes how parameter sweep dimensions build upon each other (point → line → grid → stack → film strip) (#feature/manim_summary)
- `BenchCfg.to_cartesian_animation()` method for rendering dimensional progression animations
- Automatic animation embedding in sweep descriptions via `BenchCfg.describe_sweep()`
- `CartesianProductCfg` and `CartesianProductScene` classes for animation configuration and rendering
- `bencher.results.manim_cartesian` module with Shape, StrobeShape, and TimelineShape classes
- **Complete Usage Guide**: New comprehensive `docs/how_to_use_bencher.md` documentation covering sweep types, result types, and best practices
- Tab bar sweep example (`example_tab_bar_sweep.py`) demonstrating UI layout testing with PIL rendering
- Meta example generation system for creating animation galleries
- 10-color pastel palette for dimensional visualization with proper contrast on white backgrounds
- Film strip metaphor for `over_time` dimension with sprocket holes and frame labels
- Strobe/flash animation for `repeat` dimension with tally mark counters

### Changed 
- **Dark Theme Tab Bar**: Report tabs now use dark background with improved contrast and sticky positioning
- Tab bar styling updated with rounded corners, better spacing, and proper hover states
- Meta example generation now includes animation examples in advanced gallery
- Animation rendering uses unique filenames to prevent file path collisions
- Improved tally mark visuals with thicker strikethrough, larger fonts, and centered labels

### Fixed
- Animation filepath collisions resolved with unique filename generation based on animation parameters
- ListProxy pickle serialization issues for multiprocessing compatibility
- Animation size optimization for better performance and smaller file sizes

## [1.73.1] - 2026-03-27

### Fixed
- Generate optimisation reports for all benchmarks, not just the last (#852)
- Include time event in over_time panel labels and default to last (#849)
- Wrap long description strings in generated examples to fit 100-char line limit (#851)
- Override RTD theme CSS to wrap long lines in docs code blocks (#851)

## [1.73.0] - 2026-03-26

### Added
- `bn.sweep()` API with `bounds=(low, high)` support as the unified replacement for `bn.p()` — `bn.p()` still works but emits a `DeprecationWarning` (#838)
- `SweepBase.__call__()` for concise, type-safe sweep configuration: `Cfg.param.theta([0, 0.5, 1.0])` or `Cfg.param.theta(samples=5)` (#838)
- `SweepBase.with_bounds()` for overriding sweep ranges immutably (#838)
- Dict and inline-dict shorthand for `input_vars` in `plot_sweep`: `{"theta": [0, 0.5, 1.0]}`, `{"theta": 5}`, `{"theta": None}` (#842)
- `atexit` handler to stop Panel servers on exit, preventing process hangs after `bn.run(show=True)` (#841)
- Interactive prompt in terminal mode — press Enter to stop servers after viewing results (#841)
- SIGTERM handler chaining — lazily installed only when servers are created, chains to previous handler instead of calling `sys.exit()` (#841)
- `over_time` parameter on `bn.run()` and `BenchRunner.run()` — enables time-series benchmarking without manually creating a `BenchRunCfg` (#848)
- 2-float 2-categorical aggregation example (`agg_list_2_cat`) demonstrating `aggregate=["direction", "scale"]` on a `GradientSurface` class (#845)

### Changed
- `FloatSweep`/`IntSweep` now store user-supplied bounds as param `softbounds` instead of hard bounds, so values outside the defined sweep range are no longer rejected by `update_params_from_kwargs` (#838)
- `BenchRunCfg.with_defaults()` returns a deep copy and merges defaults into caller-provided configs instead of ignoring them (#840)
- `BenchRunCfg.with_defaults()` raises `ValueError` for unknown parameter names to catch typos early (#840)
- Rename `test/test_bn_p.py` to `test/test_sweep_helper.py` to match new `bn.sweep()` API
- Generated over_time examples now pass `over_time=True` via `bn.run()` kwargs instead of setting `run_cfg.over_time` inside the function body (#848)

### Fixed
- `bn.p()` now raises `ValueError` when `max_level` is used with `SweepBase` objects, which require `run_cfg.level` at execution time (#838)
- `bn.sweep()` / `__call__()` reject combining explicit `values` with `bounds`/`samples` to prevent ambiguous configurations (#838)
- Server shutdown is exception-safe — a failing shutdown on one runner no longer prevents cleanup of remaining runners (#841)
- Shutdown errors are logged to stderr instead of silently swallowed (#841)
- Interactive prompt delayed to appear after async server startup logs (#841)
- Optuna plot failures now show diagnostic `Markdown` panels instead of silently swallowing exceptions (#847)
- `to_optuna_plots()` in `bn.run()` shows a diagnostic when `optimize()` returns `None` (#847)
- `logging.warning` when `dropna` removes all rows from optuna trial data (#847)

## [1.72.3] - 2026-03-24

### Fixed
- `aggregate` parameter in `plot_sweep` now produces the correct plot type for remaining dimensions (e.g. heatmap for 2 remaining floats) instead of always forcing a 1D band plot, collapsing all non-x dimensions

## [1.72.2] - 2026-03-23

### Changed
- `git_time_event()` now uses wall-clock time (`datetime.now()`) instead of commit date, producing labels like `"2024-06-15 14:59 abc1234"` so multiple runs on the same commit get distinct over_time labels
- `git_time_event()` uses `git rev-parse --short HEAD` for the canonical abbreviated SHA instead of hardcoded `[:8]` slicing
- `git_time_event()` falls back to `"<timestamp> unknown"` instead of just the timestamp when git is unavailable, keeping the label format consistent
- Removed the second subprocess call (`git log`) from `git_time_event()`, making it lighter for fork-sensitive environments
- Increased `wrap_long_time_labels` wrap width from 20 to 30 characters to accommodate the longer time-event label format
- Docstring documents the recommended import-time caching pattern for fork-safety in threaded environments (ROS 2, DDS, etc.)

### Performance
- Skip redundant dataset copy in `to_dataset()` for REDUCE/MINMAX paths (#826)
- Single-pass reduction avoids `xr.merge()` in `to_dataset()` (#824)
- Replace DataFrame groupby with xarray sel in curve overlay (#822)
- Batch cross-process hash tests into 2 subprocess invocations (#820)
- Add comprehensive `.save()` performance benchmark and report (#825)

## [1.72.1] - 2026-03-22

### Changed
- **Breaking:** `show_aggregated_time_tab` now defaults to `False`. The aggregated "All Time Points" tab doubled `report.save()` embed cost because Panel must pre-compute JSON patches for every slider position in both tabs. Users who need the aggregated view can set `show_aggregated_time_tab=True`. (#818)

### Added
- `report_save_ms` field on `SweepTimings` so downstream users can instrument `report.save()` cost

## [1.71.0] - 2026-03-21

### Added
- Bencher self-introspection: `SweepTimings` instruments `Bench.run_sweep()` to measure phase-level overhead (dataset setup, job submission, execution, cache checks, etc.) (#793)
- `example_self_benchmark` and `example_self_benchmark_over_time` examples for profiling bencher's own overhead (#793)

### Changed
- Rename import alias convention from `import bencher as bch` to `import bencher as bn` across all examples and tests
- Rename `test/test_bch_p.py` to `test/test_bn_p.py`
- Update AST check in `generate_examples.py` to match new `bn` alias

### Fixed
- Fix `ValueError` crash in `to_optuna_plots()` when `over_time=True` — `TimeSnapshot` param conversion only handled `np.datetime64` but pandas returns `pd.Timestamp` (#792)
- Fix `summarise_optuna_study` for single-objective studies — no longer calls `plot_pareto_front` which requires ≥2 objectives (#795)
- Fix `summarise_optuna_study` for multi-objective studies — passes explicit `target` callbacks to `plot_optimization_history` (#795)
- Fix `sweep_var_to_suggest` fall-through for TimeSnapshot/TimeEvent — now explicitly returns `None` instead of raising `ValueError` (#796)
- Auto-compute `total_ms` in `SweepTimings` and add `inspect` fallback (#796)

## [1.70.4] - 2026-03-20

### Fixed
- Fix curve plots using string-typed over_time (TimeEvent) as x-axis instead of the float input variable — explicitly set kdims in `to_curve_ds` to match `to_line_ds` behavior
- Classify TimeEvent as continuous in plot config so it is treated like TimeSnapshot for plotting
- Add TimeEvent support in optuna conversions and trial building

### Removed
- Remove vestigial `iv_time_event` field from BenchCfg (was never populated)

## [1.70.2] - 2026-03-20

### Fixed
- Fix band plots sharing axes across different metrics
- Fix plot server not working with container port forwarding

## [1.70.1] - 2026-03-19

### Fixed
- Fix over_time slider starting at first position instead of last in embedded HTML — Panel's `DiscreteSlider` sets the Bokeh `Slider.title` to `''`, so the JS that matched by `title === "over_time"` never found the slider; now uses Panel State model's widgets map to reliably locate the slider

## [1.66.3] - 2026-03-14

### Fixed
- Force `DiscreteSlider` widget for the `over_time` dimension so string-based `TimeEvent` coordinates get a slider instead of a dropdown

## [1.66.2] - 2026-03-13

### Fixed
- Fix over_time bar chart broken by unconditional image slider routing — numeric `ResultVar` types were incorrectly routed to `_pane_over_time_slider`, causing `FileNotFoundError` and `ValueError`

## [1.66.1] - 2026-03-13

### Fixed
- Fix `DTypePromotionError` crash when `over_time` coordinate type changes between runs (e.g., `time_event=None` → `time_event="v1.0"`)
- Check `over_time` dtype compatibility before concat, discarding incompatible history with a warning instead of crashing
- Include old/new dtypes in the warning message for easier debugging

## [1.66.0] - 2026-03-12

### Added
- Over-time slider support for BarResult: bar charts now show a time slider when `over_time=True` with multiple time points
- Over-time slider support for DistributionResult (BoxWhisker, Violin): distribution plots now show a time slider when `over_time=True` with multiple time points
- New meta-generated examples combining `over_time=True` with `repeats>1` for 0-1 float input configurations
- Tests for over_time + repeats across bar, distribution, and curve plot types

## [1.65.0] - 2026-03-11

### Fixed
- Fix non-deterministic `hash_persistent()` in 9 result variable classes that broke `over_time` history cache lookups across process invocations
- Fix `ResultVec.hash_persistent()` not including `size` in hash, causing cache key collisions for vectors of different sizes
- Add `_hash_slots()` helper that hashes all `__slots__` by default, with explicit `_hash_exclude` for non-deterministic runtime attributes (`obj`, `container`)
- Add comprehensive auto-discovery tests that will catch any future Result class missing deterministic hashing

## [1.64.0] - 2026-03-11

### Added
- `init_singleton()` now returns a context manager that auto-resets singleton state when first-time init raises, eliminating manual `_seen`/`_instances` cleanup boilerplate
- `reset_singleton()` public classmethod for explicitly clearing singleton state
- Thread-safe singleton operations via internal `threading.Lock`
- Full backward compatibility preserved — `if self.init_singleton():` works identically

## [1.63.0] - 2026-03-09

### Fixed
- Over-time slider now correctly defaults to the most recent time point instead of the first (#756)
- Fixed `DiscreteSlider` dict options handling — `list(w.options)` returned string keys instead of actual values, causing the slider to silently fall back to the first time point
- Added guard against empty widget options to prevent `IndexError`
- Narrowed slider default logic to only target the `over_time` widget, avoiding unintended side effects on other widgets

## [1.62.0] - 2026-03-06

### Added
- Over-time slider for visualizing benchmark results across time steps (#729, #730)
- Single-page scrollable gallery overview with CSS grid cards (#731)
- Feature-specific meta generators for result types, plot types, optimization, sampling, const vars, and statistics (#732)
- `bch.run()` API for simplified benchmark execution (#732)
- Inline rerun viewer support with `rerun_to_pane()` (#717)
- Prebuilt devcontainer image support via GHCR (#136)
- 3D visualization example
- Image, video, and volume plot type examples (#747)
- Full `ComposeType` support across all composable container backends (#746)
- Composable container gallery examples (#746)

### Changed
- Replaced notebook pipeline with Python examples + HTML reports (#734)
- Consolidated generated examples from `meta/generated/` to `example/generated/` and tracked in Git (#735)
- Updated rerun-sdk from 0.29.x to 0.30.1 (#725)
- Replaced `rerun.legacy_notebook` with `rerun_notebook.Viewer`
- Gallery now uses real iframe thumbnails with auto-crop via ResizeObserver
- Skip Tabs sidebar for single-tab reports
- Notebook generation is now fully deterministic across runs
- Updated meta generator `__main__` blocks to use `bch.run()`
- Switched gallery thumbnails from selenium+Firefox to playwright+Chromium (#741)
- Consolidated result types into a single gallery section with sub-headings (#748)
- Improved const vars documentation examples (#749)
- Improved statistics examples to showcase distinct bencher features (#751)

### Fixed
- Panel server dying on `bch.run(show=True)` (#732)
- Widget location fixed by wrapping HoloMaps in `pn.pane.HoloViews` (#730)
- Parameterized sweep benchmark naming when param counter exceeds 5 digits
- Over-time rendering for heatmap/line plots
- `const_vars` hash not chaining accumulated `hash_val` (#723)
- RTD build configuration for Playwright dependencies
- Over-time scrubber not appearing in static HTML
- Surface plot 3D rendering using xarray DataArray directly instead of pivot_table (#747)
- Gallery thumbnails broken on ReadTheDocs (#741)
- Overlay duration bug in composable containers (#746)
- apt package name `libasound2` → `libasound2t64` for Ubuntu 24.04

### Dependencies
- Bumped `rerun-sdk` and `rerun-notebook` to >= 0.30.1
- Updated `actions/checkout` from 4 to 6
- Updated `prefix-dev/setup-pixi` from 0.9.3 to 0.9.4
- Various dependency updates via Dependabot

## [1.60.0] - 2026-01-24

### Changed
- Updated numpy version constraint from `<=2.2.6` to `<=2.4.1` to support latest numpy releases
- Updated all dependencies to latest compatible versions through pixi update

### Fixed
- Resolved historical hvplot compatibility issues with numpy 2.x that were preventing updates

### Technical Details
- The numpy version limitation was due to binary compatibility issues between numpy 2.0 and hvplot that occurred when numpy 2.0 was released in June 2024
- These issues have been fully resolved in the ecosystem, with hvplot 0.12.2 now fully compatible with numpy 2.4.x
- All tests pass successfully with the updated dependencies

## [0.3.10]

Before changelogs
