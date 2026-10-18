"""``bencher ab`` against a throwaway git repo whose bench changes between commits."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from types import SimpleNamespace
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

    for name in ("base.pkl", "candidate.pkl", "evidence.md"):
        assert (out / name).exists(), name
        assert str(out / name) in proc.stdout
    # Evidence is text only: PNGs are opt-in with --png-dir.
    assert list(out.glob("*.png")) == []
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
    assert "text only" in proc.stderr
    assert "example.test" not in (repo / "bencher-ab" / "evidence.md").read_text(encoding="utf-8")
    # Base and candidate are the same commit with a clean tree: nothing moved.
    assert _metric(repo / "bencher-ab")["verdict"] == "unchanged"


def test_ab_judges_a_claim_on_a_metric_the_change_adds(repo):
    # The change adds `peak_decel` with a claim it breaks (0.6 * speed, 1.8 at speed=3).
    bench = (
        BENCH.replace(
            'claim="< 0.7")\n',
            'claim="< 0.7")\n    peak_decel = bn.ResultFloat(units="m/s^2", claim="< 1.5")\n',
        )
        .replace(
            "GAIN * self.speed\n",
            "GAIN * self.speed\n        self.peak_decel = 0.6 * self.speed\n",
        )
        .replace('["stop_distance"]', '["stop_distance", "peak_decel"]')
    )
    assert bench.count("peak_decel") == 3
    (repo / "bench.py").write_text(bench, encoding="utf-8")

    proc = _ab(repo, "--base", "main")

    # A failed claim leaves the exit status alone, whether or not the base has the metric.
    assert proc.returncode == 0, proc.stderr
    assert "warning: `peak_decel` is only in the candidate" in proc.stderr
    out = repo / "bencher-ab"
    cmp = json.loads((out / "comparison.json").read_text(encoding="utf-8"))
    assert [m["variable"] for m in cmp["metrics"]] == ["stop_distance"]
    peak = next(c for c in cmp["claims"] if c["variable"] == "peak_decel")
    assert peak["baseline"] is None
    assert peak["candidate"]["holds"] is False
    assert peak["candidate"]["worst_inputs"]["speed"] == pytest.approx(3.0)
    md = (out / "evidence.md").read_text(encoding="utf-8")
    assert "- `peak_decel` `< 1.5`: candidate fails (worst 1.8 at speed=3" in md
    assert "no baseline" in md


def test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored(repo):
    (repo / ".gitignore").write_text("cachedir/\n__pycache__/\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "track the evidence directory")

    assert _ab(repo, "--base", "main").returncode == 0
    proc = _ab(repo, "--base", "main")

    assert proc.returncode == 0, proc.stderr
    head = _git(repo, "rev-parse", "--short", "HEAD")
    cmp = json.loads((repo / "bencher-ab" / "comparison.json").read_text(encoding="utf-8"))
    assert cmp["candidate"]["provenance"]["source_revision"] == head


def test_ab_with_an_unknown_base_exits_2_before_it_runs_anything(repo):
    proc = _ab(repo, "--base", "nosuchref")

    assert proc.returncode == 2
    assert "--base 'nosuchref' does not name a commit" in proc.stderr
    assert not (repo / "bencher-ab").exists()
    assert _git(repo, "worktree", "list").count("\n") == 0


def test_ab_with_the_png_dir_as_the_image_dir_exits_before_it_runs_anything(repo, tmp_path):
    marker = tmp_path / "ran"
    proc = subprocess.run(
        [
            *(sys.executable, "-m", "bencher.render", "ab", "--base", "main"),
            *("--out", "o", "--png-dir", "o/x/../images", "--images", "--"),
            *(sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "--png-dir" in proc.stderr
    assert not marker.exists()
    assert not (repo / "o").exists()


AB_MAIN = (sys.executable, "-m", "bencher.render", "ab", "--base", "main")


def test_ab_runs_an_ignored_interpreter_on_the_base_side_too(repo):
    # A virtualenv is git-ignored, so the base worktree has none; the command names
    # it relative to where ab runs.
    venv = repo / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python").symlink_to(sys.executable)
    (repo / ".git" / "info" / "exclude").write_text(".venv/\n", encoding="utf-8")
    (repo / "gain.py").write_text("GAIN = 0.2\n", encoding="utf-8")

    proc = subprocess.run(
        [*AB_MAIN, "--", ".venv/bin/python", "bench.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    # The bench itself is tracked, so each side still runs its own copy of it.
    assert _metric(repo / "bencher-ab")["baseline_value"] == pytest.approx(0.6)
    assert _metric(repo / "bencher-ab")["current_value"] == pytest.approx(0.4)


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
    assert [str(mode) for mode in res.ds["mode"].values] == ["fast", "slow"]


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


def test_no_show_env_keeps_bench_runner_from_serving_the_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(NO_SHOW_ENV, "1")
    shown = []

    def record(*args, **_kwargs):
        shown.append(args)
        return SimpleNamespace(stop=lambda: None)

    monkeypatch.setattr(bn.BenchReport, "show", record)

    runner = bn.BenchRunner("runner_no_show", bench_class=Counted(), run_cfg=bn.BenchRunCfg())
    runner.run(show=True)

    assert runner.results
    assert shown == []


PKG_BENCH = """
import bencher as bn
from mypkg.gain import GAIN


class Braking(bn.ParametrizedSweep):
    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    stop_distance = bn.ResultFloat(units="m")

    def benchmark(self):
        self.stop_distance = GAIN * self.speed


