"""``bencher ab`` against a throwaway git repo whose bench changes between commits."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

import bencher as bn
from bencher.launch_env import NO_CACHE_ENV, NO_SHOW_ENV, RESULT_PATH_ENV

if TYPE_CHECKING:
    from pathlib import Path

# The bench caches both results and samples, the way a long sweep often does. The
# cache is keyed by inputs, not code, so without isolation the candidate would be
# answered from the cache the base revision's code filled.
BENCH = """
import bencher as bn
from gain import GAIN


class Braking(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    stop_distance = bn.ResultFloat(units="m", claim="< 0.7")

    def benchmark(self):
        self.stop_distance = GAIN * self.speed


bench = bn.Bench("ab_braking", Braking())
bench.collect(
    input_vars=["speed"],
    result_vars=["stop_distance"],
    run_cfg=bn.BenchRunCfg(repeats=2, cache_results=True, cache_samples=True),
)
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],  # noqa: S607 - git from PATH
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _bench(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "bench.py"], cwd=repo, check=True, capture_output=True, text=True
    )


def _ab(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "bencher.render", "ab", *args, "--", sys.executable, "bench.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(name="repo")
def braking_repo(tmp_path) -> Path:
    """`main` has GAIN = 0.3, and its cache is warm in the working tree."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "ab@example.test")
    _git(repo, "config", "user.name", "ab")
    (repo / "bench.py").write_text(BENCH, encoding="utf-8")
    (repo / "gain.py").write_text("GAIN = 0.3\n", encoding="utf-8")
    (repo / ".gitignore").write_text("cachedir/\nbencher-ab/\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _bench(repo)  # fills ./cachedir with GAIN = 0.3 samples
    _git(repo, "checkout", "-q", "-b", "feature")
    return repo


def _metric(out: Path) -> dict:
    return json.loads((out / "comparison.json").read_text(encoding="utf-8"))["metrics"][0]


def test_ab_measures_each_side_with_its_own_code(repo):
    (repo / "gain.py").write_text("GAIN = 0.25\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "lower gain")
    (repo / "gain.py").write_text("GAIN = 0.2\n", encoding="utf-8")  # uncommitted

    proc = _ab(repo)
    assert proc.returncode == 0, proc.stderr

    out = repo / "bencher-ab"
    metric = _metric(out)
    # Base is main (0.3); the candidate is the working tree (0.2), not the commit
    # (0.25) and not the warm cache (0.3).
    assert metric["baseline_value"] == pytest.approx(0.6)
    assert metric["current_value"] == pytest.approx(0.4)
    assert metric["verdict"] == "improved"
    assert metric["claim"]["baseline"]["holds"] is False
    assert metric["claim"]["candidate"]["holds"] is True

    head = _git(repo, "rev-parse", "--short", "HEAD")
    main = _git(repo, "rev-parse", "--short", "main")
    cmp = json.loads((out / "comparison.json").read_text(encoding="utf-8"))
    assert cmp["baseline"]["provenance"]["source_revision"] == main
    assert cmp["candidate"]["provenance"]["source_revision"] == f"{head}+dirty"
    assert cmp["candidate"]["provenance"]["display_label"] == f"candidate {head}+dirty"

    for name in ("base.pkl", "candidate.pkl", "evidence.md", "stop_distance.png"):
        assert (out / name).exists(), name
        assert str(out / name) in proc.stdout
    assert "xychart-beta" in (out / "evidence.md").read_text(encoding="utf-8")
    # The base worktree is gone.
    assert _git(repo, "worktree", "list").count("\n") == 0


def test_ab_reports_which_side_failed_and_keeps_its_output(repo, tmp_path):
    (repo / "bench.py").write_text(BENCH + "\nraise SystemExit('broke the bench')\n")
    out = tmp_path / "evidence"

    proc = _ab(repo, "--out", str(out))

    assert proc.returncode == 1
    assert "candidate run exited with status 1" in proc.stderr
    assert "broke the bench" in (out / "candidate.log").read_text(encoding="utf-8")
    assert (out / "base.pkl").exists()
    assert _git(repo, "worktree", "list").count("\n") == 0


def test_ab_explicit_base_and_image_url(repo):
    (repo / "gain.py").write_text("GAIN = 0.2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "lower gain")
    proc = _ab(repo, "--base", "HEAD", "--png-url-base", "https://example.test/x")
    assert proc.returncode == 0, proc.stderr
    # Base and candidate are the same commit with a clean tree: nothing moved.
    assert _metric(repo / "bencher-ab")["verdict"] == "unchanged"


def test_ab_without_a_base_says_how_to_name_one(tmp_path):
    repo = tmp_path / "lonely"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "trunk")
    _git(
        repo,
        "-c",
        "user.email=a@b",
        "-c",
        "user.name=a",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "x",
    )
    proc = _ab(repo)
    assert proc.returncode == 2
    assert "--base" in proc.stderr


def test_a_result_saved_by_a_script_loads_in_another_process(repo, tmp_path):
    # The sweep class lives in the script's __main__, which the loading process
    # does not have; the data, result vars and claim must still load.
    path = tmp_path / "script.pkl"
    subprocess.run(
        [sys.executable, "bench.py"],
        cwd=repo,
        env={**os.environ, RESULT_PATH_ENV: str(path)},
        check=True,
        capture_output=True,
    )
    res = bn.load_result(path)
    assert res.ds["stop_distance"].values.max() == pytest.approx(0.9)
    assert str(res.bench_cfg.result_vars[0].claim) == "< 0.7"


ENUM_BENCH = """
from enum import auto

from strenum import StrEnum

import bencher as bn


class Mode(StrEnum):
    fast = auto()
    slow = auto()


class Timed(bn.ParametrizedSweep):
    mode = bn.EnumSweep(Mode)
    t = bn.ResultFloat(units="s")

    def benchmark(self):
        self.t = 1.0 if self.mode == Mode.fast else 2.0


bn.Bench("ab_enum", Timed()).collect(input_vars=["mode"], result_vars=["t"])
"""


def test_a_result_whose_script_defines_an_enum_loads_in_another_process(tmp_path):
    # An enum member pickles as a call of its class with the value, and the class
    # is in the script's __main__ like the sweep class.
    (tmp_path / "enum_bench.py").write_text(ENUM_BENCH, encoding="utf-8")
    path = tmp_path / "enum.pkl"
    subprocess.run(
        [sys.executable, "enum_bench.py"],
        cwd=tmp_path,
        env={**os.environ, RESULT_PATH_ENV: str(path), NO_CACHE_ENV: "1"},
        check=True,
        capture_output=True,
    )
    res = bn.load_result(path)
    assert res.ds["t"].values.ravel().tolist() == [1.0, 2.0]


class Counted(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0.0, bounds=(0.0, 1.0), samples=2)
    y = bn.ResultFloat()

    calls = 0

    def benchmark(self):
        type(self).calls += 1
        self.y = self.x


def _collect_counted(name: str):
    bench = bn.Bench(name, Counted())
    bench.collect(
        input_vars=["x"],
        result_vars=["y"],
        run_cfg=bn.BenchRunCfg(cache_results=True, cache_samples=True),
    )
    bench.close()


def test_result_path_env_saves_the_collected_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "result.pkl"
    monkeypatch.setenv(RESULT_PATH_ENV, str(path))
    _collect_counted("env_saved")
    assert bn.load_result(path).ds["y"].values.ravel().tolist() == [0.0, 1.0]


def test_no_cache_env_measures_again_despite_cache_flags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Counted.calls = 0
    _collect_counted("env_uncached")
    _collect_counted("env_uncached")
    assert Counted.calls == 2  # the second sweep was served from the cache

    monkeypatch.setenv(NO_CACHE_ENV, "1")
    _collect_counted("env_uncached")
    assert Counted.calls == 4


def test_no_show_env_keeps_bn_run_from_serving_the_report(tmp_path, monkeypatch):
    # A live report server keeps a non-interactive process alive at exit, so a
    # launcher that waits for the command would wait forever.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(NO_SHOW_ENV, "1")

    def refuse(*_args, **_kwargs):
        raise AssertionError("the report was shown")

    monkeypatch.setattr(bn.BenchReport, "show", refuse)

    def example_counted(run_cfg=None):
        bench = bn.Bench("env_no_show", Counted(), run_cfg=run_cfg)
        bench.plot_sweep(input_vars=["x"], result_vars=["y"])
        return bench

    bn.run(example_counted)
