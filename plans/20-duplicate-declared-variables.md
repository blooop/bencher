# Plan 20 — Duplicate Declared Variables

**Goal:** Make a variable declared twice in one sweep either an error or an
explicit no-op, instead of what it is today: for result variables, a silent
change of cache and history identity that produces a byte-identical dataset; for
input variables, an unhelpful crash deep inside xarray.

**Branch name:** `fix/duplicate-declared-variables`

**⚠️ Read first:** the result-variable case changes a hash for configurations
that are currently accepted, so it interacts with plan 09's reset reporting. Read
the migration section before choosing the dedupe option.

---

## Problem statement (with evidence)

### P1 — Nothing checks for duplicates

`plot_sweep` converts each list positionally with no uniqueness check —
`input_vars` and `result_vars` at `bencher/bencher.py:418-422`, `const_vars` at
`:440-444`. No dedupe, no warning, no error.

### P2 — A duplicated result variable silently splits the series

Verified on v1.116.0 with a two-variable worker, comparing
`result_vars=["y", "y"]` against `result_vars=["y"]`:

| Declaration | Dataset | `hash_persistent(True)` |
|---|---|---|
| `["y"]` | dims `{x: 10}`, vars `['y']` | `92bca0b5…` |
| `["y", "y"]` | dims `{x: 10}`, vars `['y']` | `eb291525…` |

The dataset is **identical** and the key is **different**. The cause is that the
per-variable digests are folded as a sorted *tuple*, not a set
(`bencher/bench_cfg.py:841`), so a repeated entry appears twice in the hashed
sequence. Meanwhile the history layer keys its column metadata by name — a dict —
so the duplicate collapses there. Hash and history therefore disagree about what
the configuration contains.

The practical failure is a benchmark that runs, reports correct numbers, and
appends to a different trend line than the one it appears to belong to. Nothing
in the run says so.

### P3 — Duplicate declaration is a natural consequence of composition

Result variables are commonly assembled from several sources: a shared group of
core metrics, a group contributed by a base class, a group specific to one
environment. Concatenating those lists is the obvious implementation and one
overlapping entry is invisible in review. Plan 18's spec composition makes this
more likely, not less, which is why that plan defaults to replacing rather than
appending.

### P4 — A duplicated input variable crashes far from the declaration

Same worker, `input_vars=["x", "x"]`:

```
ValueError: broadcasting cannot handle duplicate dimensions on a variable: ['x', 'x', 'repeat']
```

The declaration is accepted, the sweep grid is built, and the failure arrives from
xarray with no reference to the sweep, the variable, or the call site. Unlike P2
this is at least loud, but it is diagnosed by reading a stack trace into bencher's
internals.

### P5 — Constants have a third behavior

`const_vars` given as a dict cannot contain duplicates at all — the dict collapses
them before bencher sees them (`bencher/bencher.py:437-438`). Given as a list of
pairs, a repeated variable with two *different* values is accepted, and which one
wins depends on downstream iteration order. So the same logical mistake is
impossible, silent, or order-dependent depending on which of the two accepted
forms the caller used.

---

## Proposed design

Validate once, in one place, next to the conversion loops. Different variable
kinds warrant different answers.

### D1 — Input variables: raise

A repeated dimension is never intentional and currently produces an xarray error
regardless. Raise a `ValueError` naming the variable and both positions, at
declaration time:

```
Input variable 'x' is declared twice (positions 0 and 1). Each input variable
defines one dataset dimension, so it may appear only once.
```

This is a strict improvement: the same configurations fail, with a message that
identifies the cause.

### D2 — Result variables: dedupe or raise — **OWNER DECISION**

Both defensible:

1. **Dedupe, keep first occurrence, warn.** Composition-friendly: concatenating
   overlapping metric groups keeps working, and the warning tells the author to
   clean it up. The identity produced is the same as declaring the set once, which
   is what the dataset already reflects — so this *fixes* P2's hash/dataset
   disagreement in the direction of the dataset.
