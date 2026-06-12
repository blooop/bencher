# A3 — BenchData: One Data Contract for Rendering, Serialization, and Caching

**Status:** Proposal — the keystone document. A1 (rendering), A2 (selection), and A4
(caching) all converge on the contract defined here. Read this before the others.

---

## 1. The observation

Bencher currently has **four different representations of "a finished benchmark run"**,
each crossing a different boundary:

| Boundary | Representation today | Problems |
|---|---|---|
| In-process plotting | `BenchResult` — data + 17 renderer base classes + `bench_cfg` (1,060-line param object) | god object; renderers and data inseparable |
| collect/render split | pickled `BenchResult` (`bencher/render.py`, `save_result`/`load_result`) | pickles the whole god object incl. live `plot_callbacks` callables; arbitrary-code-exec on load |
| result cache (Layer B) | pickled `BenchResult` minus `object_index` (`result_collector.py:404-411`) | same pickle exposure; cache format = internal class layout, so refactors silently invalidate or corrupt |
| over_time history (Layer C) | pickled `xr.Dataset` in diskcache; PR #799 prototypes netCDF files instead | two competing formats in flight |

Every architectural problem in A1/A2/A4 traces back to this: **the unit of exchange is
a live Python object graph instead of data.**

PR #932 already defines the right shape — frozen `BenchData` (`dataset: xr.Dataset`,
`input_vars`, `result_vars`, `plt_cnt_cfg`, `run_meta`, optional extras). This plan
promotes it from "what plugins receive" to **the single contract all four boundaries
use**.

## 2. Target contract

```python
@dataclass(frozen=True)
class BenchData:
    dataset: xr.Dataset                 # the N-D results tensor
    input_vars: tuple[VarSpec, ...]     # name, kind, units, bounds, level — plain data,
    result_vars: tuple[VarSpec, ...]    #   derived FROM param objects, not param objects
    signature: DataSignature            # A2's enriched PltCntCfg
    run_meta: RunMeta                   # name, timestamp, sweep_hash, bencher version,
                                        #   schema_version
    plot_specs: tuple[PlotSpec, ...]    # A2's serializable name+kwargs specs
    artifacts: ArtifactManifest         # media files referenced by the dataset (A4):
                                        #   relative paths + content hashes
```

Design rules:

1. **No param objects, no callables, no panel/holoviews objects inside.** `VarSpec` is
   a plain dataclass extracted from the sweep variables. (The param objects stay in
   `BenchCfg` for the *configuration* side; `BenchData` is the *output* side.)
2. **Everything is serializable without pickle**: `dataset` → netCDF (already proven
   viable by PR #799's history work; media-reference vars store relative paths as
   strings — they already do), everything else → JSON. A saved run becomes a
   directory (or zip):

   ```
   run_2026-06-11T12-00-00/
     data.nc            # xr.Dataset
     manifest.json      # VarSpecs, signature, run_meta, plot_specs, artifact hashes
     artifacts/         # img/, vid/, rrd/ referenced from data.nc
   ```

3. **Versioned**: `run_meta.schema_version`; loaders refuse-with-message on unknown
   majors. This is what makes cache entries and saved runs survive refactors.

## 3. What each subsystem gains

- **Rendering (A1):** plugins render `BenchData`; the render process of the
  collect/render split becomes literally `registry.render(load_bench_data(path))` —
  `render.py`'s purpose, with no pickle and no foreign-object reconstruction. The
  original motivation for the split (foreign C-extension state) is *better* served:
  the render process now imports nothing of the user's world.
- **Security:** `load_result` stops being an arbitrary-code-execution surface
  (current `pickle.load` in `render.py`). The pickle-warning docstring from plan 04
  becomes unnecessary. CVE-class issues like the diskcache one stop mattering for this
  layer entirely.
- **Caching (A4):** Layer B stores a run directory instead of a pickled class; cache
  hits survive bencher upgrades (schema-versioned) instead of breaking on internal
  refactors. Layer C history = appending along `over_time` in netCDF — converges with
  and supersedes PR #799's `history_dir`.
- **Interop (new capability, free):** a saved run is readable by *anything* — pandas,
  Julia, a CI script, a different visualization tool. Today it's readable only by the
  exact bencher version that wrote it.
- **`BenchResult` compatibility:** `BenchResult` becomes a facade over a `BenchData`
  (`bench_result.data`), constructed both by live sweeps and by `load()`. `.ds`,
  `.bench_cfg`, `.plt_cnt_cfg` remain as properties during deprecation.

## 4. Migration phases

**Phase D1 — extract the type.** Land #932's `BenchData`/`RunMeta` (A1 Phase 0 does
this). Add `BenchResult.to_bench_data()` building it from a live result, and
`VarSpec.from_param(v)` extractors. Pure addition; verify with unit tests asserting a
round-trip `to_bench_data()` preserves dataset identity and var metadata.

**Phase D2 — directory save format.** Implement `save_bench_data(data, path)` /
`load_bench_data(path)` (netCDF + JSON + artifacts copy). Add a *parallel* CLI path in
`render.py` that accepts a run directory. Keep pickle `save_result`/`load_result`
working unchanged. Verify: extend `test/test_render.py` round-trip tests to the new
format; `test_split_render_examples.py` gains a parametrized twin that routes every
result type through the directory format. Media-heavy types (image/video/rerun) are the
acceptance gate — their artifact paths must resolve after relocation to a different
directory.

**Phase D3 — flip the split-render default.** `BENCHER_FORCE_SPLIT_RENDER` and
`Bench.collect()` use the directory format; pickle path deprecated (warning), removed
two minors later. The existing three-layer split-render test defense is exactly the
harness that makes this flip safe — rely on it.

**Phase D4 — caching convergence.** Handled in A4 (Layer B/C move onto the format).

**Phase D5 — facade slimming.** Renderer access to `self.bench_cfg.<flag>` is replaced
by fields on `BenchData`/`DataSignature`; when no renderer touches `bench_cfg`, the
data/config separation is complete. (Long tail; track with a grep-count metric in CI:
`grep -rn "bench_cfg\." bencher/results/ | wc -l` should monotonically decrease.)

## 5. Risks & decisions

- **netCDF fidelity:** object-dtype variables (media path strings, "NAN" sentinels —
  see `result_collector.py:48-66`) need an encoding convention; PR #799 already solved
  the pandas-3.0 ArrowStringArray sanitization — reuse it. Prototype D2 against the
  worst case first: `ResultContainer` + rerun examples.
- **Dataset size:** netCDF write adds I/O vs pickle; measure in the perf-tracking CI
  job. Zarr is the escape hatch for huge tensors — keep the format choice behind
  `save_bench_data`'s implementation, not in the contract.
- **OWNER DECISION:** directory vs single-file zip for the run format (directory is
  simpler and git-LFS-friendly; zip is tidier to email). Recommend directory.
- **Sequencing:** D1–D2 can run concurrently with A1 Phase 1–2. D3 should wait until
  A2 Phase S3 (plot specs) so the manifest never has to encode callables.
