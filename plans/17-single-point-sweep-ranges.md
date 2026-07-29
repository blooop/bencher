# Plan 17 — Single-Point Sweep Ranges

**Goal:** Let a bounded sweep collapse to a single point. `with_bounds(x, x)`
currently raises, so every caller whose range is computed at run time needs a
branch to switch representation when the range degenerates — and the workaround
lands the run in a *different* cache and history series than the same point taken
from a range.

**Branch name:** `fix/degenerate-sweep-bounds`

**⚠️ Read first:** this changes what a sweep's shape-affecting fields look like
for one previously-impossible input, so re-read the hashing contract in
`bencher/variables/sweep_base.py:110-125` before starting. No existing valid
input may change identity.

---

## Problem statement (with evidence)

### P1 — A collapsed range is rejected

`SweepBase.with_bounds(low, high, samples)` raises when the bounds are equal:

```python
if low >= high:
    raise ValueError(f"low must be less than high, got low={low}, high={high}")
```

(`bencher/variables/sweep_base.py:232-233`). A one-point range is perfectly
well-defined — take one sample at that value — and rejecting it means any caller
computing bounds at run time (from configuration, a measured limit, a CLI flag,
an environment override, a previous sweep's optimum) must special-case the
degenerate case.

### P2 — Both declarative entry points inherit the raise

- `bn.sweep(name, bounds=(x, x))` with a `SweepBase` object delegates straight
  to `with_bounds` (`bencher/variables/inputs.py:748-749`).
- The deferred string form returns a spec dict (`bencher/variables/inputs.py:753`)
  that `SweepExecutor.convert_vars_to_params` resolves by calling `with_bounds`
  (`bencher/sweep_executor.py:135-137`).

So there is no spelling of "sweep this range, which happens to be one point"
that works.

### P3 — The workaround silently moves the series

The available workaround is to switch representation: pass `values=[x]` instead
of `bounds=(x, x)`, which routes to `with_sample_values` rather than
`with_bounds`. Those set *different* shape-affecting fields, and both are folded into the
sweep's identity tuple — `_sweep_identity()` appends `sweep_bounds` and
`sample_values` for `IntSweep` (`bencher/variables/inputs.py:542-545`) and those
plus `step` for `FloatSweep` (`bencher/variables/inputs.py:634-637`), per the
contract at `bencher/variables/sweep_base.py:112-125`.

The consequence is not cosmetic. A caller who sweeps `[0.1, 0.9]` on most runs
and collapses to a single point on some runs is, on those runs, writing to a
different cache key and a different history key than the range form would
produce — so the collapsed run does not append to the trend it looks like it
belongs to. Under plan 15 it would be reported; today it is silent, and it is
caused entirely by having to change representation to express a legal range.

### P4 — The error arrives late for the deferred form

For `bn.sweep("x", bounds=(lo, hi))` the bounds are not validated when the spec
is built, only when `plot_sweep` resolves it (`bencher/sweep_executor.py:135`).
A computed range that collapses therefore fails partway into a run rather than at
declaration time.

---

## Proposed design

### D1 — Accept `low == high` as a one-sample range

Change the guard to reject only `low > high`:

```python
if low > high:
    raise ValueError(f"low must not exceed high, got low={low}, high={high}")
```

A sweep whose bounds are equal yields exactly one sample at that value, at every
sampling resolution — `subsampling_divisions` cannot subdivide a zero-width
interval, so the sample count is 1 regardless.

**Relaxing the guard alone is not sufficient**, because the sample-generation
paths do not degrade gracefully:

| Sweep type | Zero-width behavior today | Needed |
|---|---|---|
| `IntSweep` (`bencher/variables/inputs.py:556-560`) | `range(x, x + 1)` → `[x]` | already correct |
| `FloatSweep`, no `step` (`bencher/variables/inputs.py:657`) | `np.linspace(x, x, N)` → **N copies of `x`** | one sample |
| `FloatSweep`, with `step` (`bencher/variables/inputs.py:659`) | `np.arange(x, x, step)` → **empty** | one sample |

So D1 is two changes: relax the comparison, and short-circuit
`values()` to a single-element list when the range is zero-width — before the
`linspace`/`arange` call, in the shared base if the check can live there.

The same relaxation applies to `with_samples` and any other bounds validation
reachable from `bn.sweep`; audit for other `>=` comparisons on bounds.

### D2 — `samples` on a degenerate range

`with_bounds(x, x, samples=5)` asks for something that does not exist. Two
defensible answers:

1. **Raise**, naming the contradiction — the caller asked for 5 samples of a
   zero-width range and probably has a bug upstream.
2. **Clamp to 1**, silently or with a warning — friendlier to a generic caller
   that always passes `samples=N` and does not inspect the range.

**Recommendation: raise.** A caller who computes bounds and passes an explicit
sample count is in a position to handle the degenerate case, and silently
returning 1 sample where 5 were requested is the kind of quiet disagreement
between declaration and data this plan exists to remove. **OWNER DECISION** —
option 2 is reasonable if the friendlier default is preferred; the tests below
assume option 1.

### D3 — Validate the deferred spec early

`bn.sweep(name, bounds=(lo, hi))` should reject `lo > hi` when the spec is built
(`bencher/variables/inputs.py:726-737`, alongside the existing `samples <= 0` and
`values`-with-`bounds` checks) rather than at resolution time. This is
independent of D1 and worth doing regardless: it turns a mid-run failure into a
declaration-time one.

### D4 — Document the equivalence and the non-equivalence

At `with_bounds` and at `bn.sweep`: a zero-width range is one sample, and
`bounds=(x, x)` is **not** interchangeable with `values=[x]` for identity
purposes — they are different declarations and hash differently. Callers who
sometimes collapse a range should keep using the bounds form so the series stays
put.

---

## Phased steps

1. Relax the guard in `with_bounds` (D1); make the sample-generation path return
   exactly one value for a zero-width range, for every bounded sweep type.
2. Decide and implement D2.
3. Add the early bounds validation to `bn.sweep` (D3).
4. Documentation and a `CHANGELOG.md` entry (D4).

## Tests / acceptance criteria

- `with_bounds(x, x)` on every bounded sweep type yields exactly one sample,
  equal to `x`, at subsampling divisions 1 through 6.
- `with_bounds(hi, lo)` with `hi > lo` still raises.
- `bn.sweep("x", bounds=(x, x))` resolves through `plot_sweep` and produces a
  dataset with a length-1 coordinate for `x`.
- A full sweep with one degenerate input variable and one normal one produces the
  expected `(1, N)` dataset shape and does not error in xarray broadcasting.
- **Identity guard:** `bounds=(x, x)` and `values=[x]` produce *different*
  `hash_persistent()` values, asserted explicitly so the distinction is a
  documented contract rather than an accident, and so a later "simplification"
  that routes one to the other is caught.
- Existing golden hashes and every currently-valid bounds input are unchanged —
  `test_sweep_bounds_change_bench_hash` (`test/test_hash_persistent.py:818`) is
  the anchor.
- `bn.sweep("x", bounds=(5, 1))` raises at spec-construction time (D3).

## Migration & compatibility

Strictly a relaxation: an input that raised now succeeds. No currently-working
call changes behavior, and no hash moves. D3 moves one error earlier, which is
observable only for code that constructs an invalid spec and never resolves it.

## Risks

- **Shipping D1 as a one-line guard change.** Relaxing the comparison without
  the `values()` short-circuit is worse than the status quo: a `linspace` sweep
  would silently take N samples at the same point (N× the run time, duplicate
  coordinates), and a `step` sweep would take none. The per-type table in D1 is
  the checklist.
- **Integer bound coercion.** `IntSweep._coerce_bound`
  (`bencher/variables/inputs.py:539-540`) casts through `int()`; confirm two
  distinct floats cannot coerce to an accidentally zero-width integer range, and
  that a genuinely zero-width one survives coercion.
- **Duplicate coordinates reaching xarray.** If a short-circuit is missed for one
  sweep type, the failure surfaces far away as an xarray indexing or
  broadcasting error. Assert on dataset shape in the tests, not just on
  `values()`.

## Coordination

- **Plan 15/16** — P3's silent series move is exactly the class of drift plan 15
  reports and plan 16 makes assertable; this plan removes one of its causes.
- **Plan 18** — a reusable sweep declaration is much less useful if a computed
  range cannot degenerate, since that is when specs are built programmatically.
