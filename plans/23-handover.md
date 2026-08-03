# Handover — plan 23 after P1

**Ephemeral.** This is working state, not a plan. Delete it when plan 23 P12 lands (or
fold anything still open into plan 23 §10). Everything here is actionable without the
conversation that produced it.

> **Status (P12b, Tier B fully enabled).** Not deleted yet, because deleting it now would
> drop content nothing else carries. What has changed since it was written:
>
> - **§5 item 5 is discharged.** P12 enabled `invalid-return-type`, which is the rule that
>   verifies `_resolve_auto` returns a member of `ResolvedReduceType`; the caveat comment
>   at the alias is gone. See §10 P12 item 1.
> - **§4's `pn.pane = None` defaults, `to_panes_multi_panel`, `run.py`'s `ty: ignore`, and
>   the `test_extra_panels.py` gap** are now owned by plan 26 R9 §10 and R10 §3. Do them
>   there, not here.
> - **§4's plan 24 Q1** (ty ceiling, third probe) is plan 26 R10 §2.
> - **§5 items 1–4 still have no owner** — the `map_plot_panes` reduction default, the
>   `ReduceType.NONE` kdim-units loss, `plot_sweep`'s understated `input_vars` domain
>   (which is why `identity.py` is still not strict-listed), and the `strenum` →
>   `enum.StrEnum` value trap. **These four are the reason this file still exists.**
> - **§6's traps all still apply**, in particular trap 1 (`--python`) and trap 3 (enumerate
>   what satisfies neither arm when you change a discrimination predicate on a union).
>   P12b added one: a synthetic probe that reports nothing is not evidence the rule does
>   not fire — see §10 P12b item 10.
> - **§2 remains the single most load-bearing thing here.** Read it before writing any
>   `assert_never`.

**State pinned to:** `main` @ `ee044f0e` plus PR #1026 (`plan/ty-enforcement-floor`,
head `b9524867`). Per plans-README rule 7, re-confirm every `file:line` before relying on
it; the symbol is the durable reference.

---

## 1. What has landed

| Change | PR | State |
|---|---|---|
| Plan 23 — the audit itself, 12 phases | #1023 | merged |
| Plan 24 — `assert_never` boundary discipline (amends 23) | — | merged (`7de09227`) |
| Python floor 3.10 → 3.11 | #1025 | merged (`1aad6bfc`) |
| **Plan 23 P1 — make the `ty` gate real** | #1026 | merged (`3e222307`) |
| **Plan 23 P2 — collection-path bugs (B2, B3) + executor normalization (C13)** | — | see §3 |

Read in this order before touching anything:

1. `plans/23-constructive-data-modeling.md` — **§10 first**. It records what P1 actually
   did and, more usefully, three claims that were falsified during implementation.
2. `plans/24-assert-never-boundary-discipline.md` — its §3 amendments bind 23-P2 and
   23-P11. Do not implement `assert_never` anywhere without reading its §2.
3. `plans/README.md` ground rules (pixi-only, `pixi run ci` before commit, cite
   `file:line` + symbol).

## 2. Read this before you write any `assert_never`

Plan 24's finding is the single most load-bearing thing in this handover, and P1
confirmed it the hard way — by breaking on it.

**A `match` that is *complete* still raises at runtime if its subject arrives untyped.**
`ty` reports `All checks passed!`; the `assert_never` arm fires as an `AssertionError`
whose message ("Expected code to be unreachable") actively misdirects the reader toward a
missing enum member rather than a bad value at the boundary. No checker closes this —
`pyrefly` is clean on the same probe. It is a property of gradual typing, not a `ty` gap.

The repo's own config names the vector: `pyproject.toml` says param descriptors "resolve
as **Unknown**". So **a `match` on a raw `param` field read never qualifies.** Normalize
at the boundary first — construct the enum (`Executors(value)`, `AggFn(value)`), raising
on unknown input — and cover that normalization with a *runtime* test, because no static
check enforces it.

Verified still true at the py311 target with stdlib `typing.assert_never`.

## 3. 23-P2 — implemented

**Done**, on `plan/p2-collection-path-bugs`. Findings are in plan 23 §10 under "P2
(implemented)"; read those before P3. The four that change what you should expect:

