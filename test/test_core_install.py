"""The evidence tools work on a ``holobench-core`` install, without the plotting stack.

``holobench-core`` ships the ``bencher`` package with only the light dependencies (see
``pyproject.toml``; ``holobench`` adds the rest). A repo that only wants to *gate* a
change -- run a sweep, check its claims, compare two runs, ``bencher ab`` -- gets that
without Panel, Bokeh, HoloViews, hvplot, Optuna, moviepy, scikit-learn or plotly.

The pixi environment has all of them installed, so each test runs its probe in a
subprocess whose ``sitecustomize`` puts a ``sys.meta_path`` finder in front of the real
ones: importing a package in ``HEAVY_PACKAGES`` there fails the way it does when the
package is absent. ``sitecustomize`` rather than a ``-c`` prelude because ``bencher ab``
starts the bench in processes of its own, and those must be core-only too.
"""

from __future__ import annotations

import json
import os
import pickle
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import holoviews as hv
import pytest

from bencher.optional_deps import HEAVY_PACKAGES

if TYPE_CHECKING:
    from pathlib import Path

HEAVY = tuple(sorted(HEAVY_PACKAGES))

SITECUSTOMIZE = f"""
import sys

HEAVY = {HEAVY!r}


class _BlockHeavy:
    def find_spec(self, name, path=None, target=None):
        if name.partition(".")[0] in HEAVY:
            raise ModuleNotFoundError(f"No module named {{name!r}}", name=name)
        return None


sys.meta_path.insert(0, _BlockHeavy())
"""

# Same shape as the ab-demo: the claim fails on the base side and holds on the
# candidate. Run through bn.run, the entry point a bench script normally uses.
BENCH = """
import bencher as bn
from gain import GAIN


class Braking(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    stop_distance = bn.ResultFloat(units="m", claim="< 0.7")

    def benchmark(self):
        self.stop_distance = GAIN * self.speed


def example_braking(run_cfg=None):
    bench = bn.Bench("core_braking", Braking(), run_cfg=run_cfg)
    bench.plot_sweep("Stop distance", input_vars=["speed"], result_vars=["stop_distance"])
    return bench


if __name__ == "__main__":
    bn.run(example_braking, repeats=2)
"""


