"""Meta-tests for the ``ty`` type-check gate itself.

The gate is configuration, so it can be weakened by a one-line edit to
``pyproject.toml`` without any test noticing. Before plan 23 P1 the gate ignored 21
rules and was effectively a no-op that still reported "All checks passed!". These tests
assert the *properties that make it a gate*, so that regression cannot happen silently
again.

See ``plans/23-constructive-data-modeling.md`` sections D1/D2 and P1.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Rules that must never be silenced globally, with the reason each one matters.
MUST_NOT_BE_IGNORED = {
    # The exhaustiveness mechanism. Silencing this turns every `assert_never` arm from a
    # compile-time proof into a runtime assertion, with no other signal.
    "type-assertion-failure": "exhaustive `match` checking (plan 23 D2)",
    # Tier B's first rule, enabled in P12. This is what verifies `_resolve_auto` really
    # returns a member of `ResolvedReduceType`, i.e. what makes `to_dataset`'s
    # `assert_never` a compile-time proof instead of a runtime assertion. Re-ignoring it
    # silently downgrades that proof, which is exactly the state P1 shipped with and P12
    # was written to end.
    "invalid-return-type": "the ReduceType exhaustiveness proof (plan 23 P12)",
    # The other four Tier-B rules, enabled in P12b. Each was paid for by fixing a
    # representation rather than by adding annotations, so re-ignoring one does not just
    # hide diagnostics -- it re-permits the shape that produced them.
    "not-iterable": "optional-list fields that mean `[]` (plan 23 P12b)",
    "no-matching-overload": "Tier B (plan 23 P12b)",
    "unsupported-operator": "operations on optionals, incl. the registry `exc` shadow "
    "(plan 23 P12b)",
    "possibly-missing-attribute": "the total public surface for optional extras (plan 23 P12b)",
    # Tier A, enabled in P1. Each was measured at <=6 diagnostics, so a reappearance in
    # the ignore list is a regression rather than a pragmatic concession.
    "call-non-callable": "Tier A (plan 23 P1)",
    "call-top-callable": "Tier A (plan 23 P1)",
    "inconsistent-mro": "Tier A (plan 23 P1)",
    "invalid-method-override": "Tier A (plan 23 P1)",
    "invalid-parameter-default": "Tier A (plan 23 P1)",
    "missing-argument": "Tier A (plan 23 P1)",
    "too-many-positional-arguments": "Tier A (plan 23 P1)",
    "unresolved-import": "Tier A (plan 23 P1)",
    "unresolved-reference": "Tier A (plan 23 P1)",
}


def _ty_config() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["tool"]["ty"]


def _global_rules() -> dict[str, str]:
    return _ty_config().get("rules", {})


# Rules ty ships DISABLED by default. For these, "absent from [tool.ty.rules]" means
# OFF, not "on at its default severity" -- so `!= "ignore"` is not evidence of anything
# and the rule must be spelled out as "error".
#
# This list exists because P12b got it wrong: it "enabled" possibly-missing-attribute by
# deleting its `= "ignore"` line, `pixi run ty` stayed green, and the seeded probe that
# was supposed to confirm the fix passed `--error possibly-missing-attribute` on the
# command line -- so it measured a rule the checked-in config did not have on. Every
# surface signal agreed the gate was armed while it was not.
#
# Verify a candidate before adding it here: write a file violating the rule, run
# `ty check` on it under a config that does NOT mention the rule, and see whether
# anything is reported.
OFF_BY_DEFAULT_IN_TY = {
    # Re-verified on the 0.0.56 -> 0.0.66 re-lock (plan 26 R10): still off by default, and
    # test_repo_rule_table_actually_fires_on_a_seeded_violation still passes, so the
    # explicit "error" is still doing the work. Re-run this file whenever the pin moves --
    # a release that flipped the default to on would make the entry redundant rather than
    # wrong, but one that renamed the rule would silently disarm it (ty warns
    # `unknown-rule` and continues; that probe asserts the warning is absent).
    "possibly-missing-attribute": "verified on ty 0.0.56, 0.0.65 and 0.0.66 with standalone probes",
}


class TestGateConfiguration:
    """Properties of the checked-in ty configuration."""

    @pytest.mark.parametrize("rule", sorted(OFF_BY_DEFAULT_IN_TY))
    def test_off_by_default_rule_is_explicitly_enabled(self, rule: str) -> None:
        setting = _global_rules().get(rule)
        assert setting == "error", (
            f"`{rule}` is off by default in ty ({OFF_BY_DEFAULT_IN_TY[rule]}), so it must "
            f"be set to 'error' in [tool.ty.rules] to be enforced -- currently {setting!r}. "
            f"Merely leaving it out of the ignore list is what P12b did first, and the gate "
            f"reported 'All checks passed!' with the rule switched off."
        )

    @pytest.mark.parametrize("rule", sorted(MUST_NOT_BE_IGNORED))
    def test_rule_not_globally_ignored(self, rule: str) -> None:
        setting = _global_rules().get(rule)
        assert setting != "ignore", (
            f"`{rule}` has been added back to [tool.ty.rules] as 'ignore'. "
            f"It guards {MUST_NOT_BE_IGNORED[rule]}. Silencing it globally makes the "
            f"gate pass while the property it protects is unenforced. Scope the "
            f"suppression to the offending line with `# ty: ignore[{rule}]` and a "
            f"reason, rather than disabling it here."
        )

    def test_ty_task_resolves_the_environment(self) -> None:
        """Without ``--python`` ty resolves no third-party import.

        param, panel, numpy and xarray all read as unresolved, which silently degrades
        every rule that needs a third-party type. The task must therefore point ty at
        the active environment.
        """
        task = _load_ty_task()
        assert "$CONDA_PREFIX" in task, (
            "the `ty` task must resolve the *active* pixi environment via $CONDA_PREFIX, "
            "so that `-e py311` and `-e py313` each check against their own interpreter. "
            f"A hardcoded or empty path would check the wrong env. Task: {task!r}"
        )
        assert "--python" in task, (
            "the `ty` pixi task no longer passes --python, so ty will type-check with "
            "no third-party packages resolved. Every rule that depends on knowing an "
            'external type degrades silently. Restore --python "$CONDA_PREFIX".'
        )

    @pytest.mark.parametrize("rule", sorted(MUST_NOT_BE_IGNORED))
    def test_rule_not_ignored_for_the_package_via_overrides(self, rule: str) -> None:
        """The global ignore table is not the only way to disable a rule.

        An ``[[tool.ty.overrides]]`` block with a broad ``include`` silences rules just
        as effectively, and asserting only on ``[tool.ty.rules]`` would not notice. This
        caught a real hole in review: a block covering ``bencher/example/**`` had
        ``missing-argument`` off across the corpus that doubles as integration tests.

        Kept alongside :class:`TestEffectiveGateConfig`, which subsumes this one's
        *coverage* by running the real gate on a seeded violation. The two are not
        redundant in the way that suggests deleting this: this test names the offending
        pattern and rule, so it says *what to edit*, and it needs no ty binary. The probe
        only reports that first-party code went unchecked. Keep both — this one for the
        message, the probe for the routes it cannot see (per-rule pattern matching is
        blind to exclude-only blocks, ``[tool.ty.src].exclude`` and ignore files).
        """
        offenders = []
        for block in _ty_config().get("overrides", []):
            if block.get("rules", {}).get(rule) != "ignore":
                continue
            for pattern in block.get("include", []):
                # Silencing a rule for first-party package code is the regression; the
                # generated-example tree and helper trees are allowed to be exempted, but
                # must be listed explicitly rather than swept in by a `bencher/**` glob.
                if pattern.startswith("bencher/") and not pattern.startswith(
                    ("bencher/example/", "bencher/_vendor/")
                ):
                    offenders.append((pattern, rule))
        assert not offenders, (
            f"`{rule}` is disabled for first-party package code by an override block "
            f"({offenders}). It guards {MUST_NOT_BE_IGNORED[rule]}. Prefer a scoped "
            f"`# ty: ignore[{rule}]` on the offending line, which is greppable and "
            f"carries a reason, over an include pattern that silently covers a subtree."
        )

    def test_strict_override_block_is_non_empty(self) -> None:
        """The Tier-C ratchet must actually cover something.

        Plan 23 couples "constructively modeled" to "strictly checked": each phase adds
        the files it reworked. An empty list means the ratchet has been disengaged.
        """
        overrides = _ty_config().get("overrides", [])
        strict = [o for o in overrides if any(v == "error" for v in o.get("rules", {}).values())]
        assert strict, "no [[tool.ty.overrides]] block sets any rule to 'error'"
        covered = [path for block in strict for path in block.get("include", [])]
        assert covered, "the strict override block covers no files"


def _load_ty_task() -> str:
    with PYPROJECT.open("rb") as fh:
        tasks = tomllib.load(fh)["tool"]["pixi"]["tasks"]
    task = tasks["ty"]
    return task["cmd"] if isinstance(task, dict) else task


def _repo_ty_argv() -> list[str]:
    """The repo's *own* ty invocation, with ``$CONDA_PREFIX`` resolved to this interpreter.

    Derived from the pixi task rather than hardcoded, so a probe built on this follows
    the gate CI actually runs. If someone drops ``--respect-ignore-files`` or the target
    path, the probe changes with it instead of silently testing a command nobody uses.
    """
    argv = shlex.split(_load_ty_task())
    return [sys.prefix if arg == "$CONDA_PREFIX" else arg for arg in argv]


# Seeded-violation sites for the effective-config probe below. Both are removed in the
# fixture's teardown; neither is importable from `bencher/__init__.py`.
_PKG_PROBE = REPO_ROOT / "bencher" / "_ty_gate_probe.py"
_NB_PROBE = REPO_ROOT / "docs" / "reference" / "_ty_gate_probe_nb" / "probe.ipynb"

# `invalid-parameter-default` is Tier A (plan 23 P1) and error-by-default in ty, so it
# needs no rule-table entry to fire -- which is what makes it the right canary: if the
# gate does not report THIS, the gate is not looking at the file at all.
_TIER_A_VIOLATION = 'def probe(x: int = "not an int") -> int:\n    return x\n'
_TIER_A_VIOLATION_NB = (
    '{"cells":[{"cell_type":"code","execution_count":null,"metadata":{},"outputs":[],'
    '"source":["def probe(x: int = \\"not an int\\") -> int:\\n","    return x\\n"]}],'
    '"metadata":{},"nbformat":4,"nbformat_minor":5}'
)


@pytest.fixture(scope="module")
def seeded_repo_gate_run() -> Iterator[tuple[str, int]]:
    """Run the repo's real ty gate over a tree seeded with two known violations.

    One ty run, ~5s, shared by the assertions below — they test opposite halves of the
    same effective configuration (package code must be checked; generated notebooks must
    not gate), so measuring both from one invocation is both cheaper and stricter than
    two runs that could disagree about the state of the tree.
    """
    if shutil.which("ty") is None:  # pragma: no cover - mirrors the class-level skipif
        pytest.skip("ty binary not on PATH")
    created_dirs = []
    parent = _NB_PROBE.parent
    if not parent.exists():
        created_dirs.append(parent)
        parent.mkdir(parents=True)
    _PKG_PROBE.write_text(_TIER_A_VIOLATION)
    _NB_PROBE.write_text(_TIER_A_VIOLATION_NB)
    try:
        result = subprocess.run(
            [*_repo_ty_argv(), "--output-format", "concise"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        yield result.stdout + result.stderr, result.returncode
    finally:
        # Unconditional: a leftover probe under `bencher/` would fail the real gate for
        # every later run, including the developer's next `pixi run ty`.
        _PKG_PROBE.unlink(missing_ok=True)
        _NB_PROBE.unlink(missing_ok=True)
        for path in reversed(created_dirs):
            path.rmdir()


@pytest.mark.skipif(shutil.which("ty") is None, reason="ty binary not on PATH")
class TestEffectiveGateConfig:
    """Does the gate, *as configured*, actually check first-party package code?

    Every other test in this file reads configuration and reasons about it. That is not
    enough, and plan 23 P12b is the proof: the rule table said one thing and the checker
    did another. `[tool.ty.rules]` is also not the only lever — the gate can be
    neutralised for `bencher/` without touching it at all, via

      1. an `[[tool.ty.overrides]]` block with a broad include (`["**"]`),
      2. an override block that only *excludes*,
      3. `[tool.ty.src].exclude`,
      4. a `.gitignore` or `.ignore` entry (the task runs `--respect-ignore-files`).

    All four were measured live while writing this (on 0.0.56, before the re-lock): routes
    3 and 4 both
    suppress a seeded diagnostic completely. `test_rule_not_ignored_for_the_package_via_overrides`
    inspects include patterns and so cannot see any of them.

    A probe that runs the real command in the real repo root closes all four at once,
    because it asks the only question that matters — is a violation in `bencher/`
    reported? — rather than enumerating the ways the answer could be no.
    """

    def test_gate_reports_a_tier_a_violation_in_first_party_code(
        self,
        seeded_repo_gate_run: tuple[str, int],  # pylint: disable=redefined-outer-name
    ) -> None:
        output, returncode = seeded_repo_gate_run
        assert "_ty_gate_probe.py" in output, (
            "The repo's own ty command did not report an `invalid-parameter-default` "
            "violation seeded at bencher/_ty_gate_probe.py, so first-party package code "
            "is no longer being type-checked. Something is excluding it: a broad "
            "`[[tool.ty.overrides]]` include, an exclude-only override block, "
            "`[tool.ty.src].exclude`, or a `.gitignore`/`.ignore` entry (the task runs "
            f"--respect-ignore-files). Command: {_repo_ty_argv()}\nOutput:\n{output}"
        )
        assert "invalid-parameter-default" in output, (
            "the seeded file was reported, but not for the Tier-A rule that was seeded; "
            f"`invalid-parameter-default` may have been renamed or downgraded:\n{output}"
        )
        assert returncode != 0, (
            "ty reported the seeded Tier-A violation but exited 0, so CI would pass over "
            f"it. The diagnostic is not error-level.\nOutput:\n{output}"
        )

    def test_generated_notebooks_do_not_gate_the_type_check(
        self,
        seeded_repo_gate_run: tuple[str, int],  # pylint: disable=redefined-outer-name
    ) -> None:
        """`pixi run ty` must not depend on whether docs have been built.

        ty type-checks `.ipynb` (measured on 0.0.56 and re-measured on 0.0.66, not assumed
        -- the assertion below is a negative, so it would pass trivially if that ever
        changed). `generate-docs` writes
        notebooks under `docs/reference/<section>/`, and only `docs/reference/meta/` is
        gitignored — so without an exclusion the gate's result changes depending on
        whether the developer has run `generate-docs`. CI escapes this today only by
        task ordering (`ty` runs before `generate-examples` in the `ci` task), which is
        not a property anyone declared or is holding onto deliberately.

        This deliberately does not assert *which* mechanism excludes them, only that one
        does. The repo previously expressed this intent in a `.tyignore` file, which ty
        does not read at all — a seeded violation under `docs/` was reported despite
        `.tyignore` listing `docs/`. If someone re-introduces that file, this fails.
        """
        output, _ = seeded_repo_gate_run
        assert "probe.ipynb" not in output, (
            "A violation seeded in a generated-style notebook under docs/reference/ was "
            "reported by the gate, so `pixi run ty` now passes or fails depending on "
            "whether `generate-docs` has been run. Exclude notebooks in a mechanism ty "
            "actually reads -- `[tool.ty.src].exclude` works; a `.tyignore` file is "
            f"silently ignored by ty.\nOutput:\n{output}"
        )


@pytest.mark.skipif(shutil.which("ty") is None, reason="ty binary not on PATH")
class TestGateActuallyFires:
    """Proof that `ty` itself enforces exhaustiveness, under a minimal config.

    Scope note: these mostly run against a *standalone* minimal config, so they verify
    the mechanism plan 23 D2 depends on rather than this repo's full gate. The exception
    is ``test_repo_rule_table_actually_fires_on_a_seeded_violation``, which reconstructs
    this repo's ``[tool.ty.rules]``. Repo-level properties are asserted by
    TestGateConfiguration above (by reading config) and by TestEffectiveGateConfig below
    (by running the real command on a seeded violation).

    Configuration assertions above can pass while the checker itself is misconfigured,
    so these run ty against seeded violations. They deliberately use a *minimal
    standalone* config rather than the repo's: under the repo config the Tier-C rules
    are ignored and a seeded probe passes, which is exactly the trap that made the
    original measurements for this plan wrong.
    """

    @staticmethod
    def _run_ty(tmp_path: Path, source: str) -> tuple[str, int]:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "probe"\nversion = "0"\nrequires-python = ">=3.11"\n'
        )
        probe = tmp_path / "probe.py"
        probe.write_text(source)
        result = subprocess.run(
            ["ty", "check", "--python", sys.prefix, str(probe)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        return result.stdout + result.stderr, result.returncode

    def test_non_exhaustive_match_is_rejected(self, tmp_path: Path) -> None:
        output, returncode = self._run_ty(
            tmp_path,
            """
from enum import Enum, auto
from typing import assert_never


class Kind(Enum):
    A = auto()
    B = auto()
    C = auto()


def handle(k: Kind) -> str:
    match k:
        case Kind.A:
            return "a"
        case Kind.B:
            return "b"
        case _ as unreachable:
            assert_never(unreachable)
""",
        )
        assert returncode != 0, (
            f"ty exited 0 on a non-exhaustive match, so the diagnostic is not "
            f"error-level and would not fail CI. Output:\n{output}"
        )
        assert "type-assertion-failure" in output, (
            "ty did not reject a match missing one enum member. The exhaustiveness "
            f"mechanism plan 23 D2 relies on is not working. Output:\n{output}"
        )
        assert "Kind.C" in output, (
            "ty flagged the incomplete match but did not name the missing variant, "
            f"which is what makes the diagnostic actionable. Output:\n{output}"
        )

    def test_repo_rule_table_actually_fires_on_a_seeded_violation(self, tmp_path: Path) -> None:
        """Run a seeded violation under **this repo's** `[tool.ty.rules]`, not a minimal one.

        The sibling probes here deliberately use a standalone config (see the class
        docstring). That leaves one thing unchecked: whether the *checked-in* rule table
        enables what it claims. It did not — P12b shipped `possibly-missing-attribute`
        switched off while `pixi run ty` said "All checks passed!", because ty defaults
        the rule to off and the PR only deleted its `"ignore"` line.

        So this reconstructs the repo's rule table verbatim and asserts the rule bites.
        Config assertions alone cannot catch a default that is not what you assumed.
        """
        rules = _global_rules()
        # Every value in [tool.ty.rules] is a severity string today, and the round-trip
        # below re-quotes it as one. Checked rather than assumed: a non-string value would
        # still serialise into valid TOML (`x = "True"`), so the probe would silently run
        # against a rule table that is not the repo's -- the exact class of false pass this
        # test exists to close.
        non_strings = {k: v for k, v in rules.items() if not isinstance(v, str)}
        assert not non_strings, (
            f"[tool.ty.rules] holds non-string values {non_strings!r}; this probe "
            "re-serialises each value as a quoted string, so it would check a rule table "
            "that differs from the checked-in one. Teach the serialisation the new shape."
        )
        rule_lines = "\n".join(f'{k} = "{v}"' for k, v in rules.items())
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "probe"\nversion = "0"\nrequires-python = ">=3.11"\n\n'
            f"[tool.ty.rules]\n{rule_lines}\n"
        )
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "opt.py").write_text("thing = 1\n")
        (pkg / "__init__.py").write_text(
            "try:\n    from pkg.opt import thing\nexcept ModuleNotFoundError:\n    pass\n"
        )
        (tmp_path / "use.py").write_text(
            "import pkg\n\n\ndef go() -> object:\n    return pkg.thing\n"
        )
        result = subprocess.run(
            ["ty", "check", "--python", sys.prefix, str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )
        output = result.stdout + result.stderr
        # Checked before the diagnostic assertion, and separately: ty reports an unknown
        # rule name as `warning[unknown-rule]: ... Did you mean \`possibly-missing-attribute\`?`
        # and exits 1. A bare substring test for the rule name plus `returncode != 0` is
        # therefore satisfied by a config where the rule is MISSPELLED and so entirely
        # off -- the suggestion text contains the name and the warning sets the exit code.
        # ty has renamed a rule this repo uses before (unused-ignore-comment ->
        # unused-type-ignore-comment), so this is a live path, not a hypothetical.
        assert "unknown-rule" not in output, (
            "ty does not recognise a rule name in this repo's [tool.ty.rules]. A renamed "
            "or misspelled rule is silently unenforced -- ty warns and moves on. Fix the "
            f"spelling in pyproject.toml. Output:\n{output}"
        )
        assert "error[possibly-missing-attribute]" in output, (
            "A name bound only inside `try: from ... except ModuleNotFoundError` was read "
            "as a module attribute and this repo's rule table did not object at error "
            "level. The rule is off by default in ty, so it must be spelled "
            f'`possibly-missing-attribute = "error"` in [tool.ty.rules]. Output:\n{output}'
        )
        assert "use.py" in output, (
            f"the diagnostic did not point at the seeded violation site:\n{output}"
        )
        assert result.returncode != 0, (
            f"the diagnostic was reported but is not error-level, so CI would not fail:\n{output}"
        )

    def test_exhaustive_match_is_accepted(self, tmp_path: Path) -> None:
        """Guards against a gate that rejects everything (which would be equally useless)."""
        output, returncode = self._run_ty(
            tmp_path,
            """
from enum import Enum, auto
from typing import assert_never


class Kind(Enum):
    A = auto()
    B = auto()


def handle(k: Kind) -> str:
    match k:
        case Kind.A:
            return "a"
        case Kind.B:
            return "b"
        case _ as unreachable:
            assert_never(unreachable)
""",
        )
        assert returncode == 0, f"ty exited {returncode} on a complete match:\n{output}"
        assert "All checks passed" in output, (
            f"ty rejected a complete match, so the gate has false positives:\n{output}"
        )

    def test_untyped_ingress_into_complete_match_is_clean(self, tmp_path: Path) -> None:
        """Pins the gate's *boundary*: what an exhaustive `match` does NOT prove.

        This probe asserts CURRENT `ty` behavior, not desired behavior (plan 24 A5,
        decision 3). A complete `match` over a closed union is type-clean even when the
        value reaching it comes from an unannotated helper that actually returns the raw
        string ``"SERIAL"`` — the annotation on ``handle``'s parameter is trusted, the
        call site passes `Unknown`, and no rule fires (not even
        ``invalid-argument-type``, per plan 24 section 2.1). At runtime the same code
        raises ``AssertionError: Expected code to be unreachable, but got: 'SERIAL'``.

        This is the gradual-typing ingress hole that NO checker in the field closes
        (plan 24 section 2.5 measured ty, pyrefly, pyright, basedpyright, mypy, zuban) —
        it is why plan 24 A1 requires normalizing `param`-sourced values at the boundary
        before any `assert_never` downstream of them.

        Asserted clean (not xfail) deliberately: if a future `ty` release starts
        rejecting this, the failure lands HERE with this explanation attached, telling
        us the gate's boundary moved — an xfail that quietly flips to xpass would be a
        silent improvement nobody notices, and the boundary comments elsewhere in the
        tree would silently go stale.
        """
        output, returncode = self._run_ty(
            tmp_path,
            """
from enum import Enum, auto
from typing import assert_never


class Kind(Enum):
    A = auto()
    B = auto()


def get_kind():  # unannotated on purpose: this is the untyped ingress
    return "SERIAL"


def handle(kind: Kind) -> str:
    match kind:
        case Kind.A:
            return "a"
        case Kind.B:
            return "b"
        case _ as unreachable:
            assert_never(unreachable)


def caller() -> str:
    # At runtime: AssertionError("Expected code to be unreachable, but got: 'SERIAL'")
    return handle(get_kind())
""",
        )
        assert returncode == 0, (
            f"ty exited {returncode} on the untyped-ingress probe. Current ty accepts "
            f"this (the gradual-typing hole no checker closes, plan 24 section 2); a "
            f"nonzero exit means the ty in this environment has CHANGED behavior and "
            f"now checks values crossing an untyped boundary. That is an improvement, "
            f"not a bug — but it moves the gate's boundary, so re-run plan 24's probes, "
            f"update the boundary documentation, and re-pin this test to the new "
            f"reality. Output:\n{output}"
        )
        assert "All checks passed" in output, (
            f"ty exited 0 but did not report a clean pass on the untyped-ingress "
            f"probe, so it emitted some diagnostic without failing. Inspect whether "
            f"the ingress hole is now at least warned about. Output:\n{output}"
        )