- The old serial `assert` was not just `-O`-fragile — with `catch=` set it was
  **downgraded to a tolerated sample failure**, so the silent-empty-dataset outcome was
  reachable on the serial path too. Both new checks raise from *outside* `except catch`.
- `JobFuture.result()` is now `-> dict | None`. **P5 removes the `| None`**; until then
  callers use `require_worker_result`.
- `Executors.factory` matches exhaustively with `assert_never` and this is the first
  place plan 24 A2 is realised end to end: verified by deleting the SCOOP arm.
- `job.py` and `result_collector.py` still **cannot** join the strict ratchet; §10 item 7
  names the exact 4 blockers, two of which are one `WorkerJob.function_input` two-phase-init
  defect that **P5/P9 should fix, unlocking both files at once**.

The original spec, kept for reference:

- **B2** `bencher/result_collector.py:463-471` — the `ResultVec` branch stores only when
  `isinstance(result_value, (list, np.ndarray))` **and** `len(result_value) == rv.size`,
  with no `else`. A wrong-length vector is silently discarded and left at the NaN fill,
  indistinguishable from "never sampled". Add the `else` → `TypeError` naming the
  variable, expected size and actual length.
- **B3** `bencher/job.py:158-160` + `bencher/result_collector.py:424` — a worker returning
  `None` trips a bare `assert` on the serial path (absent under `python -O`) but on
  MULTIPROCESSING/SCOOP the whole `store_results` body is skipped by
  `if result is not None:` with no `else`, and the sweep completes green with an
  all-sentinel dataset and `n_failed == 0`. One boundary check raising `TypeError` on
  **both** paths.
- **C13** executor normalization. **Read plan 23 C13 before writing the test** — an
  earlier draft claimed `BenchRunCfg(executor="serial")` diverged between branches and
  that was **false**: `strenum.auto()` yields the member *name*, so
  `Executors.SERIAL.value == "SERIAL"`, `"serial"` is rejected by the `Selector` with
  `ValueError`, and `factory("SERIAL")` returns `None` so even the exact-case string
  resolves serial everywhere. It is a latent smell (four sites, three comparison styles:
  `bencher.py:1180`, `:1182`, `job.py:230`, `:355`), not a shipped bug. No pre-fix
  regression test is possible; write a branch-agreement test instead.
- **Plan 24 A3 DoD addition:** state in the PR that the `executor` normalization is what
  *licenses* any later `assert_never` on that field. A2 promotes this from "hardening" to
  "precondition" — do not skip it on the grounds that C13 is only a smell.

**Owner decision 6.2 (raise vs warn for B2/B3): resolved as raise `TypeError`**, on the
recommendation on file, and explicitly not routed through plan 21's `catch=`. Both halves
are pinned by tests. Flagged in the PR as a breaking fail-loud change; if the owner prefers
warn-and-skip for parallel users, the change is localized to `require_worker_result` and the
`ResultVec` arm.

## 3a. Next phase: 23-P3

Reporting/rendering live bugs (B1, B4, B5) — plan 23 §5. Independent of P2. Note B5's
scope was narrowed during the audit: regressions are still reported correctly, and the
unit mismatch corrupts only the **improved-vs-unchanged** distinction for non-percentage
methods.

## 4. Small items P1 left on the floor

Each is independent and none blocks P2.

- **Plan 24 Q1** (small, self-contained): raise the `ty` ceiling to `<=0.0.65`
  (`pyproject.toml:80`; env resolves 0.0.56, behaviour identical across 0.0.56/0.0.64/
  0.0.65), and add plan 24 A5's third probe to `test/test_ty_gate.py` — a **complete**
  match fed from an unannotated helper asserted *type-clean*. Comment it as pinning
  current `ty` behaviour, not desired behaviour, so that a future `ty` release closing the
  hole becomes a test failure that tells us rather than a silent improvement. **P1 did not
  add this probe.**
- **Plan 24 A4** was not applied to plan 23 §9: add the DoD line "every `assert_never` in
  the tree either has a subject `ty` can type, or is preceded by a normalizing parse that
  is covered by a test", plus a grep check that no `assert_never` subject is an attribute
  read on a `param.Parameterized` instance.
- **`to_panes_multi_panel`** (`bencher/results/bench_result_base.py:833`) still declares
  `plot_callback: Callable | None = None` and forwards it into `_to_panes_da`, which P1
  narrowed to a required `Callable`. The unanswerable-`None` problem moved up one frame
  rather than being removed; `ty` cannot see it because `invalid-argument-type` is Tier C.
