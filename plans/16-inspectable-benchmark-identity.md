# Plan 16 — Inspectable, Pinnable Benchmark Identity

**Goal:** Make a benchmark's identity a value a caller can compute, print, and
pin in a test *without running the benchmark*. Today identity exists only as a
private method on a `BenchCfg` that `plot_sweep()` builds internally, so the only
way to protect a long-lived trend from an accidental reset is to reimplement the
hashing rule downstream — against a rule that has already changed twice.

**Branch name:** `feat/sweep-identity-api`

**⚠️ Read first:** this plan is purely additive — one new pure function and two
accessors, all delegating to the existing `hash_persistent()`. It must not change
any hash. The golden hashes at `test/test_hash_persistent.py:774-801` are the
acceptance gate.

---

## Problem statement (with evidence)

### P1 — Identity is only reachable through a live run

`BenchCfg.hash_persistent(include_repeats, include_result_vars)`
(`bencher/bench_cfg.py:785`) is a method on a config object that
`plot_sweep()` assembles from converted variables partway through its own body
(`bencher/bencher.py:519`). There is no way to ask "what cache key and history
key will this declaration produce?" before committing to a run — and for an
expensive benchmark, running it is exactly what you are trying to avoid when
checking that a refactor preserved identity.

### P2 — The contributing set is documented, not exposed

Which fields participate is stated in a docstring and a comment block
(`bencher/bench_cfg.py:795-827`): `bench_name`, `over_time`, `repeats`, `tag`,
`input_vars` in list order, `const_vars` and `result_vars` as sorted sets, with
`CACHE_VERSION` folded in and `title` deliberately excluded. That rule has
changed twice in recent history — `CACHE_VERSION` reached 5, and
`include_result_vars=False` was introduced for the history key by plans 09/14.

Anything downstream that protects a trend by asserting on "the fields that make
up the key" is therefore asserting on a *transcription* of the rule, which drifts
silently the next time the rule changes. The assertion keeps passing while the
thing it was protecting has moved.

### P3 — Golden-hash coverage exists, but only inward

`test/test_hash_persistent.py` pins golden hashes for bencher's own fixtures
(`:774` with repeats, `:783` without, `:789` for the history key) and asserts the
determinism contract. That is the right pattern, and there is no public entry
point that lets a user apply it to their own benchmarks.

### P4 — The reset diff payload is private

`history.config_summary(bench_cfg)` already computes a compact, readable identity
summary — inputs, consts, results, repeats (`bencher/history.py:135-152`) — and
`diff_summaries` already renders a human-readable delta between two of them
(`bencher/history.py:155-177`). Both are exactly what a caller wants when a key
moves unexpectedly, and neither is exported.

---

## Proposed design

One pure function, one accessor, one export. No new hashing code.

### D1 — `bn.sweep_identity(...)`

New public function (module `bencher/identity.py`, keeping `bencher.py` from
growing — see plans 07/08):

```python
ident = bn.sweep_identity(
    bench_name="MyWorker",
    tag="nightly",
    input_vars=[...],          # same forms plot_sweep accepts
    result_vars=[...],
    const_vars={...},
    repeats=1,
    over_time=True,
    worker=MyWorker,           # needed to resolve string/dict specs
)
ident.cache_key      # hash_persistent(True)
ident.history_key    # hash_persistent(True, include_result_vars=False)
ident.summary        # config_summary(...)
```

- Returns a frozen dataclass `SweepIdentity`.
- Implemented by building a `BenchCfg` through the *same* conversion path
  `plot_sweep` uses (`Bench.convert_vars_to_params`,
  `bencher/bencher.py:822`) and calling `hash_persistent()` — so there is
  exactly one implementation of the rule and it cannot drift from the runtime.
- `worker` is required whenever any variable is given as a string or a
  `bn.sweep()` dict, because resolution needs the declaring class
  (`bencher/sweep_executor.py:122-127` already raises a clear error otherwise).

### D2 — `BenchCfg.identity()` and `BenchResult.identity`

The same `SweepIdentity` from a config that already exists, so a completed run
can report what it actually used. This is the accessor that makes plan 15's
behavior assertable, and it costs nothing: `identity()` is a two-line wrapper.

### D3 — Export the summary and diff helpers

`bn.config_summary(bench_cfg)` and `bn.diff_identities(old, new) -> list[str]`,
re-exporting `bencher/history.py:135` and `:155`. These are already the payload
the reset warning is built from; exporting them lets a caller print the same
explanation on demand rather than waiting for a warning that may never come.

### D4 — `Bench.explain_identity() -> str`

A human-readable rendering: the two keys, the fields that contributed, and the
fields deliberately excluded (`title`, and per plan 15, `series_id`). This
follows the precedent of A2's `explain_selection()` — when a derived value
surprises a user, a method that explains it beats reading the hashing code.

---

## Phased steps

1. `bencher/identity.py` with `SweepIdentity` and `sweep_identity()`, delegating
   to the existing conversion + hashing path. Export from `bencher/__init__.py`.
2. `BenchCfg.identity()` and the `BenchResult` accessor (D2).
3. Export `config_summary` / `diff_identities` (D3).
4. `explain_identity()` (D4).
5. Docs: a short "protecting a long-lived trend" section in the caching docs
   showing the golden-key test pattern, plus a `CHANGELOG.md` entry.

Phases 1–4 are independent; do 1 first since the rest reference `SweepIdentity`.

## Tests / acceptance criteria

- **Equivalence, the central test:** for a matrix of declarations (bounded and
  explicit sweeps, string and object variables, consts as dict and as list,
  `over_time` on and off, several repeat counts), `sweep_identity(...)` returns
  keys byte-identical to those of a real `plot_sweep()` run with the same
  arguments. Property-based coverage here is worth more than any number of
  hand-written cases, and the existing hypothesis tests in this file are the
  pattern to follow.
- Every golden hash in `test/test_hash_persistent.py` is unchanged.
- `sweep_identity` with a string variable and no `worker` raises the existing
  clear error rather than a `None` dereference.
- `history_key` ignores `result_vars` and `cache_key` does not — the plan 09/14
  contract, asserted through the new surface.
- `explain_identity()` names `title` as excluded (a regression guard for the
  deliberate exclusion at `bencher/bench_cfg.py:822`).

## Migration & compatibility

Purely additive. No existing signature changes, no hash changes, no cache
invalidation. `hash_persistent()` stays where it is and keeps its current
semantics; this plan only gives it a public, documented front door.

## Risks

- **A second implementation of the rule.** The whole value of the plan
  evaporates if `sweep_identity` reimplements hashing instead of delegating. The
  equivalence test is the guard, and it must cover every argument form
  `plot_sweep` accepts, not just the common one.
- **Encouraging users to depend on hash stability across versions.** They
  cannot: `CACHE_VERSION` is folded in deliberately
  (`bencher/bench_cfg.py:824-827`). Document that a pinned key is a
  *within-version* guard against accidental drift, and that a `CACHE_VERSION`
  bump legitimately moves every key.

## Coordination

- **Plan 15** — this makes 15's adoption/reset behavior directly assertable;
  15 adds `series_id` to what `explain_identity()` must report as excluded.
- **Plans 09/14** own the rule this exposes; any change there must update the
  equivalence matrix rather than the transcription (there is none).
- **A3/A4** — a frozen identity value object is the natural key type for A4's
  storage interface; keep `SweepIdentity` free of live objects so it stays
  serializable.
