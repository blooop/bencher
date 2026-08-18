"""Meta-tests for the ``ty`` type-check gate itself.

The gate is configuration, so it can be weakened by a one-line edit to
``pyproject.toml`` without any test noticing. These tests assert the *properties that
make it a gate* -- including, in :class:`TestEffectiveGateConfig`, by running the real
command on a seeded violation rather than reading config.

See ``plans/23-constructive-data-modeling.md`` sections D1/D2 for the tier design.
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
    # Silencing this turns every `assert_never` arm from a compile-time proof into a
    # runtime assertion, with no other signal.
    "type-assertion-failure": "exhaustive `match` checking (plan 23 D2)",
    # Tier B. Each was paid for by fixing a representation rather than by annotating, so
    # re-ignoring one re-permits the shape that produced the diagnostics.
    "invalid-return-type": "the ReduceType exhaustiveness proof (plan 23 P12)",
    "not-iterable": "optional-list fields that mean `[]` (plan 23 P12b)",
    "no-matching-overload": "Tier B (plan 23 P12b)",
    "unsupported-operator": "operations on optionals, incl. the registry `exc` shadow "
    "(plan 23 P12b)",
    "possibly-missing-attribute": "the total public surface for optional extras (plan 23 P12b)",
    # Tier A. Each sits at <=6 diagnostics, so a reappearance here is a regression rather
    # than a pragmatic concession.
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


# Rules ty ships DISABLED by default: absent from [tool.ty.rules] means OFF, so
# `!= "ignore"` proves nothing and the rule must be spelled out as "error".
#
# To add one, first verify it: write a file violating the rule, run `ty check` under a
# config that does not mention it, and see whether anything is reported. Re-run this file
# whenever the ty pin moves -- a renamed rule is silently unenforced (ty warns
# `unknown-rule` and continues).
OFF_BY_DEFAULT_IN_TY = {
    "possibly-missing-attribute": "verified with a standalone probe",
}


class TestGateConfiguration:
    """Properties of the checked-in ty configuration."""

    @pytest.mark.parametrize("rule", sorted(OFF_BY_DEFAULT_IN_TY))
    def test_off_by_default_rule_is_explicitly_enabled(self, rule: str) -> None:
        setting = _global_rules().get(rule)
        assert setting == "error", (
            f"`{rule}` is off by default in ty ({OFF_BY_DEFAULT_IN_TY[rule]}), so it must "
            f"be set to 'error' in [tool.ty.rules] to be enforced -- currently {setting!r}. "
            f"Leaving it out of the ignore list is not enough: the gate reports 'All checks "
            f"passed!' with the rule switched off."
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
        as effectively, and asserting only on ``[tool.ty.rules]`` would not notice.

        Complements :class:`TestEffectiveGateConfig`: that probe covers more routes but
        only reports *that* first-party code went unchecked, while this one names the
        offending pattern and rule, and needs no ty binary.
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
    """The repo's own ty invocation, with ``$CONDA_PREFIX`` resolved to this interpreter.

    Read from the pixi task so the probe follows the gate CI runs, rather than a
    hardcoded copy that can drift from it.
    """
    argv = shlex.split(_load_ty_task())
    return [sys.prefix if arg == "$CONDA_PREFIX" else arg for arg in argv]


# Seeded-violation sites for the effective-config probe below. Removed in the fixture's
# teardown; neither is importable from `bencher/__init__.py`.
_PKG_PROBE = REPO_ROOT / "bencher" / "_ty_gate_probe.py"
_NB_PROBE = REPO_ROOT / "docs" / "reference" / "_ty_gate_probe_nb" / "probe.ipynb"

# `invalid-parameter-default` is Tier A and error-by-default in ty, so it fires without a
# rule-table entry. If the gate does not report this, it is not reading the file at all.
_TIER_A_VIOLATION = 'def probe(x: int = "not an int") -> int:\n    return x\n'
_TIER_A_VIOLATION_NB = (
    '{"cells":[{"cell_type":"code","execution_count":null,"metadata":{},"outputs":[],'
    '"source":["def probe(x: int = \\"not an int\\") -> int:\\n","    return x\\n"]}],'
    '"metadata":{},"nbformat":4,"nbformat_minor":5}'
)


@pytest.fixture(scope="module")
def seeded_repo_gate_run() -> Iterator[tuple[str, int]]:
    """Run the repo's real ty gate over a tree seeded with two known violations.

    One run (~5s) shared by both assertions below. They test opposite halves of the same
    effective config — package code must be checked, generated notebooks must not gate —
    so a single invocation is cheaper, and stricter than two runs that could disagree
    about the state of the tree.
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
        # Unconditional: a leftover probe under `bencher/` fails the real gate for every
        # later run, including the next `pixi run ty`.
        _PKG_PROBE.unlink(missing_ok=True)
        _NB_PROBE.unlink(missing_ok=True)
        for path in reversed(created_dirs):
            path.rmdir()