bn.Bench("ab_pkg", Braking()).collect(
    input_vars=["speed"], result_vars=["stop_distance"], run_cfg=bn.BenchRunCfg(repeats=1)
)
"""


def _package_repo(tmp_path: Path, pkg_dir: str) -> Path:
    """GAIN is 0.3 at HEAD~1 and 0.2 at HEAD, in a package under *pkg_dir*."""
    repo = tmp_path / "pkgrepo"
    (repo / pkg_dir / "mypkg").mkdir(parents=True)
    (repo / "benchmarks").mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "ab@example.test")
    _git(repo, "config", "user.name", "ab")
    (repo / pkg_dir / "mypkg" / "__init__.py").write_text("", encoding="utf-8")
    (repo / pkg_dir / "mypkg" / "gain.py").write_text("GAIN = 0.3\n", encoding="utf-8")
    (repo / "benchmarks" / "bench.py").write_text(PKG_BENCH, encoding="utf-8")
    (repo / ".gitignore").write_text("cachedir/\nbencher-ab/\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    (repo / pkg_dir / "mypkg" / "gain.py").write_text("GAIN = 0.2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "lower gain")
    return repo


def _ab_with_pythonpath(repo: Path, pythonpath: Path) -> subprocess.CompletedProcess:
    # An absolute PYTHONPATH entry stands in for an editable install, whose .pth
    # file adds the candidate tree's absolute path in the same way.
    return subprocess.run(
        [
            *(sys.executable, "-m", "bencher.render", "ab", "--base", "HEAD~1"),
            *("--", sys.executable, "benchmarks/bench.py"),
        ],
        cwd=repo,
        env={**os.environ, "PYTHONPATH": str(pythonpath)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_ab_base_imports_its_own_package_over_an_absolute_path_to_the_candidate(tmp_path):
    repo = _package_repo(tmp_path, "src")

    proc = _ab_with_pythonpath(repo, repo / "src")

    assert proc.returncode == 0, proc.stderr
    assert _metric(repo / "bencher-ab")["baseline_value"] == pytest.approx(0.6)
    assert _metric(repo / "bencher-ab")["current_value"] == pytest.approx(0.4)
    assert _git(repo, "worktree", "list").count("\n") == 0


def test_ab_fails_when_the_base_still_imports_the_candidates_code(tmp_path):
    # lib/ is not a directory the base run puts first on PYTHONPATH, so the
    # absolute entry still reaches the candidate's package from the base side.
    repo = _package_repo(tmp_path, "lib")

    proc = _ab_with_pythonpath(repo, repo / "lib")

    assert proc.returncode == 1
    assert "base run exited with status 1" in proc.stderr
    log = (repo / "bencher-ab" / "base.log").read_text(encoding="utf-8")
    assert "mypkg.gain" in log
    assert str(repo / "lib" / "mypkg" / "gain.py") in log
    assert not (repo / "bencher-ab" / "base.pkl").exists()
    assert _git(repo, "worktree", "list").count("\n") == 0


def test_ab_png_dir_writes_one_png_per_metric(repo, tmp_path):
    pngs = tmp_path / "pngs"
    proc = _ab(repo, "--base", "HEAD", "--png-dir", str(pngs))
    assert proc.returncode == 0, proc.stderr
    assert (pngs / "stop_distance.png").exists()
    assert str(pngs / "stop_distance.png") in proc.stdout


def _github_remote(repo: Path, tmp_path: Path) -> Path:
    """Name origin as a GitHub repo, and route it to a local bare repo."""
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    github = "git@github.com:someone/braking.git"
    _git(repo, "remote", "add", "origin", github)
    _git(repo, "config", f"url.{bare}.insteadOf", github)
    return bare


def test_ab_images_pushes_them_to_the_evidence_ref_and_links_them(repo, tmp_path):
    bare = _github_remote(repo, tmp_path)
    (repo / "gain.py").write_text("GAIN = 0.25\n", encoding="utf-8")
    head = _git(repo, "rev-parse", "HEAD")

    proc = _ab(repo, "--base", "main", "--images")

    assert proc.returncode == 0, proc.stderr
    commit = _git(bare, "rev-parse", "refs/bencher/evidence")
    (run_dir,) = _git(bare, "ls-tree", "--name-only", commit).splitlines()
    assert _git(bare, "ls-tree", "--name-only", f"{commit}:{run_dir}").splitlines() == [
        "stop_distance.csv",
        "stop_distance.png",
    ]
    md = (repo / "bencher-ab" / "evidence.md").read_text(encoding="utf-8")
    url = f"https://github.com/someone/braking/blob/{commit}/{run_dir}/stop_distance.png?raw=true"
    assert f"]({url})" in md
    assert "```mermaid" in md  # the text chart stays
    assert str(repo / "bencher-ab" / "images" / "stop_distance.png") in proc.stdout
    # Nothing else moved: same HEAD, same branch, only the uncommitted change.
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == "M gain.py"
    assert _git(bare, "for-each-ref", "refs/heads") == ""


def test_ab_images_without_a_github_remote_keeps_text_and_exits_0(repo):
    (repo / "gain.py").write_text("GAIN = 0.25\n", encoding="utf-8")

    proc = _ab(repo, "--base", "main", "--images")

    assert proc.returncode == 0, proc.stderr
    notes = [line for line in proc.stderr.splitlines() if "images not linked" in line]
    assert len(notes) == 1
    out = repo / "bencher-ab"
    assert (out / "images" / "stop_distance.png").exists()
    assert "![" not in (out / "evidence.md").read_text(encoding="utf-8")


def test_ab_without_images_pushes_nothing(repo, tmp_path):
    bare = _github_remote(repo, tmp_path)

    proc = _ab(repo, "--base", "HEAD")

    assert proc.returncode == 0, proc.stderr
    assert _git(bare, "for-each-ref") == ""
    assert not (repo / "bencher-ab" / "images").exists()