2. **Raise.** Consistent with D1 and unambiguous, but breaks any currently-working
   benchmark that happens to have an overlap, and does so at declaration time
   rather than when the numbers are wrong.

**Recommendation: option 1.** The dataset is already the deduped set; making the
hash agree with the data is the correct resolution, and the warning preserves
discoverability. Option 2's strictness buys little here because, unlike an input
variable, a duplicated result variable has an unambiguous intended meaning.

Whichever is chosen, apply it identically to the deferred and the object forms,
comparing on resolved variable *name*.

### D3 — Constants: normalize the two forms

Convert the list form to a mapping keyed by resolved name before use, so both
accepted spellings behave identically. A repeated constant with the **same** value
is deduped silently; with **different** values it raises, naming the variable and
both values — that is a genuine contradiction in the declaration, not a
redundancy.

### D4 — One validation site

Put all three checks in a single helper called from `plot_sweep` after
conversion (so comparison is on resolved names, not on the mixed bag of strings,
dicts, and objects the caller passed). One function makes the three policies
readable side by side and gives plan 18's `bind()` a natural place to call the
same validation.

---

## Phased steps

1. The validation helper plus D1 (input variables raise). Self-contained, no
   identity change for anything that currently succeeds.
2. D3 (constant normalization). Also no identity change, since same-valued
   duplicates already collapse.
3. D2, once the owner decision is made. This is the phase with a hash change;
   land it alone so any reported reset has one obvious cause.
4. `CHANGELOG.md` and a docs note that variable lists are sets by name, ordered
   only for inputs.

## Tests / acceptance criteria

- Duplicate input variable raises `ValueError` at `plot_sweep`, naming the
  variable and both positions; the xarray broadcasting error is no longer
  reachable. Cover string, dict, and object forms, and a mixture of them.
- Duplicate result variable (D2 option 1): a warning is emitted, and the resulting
  `hash_persistent()` equals that of the same set declared once — the direct
  regression test for P2's `eb291525…` vs `92bca0b5…` split.
- Duplicate constant with equal values: accepted silently, one entry. With
  differing values: raises, naming both values.
- List-form and dict-form `const_vars` produce identical configs and identical
  hashes for the same logical content (P5).
- Non-duplicate configurations are bit-identical before and after: every golden
  hash in `test/test_hash_persistent.py` unchanged.

## Migration & compatibility

D1 and D3 change no currently-succeeding configuration. D2 option 1 **does** move
the key of any benchmark that currently declares an overlapping result variable —
onto the key it would have had if declared correctly, so in the common case a
benchmark rejoins the trend it should have been on all along, and in the worst
case it starts a fresh series with a `full_reset` event from plan 09.

Call this out explicitly in `CHANGELOG.md`: the change is a fix for a
misdeclaration, the affected benchmarks are exactly those emitting the new
warning, and `on_history_reset` controls how loudly the transition surfaces.

## Risks

- **A hash change delivered quietly.** Mitigated by landing D2 alone (phase 3)
  and by the CHANGELOG note. Users who never duplicated see nothing.
- **Over-strict comparison.** Two *different* variables must never be judged
  duplicates. Compare resolved `name` only, after conversion, and cover the case
  of two distinct variables whose configured objects happen to be equal.
- **Warning fatigue.** If a project legitimately builds result-variable lists by
  concatenation, the warning fires on every run. That is the intended signal, and
  plan 18's `plus_result_vars` gives them a clean way to fix it — reference it in
  the warning text.

## Coordination

- **Plan 18** — spec composition is the main generator of duplicates; 18's
  replace-by-default design and this plan's validation are two halves of the same
  guard, and 18's `bind()` should call D4's helper.
- **Plan 09/15** — D2's key change surfaces through the reset-reporting path;
  plan 15's series identity makes the transition legible.
- **Plan 19** — the sibling validation in the same code path; consider landing
  both behind one "validate declared variables" review.