@pytest.mark.skipif(shutil.which("ty") is None, reason="ty binary not on PATH")
class TestEffectiveGateConfig:
    """Does the gate, *as configured*, actually check first-party package code?

    Reading config cannot answer that. `[tool.ty.rules]` is not the only lever: the gate
    can be switched off for `bencher/` via a broad `[[tool.ty.overrides]]` include, an
    exclude-only override block, `[tool.ty.src].exclude`, or a `.gitignore`/`.ignore`
    entry (the task runs `--respect-ignore-files`). The last two suppress a seeded
    diagnostic completely, and none of the four is visible to
    `test_rule_not_ignored_for_the_package_via_overrides`, which inspects include patterns.

    Running the real command in the real repo root closes all four at once, by asking the
    only question that matters — is a violation in `bencher/` reported? — instead of
    enumerating the ways the answer could be no.
    """

    def test_gate_reports_a_tier_a_violation_in_first_party_code(
        self,
        seeded_repo_gate_run: tuple[str, int],  # pylint: disable=redefined-outer-name
    ) -> None:
        output, returncode = seeded_repo_gate_run
        assert "_ty_gate_probe.py" in output, (
            "first-party package code is not being type-checked: a seeded "
            "`invalid-parameter-default` in bencher/_ty_gate_probe.py went unreported. "
            "Something excludes it -- a broad `[[tool.ty.overrides]]` include, an "
            "exclude-only override block, `[tool.ty.src].exclude`, or a "
            f"`.gitignore`/`.ignore` entry. Command: {_repo_ty_argv()}\nOutput:\n{output}"
        )
        assert "invalid-parameter-default" in output, (
            "the seeded file was reported, but not for the rule seeded in it; "
            f"`invalid-parameter-default` may be renamed or downgraded:\n{output}"
        )
        assert returncode != 0, (
            f"the seeded violation was reported but ty exited 0, so CI would pass:\n{output}"
        )

    def test_generated_notebooks_do_not_gate_the_type_check(
        self,
        seeded_repo_gate_run: tuple[str, int],  # pylint: disable=redefined-outer-name
    ) -> None:
        """`pixi run ty` must not depend on whether docs have been built.

        ty type-checks `.ipynb`, `generate-docs` writes notebooks under
        `docs/reference/<section>/`, and only `docs/reference/meta/` is gitignored — so
        without an exclusion the gate's answer changes after a docs build. CI escapes it
        only by task ordering (`ty` before `generate-examples`), which nothing enforces.

        Asserts that notebooks are excluded, not *which* mechanism does it, so the config
        is free to change. Note ty does not read `.tyignore`, so that is not an option.
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

    These run ty against seeded violations under a *minimal standalone* config, so they
    verify the mechanism plan 23 D2 depends on rather than this repo's gate. The standalone
    config is deliberate: under the repo config the Tier-C rules are ignored, so a seeded
    Tier-C probe passes and measures nothing.

    The exception is ``test_repo_rule_table_actually_fires_on_a_seeded_violation``, which
    reconstructs this repo's ``[tool.ty.rules]``. Repo-level properties otherwise belong to
    TestGateConfiguration (reads config) and TestEffectiveGateConfig (runs the real gate).
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

        The sibling probes use a standalone config, which leaves the checked-in rule table
        unchecked: config assertions cannot catch a rule whose default is not what you
        assumed. This reconstructs the table verbatim and asserts the rule bites.
        """
        rules = _global_rules()
        # The round-trip below re-quotes each value as a string. A non-string would still
        # serialise into valid TOML (`x = "True"`), so the probe would silently check a
        # rule table that is not the repo's.
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
        # ty renames rules (unused-ignore-comment -> unused-type-ignore-comment), so this
        # is a live path.
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

        A complete `match` over a closed union is type-clean even when the value reaching
        it comes from an unannotated helper returning the raw string ``"SERIAL"``: the
        parameter annotation is trusted, the call site passes `Unknown`, and no rule fires
        (not even ``invalid-argument-type``). At runtime the same code raises
        ``AssertionError: Expected code to be unreachable, but got: 'SERIAL'``.

        No checker in the field closes this gradual-typing ingress hole (plan 24 §2.5), so
        plan 24 A1 requires normalizing `param`-sourced values at the boundary before any
        `assert_never` downstream of them.

        Asserts CURRENT ty behaviour, not desired behaviour, and clean rather than xfail:
        if a release starts rejecting this, the failure lands here with the explanation
        attached instead of an xpass nobody notices.
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
