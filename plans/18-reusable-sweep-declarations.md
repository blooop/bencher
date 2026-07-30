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
`{name: value}` dict (`bencher/bencher.py:436-437`, converted through the same
by-name resolution). Together these already let a declaration be written without
referencing any class — which is exactly what makes reuse across workers
possible.

This is close to unadvertised. The name-based form appears in `bn.sweep`'s
docstring and, indirectly, in a deprecation warning telling users to stop passing
`input_vars` as a dict (`Bench.plot_sweep`, `bencher/bencher.py:406-417`). Nothing in the docs or
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

Seven fields, one per declarative argument of `plot_sweep`
(`bencher/bencher.py:271-288`). Every field defaults to `None`, meaning *unset*,
so a spec never has to state what it does not care about:

| Field | Type | Accepted forms | Notes |
|---|---|---|---|
| `title` | `str \| None` | string | Unset keeps `plot_sweep`'s generated title (`bencher/bencher.py:445-456`). Outside cache identity (`bencher/bench_cfg.py:820-823`). |
| `description` | `str \| None` | string | Rendered before the plots. Not hashed. |
| `post_description` | `str \| None` | string | Rendered after the plots. Not hashed. |
| `input_vars` | `list[param.Parameter \| str \| dict] \| None` | `Cls.param.x`, `"x"`, `bn.sweep("x", bounds=(1, 8))` | Order is the dimension layout and is folded into the hash in list order (`bencher/bench_cfg.py:837-838`). Unset auto-discovers every input on the worker (`bencher/bencher.py:347-357`); `[]` declares none. |
| `result_vars` | `list[param.Parameter \| str \| dict] \| None` | `Cls.param.y`, `"y"`, `bn.sweep("y")` | Contributes as an unordered set (`bencher/bench_cfg.py:840-841`). Sweep shaping is input-only — see below. |
| `const_vars` | `list[tuple[param.Parameter \| str \| dict, Any]] \| dict[str, Any] \| None` | `[(Cls.param.x, 4)]`, `[("x", 4)]`, `{"x": 4}` | The mapping form expands to pairs (`bencher/bencher.py:436-437`); list entries must be 2-sequences. Unordered set in the hash (`bencher/bench_cfg.py:845-849`). |
| `tag` | `str \| None` | string | Cache and history identity: hashed (`bencher/bench_cfg.py:834`) and composed as `run_cfg.run_tag + tag` (`bencher/bencher.py:524`, and on the `optimize()` path at `:1224`). Precedence against plan 13 is D5. |

Three facts about the variable fields, each checked against
`SweepExecutor.convert_vars_to_params` (`bencher/sweep_executor.py:89-149`):

- The by-name forms — a plain string, a `bn.sweep(...)` spec dict, a
  `{name: value}` const mapping — are what make a spec class-independent, and the
  docstring should say so. They resolve against the worker at `plot_sweep` time,
  so a spec written entirely from names raises `TypeError` on a bench with no
  worker class instance (`bencher/sweep_executor.py:122-126`); pair it with
  `bind()` (D3), or use param objects.
- Sweep shaping (`values`, `bounds`, `samples`, `max_subsampling_divisions`)
  applies to inputs and consts only. A `result_vars` entry may be a bare
  `bn.sweep("y")`, but `bn.sweep("y", samples=3)` raises `AttributeError`: the
  dict branch calls `with_samples` (`bencher/sweep_executor.py:132-138`) and
  result variables are not `SweepBase` (`ResultFloat(Number)`,
  `bencher/variables/results.py:103`). A spec rejects a shaped result var at
  construction rather than mid-run.
- Passing the *whole* `input_vars` field as a `{name: values}` mapping is
  deprecated and normalized to a list of spec dicts
  (`bencher/bencher.py:406-416`); a spec holds the list.

Excluded on purpose — the remaining eight arguments, every one a run-time or
render-time concern:

- `run_cfg` — run configuration; plan 13 owns it, and a spec carrying it
  duplicates that plan.
- `pass_repeat` — execution: whether the repeat index reaches the worker
  (`bencher/sweep_executor.py:61-65`).
- `sample_order` — sampling traversal only, documented as leaving dataset and
  plot dimension order unchanged (`bencher/bencher.py:323-324`).
- `time_src` — the timestamp of one run, not a property of the measurement.
- `auto_plot` — rendering; resolved through `run_cfg.auto_plot`
  (`bencher/bencher.py:401-402`).
