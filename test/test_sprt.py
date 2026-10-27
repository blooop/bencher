"""Wald's sequential probability ratio test for deciding whether a test is flaky."""

from __future__ import annotations

import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

import bencher as bn
from bencher.sprt import Sprt, SprtCfg, SprtVerdict, sprt

# The worked example: 0.1% acceptable, 1% unacceptable, 5% false-flaky, 10% false-pass.
CFG = SprtCfg(p0=0.001, p1=0.01, alpha=0.05, beta=0.10)


def _feed(cfg: SprtCfg, outcomes: list[bool]):
    test = Sprt(cfg)
    verdict = None
    for passed in outcomes:
        verdict = test.record(passed)
        if verdict is not None:
            break
    return verdict, test


class TestWorkedExample:
    def test_all_passes_accept_after_249_runs(self):
        verdict, test = _feed(CFG, [True] * 1000)
        assert verdict is SprtVerdict.PASS
        assert test.result().runs == 249
        assert CFG.runs_to_pass() == 249

    def test_one_failure_needs_about_503_more_runs(self):
        verdict, test = _feed(CFG, [False] + [True] * 1000)
        assert verdict is SprtVerdict.PASS
        assert test.result().runs == CFG.runs_to_pass(failures=1)
        assert 500 <= CFG.runs_to_pass(failures=1) <= 506

    def test_two_failures_need_a_gap_to_be_judged(self):
        assert SprtCfg(p0=0.01, p1=0.02).flaky_window() is None

    def test_no_window_when_one_failure_already_rejects(self):
        cfg = SprtCfg(p0=0.01, p1=0.2, alpha=0.1, beta=0.1)
        verdict, test = _feed(cfg, [False])
        assert verdict is SprtVerdict.FLAKY
        assert test.result().runs == 1
        assert cfg.flaky_window() is None

    def test_two_failures_close_together_reject(self):
        verdict, test = _feed(CFG, [False] + [True] * 150 + [False] + [True] * 1000)
        assert verdict is SprtVerdict.FLAKY
        assert test.result().runs == 152
        assert test.result().failure_runs == (1, 152)

    def test_two_failures_far_apart_do_not_reject(self):
        verdict, _ = _feed(CFG, [False] + [True] * 200 + [False] + [True] * 1000)
        assert verdict is SprtVerdict.PASS

    def test_rejection_window_is_about_189_passes(self):
        gap = CFG.flaky_window()
        assert gap is not None
        assert 185 <= gap <= 192
        inside, _ = _feed(CFG, [False] + [True] * gap + [False])
        outside, _ = _feed(CFG, [False] + [True] * (gap + 1) + [False] + [True] * 2000)
        assert inside is SprtVerdict.FLAKY
        assert outside is SprtVerdict.PASS

    def test_earlier_passes_shrink_the_rejection_window(self):
        # flaky_window() holds only for a fresh test: 100 earlier passes cut 189 to 89.
        inside, _ = _feed(CFG, [True] * 100 + [False] + [True] * 89 + [False])
        outside, _ = _feed(CFG, [True] * 100 + [False] + [True] * 90 + [False])
        assert inside is SprtVerdict.FLAKY
        assert outside is not SprtVerdict.FLAKY

    def test_rejection_window_is_exactly_189_passes(self):
        # Two failures add 2*ln(p1/p0); the passes between them may spend only the
        # excess over ln((1-beta)/alpha), each pass costing ln((1-p0)/(1-p1)).
        slack = 2 * math.log(0.01 / 0.001) - math.log(0.90 / 0.05)
        per_pass = math.log(0.999 / 0.99)
        assert slack / per_pass == pytest.approx(189.48, abs=0.01)
        assert CFG.flaky_window() == 189

    def test_result_llr_is_the_llr_after_the_deciding_run(self):
        _, test = _feed(CFG, [True] * 1000)
        result = test.result()
        assert result.llr == pytest.approx(249 * CFG.pass_step)
        assert result.llr <= CFG.pass_bound < result.llr - CFG.pass_step


class TestCap:
    def test_hitting_max_runs_is_inconclusive(self):
        cfg = SprtCfg(p0=0.001, p1=0.01, max_runs=100)
        verdict, test = _feed(cfg, [True] * 100)
        assert verdict is SprtVerdict.INCONCLUSIVE
        assert test.result().runs == 100

    def test_a_boundary_on_the_last_allowed_run_beats_the_cap(self):
        cfg = SprtCfg(p0=0.001, p1=0.01, max_runs=249)
        verdict, test = _feed(cfg, [True] * 249)
        assert verdict is SprtVerdict.PASS
        assert test.result().runs == 249

    def test_record_after_a_verdict_raises(self):
        _, test = _feed(CFG, [True] * 249)
        with pytest.raises(RuntimeError, match="already decided"):
            test.record(True)

    def test_result_before_a_verdict_raises(self):
        test = Sprt(CFG)
        test.record(True)
        with pytest.raises(RuntimeError, match="no verdict"):
            test.result()

    def test_run_state_cannot_be_injected_at_construction(self):
        state = {"runs": 0, "llr": 0.0, "failure_runs": [7, 3], "verdict": SprtVerdict.FLAKY}
        with pytest.raises(TypeError):
            Sprt(CFG, **state)

    def test_a_decided_test_cannot_be_reopened(self):
        _, test = _feed(CFG, [True] * 249)
        for name, value in (("verdict", None), ("llr", 100.0), ("runs", 0)):
            with pytest.raises(AttributeError):
                setattr(test, name, value)
        assert test.verdict is SprtVerdict.PASS
        assert test.runs == 249

    def test_the_cfg_cannot_be_swapped_mid_run(self):
        test = Sprt(CFG)
        test.record(False)
        with pytest.raises(AttributeError):
            test.cfg = SprtCfg(p0=0.2, p1=0.5, max_runs=3)
        assert test.cfg is CFG
        assert test.runs == 1
        assert test.llr == pytest.approx(CFG.fail_step)
        assert test.failure_runs == (1,)
        assert test.verdict is None

    def test_cfg_is_accepted_by_keyword(self):
        assert Sprt(cfg=CFG).cfg is CFG


