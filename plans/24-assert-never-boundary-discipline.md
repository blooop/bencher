# Plan 24 — `assert_never` boundary discipline (amends plan 23)

**Goal:** plan 23's D2 exhaustiveness thesis is sound, but it holds *only* where the
`match` subject's type is established at the boundary. Measured: for `param`-descriptor
reads it is **not** established, **no** type checker in the field closes the gap, and the
resulting `assert_never` arm is therefore a live `AssertionError` path rather than a
proof. This plan adds the missing precondition, scopes it to the two phases that
actually need it, and re-affirms plan 23's "`ty` only" decision with the evidence that
decision was originally made without.

**Status:** amendment, not a replacement. Plan 23's P1, P3–P10 and P12 are unchanged.
Two DoD additions land inside 23-P2 and 23-P11; one small independent phase (Q1) is
new. **Q1 is half-landed** as of 2026-08-04: plan 26 R10 did the pin (exactly 0.0.66,
locked in every environment); A5's third probe is still not written.

**Citations pinned to:** `main` @ `fa28ba73` (the plan 23 merge, PR #1023, 2026-07-31).
Per plans-README rule 7, confirm each `file:line` against the current tree before
relying on it; the symbol is the durable reference.

**Tool versions all facts below were measured with:** `ty` 0.0.56 (what the pin resolved
to when this plan was written), `typing_extensions` 4.16.0, py310 target. Cross-checked on
`ty` 0.0.64 and 0.0.65, and on `pyrefly` 1.1.1. The repo now pins `ty` **exactly to
0.0.66** (plan 26 R10); the boundary finding below still holds there — the gate's
`test_untyped_ingress_into_complete_match_is_clean` probe passes on 0.0.66.

**Re-verified after the 3.11 floor raise:** the floor is now
`requires-python = ">=3.11,<3.14"` (`pyproject.toml:10`), so `assert_never` comes from
the stdlib and `typing_extensions` is no longer involved. **This plan's central finding
is unaffected** — re-ran the §2.1 ingress probe at a py311 target with
`from typing import assert_never`: a *complete* `match` fed from an unannotated source is
still `All checks passed!` while raising
`AssertionError: Expected code to be unreachable, but got: 'SERIAL'` at runtime. The hole
is a property of gradual typing at an untyped boundary (§2.5), not of the import source or
the target version, so every amendment below stands as written. Read
`typing_extensions.assert_never` as `typing.assert_never` throughout.

---

## 1. What plan 23 got right (re-verified — do not re-litigate)

Plan 23 §2.3's controls reproduce exactly at `fa28ba73`:

| Probe | Result |
|---|---|
| Complete `match` over a 2-arm frozen-dataclass union + `from typing_extensions import assert_never` | ✅ `All checks passed!` |
| Same union widened to 3 arms, third arm unhandled | ✅ `error[type-assertion-failure]` |

The diagnostic is also better than plan 23 recorded — it names the residual type, not
just the failure:

```
error[type-assertion-failure]: Argument does not have asserted type `Never`
  --> p2_incomplete.py:32:13
   |             assert_never(unreachable)
   |                          Inferred type of argument is `Cancelled & ~Ready & ~Pending`
```

So D2's mechanism works, §2.4 stands (`type-assertion-failure` is not in the ignore
list), and the diagnostic names the forgotten variant well enough to drive
`pixi run agent-iterate` without a human reading the union definition.

One new supporting fact plan 23 did not have: **`ty` narrows tuple `match` subjects
correctly.** A `match` over `tuple[Side, Side]` covering 3 of 4 combinations raises
`type-assertion-failure`; the complete 4-of-4 version passes clean. Product-of-sums
subjects are therefore safe to use under this repo's gate — which is not true of the
alternative checkers (§4).

## 2. Measured facts (verified 2026-07-31 against `fa28ba73`; do not re-litigate)

1. **The ingress hole.** A **complete** `match` — one plan 23's D2 treats as having a
   provably-dead `assert_never` arm — is type-clean while raising at runtime, whenever
   its subject arrives from an untyped source.

   Probe: complete 2-arm union + `typing_extensions.assert_never`; the caller obtains
   its subject from an unannotated helper returning `"SERIAL"`.

   | Config | `ty` verdict |
   |---|---|
   | Replica of the repo's 21-rule `[tool.ty.rules]` ignore list | `All checks passed!` |
   | Same, but `invalid-argument-type = "error"` | `All checks passed!` |

   Runtime: `AssertionError: Expected code to be unreachable, but got: 'SERIAL'`.
   Identical on `ty` 0.0.56, 0.0.64, 0.0.65 and 0.0.66.