- `plot_callbacks` — rendering, and it must stay out for a second reason: a
  callable in a frozen spec breaks equality and pickling, and A2 is moving toward
  serializable plot specs.
- `aggregate` / `agg_fn` — post-collection reduction. They land as
  `agg_over_dims`/`agg_fn` on `BenchCfg` (`bencher/bencher.py:512`, `:526-527`)
  and never reach `hash_persistent` (`bencher/bench_cfg.py:828-851`), so they can
  change between runs without invalidating collected samples: analysis-time, not
  declaration.

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

### D5 — `tag` precedence against plan 13

Plan 13's spine is **env > call-site > declared > library default**, applied to
the tag in its D3 (*Tag defaulting from the callable*). A spec's `tag` belongs to
the *measurement* declaration, so it sits at the **declared** tier beside plan
13's `@bn.benchmark(tag=...)` — and when both are set the spec wins, because the
spec states what is being measured while the decorator states how the run is
driven, and the tag is measurement identity (it is hashed,
`bencher/bench_cfg.py:834`). An explicit `plot_sweep(tag=...)` or
`bn.run(tag=...)` at the call site still beats both; an env override still beats
everything.

Effective tag for one sweep, highest precedence first:

1. `BENCHER_TAG` — env (plan 13 D2, *Env overrides in `bn.run`*).
2. `plot_sweep(tag=...)` or `bn.run(tag=...)` — call site.
3. `SweepSpec.tag` — declared, measurement side.
4. `@bn.benchmark(tag=...)` — declared, run side (plan 13 D3).
5. The decorated callable's `__name__` — plan 13 D3, decorated targets only.
6. `""` — library default (`bencher/bencher.py:281`).

A spec's `tag=None` is unset and leaves tiers 4–6 alone, so adopting specs
changes no existing tag. Tier 3 beating tier 4 must be resolved *before* the tag
reaches `BenchCfg`, not left to the existing plumbing: plan 13's tag lands in
`run_cfg.run_tag`, a `plot_sweep` tag is the per-sweep component, and the
effective tag is their concatenation `run_cfg.run_tag + tag`
(`bencher/bencher.py:524`). Appending instead of suppressing would give a
spec-tagged sweep both tags and a cache key matching neither. Because the tag is
hashed, which tier wins decides cache and over_time identity — settled once here,
not per project.

**OWNER DECISION** — confirm this ordering, tier 3 over tier 4 in particular,
before phase 2.

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
  field is rejected at construction with a message pointing at D1's exclusions, as
  is a shaped result var (`bn.sweep("y", samples=3)`) rather than letting it
  surface as an `AttributeError` mid-run.
- A spec referencing an unknown variable name surfaces the existing `KeyError`
  from `_resolve_param` at `bind` time, listing available parameters.

## Migration & compatibility

Additive. Every existing `plot_sweep` call keeps working unchanged; a spec is an
alternative way to supply the same arguments. Phase 1 alone requires no change to
`bencher.py` at all.

## Risks

- **Overlap with plan 13.** The two must not both own `repeats`/`tag`. `repeats`
  stays plan 13's alone; the `tag` split is written out as a full precedence
  ordering in D5, for the owner to confirm before phase 2. **OWNER DECISION.**
- **A spec drifting into a second config type.** If `SweepSpec` accumulates
  run-time fields it becomes a rival `BenchCfg`. Keep it strictly a frozen record
  of `plot_sweep`'s declarative arguments; anything computed belongs in
  `BenchCfg`.
- **Encouraging appended `result_vars`.** Convenient appending is exactly how
  duplicate result variables get declared, which today silently splits a cache
  key (plan 20). D2's replace-by-default and the explicit `plus_result_vars` are
  deliberate; plan 20's validation is the backstop.

## Coordination

- **Plan 13** — complementary halves of one declaration; D5 states the `tag`
  precedence, and plan 13's D3 (*Tag defaulting from the callable*) is the other
  half of it.
- **Plan 16** — `spec.bind()` feeding `sweep_identity()` is how a project pins
  what each environment resolves to.
- **Plan 17** — programmatically built specs are exactly where computed ranges
  collapse to a single point.
- **Plan 20** — spec composition is the main source of duplicate variables;
  these two plans should land in either order but be aware of each other.
- **A2/A3** — keep specs free of callables and live objects so they stay
  serializable under A3's contract.
