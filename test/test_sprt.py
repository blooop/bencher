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
            ({"p0": 0.001, "p1": 0.01, "max_runs": 1.5}, "max_runs"),
            ({"p0": 0.001, "p1": 0.01, "max_runs": math.inf}, "max_runs"),
            ({"p0": 0.001, "p1": 0.01, "max_runs": math.nan}, "max_runs"),
            ({"p0": 0.001, "p1": 0.01, "max_runs": True}, "max_runs"),
            ({"p0": 0.001, "p1": 0.01, "max_runs": "10"}, "max_runs"),
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

    @pytest.mark.parametrize("offset", [-1e-9, -1e-11, -1e-13, 1e-13, 1e-11, 1e-9])
    def test_expected_runs_keeps_its_precision_near_zero_drift(self, offset):
        s, f = CFG.pass_step, CFG.fail_step
        p_zero = -s / (f - s)
        assert CFG.expected_runs(p_zero + offset) == pytest.approx(
            CFG.expected_runs(p_zero), rel=1e-6
        )

    def test_expected_runs_at_zero_drift_is_walds_limit(self):
        # At zero drift Wald's mean is -a*b / E[z^2].
        a, b = CFG.flaky_bound, CFG.pass_bound
        f, s = CFG.fail_step, CFG.pass_step
        p = -s / (f - s)
        expected = -a * b / (p * f * f + (1 - p) * s * s)
        assert expected == pytest.approx(312.26917765914, rel=1e-9)
        assert CFG.expected_runs(p) == pytest.approx(expected, rel=1e-9)

    @pytest.mark.parametrize(("p_fail", "approx_runs"), [(0.003, 324.509157), (0.0045, 299.600521)])
    def test_expected_runs_near_zero_drift_is_walds_closed_form(self, p_fail, approx_runs):
        a, b = CFG.flaky_bound, CFG.pass_bound
        f, s = CFG.fail_step, CFG.pass_step
        drift = p_fail * f + (1 - p_fail) * s

        def mgf_minus_one(h: float) -> float:
            return p_fail * math.exp(h * f) + (1 - p_fail) * math.exp(h * s) - 1

        # The nonzero root lies on the side opposite the drift; bisect a sign change.
        sign = -1.0 if drift > 0 else 1.0
        lo, hi = sign * 1e-6, sign * 10.0
        assert mgf_minus_one(lo) < 0 < mgf_minus_one(hi)
        for _ in range(200):
            mid = (lo + hi) / 2
            if mgf_minus_one(mid) < 0:
                lo = mid
            else:
                hi = mid
        h = (lo + hi) / 2
        accept = (math.exp(h * a) - 1) / (math.exp(h * a) - math.exp(h * b))
        expected = (accept * b + (1 - accept) * a) / drift
        assert expected == pytest.approx(approx_runs, rel=1e-6)
        assert CFG.expected_runs(p_fail) == pytest.approx(expected, rel=1e-9)


class TestExpectedRunsRange:
    @pytest.mark.parametrize("p_fail", [1e-300, 1e-250, 1e-20, 0.5, 0.95, 1 - 1e-6, 1 - 1e-12])
    def test_expected_runs_is_finite_and_positive(self, p_fail):
        runs = CFG.expected_runs(p_fail)
        assert math.isfinite(runs)
        assert runs > 0

    def test_expected_runs_is_continuous_across_0_1(self):
        rates = sorted(
            {10 ** (-k / 8) for k in range(1, 2400)}
            | {1 - 10 ** (-k / 8) for k in range(1, 128)}
            | {k / 1000 for k in range(1, 1000)}
        )
        runs = [CFG.expected_runs(p) for p in rates]
        for p, before, after in zip(rates[1:], runs, runs[1:], strict=False):
            assert after == pytest.approx(before, rel=0.2), p

    def test_expected_runs_tends_to_its_endpoint_values(self):
        assert CFG.expected_runs(1e-300) == pytest.approx(CFG.expected_runs(0.0), rel=1e-9)
        assert CFG.expected_runs(1 - 1e-15) == pytest.approx(CFG.expected_runs(1.0), rel=1e-9)


class TestErrorRates:
    """Monte Carlo check that the decision keeps its alpha/beta promise."""

    @pytest.mark.parametrize(
        ("p_fail", "wrong", "bound"),
        [
            # Wald's guarantee: P(FLAKY | p0) <= alpha/(1-beta), P(PASS | p1) <= beta/(1-alpha).
            (0.001, SprtVerdict.FLAKY, CFG.alpha / (1 - CFG.beta)),
            (0.01, SprtVerdict.PASS, CFG.beta / (1 - CFG.alpha)),
        ],
    )
    def test_error_rate_within_wald_bound(self, p_fail, wrong, bound):
        rng = random.Random(1234)  # noqa: S311 - seeded simulation, not crypto
        trials = 10_000
        wrong_count = sum(
            sprt(lambda: rng.random() >= p_fail, CFG).verdict is wrong for _ in range(trials)
        )
        # Three binomial standard errors at the bound: a rule whose true error rate sits
        # at the bound passes this almost always, one a point or more above it fails.
        sigma = math.sqrt(bound * (1 - bound) / trials)
        assert wrong_count / trials <= bound + 3 * sigma

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