2. **The repo's own config documents the ingress vector.** `pyproject.toml:281`:
   "param library StrEnum/enum descriptors resolve as **Unknown**". Every `match` whose
   subject is a read of a `param` field is therefore this shape, by the repo's own
   analysis.

3. **Reproduced through that exact mechanism.** A `param.Parameterized` with
   `executor = param.Selector(objects=list(Executors))` (the shape at
   `bench_cfg.py:241`) and `dispatch(cfg.executor)` where `dispatch` matches both
   members exhaustively → `All checks passed!`. At runtime, appending a value to
   `.objects` and assigning it reaches the arm:
   `AssertionError: Expected code to be unreachable, but got: 'LEGACY'`.

4. **Enabling the Tier-C rule does not close it** (row 2 of the table in fact 1). This is
   the one gap D1's strict-list ratchet cannot reach — worth stating explicitly, because
   the natural assumption when reading D1 is that putting a file on the strict list makes
   its `assert_never` arms sound. It does not.

5. **No other checker closes it either.** `pyrefly` 1.1.1, py310 target, pointed at this
   repo's site-packages: clean on **both** probes. So this is not "`ty` is behind" — it
   is a property of gradual typing at an untyped boundary, and it is not fixable by
   checker choice.

6. **Pin is one release stale.** `ty>=0.0.13,<=0.0.64`; 0.0.65 is the latest published
   version; the env resolves 0.0.56. Behavior on every probe in this plan is identical
   across all three.

   **Resolved** by plan 26 R10 (2026-08-04), which also found the framing here too narrow:
   a stale *ceiling* was not the whole problem. CI runs bare `pixi update` before
   `pixi run ci`, so it resolved to the ceiling while the committed lock gave developers
   0.0.56 — the two ran different checkers. ty is now pinned exactly to 0.0.66, so
   "resolves" and "is pinned to" are the same statement.

## 3. Amendments to plan 23

### A1 — D2 gains a third category (it currently has two)

D2 today: `assert_never` everywhere, **except** where the subject crosses a trust
boundary (deserialized cache / user input), where a runtime `raise` is correct. Add a
third:

> **Descriptor-sourced subjects.** A `match` may end in `assert_never` only if the
> subject is a parameter, local, or field whose type `ty` can establish. **A read of a
> `param` field does not qualify** (§2.2). Normalize at the boundary first — construct
> the enum (`Executors(value)`, `AggFn(value)`), raising on an unknown value — and cover
> that normalization with a **runtime** test, because §2.1 and §2.5 show no type checker
> enforces it.

Rationale to record alongside it: an `assert_never` on an un-established subject is
strictly worse than the `case _: raise` it replaced, because it reads as a proof while
behaving as an assertion — and `assert_never`'s message ("Expected code to be
unreachable") actively misdirects the reader of the traceback, who will look for a
missing enum member rather than a bad value at the boundary.

### A2 — D4's boundary normalization is promoted from hardening to precondition