class TestDriver:
    def test_sprt_calls_run_test_until_a_verdict(self):
        calls = []

        def run_test() -> bool:
            calls.append(1)
            return True

        result = sprt(run_test, CFG)
        assert result.verdict is SprtVerdict.PASS
        assert result.runs == len(calls) == 249
        assert result.failures == 0

    def test_exported_from_package(self):
        assert bn.sprt is sprt
        assert bn.SprtCfg is SprtCfg
        assert bn.SprtVerdict is SprtVerdict


class TestCfgValidation:
    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"p0": 0.01, "p1": 0.001}, "p0 < p1"),
            ({"p0": 0.01, "p1": 0.01}, "p0 < p1"),
            ({"p0": 0.0, "p1": 0.01}, "p0 < p1"),
            ({"p0": 0.001, "p1": 1.0}, "p0 < p1"),
            ({"p0": 0.001, "p1": 0.01, "alpha": 0.0}, "alpha"),
            ({"p0": 0.001, "p1": 0.01, "beta": 1.0}, "beta"),
            ({"p0": 0.001, "p1": 0.01, "alpha": 0.6, "beta": 0.5}, "alpha \\+ beta"),
            ({"p0": 0.001, "p1": 0.01, "max_runs": 0}, "max_runs"),
        ],
    )
    def test_rejects_bad_config(self, kwargs, match):
        with pytest.raises(ValueError, match=match):
            SprtCfg(**kwargs)


class TestGuards:
    @pytest.mark.parametrize("p_fail", [-0.1, 1.1])
    def test_expected_runs_rejects_a_rate_outside_0_1(self, p_fail):
        with pytest.raises(ValueError, match="p_fail"):
            CFG.expected_runs(p_fail)

    def test_runs_to_pass_rejects_negative_failures(self):
        with pytest.raises(ValueError, match="failures"):
            CFG.runs_to_pass(failures=-1)


class TestZeroDrift:
    def test_expected_runs_is_continuous_where_the_drift_is_zero(self):
        s, f = CFG.pass_step, CFG.fail_step
        p_zero = -s / (f - s)
        at_zero = CFG.expected_runs(p_zero)
        assert math.isfinite(at_zero)
        assert at_zero == pytest.approx(CFG.expected_runs(p_zero + 1e-4), rel=0.01)
        assert at_zero == pytest.approx(CFG.expected_runs(p_zero - 1e-4), rel=0.01)


class TestErrorRates:
    """Monte Carlo check that the decision keeps its alpha/beta promise."""

    @pytest.mark.parametrize(
        ("p_fail", "wrong", "limit"),
        [(0.001, SprtVerdict.FLAKY, 0.05), (0.01, SprtVerdict.PASS, 0.10)],
    )
    def test_error_rate_within_nominal(self, p_fail, wrong, limit):
        rng = random.Random(1234)  # noqa: S311 - seeded simulation, not crypto
        trials = 2000
        wrong_count = sum(
            sprt(lambda: rng.random() >= p_fail, CFG).verdict is wrong for _ in range(trials)
        )
        # Wald's bounds are conservative; allow Monte Carlo noise on top.
        assert wrong_count / trials <= limit + 0.02

    @pytest.mark.parametrize("p_fail", [0.001, 0.003, 0.01])
    def test_expected_runs_matches_simulation(self, p_fail):
        rng = random.Random(99)  # noqa: S311 - seeded simulation, not crypto
        trials = 2000
        mean_runs = (
            sum(sprt(lambda: rng.random() >= p_fail, CFG).runs for _ in range(trials)) / trials
        )
        # Wald's ASN ignores overshoot past the boundary, so allow a loose margin.
        assert CFG.expected_runs(p_fail) == pytest.approx(mean_runs, rel=0.25)

    def test_expected_runs_never_failing_is_pass_bound_over_pass_step(self):
        cfg = SprtCfg(p0=0.001, p1=0.01)
        assert cfg.expected_runs(0.0) == pytest.approx(cfg.pass_bound / cfg.pass_step)

    def test_expected_runs_always_failing_is_flaky_bound_over_fail_step(self):
        cfg = SprtCfg(p0=0.001, p1=0.01)
        assert cfg.expected_runs(1.0) == pytest.approx(cfg.flaky_bound / cfg.fail_step)


# Loads sprt.py by path with site-packages off (-S), as a caller with only the
# standard library does: kbench merges CI shards on a bare runner.
_LOAD_ALONE = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("sprt", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules["sprt"] = module
spec.loader.exec_module(module)
print(module.SprtCfg(p0=0.001, p1=0.01).runs_to_pass(0))
"""


def test_sprt_module_needs_only_the_standard_library():
    path = Path(bn.__file__).parent / "sprt.py"
    out = subprocess.run(
        [sys.executable, "-S", "-c", _LOAD_ALONE, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "249"
