# 27 — CACHE_VERSION bump ledger

**Status: OPEN, standing.** This plan has no end state and is never "implemented". It is a
ledger: one place holding every change that was shaped, weakened, or postponed because it
would have invalidated persisted caches. When `CACHE_VERSION` is next bumped, work this
list — the bump is the expensive part, and it is already paid for once the decision is
made, so everything blocked on it should land in the same release.

Citations are `file:line` as of `main` @ `19569731`; per plans-README rule 7 the symbol is
the durable reference and the line number goes stale. **Re-confirm every entry before
acting on it** — an entry whose premise no longer holds should be struck with a note, not
silently executed.

## 1. Why this file exists

Bencher's standing cache policy is good: any change to what a key composes is
cache-busting, so bump `CACHE_VERSION` and say so in the changelog (plan 09 §"Read
first"). The cost is that the policy is *per-change*, so the cheap answer to "this fix
would move a key" is always "annotate around it and record the reason". That has happened
enough times that the reasons are now spread across four plans, two architecture docs and
a dozen changelog entries, each individually well-written and collectively unfindable.

The failure mode this prevents is bumping `CACHE_VERSION` for one reason, paying the full
invalidation cost, and *still* shipping the other eight compromises — because nobody
assembled the list. Worse: a later phase then re-derives one of them from scratch and
records the same deferral again.

Two things follow, and both are obligations on future work rather than suggestions:

- **When you defer something for cache reasons, add it here** in the same PR, with its
  blocker and its unblocked fix. Recording it only in a plan's §10 or in the changelog is
  what produced this problem.
- **When you bump `CACHE_VERSION`, read this whole file first.** Entries are individually
  small; the point is that they are free once the bump is happening.

## 2. Current state

| Fact | Where |
|---|---|
| `CACHE_VERSION = "5"` | `bencher/cache_management.py:60` |
| Folded into the key, so a bump invalidates atomically | `BenchCfg.hash_persistent`, `bencher/bench_cfg.py` (the `CACHE_VERSION` element of `hash_val`) |
| Enforced by test | `test/test_hash_persistent.py::TestGoldenBenchCfgHash::test_cache_version_participates_in_hash` |
| Version file written/compared per cachedir | `cache_management.py` `ensure_cache_version`; mismatch wipes the tree |
| Golden digests pinning the composition | `GOLDEN_BENCH_CFG_HASH_*`, `test/test_hash_persistent.py:741-744` |

The bump procedure already documented at `test/test_hash_persistent.py:727-739` is the
authority and is not restated here: bump the constant, update the three golden digests,
document the break in the changelog. §5 below adds only the ledger-specific steps.

## 3. The ledger

Ordered by how much each one costs to keep, not by size.

### L1 — `param_hash`/`hash_persistent` return `int | str`

- **Compromise:** annotated as a union rather than normalized. Returns a sha1 digest
  normally, but the literal `0` when nothing was hashed, so every consumer handles both.
- **Where:** `ParametrizedSweep.param_hash`, `ParametrizedSweep.hash_persistent`.
- **Blocker:** always returning a digest changes the key for parameter-less sweeps.
- **At bump:** return a digest unconditionally; delete the `int` arm and the union from
  every consumer. Recorded in plan 23 §10 P12 items 9 and 10.
- **Note:** this is the one entry the type system will keep reminding you about, which is
  why it is first. It is also the smallest.

### L2 — `SweepBase.values()` / `FloatSweep.values()` return `list[Any] | np.ndarray`

- **Compromise:** annotated honestly instead of coerced to one type. `linspace`/`arange`
  return arrays; other leaves return lists.
- **Where:** `bencher/variables/sweep_base.py`, `bencher/variables/inputs.py`.
- **Blocker:** the value flows into hashing *and* into dataset construction, so coercing it
  is a behaviour change, not an annotation fix — it can move keys and can change coord
  dtypes.
- **At bump:** pick one return type for every leaf. Verify against the golden digests and
  against coord dtypes in a round-tripped dataset, not just the hash.
- **Recorded in:** plan 23 §10 P12 items 5 and 10.

### L3 — dual-generation missing-value sentinels

- **Compromise:** two sentinel conventions are read forever. Old cells hold `-1`
  (`ResultReference`/`ResultDataSet`) and `"NAN"` (object/file types); the current
  convention is centralised in `result_missing_fill`/`result_is_missing`
  (`bencher/variables/results.py`).
- **Blocker:** cells written before the change are still on disk; simplifying to one
  convention makes them unreadable. Plan 23 §7 P4 states this as a hard constraint —
  "plan 22's `-1`/`"NAN"` compatibility is **not** to be simplified away".
- **At bump:** collapse to a single convention and delete the legacy acceptance arm from
  `result_is_missing` and from the `missing_sentinels` sets.
- **Careful:** a `CACHE_VERSION` bump invalidates the *result* and *history* caches, which
  is what holds these cells — confirm that before deleting, because this is the one entry
  whose premise a bump genuinely removes rather than merely permits.

### L4 — `ResultDataSet` legacy int cells + pickled `dataset_list`

- **Compromise:** a dual read path. New writes store blob paths as `str` cells; old entries
  hold int indices into a pickled `dataset_list`, and plan 22 D3(2) keeps them rendering.
- **Blocker:** same as L3 — pre-change values on disk.
- **At bump:** delete the legacy branch and the `object_index` read path. Plan 23 §8 leaves
  this to "plan 22 phase 3"; it belongs to whichever lands first after the bump.

### L5 — mixed `0`/`NaN` result-var defaults

- **Compromise:** when the result-var default became `NaN`, `CACHE_VERSION` was
  deliberately not bumped, so a benchmark with missing samples can hold a *mix* of `0`
  (cached before) and `NaN` (computed after) until those cells are recomputed.
- **Where:** recorded in `CHANGELOG.md` under the entry that introduced the `NaN` default.
- **At bump:** nothing to code — the bump *is* the fix, since it forces recomputation. Note
  it in the bump's changelog entry as a resolved inconsistency, and delete any test that
  tolerates the mix.

### L6 — legacy blob re-materialization on cache hit

- **Compromise:** plan 22's blob store shipped without a bump (`CACHE_VERSION` stayed `5`),
  so pre-existing sample-cache entries re-materialize into blobs on a hit and stored
  histories merge an int64 column with the new object column.
- **Where:** recorded in `CHANGELOG.md` ("**No `CACHE_VERSION` bump** (stays `5`)").
- **At bump:** the re-materialization path and the int64/object concat become dead. Delete
  them together with L4, which is the same generation of data.

### L7 — the `or []` folds in `BenchCfg.hash_persistent`

- **Compromise:** three `or []` folds are now unreachable — plan 23 P12b gave the six
  variable-list fields `default=[]` and param rejects `None`. They are kept because they
  are *why* that change could not move a digest (`[]` and `None` folded identically), and
  deleting them removes the evidence for a claim the golden tests can no longer make.
- **Where:** `bencher/bench_cfg.py`, `hash_persistent` — commented in place pointing here.
- **At bump:** delete all three. Provably a no-op, so this is zero-risk cleanup rather than
  a fix; it is here only so it gets swept rather than re-discovered.

### L8 — `code_hash` for worker source (already-planned bust)

- **Compromise:** not shipped at all. The sample cache keys on inputs only, so editing a
  worker's body silently serves stale samples — A4's W1.
- **Where:** designed in `plans/architecture/A4-caching-architecture.md` §3.2, sequenced as
  the second half of Phase C2.
- **At bump:** this is the entry most worth *pairing* the bump with, because A4 already
  says the bump is its precondition ("**This is a deliberate cache-busting change**… Bump
  `CACHE_VERSION` in the same release and put it in the changelog as a headline item").
  If a bump happens for any other reason and `code_hash` does not ride along, the project
  pays the invalidation cost twice.

### L9 — storage-interface migration (#760 / diskcache CVE)

- **Compromise:** deferred, and now entangled: plan 26 R13 records that #760 must be
  reworked because #1022's GC has three `diskcache.Cache` sites #760 never touched.
- **Where:** `plans/26-post-merge-audit-remediation.md` R13 and item 2.
- **At bump:** R13 states the bump makes this migration *free* — "`CACHE_VERSION` 5→6 makes
  migration free", because there is no old data to translate. Time-sensitive on its own
  merits (the CVE is live), so this may well be what *causes* the bump rather than what
  benefits from it.
- **Related, and not fixed by a bump:** the GC does not compare `cachedir/CACHE_VERSION`
  against the library's before reading (plan 26 item 2). A bump makes that gap *more*
  dangerous, not less — a stale cachedir plus a GC that reads it anyway yields an empty
  live set and deletes every blob. **Fix item 2 before or with any bump**, not after.

### L11 — `ResultDataSet` blob cells read two generations

- **Compromise:** the cell format changed from an absolute blob *path* to the bare blob
  *name* without a bump, so `blob_name` accepts both — it matches on the basename, which
  repairs a path-shaped cell against whatever cache dir is active now.
- **Where:** `blob_store.blob_name` / `_parse_blob_ref`; shipped in #1081, narrowed in the
  follow-up that added `--cachedir` (which deleted the other half of the compromise: a
  path-shaped cell is no longer *read out of* the directory it names, only identified by
  its basename).
- **Blocker:** none that a bump removes, strictly — path-shaped cells only exist in caches
  written by 1.118.0, which had no consumers. The dual read survives because `blob_name` is
  shared with reachability GC, which needs basename matching regardless of cell generation
  (a walked object can hold a path from anywhere).
- **At bump:** nothing is forced. Optionally tighten `_parse_blob_ref` to reject a
  reference carrying any directory, which would make "a cell is a name" a type-level fact
  rather than a convention — but keep `blob_name`'s basename matching for the GC, which is
  the reason it exists.
- **Note:** this entry exists because #1081 deferred without recording, which is the exact
  failure §1 describes. It is closer to "struck" than "waiting"; do not treat it as work.

### L10 — pre-v5 history entries have no migration

- **Compromise:** plan 14 chose a one-time miss over a migration path.
- **Where:** `plans/14-history-schema-reconciliation.md` ("No migration of pre-v5 cache
  entries — `CACHE_VERSION` bump, one-time miss, per the standing cache policy").
- **At bump:** confirms the choice; nothing to do. Listed so a future reader does not
  mistake the absence of a migration for an oversight and write one.

## 4. Do NOT sweep these in

A bump is permission to change keys, not a reason to. These are deliberate exclusions that
a bump does not make obsolete, and each has a test that will fail if it is swept in.

- **`title` is excluded from the hash** so renaming a benchmark does not lose history.
  `test_hash_persistent.py::TestGoldenBenchCfgHash::test_title_change_does_not_affect_golden_hash`.
- **`agg_fn` is excluded** (it is in `identity.py`'s `EXCLUDED_FIELDS`) and feeds no
  persistent hash.
- **Declared renderers and containers are in `_hash_exclude`**, so declaring one moves no
  cache key and loses no `over_time` series. `test/test_declared_container.py`.
- **`result_vars`/`const_vars` fold as unordered *sets*** while `input_vars` folds in list
  order — the ordering asymmetry is intentional (input order determines array layout;
  result order does not). `test/test_identity.py`.
- **`executor` must not perturb any persisted hash** (plan 23 §7 P2, confirmed in P2).
- **`ResultHmap`'s `hash_persistent()` is unchanged until removal**, and its removal is
  A6-phased rather than bump-gated.

## 5. Bump checklist

Follow `test/test_hash_persistent.py:727-739` first — bump the constant, update the three
`GOLDEN_BENCH_CFG_HASH_*` digests, write the changelog entry. Then, specific to this
ledger:

1. **Read §3 end to end** and decide per entry: land, strike with a reason, or explicitly
   carry forward. An entry silently left in place is the failure this file exists to
   prevent.
2. **Fix plan 26 item 2 (GC `CACHE_VERSION` guard) in the same release or earlier.** See
   L9 — a bump plus an unguarded GC is worse than either alone.
3. **Pair with L8 (`code_hash`)** unless there is a stated reason not to; A4 already
   designates the bump as its precondition.
4. **Re-run the cache-adjacent suites**, not just `pytest`: `test_hash_persistent.py`,
   `test_identity.py`, `test_cache_management.py`, `test_declared_container.py`, and the
   split-render job (`pixi run test-split`), because L3/L4/L6 touch stored *values* and the
   split pipeline is what round-trips them.
5. **Verify §4 still holds** — the golden digests changing is expected; the §4 invariants
   changing is not.
6. **Update this file**: strike what landed, and move the version fact in §2.

## 6. Adding an entry

In the PR that makes the deferral, add a `### Lnn` section with: the compromise as shipped,
`file:line` plus symbol, the blocker in one sentence, and the concrete change to make once
the bump happens. Cross-reference from wherever else you recorded it (a plan §10, the
changelog) so the two do not drift — this file is the index, not a second copy of the
reasoning.

If you are *not* deferring, and instead shipping a compromise that a bump would never fix,
it does not belong here. §4 is for those.