@pytest.fixture(name="core_env")
def core_only_env(tmp_path) -> dict[str, str]:
    """Environment for a child process that cannot import the heavy packages."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(site), env.get("PYTHONPATH")) if p)
    env["BENCHER_NO_SHOW"] = "1"
    # gain.py is rewritten to a file of the same size within the second, which a
    # cached .pyc (keyed by mtime and size) would answer with the old value.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


# The `bencher` console script, spelled so it runs this interpreter.
BENCHER_CLI = (sys.executable, "-m", "bencher.render")


def _run(args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)  # noqa: S607 - git from PATH


def test_the_blocker_works(tmp_path, core_env):
    """The probe environment really is core-only; otherwise every test below is vacuous."""
    proc = _run([sys.executable, "-c", "import holoviews"], tmp_path, core_env)
    assert proc.returncode != 0
    assert "No module named 'holoviews'" in proc.stderr


def test_import_bencher_loads_no_heavy_package(tmp_path, core_env):
    probe = "import bencher, sys; print(sorted(m for m in sys.modules if m.startswith('bencher')))"
    proc = _run([sys.executable, "-c", probe], tmp_path, core_env)
    assert proc.returncode == 0, proc.stderr


def test_run_compare_and_ab_work_without_the_plotting_stack(tmp_path, core_env):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "core@example.test")
    _git(repo, "config", "user.name", "core")
    (repo / "bench.py").write_text(BENCH, encoding="utf-8")
    (repo / "gain.py").write_text("GAIN = 0.3\n", encoding="utf-8")
    (repo / ".gitignore").write_text("cachedir/\nbencher-ab/\n*.pkl\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")

    # bn.run saves the result where a launcher asks for it.
    base_pkl = repo / "base.pkl"
    proc = _run(
        [sys.executable, "bench.py"],
        repo,
        {**core_env, "BENCHER_RESULT_PATH": str(base_pkl), "BENCHER_NO_CACHE": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    assert base_pkl.exists()

    (repo / "gain.py").write_text("GAIN = 0.2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "lower gain")
    cand_pkl = repo / "cand.pkl"
    proc = _run(
        [sys.executable, "bench.py"],
        repo,
        {**core_env, "BENCHER_RESULT_PATH": str(cand_pkl), "BENCHER_NO_CACHE": "1"},
    )
    assert proc.returncode == 0, proc.stderr

    out = tmp_path / "compare"
    proc = _run(
        [
            *BENCHER_CLI,
            "compare",
            str(base_pkl),
            str(cand_pkl),
            "--json",
            str(out / "cmp.json"),
            "--markdown",
            str(out / "cmp.md"),
            "--png",
            str(out / "png"),
        ],
        repo,
        core_env,
    )
    assert proc.returncode == 0, proc.stderr
    metric = json.loads((out / "cmp.json").read_text(encoding="utf-8"))["metrics"][0]
    assert metric["baseline_value"] == pytest.approx(0.6)
    assert metric["current_value"] == pytest.approx(0.4)
    assert "improved" in (out / "cmp.md").read_text(encoding="utf-8")
    assert (out / "png" / "stop_distance.png").exists()

    proc = _run(
        [*BENCHER_CLI, "ab", "--base", "HEAD~1", "--", sys.executable, "bench.py"],
        repo,
        core_env,
    )
    assert proc.returncode == 0, proc.stderr
    ab = repo / "bencher-ab"
    metric = json.loads((ab / "comparison.json").read_text(encoding="utf-8"))["metrics"][0]
    assert metric["verdict"] == "improved"
    assert metric["claim"]["baseline"]["holds"] is False
    assert metric["claim"]["candidate"]["holds"] is True
    assert "1 improved" in (ab / "evidence.md").read_text(encoding="utf-8")
    assert (ab / "stop_distance.png").exists()


HEAVY_FEATURE_PROBE = textwrap.dedent(
    """
    import bencher as bn


    class Cfg(bn.ParametrizedSweep):
        x = bn.FloatSweep(default=0, bounds=(0, 1), samples=2)
        y = bn.ResultFloat()

        def benchmark(self):
            self.y = self.x


    bench = bn.Bench("core_heavy", Cfg())
    res = bench.collect(input_vars=["x"], result_vars=["y"])
    try:
        {call}
    except ImportError as exc:
        print("IMPORT-ERROR:", exc)
    """
)


REGRESSION = "bn.RegressionResult('y', 'percentage', True, 2.0, 1.0, 100.0, 5.0, 'minimize', '')"


@pytest.mark.parametrize(
    "call",
    [
        "res.to_auto_plots()",  # plotting a report
        "bench.report.show()",  # the panel server
        "bench.optimize(n_trials=1)",  # optuna
        "vw = bn.VideoWriter(); vw.append(__import__('numpy').zeros((2, 2, 3))); vw.write()",
        f"{REGRESSION}.render_png()",  # holoviews draws the regression diagnostic
        f"{REGRESSION}.render_overlay()",
    ],
)
def test_a_heavy_feature_says_how_to_get_it(tmp_path, core_env, call):
    proc = _run([sys.executable, "-c", HEAVY_FEATURE_PROBE.format(call=call)], tmp_path, core_env)
    assert proc.returncode == 0, proc.stderr
    assert "IMPORT-ERROR:" in proc.stdout, proc.stdout
    assert "pip install holobench" in proc.stdout, proc.stdout


def test_loading_a_result_that_holds_a_plot_says_how_to_get_it(tmp_path, core_env):
    """A full install can save a result whose dataset holds HoloViews objects."""
    pkl = tmp_path / "plot.pkl"
    pkl.write_bytes(pickle.dumps(hv.Curve([(0, 1), (1, 2)])))
    probe = f"""
import bencher as bn
try:
    bn.load_result({str(pkl)!r})
except ImportError as exc:
    print("IMPORT-ERROR:", exc)
"""
    proc = _run([sys.executable, "-c", probe], tmp_path, core_env)
    assert proc.returncode == 0, proc.stderr
    assert "pip install holobench" in proc.stdout, proc.stdout
