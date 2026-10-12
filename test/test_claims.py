"""A result variable's declared claim, judged against every sample a sweep took."""

from __future__ import annotations

import json

import pytest

import bencher as bn


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


def _collect(gain: float, repeats: int = 2):
    bench = bn.Bench(f"braking_{gain}", Braking())
    res = bench.collect(
        input_vars=["speed"],
        result_vars=["stop_distance", "margin", "jerk", "plain"],
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
