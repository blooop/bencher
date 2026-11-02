"""``pip install holobench`` is the light install; ``holobench[full]`` adds the heavy packages.

Two kinds of check. The static ones read ``pyproject.toml`` and keep it in step with
:data:`bencher.optional_deps.HEAVY_PACKAGES`, the pixi environments and the Read the
Docs environment. The wheel ones build the wheel, install it into a fresh venv with
plain ``pip install`` -- no extras -- and run the light features there for real, then
check that a heavy feature fails with the ``[full]`` hint. They download about 300 MB
on a cold pip cache, so they run only with ``BENCHER_TEST_WHEEL=1`` (``pixi run
test-wheel``, its own CI job).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

from bencher.optional_deps import FULL_INSTALL_COMMAND, HEAVY_PACKAGES

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
PROJECT = PYPROJECT["project"]

# Distribution name -> top-level import name, where they differ.
IMPORT_NAME = {"scikit-learn": "sklearn", "pyyaml": "yaml"}
# What `full` must install, spelled out here so that dropping a package from both
# pyproject's `full` and HEAVY_PACKAGES still fails a test.
EXPECTED_FULL = {"holoviews", "hvplot", "panel", "optuna", "plotly", "sklearn", "moviepy"}
# Declared by `full` only; the other HEAVY_PACKAGES come in with them.
TRANSITIVE_HEAVY = {"bokeh", "scipy", "tornado"}


def _import_name(requirement: str) -> str:
    name = re.split(r"[\[<>=!~ ;]", requirement, maxsplit=1)[0].lower()
    return IMPORT_NAME.get(name, name)


def test_the_full_extra_is_exactly_what_a_light_install_lacks() -> None:
    """HEAVY_PACKAGES turns a missing import into the `[full]` hint, and the tests block it.

    A package in `full` but not in HEAVY_PACKAGES fails with a bare ModuleNotFoundError
    on a light install; a light dependency in HEAVY_PACKAGES is reported missing when it
    is not.
    """
    full = {_import_name(r) for r in PROJECT["optional-dependencies"]["full"]}
    light = {_import_name(r) for r in PROJECT["dependencies"]}
    assert full == EXPECTED_FULL
    assert full == HEAVY_PACKAGES - TRANSITIVE_HEAVY
    assert not light & HEAVY_PACKAGES


def test_every_dev_environment_installs_the_full_extra() -> None:
    """The test suite and the examples need the plotting stack."""
    for name, env in PYPROJECT["tool"]["pixi"]["environments"].items():
        features = env["features"] if isinstance(env, dict) else env
        assert "full" in features, name


def test_the_docs_build_installs_the_full_extra() -> None:
    """Read the Docs installs the repo from docs/conda-environment.yml, then runs every example.

    A bare ``-e ../`` is now the light install, with no Panel or HoloViews, and the
    gallery fails to render.
    """
    env = (ROOT / "docs" / "conda-environment.yml").read_text(encoding="utf-8")
    editable = [line.strip() for line in env.splitlines() if line.strip().startswith("- -e ")]
    assert editable == ["- -e ../[full]"], editable


# ---------------------------------------------------------------- the built wheel

wheel_only = pytest.mark.skipif(
    os.environ.get("BENCHER_TEST_WHEEL") != "1",
    reason="downloads the light dependencies; run with BENCHER_TEST_WHEEL=1 (pixi run test-wheel)",
)

BENCH = textwrap.dedent(
    """
    import bencher as bn
    from gain import GAIN


    class Braking(bn.ParametrizedSweep):
        speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
        stop_distance = bn.ResultFloat(units="m", claim="< 0.7")

        def benchmark(self):
            self.stop_distance = GAIN * self.speed


    def example_braking(run_cfg=None):
        bench = bn.Bench("braking", Braking(), run_cfg=run_cfg)
        bench.plot_sweep("Stop distance", input_vars=["speed"], result_vars=["stop_distance"])
        return bench


    if __name__ == "__main__":
        bn.run(example_braking, repeats=3)
    """
)


@pytest.fixture(scope="module", name="light_venv")
def light_venv_fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A venv with the built wheel installed by plain ``pip install`` (no extras)."""
    root = tmp_path_factory.mktemp("light")
    dist = root / "dist"
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "-q", "--no-deps", "-w", str(dist), str(ROOT)],
        check=True,
    )
    (wheel,) = dist.glob("holobench-*.whl")
    venv = root / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    subprocess.run([venv / "bin" / "pip", "install", "-q", str(wheel)], check=True)
    return venv


