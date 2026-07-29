# Plan 18 — Reusable Sweep Declarations

**Goal:** Give a sweep declaration — its input, result, and constant variables,
its tag, its title — a value object that can be built once, inspected, varied,
and run against more than one worker class. Today that declaration exists only as
fifteen keyword arguments to a method on a live `Bench`, so running the same
measurement in two environments means restating all of it at both sites, with
nothing to detect drift between them.

**Branch name:** `feat/sweep-spec`

**⚠️ Read first:** plan 13 owns *run* configuration (repeats, sampling
resolution, `show`, publishing) via `@bn.benchmark(...)`. This plan owns the
*sweep* declaration — what is measured, not how the run is driven. Keep the two
surfaces separate; a spec that also carries `repeats` duplicates plan 13.

---

## Problem statement (with evidence)

### P1 — A declaration is not a value

`plot_sweep()` takes fifteen keyword arguments
(`bencher/bencher.py:271-288`) and immediately consumes them into a `BenchCfg`
inside its own body. There is no object representing "this sweep", so a
declaration cannot be stored in a module, passed to a function, compared against
another, or asserted on in a test without running the benchmark.

### P2 — One measurement in several environments means restating everything

A benchmark that must run against more than one worker — a fast and a slow
backend, a mocked and a live dependency, two hardware tiers, two library versions
— has one declaration and N call sites. Every argument is retyped at each site.
Nothing links them, so the sites drift: one gains a result variable, one keeps an
old constant, and because each side still produces a valid benchmark, nothing
fails. The divergence is only visible by reading both call sites side by side.

### P3 — Variation on a shared base is hand-merged dicts

When the environments *should* differ in a couple of places — a longer timeout
here, an extra metric there — the shared part and the local part have to be
merged by hand at each site, with the precedence expressed as whatever dict
literal ordering the author chose. There is no declared rule for which layer
wins, and no way to enumerate the asymmetries between two bindings of one
declaration.

### P4 — The class-independent form exists but is undiscoverable

`bn.sweep("name", bounds=...)` returns a spec dict resolved by name at
`plot_sweep` time (`bencher/variables/inputs.py:753-759`, resolved at
`bencher/sweep_executor.py:130-145`), and `const_vars` accepts a plain
`{name: value}` dict (`bencher/bencher.py:437-438`, converted through the same
by-name resolution). Together these already let a declaration be written without
referencing any class — which is exactly what makes reuse across workers
possible.

This is close to unadvertised. The name-based form appears in `bn.sweep`'s
docstring and, indirectly, in a deprecation warning telling users to stop passing
`input_vars` as a dict (`bencher/bencher.py:406-411`). Nothing in the docs or
gallery presents "declare a sweep without naming a class" as a pattern, so users
reach for `Cls.param.x` and bind their declaration to one class for no reason.

---

## Proposed design

### D1 — `bn.SweepSpec`

A frozen dataclass mirroring `plot_sweep`'s declarative arguments only:

```python
LATENCY = bn.SweepSpec(
    title="Request latency",
    description="...",
    input_vars=[bn.sweep("concurrency", bounds=(1, 64))],
    result_vars=["latency_ms", "error_rate"],
    const_vars={"payload_bytes": 1024},
    tag="latency",
)
```

- Variables may be given in every form `plot_sweep` already accepts; the
  name-based forms are what make a spec class-independent, and the docstring
  should say so.
- Excluded on purpose: `run_cfg`, `pass_repeat`, `auto_plot`, `plot_callbacks`,
  `sample_order` — run-time and rendering concerns. `plot_callbacks` in
  particular must stay out, since A2 is moving toward serializable plot specs and
  a callable in a frozen spec would defeat the point.

### D2 — Composition with one documented rule

```python
SLOW = LATENCY.with_(const_vars={"timeout_s": 30}, result_vars=[..., "retries"])
```

- `with_(**overrides)` returns a new spec. Precedence is **override wins**, per
  field, with one explicit rule per field kind:
  - scalars (`title`, `tag`, `description`): replaced.
  - `const_vars`: shallow-merged, override wins per key.
  - `input_vars` / `result_vars`: **replaced, not appended**, because order
    matters for `input_vars` (it sets dimension layout and is hashed in list
    order, `bencher/bench_cfg.py:838`) and silent appending is how duplicate
    result variables arise (see plan 20). Provide `plus_result_vars(...)` for
    the additive case so the intent is written down.