- **Seven `pn.pane = None` / `pn.pane.panel = None` parameter defaults** —
  `bench_result_base.py:658,737`, `video_summary.py:46`, `rerun_summary.py:82`,
  `heatmap_result.py:35,140`, `line_result.py:35`. Same shape as the
  `hv_dataset: hv.Dataset = None` bug P1 fixed. They escape `invalid-parameter-default`
  only because `pn.pane` is a *module* in annotation position and `invalid-type-form` is
  Tier C — i.e. one Tier-C suppression is currently hiding a Tier-A class of defect.
- **`bencher/run.py:52-53`** carries a `# ty: ignore[call-non-callable]`. The honest fix
  is one token: `if callable(_prev_sigterm_handler)` instead of
  `not in (signal.SIG_DFL, signal.SIG_IGN, None)`, which narrows for `ty` *and* is safer
  at runtime. Then delete the ignore.
- **`test/test_extra_panels.py` covers only `pn.pane.Markdown`** (4 references, zero
  non-Markdown cases). That gap let a P1 regression through CI — see §6. Add cases for a
  plain `str`, an `hv` element and a callable factory.

## 5. Deferred by design — each needs a phase that can own it

These are **behaviour or public-API changes**. They were found during P1 and deliberately
not made there. Do not sweep them into an unrelated PR.

1. **`map_plot_panes` defaults to no reduction, disagreeing with `to_hv_dataset`'s
   `AUTO`.** `map_plot_panes(reduce=None)` has always skipped reduction, because `None`
   fell through `to_dataset`'s old catch-all; `to_hv_dataset`'s own default averages over
   repeats. Fixing the default changes rendered output. `_resolve_auto`
   (`bench_result_base.py`) now maps `None → ReduceType.NONE` in one place and documents
   this. Compare `BenchResult.to()`, which handles the same sentinel correctly by omitting
   the argument — that is the shape to converge on.
2. **`to_hv_dataset`'s `ReduceType.NONE` arm discards kdim units** — a pre-existing bug.
   It passes `kdims=[name, ...]` as bare strings, where the generic arm lets holoviews
   infer dimensions from the xarray variables *with* units:
   ```
   reduce=None      -> [('theta', 'rad'), ('repeat', 'repeats')]
   ReduceType.NONE  -> [('theta', None),  ('repeat', None)]
   ```
   P1 does **not** route new traffic onto it (an earlier attempt did, and that is why the
   normalization moved to `_resolve_auto`). Fix by building `hv.Dimension` objects, or by
   reusing the inferred dims.
3. **`plot_sweep`'s annotation understates its domain.** `input_vars` is
   `list[ParametrizedSweep] | None`, but `convert_vars_to_params`
   (`bencher/sweep_executor.py:242`) accepts `param.Parameter | str | dict | tuple`, and
   `identity.py:155` passes `list | dict | None`. This is why **`identity.py` is not on
   the strict `ty` list** — it is not clean, and the wrong side is the annotation.
   Widening a public entry point is A5's business. Add `identity.py` to the strict block
   once resolved.
4. **`strenum` → stdlib `enum.StrEnum` is now possible but is a trap.** The 3.11 floor
   allows it; they are not drop-in equivalents:
   ```
   strenum.StrEnum + auto()  ->  member name verbatim   ('SERIAL')
   enum.StrEnum    + auto()  ->  lowercased name        ('serial')
   ```
   Five of seven StrEnums are unaffected (lowercase member names). **`Executors` and
   `SampleOrder` would silently change value**, and since `executor` is a
   `param.Selector(objects=list(Executors))`, that flips which strings callers may pass.
   Verified **not** a cache-invalidation risk: neither feeds `hash_persistent`, and
   `sample_order` is in `EXCLUDED_FIELDS` (`identity.py:49`). If done, give those two
   enums **explicit string values** rather than `auto()`, in its own PR.
