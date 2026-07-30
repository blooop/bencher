# Plan 16 — Inspectable, Pinnable Benchmark Identity

**Goal:** Make a benchmark's identity a value a caller can compute, print, and
pin in a test *without running the benchmark*. Today identity exists only as a
private method on a `BenchCfg` that `plot_sweep()` builds internally, so the only
way to protect a long-lived trend from an accidental reset is to reimplement the
hashing rule downstream — against a rule that has already changed twice.

**Branch name:** `feat/sweep-identity-api`

**⚠️ Read first:** this plan is purely additive — one new pure function and two
accessors, all delegating to the existing `hash_persistent()`. It must not change
any hash. The golden hashes in `TestGoldenBenchCfgHash`
(`test/test_hash_persistent.py:774-801`) are the acceptance gate. Every line
number in this document is pinned to `main` @ `7dad0cd4` (v1.116.0); the symbol
named beside each one is the durable reference — grep the symbol if the line has
moved.

---

## Problem statement (with evidence)

### P1 — Identity is only reachable through a live run

`BenchCfg.hash_persistent(include_repeats, include_result_vars)`
(`bencher/bench_cfg.py:785`) is a method on a config object that
`Bench.plot_sweep` assembles from converted variables partway through its own
body (the `BenchCfg(...)` construction, `bencher/bencher.py:514-530`). There is
no way to ask "what cache key and history key will this declaration produce?"
before committing to a run — and for an expensive benchmark, running it is
exactly what you are trying to avoid when checking that a refactor preserved
identity.

### P2 — The contributing set is documented, not exposed

Which fields participate is stated in `BenchCfg.hash_persistent`'s docstring and
its `title`/`CACHE_VERSION` comment block (`bencher/bench_cfg.py:793-827`):
`bench_name`, `over_time`, `repeats`, `tag`, `input_vars` in list order,
`const_vars` and `result_vars` as sorted sets, with `CACHE_VERSION` folded in and
`title` deliberately excluded. That rule has changed twice in recent history —
`CACHE_VERSION` reached 5, and `include_result_vars=False` was introduced for the
history key by plans 09/14.

Anything downstream that protects a trend by asserting on "the fields that make
up the key" is therefore asserting on a *transcription* of the rule, which drifts
silently the next time the rule changes. The assertion keeps passing while the
thing it was protecting has moved.

### P3 — Golden-hash coverage exists, but only inward

`TestGoldenBenchCfgHash` pins golden hashes for bencher's own fixtures —
`test_golden_hash_with_repeats` (`test/test_hash_persistent.py:774`),
`test_golden_hash_without_repeats` (`:783`), `test_golden_hash_history_key`
(`:789`) — and asserts the determinism contract. That is the right pattern, and
there is no public entry point that lets a user apply it to their own
benchmarks.

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
  `bencher/bencher.py:821`) and calling `hash_persistent()` — so there is
  exactly one implementation of the rule and it cannot drift from the runtime.
- `worker` is required whenever any variable is given as a string or a
  `bn.sweep()` dict, because resolution needs the declaring class
  (`SweepExecutor.convert_vars_to_params`'s string/dict guard,
  `bencher/sweep_executor.py:122-126`, already raises a clear error otherwise).

`SweepIdentity` is a value, not a handle. Its fields are primitives and immutable
containers only — `str`, `int`, `bool`, `tuple`, nested frozen dataclasses — and
never a callable, a `param` object, or a live worker instance. `cache_key` and
`history_key` are hex digest strings; `summary` is the plain dict
`config_summary` already returns. An identity must survive `pickle` unchanged and
serialize through `json.dumps(asdict(ident))` with no custom encoder, and its
equality and hashing are value-based, so it works as a dict key and compares
equal across processes. This is a constraint rather than a preference because A4
wants an identity *as* a storage key, and a key carrying a live object cannot
cross a process boundary or a cache: the worker belongs in `sweep_identity`'s
arguments, never in its return value.

### D2 — `BenchCfg.identity()` and `BenchResult.identity`

The same `SweepIdentity` from a config that already exists, so a completed run
can report what it actually used. This is the accessor that makes plan 15's
behavior assertable, and it costs nothing: `identity()` is a two-line wrapper.

### D3 — Export the summary and diff helpers

`bn.config_summary(bench_cfg)` and `bn.diff_identities(old, new) -> list[str]`,
re-exporting `history.config_summary` (`bencher/history.py:135`) and
`history.diff_summaries` (`:155`). These are already the payload the reset
warning is built from; exporting them lets a caller print the same
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
  exclusion documented in `hash_persistent`'s `title` NOTE comment,
  `bencher/bench_cfg.py:820-823`).
- Every field the explanation names as contributing or as excluded is checked
  *behaviourally* — change it, assert a key moves or does not — and the checks are
  asserted to cover the lists exactly, so extending either list without a check
  fails. The explanation is prose about a rule defined elsewhere, which is the same
  transcription hazard listed under Risks; only a behavioural check retires it.
- Asking for an identity never mutates what it was asked about. `BenchCfg`
  subclasses `BenchRunCfg`, so replaying `run_sweep`'s merge in place would write
  every run-side field (`repeats`, `cache_results`, `dry_run`, ...) onto a config
  the caller still holds — a query that silently reconfigures the next run.
- A `SweepIdentity` round-trips through `pickle` unchanged, and through
  `json.dumps(asdict(ident))` with no custom encoder — tuple-to-list is the only
  normalization the JSON form may introduce. Two identities built from the same
  declaration compare equal, hash equal, and address the same dict entry.

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
  cannot: `CACHE_VERSION` is folded in deliberately as the first element of
  `hash_persistent`'s hash tuple (`bencher/bench_cfg.py:825-830`). Document that
  a pinned key is a *within-version* guard against accidental drift, and that a
  `CACHE_VERSION` bump legitimately moves every key.

## Coordination

- **Plan 15** — this makes 15's adoption/reset behavior directly assertable;
  15 adds `series_id` to what `explain_identity()` must report as excluded.
- **Plans 09/14** own the rule this exposes; any change there must update the
  equivalence matrix rather than the transcription (there is none).
- **A3/A4** — a frozen identity value object is the natural key type for A4's
  storage interface; D1's serialization constraints exist for exactly that, and
  A4 should key on `SweepIdentity` rather than reconstruct a key from its parts.