D4 already says: "Normalize enum-typed param fields at the config boundary so `==` vs
`is` can never diverge again (C13's class of bug)." That justification undersells it.
Normalization is the **precondition that licenses D2 on those fields** — C13's `==`/`is`
hazard is the lesser of the two things it buys. Reorder the reasoning so a phase author
who reads D4 and judges C13 "a latent smell, not worth much" does not skip the step D2
depends on.

### A3 — Scope: exactly two phases are affected

Verified by grepping every `param.Selector` / `param.ObjectSelector` that plan 23
proposes to match on:

- **23-P2 — `executor`** (`param.Selector(objects=list(Executors))`,
  `bench_cfg.py:241`). P2 already normalizes it, for C13's reason. **DoD addition:**
  state in the PR that the normalization is what licenses any later `assert_never` on
  `executor`, and keep a test asserting an out-of-vocabulary value raises **at
  normalization**, not at a match site.
- **23-P11 — `agg_fn`** (`param.ObjectSelector(default="mean", objects=["mean", "sum",
  "max", "min", "median"])`, `bench_cfg.py:820-824`). Strictly worse than `executor`:
  the objects are **raw strings, not enum members**, so P11's proposed `AggFn` enum must
  be *constructed* at the boundary rather than assumed to be what the descriptor holds.
  **DoD addition:** the "unknown agg raises" test must drive the raw string through the
  `param` field, not call the enum-typed function directly — the latter passes while the
  shipped path still reaches `assert_never`.

Explicitly **not** affected, so no phase pays for this twice:

- **23-P1's `reduce`** — a plain annotated parameter (`reduce: ReduceType`,
  `bench_result_base.py:199`, `:245`), and `ReduceType` is a stdlib `Enum`
  (`bench_result_base.py:54`), not a `param` field. P1's conversion of the
  `case _:` at `bench_result_base.py:353` is sound as written. (Its current arm absorbs
  `ReduceType.NONE` — see the comment at `:354` — so the conversion must enumerate
  `NONE` explicitly and rely on `_resolve_auto` (`:237-239`) having eliminated `AUTO`,
  exactly as P1 already says.)
- **23-P8's `compose_method`** — not a `param` field anywhere in the tree.
- **23-P7's `HistoryEvent.kind`** — internally produced (`history.py:77`); the
  policy string read at `load_history_cache` is a genuine trust boundary, which P7
  already handles with a raise.

### A4 — §9 (plan-level DoD) gains one line

> Every `assert_never` in the tree either has a subject `ty` can type, or is preceded by
> a normalizing parse that is covered by a test.

And one grep-level check alongside the existing ones: no `assert_never` whose subject
expression is an attribute read on a `param.Parameterized` instance.

### A5 — 23-P1's meta-test gains a third probe

`test/test_ty_gate.py` (new in P1) should add, beside its non-exhaustive-match and
Tier-A probes, a case asserting that a **complete** match fed from an unannotated helper
is type-clean. Two reasons: it pins the boundary of what the gate proves so a future
reader does not over-trust it, and it converts a future `ty` release that closes the
hole into a **test failure that tells us**, rather than a silent improvement nobody
notices. Comment it as pinning current reality, not desired behavior.

### A6 — "`ty` only" re-affirmed, now evidence-backed

Plan 23 §1 lists "switching or adding type checkers" as a non-goal, resolved on
convenience grounds ("already wired in"). That decision is **correct and should stand**,
and now has evidence behind it:

- Adding `pyrefly` would not fix the gap this plan is about (§2.5).
- It would actively break correct code: `pyrefly`, `mypy` and `zuban` all reject a
  **complete** tuple `match` that `ty` accepts (§4) — pushing authors to add a fallback
  arm, which is precisely what defeats exhaustiveness.

Two housekeeping items, neither urgent:

- **Raise the pin ceiling to `<=0.0.65`** (§2.6); behavior verified identical.
- **Governance watch item, no action:** Astral was acquired by OpenAI on 2026-03-19, and
  `ty` remains `0.0.x` with no stability guarantee (breaking diagnostic changes are
  permitted between any two releases). The existing upper pin is already the right
  mitigation; this is recorded so a future reader does not have to rediscover why the
  ceiling exists.

## 4. Why not add a second checker (measured)

Fourteen constructive-modeling probes were run across `pyright` 1.1.411,
`basedpyright` 1.39.9, `pyrefly` 1.1.1, `ty` 0.0.65, `mypy` 2.3.0 and `zuban` 0.9.0.
Only the three rows that discriminate are reproduced here:

| Probe | pyright | basedpyright | pyrefly | ty | mypy | zuban |
|---|---|---|---|---|---|---|
| Core exhaustiveness — union / enum / `Literal` / `if`-`elif` / PEP 695 generic / nested union, arm missing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Complete** `tuple[A, A]` match (error here is a false positive) | ✅ clean | ✅ clean | ❌ error | ✅ clean | ❌ error | ❌ error |
| `Unknown`/`Any` ingress into a complete match | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

Reading:

- The **core is universal** — every checker enforces single-level sum-type
  exhaustiveness. No checker choice buys bencher anything there.
