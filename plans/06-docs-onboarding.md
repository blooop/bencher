# Plan 06 — Docs & Onboarding

**Goal:** Make a new user productive in 5 minutes and consolidate scattered feature docs.
All tasks are docs-only; the risk is staleness, so every code snippet you write must be
copy-pasted from a *working* example file, not written from memory.

**Branch name:** `docs/onboarding`

**After every task:** run `pixi run generate-docs` (must complete without errors) and
`pixi run ci`. New doc pages must be added to the toctree in `docs/index.md` AND checked
against `docs/conf.py` (CLAUDE.md requires conf.py to include added docs).

---

## Task 1: README "Getting Started" section

`README.md` currently states "More documentation is needed" and never links the gallery.

1. Add, directly after the badges, a section:
   - One-paragraph pitch: bencher sweeps a function across the Cartesian product of typed
     parameters, caches each sample, stores results in an N-D xarray, and auto-selects
     interactive plots from the parameter/result types — no loops, no plot code.
   - A minimal runnable example: copy the code from
     `bencher/example/example_simple_float.py`, trimmed to its essence (sweep class,
     `benchmark()` method, run call). Verify your trimmed version actually runs:
     save it to `/tmp/readme_check.py` and `pixi run python /tmp/readme_check.py`.
   - Links: live docs `https://bencher.readthedocs.io/`, the full getting-started guide
     `docs/how_to_use_bencher.md`.
2. Delete or rewrite the "More documentation is needed..." sentence.

## Task 2: "Choosing a result type" decision table

In `docs/how_to_use_bencher.md`, add a section with this table (verify each class exists
in `bencher/variables/results.py` before listing it):

| You return... | Use | Example in gallery |
|---|---|---|
| a single number | `ResultFloat` | link a `result_types/result_float` example |
| success/failure | `ResultBool` | ... |
| a vector | `ResultVec` | ... |
| text | `ResultString` | ... |
| an image file path | `ResultImage` | ... |
| a video file path | `ResultVideo` | ... |
| any file path | `ResultPath` | ... |
| a container/composite | `ResultContainer` / composable containers | ... |

Fill the example links by finding one generated example per type:
`ls bencher/example/generated/result_types/`.

## Task 3: "Common mistakes" section

Append to `docs/how_to_use_bencher.md` (it already has a common-mistakes orientation —
extend, don't duplicate):

- Encoding combinations in one variable instead of separate sweep dimensions.
- Non-pure benchmark functions (global state + caching = corrupted results).
- NaN defaults: since v1.105, missing results default to NaN, not 0. If downstream code
  expects 0, set `default=0` explicitly on the result variable. (Verify the exact
  behavior in CHANGELOG.md before writing this.)
- Forgetting `pixi run` prefixes when developing bencher itself.

## Task 4: Caching guide — new `docs/caching.md`

Explain, sourcing facts from `bencher/job.py`, `bencher/bench_cfg.py` (cache params) and
`bencher/example/example_sample_cache.py`:

1. The two caches: per-sample cache (hash of inputs → result, survives restarts in
   `cachedir/`) vs benchmark-level result cache.
2. Which `BenchRunCfg` flags control each (`cache_results`, `cache_samples`,
   `clear_cache`, `clear_sample_cache`, `overwrite_sample_cache`, `only_hash_tag`) —
   copy the param docstrings, don't invent semantics.
3. A worked example based on `example_sample_cache.py`.
4. How `save_result`/`load_result`/`render_report` (the collect/render split) relate.

Add to toctree + conf.py.

## Task 5: Over-time guide — new `docs/over_time.md`

Consolidate the over_time story currently scattered across `docs/intro.md` (lines ~41-66),
`docs/over_time_slider_fix.md`, and generated examples in
`bencher/example/generated/*/over_time/`:

1. What it does (snapshot sweeps over time, slider scrubbing) and when to use it (CI
   trend tracking, long studies).
2. How to record: copy a working pattern from an over_time generated example.
3. Link to the regression-detection features (`regression_method` etc. in bench_cfg)
   since over_time history feeds them.
4. Move `docs/over_time_slider_fix.md` content into a "Known limitations" appendix of
   this page, then delete the old file and remove it from any toctree/conf.py reference.

## Task 6: Examples index — new `docs/examples_index.md`

List every hand-written example in `bencher/example/*.py` (not `generated/`, not `meta/`)
with a one-sentence description **derived from reading each file's docstring/code**.
End with links to the generated galleries by category. Add to toctree + conf.py.

## Task 7: Missing public docstrings

1. `BenchRunCfg` (in `bencher/bench_cfg.py`): the class has param docs per-field but
   verify whether the class itself has a docstring; if not, add one summarizing what it
   configures and pointing to docs/caching.md and docs/over_time.md.
2. `Bench.optimize()` in `bencher/bencher.py`: extend the docstring to document the
   aggregation and multi-objective behavior — derive the description from the code and
   from `test/` files covering optimize, not from guesswork.

## Final verification

```bash
pixi run generate-docs
pixi run ci
```

Then build docs if a task exists for it (`grep -n "docs" pyproject.toml` for a
sphinx-build task) and confirm new pages appear with no broken-link warnings.
