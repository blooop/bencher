"""``bencher/__init__.py`` loads its public names lazily, so light entry points stay light.

``import bencher.scorecard`` runs ``bencher/__init__.py`` first. When that file imported
every public name eagerly, a consumer that only renders scorecards (summary JSON in,
HTML out) loaded numpy, pandas, xarray, param, holoviews, panel and bokeh as well. The
probes run in a fresh subprocess, because the test session itself has imported all of
them by the time this file runs.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

import bencher

REPO = Path(__file__).resolve().parents[1]
INIT = REPO / "bencher" / "__init__.py"

# Not one of these is needed to read summary JSON and render a scorecard.
HEAVY = ("numpy", "pandas", "xarray", "param", "holoviews", "panel", "bokeh")

PROBE = """
import json, sys
import {module}  # noqa: F401
print(json.dumps(sorted(m for m in {heavy!r} if m in sys.modules)))
"""


@pytest.mark.parametrize("module", ["bencher", "bencher.scorecard"])
def test_light_import_loads_no_heavy_package(module: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-c", PROBE.format(module=module, heavy=HEAVY)],
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = json.loads(proc.stdout)
    assert not leaked, (
        f"`import {module}` now loads {leaked}. Something on its import path gained a "
        "module-scope import of the numerical or plotting stack: either an eager import "
        "in bencher/__init__.py, or a bencher.scorecard dependency that imports "
        "bencher.report_export / bencher.complete_report instead of the stdlib-only "
        "bencher.verdict / bencher.report_inventory."
    )


def _type_checking_names() -> dict[str, str]:
    """Name -> relative module for every import in the ``if TYPE_CHECKING:`` block."""
    tree = ast.parse(INIT.read_text(encoding="utf-8"))
    block = next(
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Attribute)
        and node.test.attr == "TYPE_CHECKING"
    )
    names: dict[str, str] = {}
    for node in block.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert alias.asname == alias.name, f"{alias.name} needs `as {alias.name}`"
                names[alias.name] = "." * node.level + (node.module or "")
    return names


def test_type_checking_block_matches_the_runtime_exports() -> None:
    """The static names (for ty and IDEs) and the lazy runtime map must agree."""
    static = _type_checking_names()
    runtime = dict(bencher._NAME_TO_MODULE)
    runtime.update(dict.fromkeys(bencher._RERUN_EXPORTS, ".utils_rerun"))
    assert static == runtime
    assert set(bencher.__all__) == set(runtime) | set(bencher._ALIASES)


def test_every_public_name_resolves() -> None:
    for name in bencher.__all__:
        assert getattr(bencher, name) is not None, name
    assert bencher.VideoResult is bencher.PaneResult
    assert set(bencher.__all__) <= set(dir(bencher))


def test_unknown_name_raises_attribute_error() -> None:
    assert not hasattr(bencher, "no_such_name")
    with pytest.raises(AttributeError, match="no_such_name"):
        _ = bencher.no_such_name


def test_shadowed_names_are_every_export_that_matches_a_submodule() -> None:
    submodules = {p.stem for p in (REPO / "bencher").glob("*.py")} | {
        p.name for p in (REPO / "bencher").iterdir() if (p / "__init__.py").exists()
    }
    assert set(bencher.__all__) & submodules == bencher._SHADOWED_BY_SUBMODULE


def test_importing_a_shadowing_submodule_keeps_the_function() -> None:
    """``import bencher.run`` must not replace ``bencher.run`` the function with the module."""
    probe = (
        "import types, bencher.run, bencher.sprt, bencher\n"
        "assert callable(bencher.run) and not isinstance(bencher.run, types.ModuleType)\n"
        "assert callable(bencher.sprt) and not isinstance(bencher.sprt, types.ModuleType)\n"
    )
    subprocess.run([sys.executable, "-c", probe], check=True)
    assert not isinstance(bencher.run, types.ModuleType)
    assert not isinstance(bencher.sprt, types.ModuleType)


def test_verdict_direction_constants_match_optdir() -> None:
    from bencher.variables.results import OptDir
    from bencher.verdict import _MAXIMIZE, _MINIMIZE

    assert OptDir.minimize.value == _MINIMIZE
    assert OptDir.maximize.value == _MAXIMIZE


def test_moved_helpers_are_still_importable_from_their_old_modules() -> None:
    from bencher import complete_report, report_export, report_inventory, verdict

    assert complete_report.verify_report is report_inventory.verify_report
    assert complete_report.safe_path is report_inventory.safe_path
    assert complete_report.file_digest is report_inventory.file_digest
    assert report_export._verdict is verdict._verdict