def _run(venv: Path, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PATH": f"{venv / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "BENCHER_NO_SHOW": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop("PYTHONPATH", None)
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, check=False)


@wheel_only
def test_the_light_install_has_no_heavy_package(light_venv: Path, tmp_path: Path) -> None:
    probe = (
        "import importlib.util, json; "
        f"print(json.dumps(sorted(m for m in {sorted(HEAVY_PACKAGES | EXPECTED_FULL)!r} "
        "if importlib.util.find_spec(m))))"
    )
    proc = _run(light_venv, [str(light_venv / "bin" / "python"), "-c", probe], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == []


@wheel_only
def test_the_scorecard_renders_on_the_light_install(light_venv: Path, tmp_path: Path) -> None:
    probe = (
        "import json, sys\n"
        "from bencher.example.example_scorecard import example_scorecard\n"
        f"page = example_scorecard({str(tmp_path)!r})\n"
        "heavy = ('numpy', 'pandas', 'xarray', 'param', 'holoviews', 'panel', 'bokeh')\n"
        "print(json.dumps([page.stat().st_size, [m for m in heavy if m in sys.modules]]))\n"
    )
    proc = _run(light_venv, [str(light_venv / "bin" / "python"), "-c", probe], tmp_path)
    assert proc.returncode == 0, proc.stderr
    size, loaded = json.loads(proc.stdout.strip().splitlines()[-1])
    assert size > 0
    assert loaded == []


@wheel_only
def test_ab_and_compare_work_and_a_heavy_feature_gives_the_full_hint(
    light_venv: Path, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "light@example.test"],
        ["config", "user.name", "light"],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True)  # noqa: S607 - git from PATH
    (repo / "bench.py").write_text(BENCH, encoding="utf-8")
    (repo / "gain.py").write_text("GAIN = 0.3\n", encoding="utf-8")
    (repo / ".gitignore").write_text("cachedir/\nbencher-ab/\n*.pkl\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)  # noqa: S607
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)  # noqa: S607
    (repo / "gain.py").write_text("GAIN = 0.2\n", encoding="utf-8")

    ab = _run(light_venv, ["bencher", "ab", "--base", "HEAD", "--", "python", "bench.py"], repo)
    assert ab.returncode == 0, ab.stderr
    metric = json.loads((repo / "bencher-ab" / "comparison.json").read_text())["metrics"][0]
    assert metric["verdict"] == "improved"

    pkls = [str(repo / "bencher-ab" / f"{side}.pkl") for side in ("base", "candidate")]
    compare = _run(light_venv, ["bencher", "compare", *pkls, "--report", "report"], repo)
    assert compare.returncode == 0, compare.stderr
    assert (repo / "report" / "evidence.md").exists()

    # An HTML report needs panel: the CLI says how to get it.
    render = _run(light_venv, ["bencher", pkls[1], "html"], repo)
    assert render.returncode != 0
    assert FULL_INSTALL_COMMAND in render.stderr, render.stderr

    # In Python, the first use of a heavy package raises FullInstallRequiredError.
    probe = (
        "from bencher.optional_deps import FullInstallRequiredError, hv\n"
        "try:\n"
        "    hv.Curve\n"
        "except FullInstallRequiredError as exc:\n"
        "    print(exc)\n"
    )
    proc = _run(light_venv, [str(light_venv / "bin" / "python"), "-c", probe], repo)
    assert proc.returncode == 0, proc.stderr
    assert FULL_INSTALL_COMMAND in proc.stdout, proc.stdout