SVG_NS = "{http://www.w3.org/2000/svg}"


def _svg_tree(test: Sprt):
    import xml.etree.ElementTree as ET

    return ET.fromstring(test.to_svg())  # noqa: S314 - parses our own output


def _by_class(root, cls: str):
    return [el for el in root.iter() if cls in (el.get("class") or "").split()]


def _all_text(root) -> str:
    return " ".join("".join(el.itertext()) for el in root.iter(f"{SVG_NS}text"))


class TestSvg:
    def test_flaky_chart_shows_verdict_failures_and_boundaries(self):
        _, test = _feed(CFG, [False] + [True] * 150 + [False])
        root = _svg_tree(test)
        assert root.tag == f"{SVG_NS}svg"
        text = _all_text(root)
        assert "FLAKY" in text
        assert "152 runs" in text
        assert "2 failures" in text
        assert "p0=0.001" in text
        assert "p1=0.01" in text
        assert len(_by_class(root, "failure")) == 2
        assert len(_by_class(root, "boundary-flaky")) == 1
        assert len(_by_class(root, "boundary-pass")) == 1
        assert len(_by_class(root, "continue-band")) == 1
        assert len(_by_class(root, "max-runs")) == 1

    def test_max_runs_on_the_chart_is_a_line_at_its_run(self):
        from bencher.sprt import _SVG_LEFT, _SVG_RIGHT, _SVG_W

        verdict, test = _feed(SprtCfg(p0=0.001, p1=0.01, max_runs=50), [True] * 50)
        assert verdict is SprtVerdict.INCONCLUSIVE
        (cap,) = _by_class(_svg_tree(test), "max-runs")
        assert cap.tag == f"{SVG_NS}line"
        # A cap near the data sets the x axis to 0..max_runs*1.04.
        x_cap = _SVG_LEFT + 50 / (50 * 1.04) * (_SVG_W - _SVG_LEFT - _SVG_RIGHT)
        assert float(cap.get("x1")) == pytest.approx(x_cap, abs=0.06)
        assert float(cap.get("x2")) == pytest.approx(x_cap, abs=0.06)

    def test_max_runs_off_the_chart_is_a_label(self):
        _, test = _feed(CFG, [False] + [True] * 150 + [False])
        (cap,) = _by_class(_svg_tree(test), "max-runs")
        assert cap.tag == f"{SVG_NS}text"
        assert "off the chart" in "".join(cap.itertext())

    def test_pass_chart_draws_one_point_per_pass(self):
        _, test = _feed(CFG, [False] + [True] * 1000)
        root = _svg_tree(test)
        assert "PASS" in _all_text(root)
        assert len(_by_class(root, "failure")) == 1
        assert len(_by_class(root, "pass")) == test.runs - 1

    def test_undecided_and_inconclusive_render(self):
        undecided = Sprt(CFG)
        undecided.record(True)
        assert "no verdict yet" in _all_text(_svg_tree(undecided))
        _, capped = _feed(SprtCfg(p0=0.001, p1=0.01, max_runs=50), [True] * 50)
        assert "INCONCLUSIVE" in _all_text(_svg_tree(capped))
        assert len(_by_class(_svg_tree(Sprt(CFG)), "failure")) == 0

    def test_long_run_stays_bounded_and_keeps_every_failure(self):
        # A failure every 256 runs is close to zero drift, so the walk stays inside
        # the band until the cap.
        cfg = SprtCfg(p0=0.001, p1=0.01, max_runs=10_000)
        outcomes = [i % 256 != 1 for i in range(1, 10_001)]
        verdict, test = _feed(cfg, outcomes)
        assert verdict is SprtVerdict.INCONCLUSIVE
        assert test.runs == 10_000
        svg = test.to_svg()
        assert len(svg) < 150_000
        root = _svg_tree(test)
        assert len(_by_class(root, "failure")) == test.result().failures == 40
        assert len(_by_class(root, "pass")) <= 2000

    def test_repr_svg_and_save_svg(self, tmp_path):
        _, test = _feed(CFG, [True] * 300)
        assert test._repr_svg_() == test.to_svg()
        path = tmp_path / "sprt.svg"
        test.save_svg(path)
        assert path.read_text(encoding="utf-8") == test.to_svg()
