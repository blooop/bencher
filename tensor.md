Tensor Results & Unified N-D Slicing (Architecture Plan A5)                                   ↑

 Context                                                                                       ↑

 Benchmark functions can only return scalars per result var. ResultVec nominally supports      ↑
 fixed-size vectors, but it is exploded into {name}_x/_y/_z scalar columns at dataset setup
esult_collector.py:233-238), so vector-ness never reaches the dataset — and no numeric       art can plot it (charts gate on result_types=(ResultFloat, ResultBool) and iterate 
 bench_cfg.result_vars, where the vec's name matches no column; bench_result_base.py:596-600). ↑
 Wrong-length vec returns are silently dropped. Past attempts (feature/tensor branch,
 ResultSeries, to_dataframe, the dead ds_dynamic dict) were all abandoned. Meanwhile the
 N-D→chart slicing machinery (ReduceType, agg_over_dims, the _to_panes_da leftover-dim pane    ↑
 recursion, hvplot sliders) exists but only operates on input dims, with repeat/over_time
 hardcoded as string literals.                                                                 ↑

 Goal: benchmark functions return vectors and arbitrary-shaped tensors as first-class result   ↑
 values, stored in a unified xarray representation, and the same slicing machinery routes any
 N-D slice — input dims or element dims — to charts, with an explicit serializable slice API.
                                                                                               ↑
 Owner decisions (confirmed this session):
 Shape is declared at result-var declaration: dims + optional coords.                        
 2. ResultVec is rebuilt on the new path with a flatten-view for back-compat.                  ↑
 3. Milestone 1 = live runs + slicing + plots + caching; over_time history/regression for
 general tensors is deferred (must fail loudly, never corrupt history). ResultVec's existing
 over_time history must not regress.                                                           ↑

 Roadmap fit: lands as plans/architecture/A5; complements A2 (uses the S1 signature fields from↑
 PR #983, is friendly to S3 serializable specs, does not take over S2 centralization), feeds the
 A3 BenchData contract ("dataset = the N-D results tensor"), respects the 09/14 cache/history  ↑
 key contracts.

 The unified model

 ┌───────────┬────────────────────────────────┬──────────────────────────────────────────┐     ↑
 │  Result   │             Today              │                  After                   │
  kind    │                                │                                          │      
 ├───────────┼────────────────────────────────┼──────────────────────────────────────────┤     ↑
 │ scalar    │ one data_var, dims [inputs..., │ unchanged                                │
 │           │  repeat]                       │                                          │     ↑
 ├───────────┼────────────────────────────────┼──────────────────────────────────────────┤
 │ vector    │ N unrelated scalar columns     │ one data_var, dims [inputs..., repeat,   │
 │           │                                │ elem]                                    │     ↑
 ├───────────┼────────────────────────────────┼──────────────────────────────────────────┤
 │ tensor    │ impossible                     │ one data_var, dims [inputs..., repeat,   │
 │           │                                │ d1, d2, ...]                             │
 └───────────┴────────────────────────────────┴──────────────────────────────────────────┘

 - Verified: xarray reductions over a dim skip data_vars lacking it, so mixed scalar/tensor
 datasets reduce uniformly (ds.mean("repeat") touches all; ds.mean("freq") only the tensor).
 - Every dataset dim gets a role: input_float | input_cat | repeat | time | element(owner).
 - Element dims become plot-axis candidates classified float-like/cat-like by coord dtype, flowing
 through the same signature counting, chart matching, aggregation, and leftover-dim slicing as
 input dims. A 1-float-input sweep returning a 128-bin spectrum auto-plots like a 2-float sweep.
                                                                                               ↑
 Design decisions (so implementers don't re-derive)

 - ResultTensor declaration: bn.ResultTensor(dims={"freq": np.linspace(0, 20e3, 128), "channel": 4}, units="dB")
 — dict value = int size (coords default range(n)) or 1-D array-like coords. Coords normalized
 to tuples of Python scalars at declaration (numpy-repr drift + str(ndarray) truncation would
 otherwise corrupt hash_persistent). No direction (auto-excludes tensors from optuna via the
 existing hasattr(rv, "direction") gate), no meaning_version (would flip vec history column
 identity). Wrong-shape returns raise with var/expected/got/job-id (fixes the silent drop);
 strict shape == equality prevents silent numpy broadcasting.
 - Dim-name collisions: element dim names may not collide with input var names, result var
 names, or repeat/over_time. Two tensor vars may share an element dim name iff their
 normalized coords are identical (shared-axis feature); any mismatch errors at setup.
 - ResultVec rebuild: subclasses ResultTensor with one element dim (coords x,y,z for size≤3,
 ints above), keeps its own direction slot, and pins its exact current hash_persistent
 via a 3-line override (golden test captured from main pre-merge) — avoids invalidating every
 existing cache without a CACHE_VERSION bump (which would orphan all over_time history, since
 CACHE_VERSION is folded into the history key).
 - Flatten compat seam: storage is always tensor-form; to_dataset() gains
 element_dims="flatten"|"keep" defaulting to "flatten" so every existing consumer sees
 today's shapes byte-for-byte (vec → _x/_y/_z columns). Tensor-aware charts opt into "keep".
 For over_time runs, flatten_element_dims is applied to bench_res.ds just before
 load_history_cache (bencher.py:~730) so existing on-disk vec history reconciles with
 zero migration.
 - over_time guard: general tensors + over_time=True → NotImplementedError at run_sweep        ↑
 setup, before any cache/history write. Defensive raise in history.data_var_columns too.
 - Slice surface = sel= / isel= (two kwargs, xarray-familiar, plain-data serializable →
 A2-S3 spec friendly: plots=[{"name": "heatmap", "sel": {"freq": 1000.0}}]). Numeric-coord     ↑
 dims use method="nearest"; string coords exact; scalar drops the dim, list keeps a subset.
 Works on input dims too (post-hoc complement to const_vars). repeat/over_time
 rejected in M1. No aggregation entries inside sel (ambiguous with string coords) —            ↑
 aggregation stays on the existing aggregate=/agg_fn= surface, whose explicit-list form is
 extended to accept element-dim names. Applied in to_dataset after result_var/flatten, before
 reduce; joins the _to_dataset_cache key via a canonical frozen form.                          ↑
 - Per-var matching, not global: PltCntCfg gains an element_dims fact
 ({var: [{dim, size, kind}]}) and effective_for(rv_name, removed_dims) returning per-var
 effective counts (input floats + surviving float-like element dims, etc.). filter() matches   ↑
 each candidate var; scalar-only sweeps take an identity path — bit-identical behavior.
 The vestigial vector_len axis and PltCntCfg.result_vars stay untouched (populating
 vector_len would globally un-match every chart; A2 S2 retires them later).                    ↑
 - Axis precedence: element dims (declared order) are highest-preference axes, then input dims
 (sweep order) — a spectrum's freq belongs on the x-axis, never on a 128-position slider.
 _to_panes_da therefore slices leftover input dims first (element dims moved to the front      ↑
 of pane_dims; scalar datasets unchanged).
 - M1 tensor-aware charts: line, heatmap, curve (the only repeats>1 renderer for 1 effective   ↑
 float dim), table. Bar/surface/volume/distribution keep scalar gates — tensor vars simply skip
 them while scalar vars in the same sweep render normally.                                     ↑
 - SQUEEZE must exempt element dims when element_dims="keep" (today's
 ds.squeeze(drop=True) at bench_result_base.py:336 would drop size-1 element dims).

 Auto-plot mapping (per result var, effective counts after sel/agg; encoded only in existing per-chart filters — no new hand-wired branches, per A2 P4)                                    ↑
 ┌──────────────────┬───────────┬─────────┬──────────────────────────────────────────────┐
 │ float-like elem  │  input    │ repeats │                  auto chart                  │
 │       dims       │  floats   │         │                                              │     ↑
 ├──────────────────┼───────────┼─────────┼──────────────────────────────────────────────┤
 │ 0 (scalar)       │ any       │ any     │ unchanged — today's behavior                 │     ↑
 ├──────────────────┼───────────┼─────────┼──────────────────────────────────────────────┤
 │ 1                │ 0         │ 1       │ line (x = elem dim; cats → by/panes)         │
 ├──────────────────┼───────────┼─────────┼──────────────────────────────────────────────┤     ↑
 │ 1                │ 0         │ >1      │ curve, mean±std vs elem dim                  │
 ├──────────────────┼───────────┼─────────┼──────────────────────────────────────────────┤
 │ 1                │ 1         │ any     │ heatmap (x = elem, y = input)                │
 ├──────────────────┼───────────┼─────────┼──────────────────────────────────────────────┤
 │ 2                │ 0         │ any     │ heatmap (x = elem₁, y = elem₂)               │
 ├──────────────────┼───────────┼─────────┼──────────────────────────────────────────────┤
 │ ≥3 effective     │           │         │ heatmap + panes/sliders (_to_panes_da slices │
 │ floats           │           │         │  input dims first)                           │
 ├──────────────────┼───────────┼─────────┼──────────────────────────────────────────────┤
 │ cat-like elem    │           │         │ counts into eff. cats → by grouping / panes  │
 │ dim              │           │         │                                              │
 └──────────────────┴───────────┴─────────┴──────────────────────────────────────────────┘
                                                                                               ↑
 Implementation phases (each an independently-green PR; pixi run ci gates each)

 PR 0 — the plan doc itself: plans/architecture/A5-tensor-results-and-nd-slicing.md
 (this design, both halves) + index row in plans/README.md. CHANGELOG note deferred to code PRs.

 PR 1 — type layer + dim roles
 - bencher/variables/results.py: ResultTensor (+ ElementDim NamedTuple: name, coords,
 kind ∈ float/int/cat), _normalize_dims validation (≥1 dim, no dup/NaN coords, reserved names),
 accessors element_dims()/element_dim_names()/shape/coords()/validate_value()/flat_names()/as_dim(),
 hash_persistent over (class, name, units, dims_spec). Add to ALL_RESULT_TYPES (critical —
 parametrised_sweep.py:83-90 classifies result vars by it) and RESULT_KIND_ORDER
 ((ResultTensor, "tensor") after (ResultVec, "vec")). Export from bencher/__init__.py.
 - New bencher/dim_roles.py: DimRole, REPEAT_DIM/TIME_DIM/RESERVED_DIM_NAMES,
 classify_dims, element_dims_for (raises on coord conflict), sweep_dims,
 validate_element_dims, flatten_element_dims, cell_present_mask — all callable from
 BenchData fields alone (no bench_cfg needed).
 - Tests: test/test_result_tensor.py (normalization, hash stability incl. linspace-vs-list and
 long-coord truncation guard); test_hash_persistent.py factories (:58-62, _BATCH_HASH_SCRIPT
 :340-373) get a cls(dims={"i": 3}) case; golden BenchCfg hashes must pass unmodified.

 PR 2 — serializable slice spec + to_dataset sel/isel
 - New bencher/results/slice_spec.py: validate_slice_spec (unknown/reserved dims,
 sel∩isel overlap), split_sel_by_method (numeric→nearest), freeze_spec (canonical hashable),
 dims_dropped_by_spec.                                                                         ↑
 - bench_result_base.py: to_dataset/to_hv_dataset gain sel/isel; applied after
 result_var subset (:284-293), before reduce; _to_dataset_cache_key (:227-242) appends
 freeze_spec. Fix NONE-path kdims (:208) to include surviving element dims.                    ↑
 - Tests: test/test_slice_spec.py + to_dataset(sel=...) cases on synthetic datasets
 (nearest/exact, isel=-1, sel-before-REDUCE std correctness, cache hit/miss, sel on input dims).
                                                                                               ↑
 PR 3 — tensor storage + guards + flatten seam
 - bencher/result_collector.py: setup_dataset (:233-238 region) allocates
 np.full(sweep_shape + rv.shape) with element coords after validate_element_dims;              ↑
 store_results (:370-376) validates + writes whole blocks (None/NaN → missing);
 precompute_result_arrays (:291-306) unified; add_metadata_to_dataset (:598-601) tensor
 branch. Delete dead ds_dynamic (result_collector.py:153,163,246; bencher.py:152-160).         ↑
 - bencher.py run_sweep: over_time × general-tensor NotImplementedError guard (before any
 cache access). history.py data_var_columns: defensive tensor raise.
 - bench_result_base.py: to_dataset(element_dims="flatten") default seam (lands here, with     ↑
 storage, so legacy consumers are protected the moment tensors can exist); SQUEEZE exempts
 element dims under "keep".
 - plt_cnt_cfg.py _samples_per_point (:156-181): presence per (point, repeat) = any            ↑
 element non-NaN (cells are written atomically, so all-NaN = unrecorded; partial NaN = real
 sample with invalid bins).                                                                    ↑
 - Tests: end-to-end live run (dims/coords/attrs/values, None → all-NaN cell, wrong shape and
 scalar-return raise), shared-dim conflict, benchmark + sample cache round-trips,              ↑
 save_result/load_result pickle, over_time guard leaves caches untouched.

 PR 4 — ResultVec unification (one PR; the risky one)
 - ResultVec(ResultTensor) per the design decision above; keep index_name/index_names
 verbatim; flat_names() -> index_names(). Drop the exploded branches in setup_dataset/         ↑
 store_results/precompute_result_arrays/add_metadata_to_dataset.
run_sweep: bench_res.ds = flatten_element_dims(...) immediately before load_history_cache
 — history sees the exact legacy schema (zero migration; incompatible_reason, regression,      ↑
 report_export, over_time plotting all untouched).
 - Tests (test/test_result_vec_compat.py + test_history_reconciliation additions): golden      ↑
 ResultVec hash pinned from main; column_identity pinned; flatten output byte-compatible
 with legacy layout (incl. size=4 x,y,z,3 naming); seeded legacy history record reconciles
 with no discard/retire events; test_result_nan_default, test_band_result stay green.          ↑

 PR 5 — signature + per-var matching + pane machinery
 - plt_cnt_cfg.py: element_dims fact populated in generate_plt_cnt_cfg (sizes cross-checked
 vs ds.sizes); effective_for(rv_name, removed_dims) with a zero-cost identity path.
 - bench_result_base.py filter() (:644-749): gains sel/isel (consumed here, never leaked
 to hvplot kwargs); agg-adjust block (:695-722) refactored to also drop scalar-sel'd dims;
 per-var matching replaces the single global match (:723), matched vars passed as the
 result_var list. map_plot_panes (:623): per-var drop_dims of foreign element dims.
 _to_panes_da (:805-884): element dims moved to front of pane_dims (input dims sliced
 first; scalar datasets unchanged).
 - Early spike test: heatmap + table over a hand-built element-dim dataset (de-risks hv.Dataset/
 hvplot behavior before chart edits).

 PR 6 — dataset-driven chart axes: line, heatmap, curve, table
 - holoview_result.py: _axis_dims(dataset, result_var) (float/cat axis candidates, element
 dims first, via dim roles) + _axis_label.
 - line_result.py: gate SCALAR_RESULT_TYPES + (ResultTensor,); to_line_ds derives x/by from
 _axis_dims (replaces float_vars[0] at :142); tensor vars bypass the tap path.
 - heatmap_result.py: gate (ResultFloat, ResultTensor); _pick_xy_axes re-signatured to
 dataset-driven (:84-90, call sites :112,:157,:201); tensors skip tap.
 - curve_result.py + _build_curve_overlay (holoview_result.py:246-291): kdims from
 _axis_dims; groupby = cat axes only; REDUCE {var}_std already keeps element dims.
 - Table: verify + test only.                                                                  ↑
 - Tests: per-chart tensor assertions via unwrap_hv (line x == elem dim; heatmap kdims ==
lem, input]; curve Spread present; mixed scalar+tensor sweep renders both with scalar chart
t unchanged, asserted against explain_selection()).

 7 — user API + docs
bench_result.py BenchResult.to (:101-135): sel=/isel= kwargs (flow to filter()
rough chart **kwargs; to_auto(plot_list=["line"], sel={...}) already flows via
nder_kwargs). utils.py resolve_aggregate (:321-379): explicit-list form validates
ainst input ∪ element dim names; True/int forms untouched (input dims only).
docs/how_to_use_bencher.md: new "Slicing Result Tensors" section after "Aggregating
mensions" (:272-295) — declaration, sel/isel semantics, sel-on-input-dims vs const_vars,
 combining with aggregate=["freq"], the auto-plot mapping table.

 PR 8 — generated examples + CHANGELOG
 - generate_meta_result_types.py: new "result_tensor" kind → example_result_tensor_1d/2d.py
 (spectrum-analyzer worker, small coord counts for HTML size) under
 bencher/example/generated/result_types/result_tensor/; hand-written
ample_result_tensor_slice.py showing sel/isel/aggregate side by side. Globally-unique
ample_result_* basenames; auto-enter test_generated_examples + split-render suite.
CHANGELOG: new type; behavior change: wrong-length ResultVec returns now raise; vec dataset
yout change for non-over_time runs (flatten default noted as the compat shim).

 Optional follow-up: mechanical "repeat"/"over_time" literal → REPEAT_DIM/TIME_DIM
 sweep (~40 sites).

 Explicitly deferred (M2+): over_time history + regression for general tensors; range/slice
 entries in sel; tensor tap→detail views; bar/surface/volume/distribution tensor support;
 per-element-dim units; to_dataset cache size cap.

 Verification

 - Per PR: pixi run ci (format, lint, tests+coverage). Full suite proves scalar-path
-regression via the effective_for identity path and unchanged _to_panes_da ordering —
pecially test_line_result, test_heatmap_result, test_curve_result,
st_bench_result_base, test_resolve_aggregate, test_explain_selection,
st_result_collector, test_history_reconciliation, test_generated_examples.
pixi run test-split (BENCHER_FORCE_SPLIT_RENDER=1) — tensor datasets must survive
 plot_sweep → save → load → render, with element_dims reconstructible from result_vars +
 loaded ds.
End-to-end eyeball: pixi run python ncher/example/generated/result_types/result_tensor/example_result_tensor_1d.py
 → line with freq on x; 2d variant → heatmap; slicing example → three sliced views.
 - Golden-hash tests: capture ResultVec hash_persistent and column_identity values from main
 before PR 4 merges.

 Top risks

 1. Vec history schema drift (PR 4): flatten output must be byte-compatible with the legacy
 exploded layout or existing over_time history is discarded/retired. Mitigation: seeded
 legacy-record reconciliation test + golden hash/identity pins.
 2. Legacy consumers seeing element dims early: mitigated by the element_dims="flatten"
 default landing with storage (PR 3), before any tensor example exists.
 3. hv.Dataset/hvplot behavior with element dims (kdims inference, groupby widgets): de-risked
 by the PR 5 spike test before chart edits.
 4. Per-var matching semantics (filter() debug output becomes per-var): log per-var at
 DEBUG, one summary at INFO; adjust test_explain_selection-style assertions.
 5. Pre-change benchmark caches (exploded vec datasets) served after upgrade: render as today,
 lack the tensor var for new charts — degrade-only, documented; clear_cache=True recovers.