5. **The `ReduceType` exhaustiveness guarantee is incomplete until P12.** `to_dataset`'s
   match is exhaustive over `ResolvedReduceType`, but the only rule that verifies
   `_resolve_auto` actually returns a member of that `Literal` — `invalid-return-type` —
   is Tier B and still globally ignored. Seeding `return ReduceType.AUTO` passes
   `pixi run ty`. So adding a `ReduceType` member without updating both the alias and the
   match currently fails at *runtime*, not at check time. A caveat comment records this at
   the alias. **P12 closes it**; `bench_result_base.py` has 3 other `invalid-return-type`
   diagnostics (`:202`, `:507`, `:543`) that must be fixed first.

## 6. Traps that cost real time — please read

1. **`ty` is not a no-op gate in the way the old config implied — but measuring it is
   easy to get wrong.** Every per-rule count in plan 23 §2.1 is only reproducible with
   `--python` pointing at a resolved environment. Without it, `param`/`panel`/`numpy`/
   `xarray` are all unresolved and the numbers are meaningless. The `ty` task now passes
   `--python "$CONDA_PREFIX"`; a meta-test pins the flag.
2. **A seeded `ty` probe run under the repo's own config silently passes**, because Tier C
   is globally ignored. `test/test_ty_gate.py` writes a minimal standalone `pyproject.toml`
   on purpose. This is the exact trap that made this plan's first measurements wrong.
3. **A regression can pass full CI here.** P1's first commit replaced
   `if callable(ep)` with `if isinstance(ep, pn.viewable.Viewable)` in `extra_panels` and
   swapped the branches. The predicates are **not complementary**: a `str`, `hv` element or
   `DataFrame` — previously appended, where `Column.append` coerces it — was called
   instead, raising `TypeError` into a surrounding `except Exception`, so the panel
   vanished from the report with only a log line. 2400+ tests stayed green because
   `test_extra_panels.py` only covers `Markdown` (§4). Corrected to
   `callable(ep) and not isinstance(ep, Viewable)`. **Whenever you change a discrimination
   predicate on a union, enumerate the objects that satisfy neither arm.**
4. **Three claims made during this work were later falsified** (the executor "bug", the
   `reduce` normalization being behaviour-preserving, and the `extra_panels` fix). All are
   recorded in plan 23 §10 with the falsifying evidence rather than quietly amended.
   Expect to falsify more; prefer running the probe over reasoning about it.
5. **Sourcery was rate-limited** (weekly 500k diff-char cap) on #1025 and #1026, so
   neither got an automated review. If it is still limited, budget for a manual or
   subagent adversarial pass — that is what caught trap 3.
6. **Do not add a file to the strict `ty` block until it is clean.** The block's whole
   value is that it only ever grows. Current members: `sample_order.py`,
   `sweep_timings.py`, `blob_store.py`.
7. **Do not silence a Tier-A rule with a broad `include` glob.** P1 replaced a five-tree,
   twelve-rule relaxed block (whose real effect was disabling seven Tier-A rules over
   `test/` and `bencher/example/`, including `missing-argument` — the rule that catches a
   call site omitting a newly-required argument) with one inline ignore plus a
   **file-precise** override for three files. A meta-test now fails on any override
   silencing a protected rule for first-party package code. Prefer a scoped
   `# ty: ignore[rule]` with a reason.
8. Annotating those three files inline is not possible: ruff reflows the import past the
   line limit and the comment lands on the inner line, where pylint's own
   `import-error` pragma stops applying — it dropped `pixi run pylint` from 10.00/10.

## 7. Verification recipe

```bash
pixi run ci                 # format, ruff, pylint, ty, tests+coverage (gate 85%)
pixi run -e py311 ci        # the other CI matrix entry
pixi run ty                 # gate only, fast
pixi run pytest test/test_ty_gate.py -q     # 24 tests, the gate's own meta-tests
```

Always prefix with `pixi run`. Never bump the version in `pyproject.toml` — a version
increase on `main` auto-publishes to PyPI (`.github/workflows/publish.yml` publishes only
on an *increase*, so leaving it alone is safe).

To prove the exhaustiveness gate still bites, delete one `case ReduceType.*` arm from
`to_dataset` and run `pixi run ty`: expect
`error[type-assertion-failure] … Inferred type of argument is Literal[ReduceType.<member>]`.

## 8. Remaining phase order

`P2` (§3) → `P3` → `P4` (result-type registry; A6 phase 2 consumes it, so do it before
that) → `P5`–`P11` (mutually independent, individually droppable) → `P12` (Tier-B ratchet,
which also closes §5.5). Plan 24's Q1 (§4) is independent and can go any time.
