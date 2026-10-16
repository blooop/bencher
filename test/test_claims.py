"""A result variable's declared claim, judged against every sample a sweep took."""

from __future__ import annotations

import json
import math

import pytest
import xarray as xr

import bencher as bn
from bencher.claims import Holds, Unmeasured, WorstSample, evaluate_claim, outcome_to_dict


class Braking(bn.ParametrizedSweep):
    """Stop distance grows with speed; the worst case is the top speed."""

    speed = bn.FloatSweep(default=1.0, bounds=(1.0, 3.0), samples=3)
    gain = bn.FloatSweep(default=0.2)

    stop_distance = bn.ResultFloat(units="m", claim="< 0.7")
    margin = bn.ResultFloat(units="m", direction=bn.OptDir.maximize, claim=">= 0.5")
    jerk = bn.ResultFloat(units="m/s3", claim="0.1..0.4")
    plain = bn.ResultFloat(units="ul")

    def benchmark(self):
        self.stop_distance = self.gain * self.speed
        self.margin = 1.0 / self.speed
        self.jerk = 0.1 * self.speed
        self.plain = self.speed


_ALL_VARS = ("stop_distance", "margin", "jerk", "plain")


def _collect(gain: float, repeats: int = 2, result_vars: tuple[str, ...] = _ALL_VARS):
    bench = bn.Bench(f"braking_{gain}", Braking())
    res = bench.collect(
        input_vars=["speed"],
        result_vars=list(result_vars),
        const_vars=[("gain", gain)],
        run_cfg=bn.BenchRunCfg(repeats=repeats),
    )
    bench.close()
    return res


def _metric(data: dict, name: str) -> dict:
    return next(m for m in data["metrics"] if m["variable"] == name)


@pytest.mark.parametrize("text", ["<< 3", "0.7", "< abc", "< nan", "0.9..0.1", "", "~ 2"])
def test_an_unreadable_claim_fails_where_the_class_is_defined(text):
    with pytest.raises(ValueError, match="claim"):

        class _Bad(bn.ParametrizedSweep):
            out = bn.ResultFloat(claim=text)


def test_a_claim_is_parsed_once_into_a_typed_value():
    assert Braking.param.stop_distance.claim == bn.Threshold(bn.Comparison.LT, 0.7)
    assert Braking.param.jerk.claim == bn.Within(0.1, 0.4)
    assert Braking.param.plain.claim is None


def test_the_claim_holds_only_if_the_worst_sample_satisfies_it():
    # speed 3.0 * gain 0.2 = 0.6 < 0.7. Repeats tie, so the first one is named.
    holds = _metric(bn.result_to_dict(_collect(gain=0.2)), "stop_distance")["claim"]
    assert holds["claim"] == "< 0.7"
    assert holds["holds"] is True
    assert holds["worst_value"] == pytest.approx(0.6)
    assert holds["worst_inputs"] == {"speed": 3.0, "repeat": 1}
    assert holds["samples"] == 6

    # gain 0.3: the mean over the sweep (0.6) is inside, the top speed (0.9) is not.
    fails = _metric(bn.result_to_dict(_collect(gain=0.3)), "stop_distance")["claim"]
    assert fails["holds"] is False
    assert fails["worst_value"] == pytest.approx(0.9)
    assert fails["worst_inputs"] == {"speed": 3.0, "repeat": 1}


def test_a_lower_bound_is_judged_by_the_smallest_sample():
    margin = _metric(bn.result_to_dict(_collect(gain=0.2)), "margin")["claim"]
    # 1/3 is the smallest margin, at the top speed, and it is below 0.5.
    assert margin["holds"] is False
    assert margin["worst_value"] == pytest.approx(1 / 3)
    assert margin["worst_inputs"]["speed"] == 3.0


def test_a_range_is_judged_by_the_sample_nearest_or_furthest_past_an_edge():
    jerk = _metric(bn.result_to_dict(_collect(gain=0.2)), "jerk")["claim"]
    # 0.1, 0.2, 0.3 are all inside 0.1..0.4; the closest to an edge is 0.1.
    assert jerk["claim"] == "0.1..0.4"
    assert jerk["holds"] is True
    assert jerk["worst_value"] == pytest.approx(0.1)


def test_a_metric_without_a_claim_carries_no_claim_key():
    data = bn.result_to_dict(_collect(gain=0.2))
    assert "claim" not in _metric(data, "plain")
    json.dumps(data, allow_nan=False)


def test_changing_a_claim_keeps_the_cache_identity():
    # A claim is how a result is judged, not what it measures: it must not
    # orphan cached samples or over_time history.
    assert (
        bn.ResultFloat(units="m", claim="< 1").hash_persistent()
        == bn.ResultFloat(units="m", claim="> 5").hash_persistent()
        == bn.ResultFloat(units="m").hash_persistent()
    )


def test_compare_reports_the_claim_on_both_sides():
    cmp = bn.compare_results(_collect(gain=0.3), _collect(gain=0.2))
    claim = _metric(cmp, "stop_distance")["claim"]
    assert claim["claim"] == "< 0.7"
    assert claim["baseline"]["holds"] is False
    assert claim["candidate"]["holds"] is True
    assert claim["candidate"]["worst_inputs"] == {"speed": 3.0, "repeat": 1}
    json.dumps(cmp, allow_nan=False)


