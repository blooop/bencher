# Plan 19 — Reject Unnamed Parameters at Resolution Time

**Goal:** Turn a silent, hard-to-diagnose composition mistake into an error that
names its own cause. A sweep or result variable declared on a class that is not
`param.Parameterized` is picked up by param's MRO scan but never receives a
`name`, and bencher resolves it *successfully* — then fails much later, in
dataset assembly, with a message that points nowhere near the declaration.

**Branch name:** `fix/reject-unnamed-parameters`

**⚠️ Read first:** the check must not reject the legitimate case of a parameter
object whose name was assigned outside a metaclass — `bn.box()` does exactly that
(`bencher/variables/inputs.py:672`). See D2's implementation note.

---

## Problem statement (with evidence)

### P1 — param only names parameters declared on a `Parameterized` class

`param` assigns `Parameter.name` in the metaclass of the class that *defines* the
parameter. A parameter declared on a plain class — a mixin written to be combined
with a `ParametrizedSweep` later — never passes through that metaclass. When the
mixin is combined into a real `ParametrizedSweep`, param's MRO scan *does* find
the parameter, so it appears in `param.objects()` under its attribute key, but
its `.name` stays `None`.

This is a reasonable thing for a user to try. Splitting shared measurement code
into a mixin and combining it with different bases per environment is the obvious
way to share a benchmark, and it works right up until the mixin declares a
variable of its own.

### P2 — Resolution succeeds and the failure surfaces far away

`_resolve_param(name, worker, var_type)` looks the variable up in
`worker.param.objects(instance=False)` and returns whatever it finds
(`bencher/sweep_executor.py:28-36`). The lookup is by *dictionary key*, so an
unnamed parameter is found and returned without complaint, and `plot_sweep`
proceeds to build a config around it (`bencher/bencher.py:418-421`).

The failure lands in result storage, which uses `rv.name` as the key into the
worker's returned dictionary (`bencher/result_collector.py:344-354`). With
`rv.name is None` the user sees a `KeyError` for result variable `'None'` and a
list of available keys — an accurate message about a symptom, with no path back
to the mixin that caused it. The same `.name` is used for dataset variable names
and dimension labels, so an unnamed *input* variable corrupts the dataset's
coordinate identity instead.

### P3 — Nothing validates that a resolved parameter knows its own name

The invariant is simple and currently unchecked: a parameter found under key `k`
must satisfy `param.name == k`. Any violation means the parameter was not named
by the metaclass of a `Parameterized` class, which is the only way this state
arises.

### P4 — The requirement is not documented where it is needed

`ParametrizedSweep`'s documentation describes declaring variables on the sweep
class; it does not say that a base or mixin contributing variables must itself be
`Parameterized`. A user composing classes has no reason to know that param's
naming happens in a metaclass.

---

## Proposed design

### D1 — Check the invariant in `_resolve_param`

After the existing lookup (`bencher/sweep_executor.py:28-36`), before returning:

```python
resolved = all_params[name]
if getattr(resolved, "name", None) != name:
    raise TypeError(
        f"{var_type.capitalize()} variable '{name}' on "
        f"{type(worker).__name__} has no name (param.name={resolved.name!r}). "
        f"This happens when the variable is declared on a base class that is "
        f"not a param.Parameterized subclass: param assigns a Parameter's name "
        f"in the metaclass of the class that declares it, and a plain mixin has "
        f"no such metaclass. Make that base subclass bn.ParametrizedSweep "
        f"(or param.Parameterized) and the variable will register correctly."
    )
```

`TypeError` rather than `KeyError`: the variable was found, so this is a
malformed declaration, not a missing one. The message must name the *cause*, not
just the symptom — diagnosing this from first principles requires knowing how
param's metaclass works, which is precisely what the message should spare the
user.

### D2 — Check parameter objects too, not only names

A caller may pass a parameter object directly (`Cls.param.x`) rather than a
string, bypassing `_resolve_param` entirely. `plot_sweep`'s conversion loops
(`bencher/bencher.py:418-421`, and the const loop at `:439-443`) should reject a
`param.Parameter` whose `.name` is `None`, with the same explanation.

**Implementation note — do not check `name != key` here.** A parameter object
need not correspond to any attribute on the worker: `bn.box()` builds a
`FloatSweep` and assigns `var.name` by hand
(`bencher/variables/inputs.py:672`), and `bn.sweep()` returns copies configured
via `with_bounds`/`with_sample_values`. Those are legitimate and have real names.
The object path can therefore only assert `name is not None`; the
stronger key-equality check belongs to the by-name path in D1, where a key
exists to compare against.

### D3 — Document the requirement at the point of composition

- In `ParametrizedSweep`'s class docstring: any base or mixin that declares sweep
  or result variables must itself subclass `ParametrizedSweep` (or
  `param.Parameterized`); a plain mixin's variables register without names.
- Same note in the docs section on sharing benchmark code between classes, which
  is where a user composing mixins will be looking.

---

## Phased steps

1. Add the D1 check with the explanatory message.
2. Add the D2 object-path check, honoring the implementation note.
3. Documentation (D3) and a `CHANGELOG.md` entry.

Small enough to land as one change; keep the phases separate in review because
D2 is the one with a false-positive risk.

## Tests / acceptance criteria

- A worker whose variables come from a plain (non-`Parameterized`) mixin raises
  `TypeError` from `plot_sweep`, and the message contains both the variable name
  and the guidance to make the base `Parameterized`. Cover an input variable and
  a result variable separately, since they fail differently today.
- The same mixin, changed to subclass `bn.ParametrizedSweep`, runs to completion
  and produces the expected dataset variable names — this is the "correct
  composition still works" guard.
- **No false positives**, the critical case: `bn.box("x", 0.5, 0.1)`,
  `bn.sweep("x", bounds=(0, 1))` with a string name, `bn.sweep(Cls.param.x,
  samples=5)`, and a bare `Cls.param.x` all continue to work as input variables.
- An unknown variable name still raises the existing `KeyError` listing available
  parameters — the new check must not shadow it.
- A regression case asserting the *old* symptom no longer occurs: no benchmark
  can reach `store_results` with a result variable whose `name` is `None`.

## Migration & compatibility

This converts a latent misconfiguration into an immediate error. Any user whose
benchmark currently declares variables on a plain mixin was already producing a
broken dataset (unnamed columns) or crashing in result storage, so no working
configuration changes behavior. Worth an explicit `CHANGELOG.md` line naming the
new error, since a user who is *partly* affected — an unnamed variable that never
made it into `result_vars`, and so never crashed — will newly see the failure.

## Risks

- **False positives on the object path** (D2) — the `box()`/`sweep()` cases
  above. The mitigation is in the implementation note: never compare against a
  key on the object path. The no-false-positives test is the gate.
- **Dynamically constructed workers.** A worker class built with `type()` at run
  time still goes through param's metaclass, so its variables are named
  correctly; add one such case to the tests to confirm the check does not
  penalize programmatic construction.
- **Message length.** The message is long by bencher's standards, deliberately:
  the failure is otherwise close to undiagnosable. Keep it as prose, not a
  multi-line template, so it stays readable in a traceback.

## Coordination

- **Plan 18** — sharing one declaration across worker classes is what leads users
  to mixins in the first place, so these two plans are read together; 18's docs
  should link this requirement.
- **Plans 07/08** — `_resolve_param` lives in `sweep_executor.py`; if those plans
  move variable resolution, this check moves with it.
