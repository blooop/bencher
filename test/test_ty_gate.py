"""Meta-tests for the ``ty`` type-check gate itself.

The gate is configuration, so it can be weakened by a one-line edit to
``pyproject.toml`` without any test noticing. Before plan 23 P1 the gate ignored 21
rules and was effectively a no-op that still reported "All checks passed!". These tests
assert the *properties that make it a gate*, so that regression cannot happen silently
again.

See ``plans/23-constructive-data-modeling.md`` sections D1/D2 and P1.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Rules that must never be silenced globally, with the reason each one matters.
MUST_NOT_BE_IGNORED = {
    # The exhaustiveness mechanism. Silencing this turns every `assert_never` arm from a
    # compile-time proof into a runtime assertion, with no other signal.
    "type-assertion-failure": "exhaustive `match` checking (plan 23 D2)",
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


class TestGateConfiguration:
    """Properties of the checked-in ty configuration."""

    @pytest.mark.parametrize("rule", sorted(MUST_NOT_BE_IGNORED))
    def test_rule_not_globally_ignored(self, rule: str) -> None:
        setting = _global_rules().get(rule)
        assert setting != "ignore", (
            f"`{rule}` has been added back to [tool.ty.rules] as 'ignore'. "
            f"It guards {MUST_NOT_BE_IGNORED[rule]}. Silencing it globally makes the "
            f"gate pass while the property it protects is unenforced. Scope the "
            f"suppression to the offending file with `# ty: ignore[{rule}]`, or relax "
            f"it for a path in [[tool.ty.overrides]], rather than disabling it here."
        )

    def test_ty_task_resolves_the_environment(self) -> None:
        """Without ``--python`` ty resolves no third-party import.

        param, panel, numpy and xarray all read as unresolved, which silently degrades
        every rule that needs a third-party type. The task must therefore point ty at
        the active environment.
        """
        task = _load_ty_task()
        assert "--python" in task, (
            "the `ty` pixi task no longer passes --python, so ty will type-check with "
            "no third-party packages resolved. Every rule that depends on knowing an "
            'external type degrades silently. Restore --python "$CONDA_PREFIX".'
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


@pytest.mark.skipif(shutil.which("ty") is None, reason="ty binary not on PATH")
class TestGateActuallyFires:
    """End-to-end proof that the configured gate rejects real violations.

    Configuration assertions above can pass while the checker itself is misconfigured,
    so these run ty against seeded violations. They deliberately use a *minimal
    standalone* config rather than the repo's: under the repo config the Tier-C rules
    are ignored and a seeded probe passes, which is exactly the trap that made the
    original measurements for this plan wrong.
    """

    @staticmethod
    def _run_ty(tmp_path: Path, source: str) -> str:
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
        return result.stdout + result.stderr

    def test_non_exhaustive_match_is_rejected(self, tmp_path: Path) -> None:
        output = self._run_ty(
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
        assert "type-assertion-failure" in output, (
            "ty did not reject a match missing one enum member. The exhaustiveness "
            f"mechanism plan 23 D2 relies on is not working. Output:\n{output}"
        )
        assert "Kind.C" in output, (
            "ty flagged the incomplete match but did not name the missing variant, "
            f"which is what makes the diagnostic actionable. Output:\n{output}"
        )

    def test_exhaustive_match_is_accepted(self, tmp_path: Path) -> None:
        """Guards against a gate that rejects everything (which would be equally useless)."""
        output = self._run_ty(
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
        assert "All checks passed" in output, (
            f"ty rejected a complete match, so the gate has false positives:\n{output}"
        )