def test_compare_judges_a_claim_the_baseline_does_not_measure():
    # The candidate adds `margin` (claim >= 0.5; 1/3 at speed=3, so it fails); the base has
    # `plain`, which the candidate dropped.
    base = _collect(gain=0.3, result_vars=("stop_distance", "plain"))
    cand = _collect(gain=0.2, result_vars=("stop_distance", "margin"))
    cmp = bn.compare_results(base, cand)
    claims = {c["variable"]: c for c in cmp["claims"]}
    assert list(claims) == ["stop_distance", "margin"]
    margin = claims["margin"]
    assert margin["claim"] == ">= 0.5"
    assert margin["baseline"] is None
    assert margin["candidate"]["holds"] is False
    assert margin["candidate"]["worst_value"] == pytest.approx(1 / 3)
    assert margin["candidate"]["worst_inputs"] == {"speed": 3.0, "repeat": 1}
    paired = claims["stop_distance"]
    assert paired["baseline"]["holds"] is False
    assert paired["candidate"]["holds"] is True
    # The paired metric's own claim says the same as the claims list.
    stop = _metric(cmp, "stop_distance")["claim"]
    assert stop == {k: paired[k] for k in ("claim", "baseline", "candidate")}
    assert cmp["unpaired"] == {"candidate_only": ["margin"], "baseline_only": ["plain"]}
    json.dumps(cmp, allow_nan=False)


def test_unpaired_metrics_do_not_change_the_metrics_list():
    base = _collect(gain=0.3, result_vars=("stop_distance", "plain"))
    cand = _collect(gain=0.2, result_vars=("stop_distance", "margin"))
    cmp = bn.compare_results(base, cand)
    assert [m["variable"] for m in cmp["metrics"]] == ["stop_distance"]
    assert set(cmp["metrics"][0]) == {
        "variable",
        "baseline_value",
        "current_value",
        "change_percent",
        "direction",
        "method",
        "regressed",
        "verdict",
        "claim",
    }
    assert cmp["metrics"][0]["verdict"] == "improved"
    assert cmp["summary"] == {"improved": 1, "regressed": 0, "unchanged": 0}
    # The added keys are additive: the contract version stays 1.
    assert cmp["schema_version"] == 1


def test_a_fully_paired_comparison_reports_nothing_unpaired():
    cmp = bn.compare_results(_collect(gain=0.3), _collect(gain=0.2))
    assert cmp["unpaired"] == {"candidate_only": [], "baseline_only": []}
    assert [c["variable"] for c in cmp["claims"]] == ["stop_distance", "margin", "jerk"]


@pytest.mark.parametrize(("claim", "infinite"), [("> 0", math.inf), ("< 0.7", -math.inf)])
def test_an_unrecorded_sample_is_never_named_the_worst(claim, infinite):
    # The infinite sample has an infinite margin; the NaN before it has none.
    da = xr.DataArray([math.nan, infinite], dims=["speed"], coords={"speed": [1.0, 2.0]})
    outcome = evaluate_claim(bn.parse_claim(claim), da)
    assert outcome == Holds(WorstSample(infinite, {"speed": 2.0}), samples=1)


@pytest.mark.parametrize(
    ("claim", "holds"),
    [("< 0.5", False), ("<= 0.5", True), ("> 0.5", False), (">= 0.5", True)],
)
def test_a_sample_on_the_bound_satisfies_only_the_inclusive_operator(claim, holds):
    da = xr.DataArray([0.5], dims=["speed"], coords={"speed": [1.0]})
    outcome = evaluate_claim(bn.parse_claim(claim), da)
    assert isinstance(outcome, Holds) is holds
    assert outcome.worst.value == 0.5


@pytest.mark.parametrize(
    ("samples", "holds", "worst"), [([0.2, 0.4], True, 0.4), ([0.2, 0.5], False, 0.5)]
)
def test_a_range_includes_its_high_edge_and_fails_past_it(samples, holds, worst):
    da = xr.DataArray(samples, dims=["speed"], coords={"speed": [1.0, 2.0]})
    outcome = evaluate_claim(bn.Within(0.1, 0.4), da)
    assert isinstance(outcome, Holds) is holds
    assert outcome.worst.value == worst


@pytest.mark.parametrize("bound", [math.nan, math.inf, -math.inf])
def test_a_threshold_built_directly_rejects_a_bound_that_is_not_finite(bound):
    # A NaN bound gives every sample a NaN margin, so the first sample was named
    # the worst and the claim failed on any data.
    with pytest.raises(ValueError, match="finite"):
        bn.Threshold(bn.Comparison.LT, bound)


def test_a_claim_that_is_not_a_string_raises_a_type_error():
    with pytest.raises(TypeError, match="claim"):
        bn.ResultFloat(claim=0.7)


def test_no_recorded_sample_leaves_the_claim_unmeasured():
    da = xr.DataArray([math.nan, math.nan], dims=["speed"], coords={"speed": [1.0, 2.0]})
    outcome = evaluate_claim(bn.parse_claim("< 0.7"), da)
    assert outcome == Unmeasured()
    assert outcome_to_dict(outcome) == {
        "holds": None,
        "worst_value": None,
        "worst_inputs": {},
        "samples": 0,
    }


def test_an_infinite_worst_sample_exports_as_null_beside_a_failed_claim():
    da = xr.DataArray([0.1, math.inf], dims=["speed"], coords={"speed": [1.0, 2.0]})
    data = outcome_to_dict(evaluate_claim(bn.parse_claim("< 0.7"), da))
    assert data["holds"] is False
    assert data["worst_value"] is None
    assert data["worst_inputs"] == {"speed": 2.0}
    json.dumps(data, allow_nan=False)