- `merge(other)` for the symmetric case, defined as `self.with_(**other.set_fields)`.
- Because a spec is a value, `spec_a == spec_b` and a rendered diff of two specs
  both become available — which is what makes P2's drift visible.

### D3 — `bench.plot_sweep(spec)` and `spec.bind(worker)`

- `plot_sweep` accepts a `SweepSpec` as its first positional argument (it is
  currently `title`, so accept a spec there by type and keep `title=` working).
  Explicit keyword arguments passed alongside a spec win over it, for one-off
  tweaks.
- `spec.bind(worker_cls) -> dict` resolves the spec against a worker and returns
  the exact keyword arguments `plot_sweep` would receive. This is the testability
  payoff: a project can assert what each of its environments resolves to without
  constructing a bench or running anything, and it pairs directly with plan 16's
  identity API — `bn.sweep_identity(**spec.bind(Worker))`.

### D4 — Documentation

- A gallery example: one spec, two workers, one report. This is the pattern P2
  describes and there is currently nothing to point at.
- A docs section on class-independent declarations (P4): prefer
  `bn.sweep("name", ...)` and `const_vars={"name": value}` over
  `Cls.param.name` when a declaration is meant to be reused, and note that
  by-name resolution raises a clear error listing available parameters when a
  name is wrong (`bencher/sweep_executor.py:28-36`).

---

## Phased steps

1. `bencher/sweep_spec.py`: the frozen dataclass, `with_`, `plus_result_vars`,
   `merge`, `bind`. No changes to `plot_sweep` yet — `bench.plot_sweep(**spec.bind(W))`
   already works and is a complete, shippable increment on its own.
2. `plot_sweep` accepts a spec positionally, with keyword arguments taking
   precedence.
3. Docs and gallery example (D4).
4. *(Optional)* `SweepSpec` accepted wherever plan 13's declaration bundle is
   read, so a benchmark can declare both halves in one place.

## Tests / acceptance criteria

- `bench.plot_sweep(spec)` and `bench.plot_sweep(**spec.bind(W))` produce
  identical `BenchCfg` hashes.
- A keyword argument passed alongside a spec overrides the spec's value.
- `with_` precedence per field kind, including that `const_vars` merges and
  `result_vars` replaces; `plus_result_vars` appends.
- One spec bound to two different worker classes yields two configs differing
  *only* in `bench_name`, with identical input/const/result identity — the
  property that makes P2's drift detectable.
- A spec is picklable and equality-comparable; a spec containing a lambda in any
  field is rejected at construction with a message pointing at D1's exclusions.
- A spec referencing an unknown variable name surfaces the existing `KeyError`
  from `_resolve_param` at `bind` time, listing available parameters.

## Migration & compatibility

Additive. Every existing `plot_sweep` call keeps working unchanged; a spec is an
alternative way to supply the same arguments. Phase 1 alone requires no change to
`bencher.py` at all.

## Risks

- **Overlap with plan 13.** The two must not both own `repeats`/`tag`. Suggested
  split: plan 13's bundle owns run defaults and *may* carry a default `tag`; a
  spec's `tag` is part of the measurement declaration and wins when both are
  present. Settle this before phase 2. **OWNER DECISION.**
- **A spec drifting into a second config type.** If `SweepSpec` accumulates
  run-time fields it becomes a rival `BenchCfg`. Keep it strictly a frozen record
  of `plot_sweep`'s declarative arguments; anything computed belongs in
  `BenchCfg`.
- **Encouraging appended `result_vars`.** Convenient appending is exactly how
  duplicate result variables get declared, which today silently splits a cache
  key (plan 20). D2's replace-by-default and the explicit `plus_result_vars` are
  deliberate; plan 20's validation is the backstop.

## Coordination

- **Plan 13** — complementary halves of one declaration; resolve the `tag`
  ownership question above.
- **Plan 16** — `spec.bind()` feeding `sweep_identity()` is how a project pins
  what each environment resolves to.
- **Plan 17** — programmatically built specs are exactly where computed ranges
  collapse to a single point.
- **Plan 20** — spec composition is the main source of duplicate variables;
  these two plans should land in either order but be aware of each other.
- **A2/A3** — keep specs free of callables and live objects so they stay
  serializable under A3's contract.