- **Tuple subjects discriminate, in `ty`'s favour.** `pyrefly`/`mypy`/`zuban` never
  narrow tuple subjects, so `assert_never` fails no matter how many combinations are
  covered.
- **Nothing catches the ingress hole.** The remedy is a modeling rule (A1), not a tool.
- Separately, `basedpyright` flags the `case _ as unreachable:` arm itself under
  `reportUnnecessaryComparison` ("Pattern will never be matched for subject type"), so it
  cannot express D2's idiom without a config carve-out. Another reason not to add it.

## 5. Phases

### Q1 — pin ceiling + gate-boundary probe (independent, small) — **pin done, probe open**

- ~~Raise the `ty` ceiling to `<=0.0.65`.~~ **Done** in plan 26 R10 (2026-08-04), which
  went further: ty is pinned *exactly* to 0.0.66 and locked there in every environment,
  because a range let CI (which runs bare `pixi update`) and local runs use different
  checkers.
- Add A5's third probe to `test/test_ty_gate.py`. **Still open** — neither 23-P1 nor R10
  added it.
- **Ordering:** depends on 23-P1 having created `test/test_ty_gate.py`. If Q1 lands
  first, it carries the pin bump only and A5 folds into P1.
- **DoD:** `pixi run ci` green on py311 and py313 (the post-floor-raise matrix); the new probe documents, in a
  comment, that it pins current `ty` behaviour rather than desired behaviour.

### Folded into existing plan 23 phases (no new PRs)

- **23-P2** — A3's `executor` DoD addition.
- **23-P11** — A3's `agg_fn` DoD addition (drive the raw string through the `param`
  field).
- **23-P1** — A5, if Q1 has not already landed it.
- **Plan 23 §9** — A4's DoD line and grep check.

If plan 23's phases are dropped or deferred, A4's grep check is the residue worth
keeping on its own.

## 6. OWNER DECISIONS

1. **Normalize-at-boundary vs raise-at-match for `param`-sourced enums.**
   Recommendation: **normalize** — raise on an unknown value where the config is
   accepted. A raise at each match site is the trust-boundary pattern (D2 category two)
   and would spread boundary-checking across every consumer of the field, which is the
   shape plan 23 exists to remove.
2. **Pin ceiling `<=0.0.65`.** Recommendation: **yes** — §2.6 verified identical
   behaviour on every probe.
3. **A5's probe: assert-clean vs `xfail`.** Recommendation: **assert-clean with an
   explanatory comment** — an `xfail` that starts passing is easy to miss, whereas a
   failing assertion names the reason in the output.
4. **Whether A4's grep check ships as a test or a review checklist item.**
   Recommendation: **test** — it is a one-line `grep` over `bencher/`, and the whole
   point of this plan is that the type checker cannot carry the invariant.

## 7. Cache safety

Docs-only; no phase here changes stored values. The amendments inherit plan 23 §7's
constraints, and A3's `executor` normalization is already covered by §7's requirement
that it "must not perturb any persisted hash" — confirm in 23-P2 and state the finding
in that PR, as §7 already directs.

## 8. Provenance

Every fact in §1, §2 and §4 was measured in scratch directories outside the repo;
nothing from the probes is committed. The probes were: complete/incomplete unions,
enums, `Literal`s, `if`/`elif` chains, PEP 695 generic sum types, nested unions,
frozen-dataclass mutation, complete and incomplete `tuple[A, A]` matches, and two
ingress probes (unannotated-helper and `param.Selector`). Reproducing them needs only
the `.pixi/envs/default` interpreter and a `[rules]` file replicating
`pyproject.toml:246-285`; the method is worth re-running whenever the `ty` pin moves,
which is what A5 automates for the one case that matters most.

Two corrections to earlier drafts of this analysis, recorded per plans-README rule 7:

1. An earlier draft claimed `pyrefly` **catches** the ingress hole, based on a probe
   where the untyped helper was first-party code in the same directory and `pyrefly`
   inferred through it. Re-run against this repo's environment, `pyrefly` reports the
   probe clean (§2.5). The stronger claim — "adding `pyrefly` would close the gap" — is
   **false** and is the reason A6 recommends against adding it rather than for it.
2. An earlier draft claimed `ty`'s exhaustiveness diagnostic does not name the missing
   variant. It does (§1) — the intersection type in the `info` line identifies it.
