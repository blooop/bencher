"""Plan 18 — one measurement declared once, bound to several workers.

The property that matters is the last test class here: one spec bound to two
different worker classes yields two configs differing *only* in ``bench_name``,
with identical input/const/result identity. That is what makes the drift described
in P2 detectable, and it is unavailable while a declaration exists only as fifteen
keyword arguments at N call sites.
"""

from __future__ import annotations

import pickle
import unittest

import pytest

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg


class OtherWorker(bn.ParametrizedSweep):
    """A second worker declaring the same variable names as ExampleBenchCfg."""

    theta = bn.FloatSweep(default=0, bounds=[0, 3.2], units="rad", samples=30)
    offset = bn.FloatSweep(default=0, bounds=[0, 0.3], units="v", samples=30)
    out_sin = bn.ResultFloat(units="v")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = self.theta + self.offset
        return super().__call__(**kwargs)


LATENCY = bn.SweepSpec(
    title="Request latency",
    description="declared once",
    input_vars=[bn.sweep("theta", bounds=(0, 1), samples=3)],
    result_vars=["out_sin"],
    const_vars={"offset": 0.1},
    tag="latency",
)


def _bench(worker=ExampleBenchCfg):
    cfg = bn.BenchRunCfg()
    cfg.auto_plot = False
    cfg.cache_results = False
    cfg.cache_samples = False
    return worker().to_bench(cfg)


class TestValueSemantics(unittest.TestCase):
    def test_frozen(self) -> None:
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            LATENCY.title = "no"

    def test_equality_and_pickling(self) -> None:
        twin = bn.SweepSpec(
            title="Request latency",
            description="declared once",
            input_vars=[bn.sweep("theta", bounds=(0, 1), samples=3)],
            result_vars=["out_sin"],
            const_vars={"offset": 0.1},
            tag="latency",
        )
        assert twin == LATENCY
        assert pickle.loads(pickle.dumps(LATENCY)) == LATENCY

    def test_unset_fields_are_absent_from_bind(self) -> None:
        spec = bn.SweepSpec(result_vars=["out_sin"])
        assert spec.bind() == {"result_vars": ["out_sin"]}

    def test_empty_and_unset_input_vars_are_different(self) -> None:
        """None auto-discovers; () declares none."""
        assert "input_vars" not in bn.SweepSpec(result_vars=["y"]).bind()
        assert bn.SweepSpec(input_vars=[], result_vars=["y"]).bind()["input_vars"] == []

    def test_a_lambda_is_rejected_at_construction(self) -> None:
        with pytest.raises(TypeError) as ctx:
            bn.SweepSpec(result_vars=[lambda: None])
        assert "may not contain a callable" in str(ctx.value)

    def test_a_shaped_result_var_is_rejected_at_construction(self) -> None:
        """It would otherwise raise AttributeError mid-run: result vars are not SweepBase."""
        with pytest.raises(TypeError) as ctx:
            bn.SweepSpec(result_vars=[bn.sweep("out_sin", samples=3)])
        assert "Shaping applies to inputs and consts only" in str(ctx.value)

    def test_a_bare_sweep_spec_result_var_is_allowed(self) -> None:
        spec = bn.SweepSpec(result_vars=[bn.sweep("out_sin")])
        assert len(spec.bind()["result_vars"]) == 1

    def test_the_deprecated_whole_list_mapping_form_is_rejected(self) -> None:
        with pytest.raises(TypeError) as ctx:
            bn.SweepSpec(input_vars={"theta": [0, 1]})
        assert "must be a list, not a mapping" in str(ctx.value)

    def test_a_malformed_const_entry_is_rejected(self) -> None:
        for bad in ([("offset", 1, 2)], ["offset"], [42]):
            with self.subTest(value=bad), pytest.raises(TypeError):
                bn.SweepSpec(const_vars=bad)


class TestComposition(unittest.TestCase):
    def test_scalars_are_replaced(self) -> None:
        assert LATENCY.with_(tag="slow").tag == "slow"
        assert LATENCY.tag == "latency", "with_ must not mutate"

    def test_const_vars_merge_per_key(self) -> None:
        slow = LATENCY.with_(const_vars={"timeout_s": 30})
        assert slow.const_vars is not None
        assert dict(slow.const_vars) == {"offset": 0.1, "timeout_s": 30}

    def test_const_vars_override_wins_per_key(self) -> None:
        overridden = LATENCY.with_(const_vars={"offset": 0.9}).const_vars
        assert overridden is not None
        assert dict(overridden)["offset"] == 0.9

    def test_result_vars_are_replaced_not_appended(self) -> None:
        replaced = LATENCY.with_(result_vars=["out_cos"])
        assert list(replaced.result_vars) == ["out_cos"]

    def test_input_vars_are_replaced_not_appended(self) -> None:
        replaced = LATENCY.with_(input_vars=["offset"])
        assert list(replaced.input_vars) == ["offset"]

    def test_plus_result_vars_appends(self) -> None:
        more = LATENCY.plus_result_vars("out_cos", "out_bool")
        assert list(more.result_vars) == ["out_sin", "out_cos", "out_bool"]

    def test_plus_result_vars_accepts_a_list(self) -> None:
        more = LATENCY.plus_result_vars(["out_cos", "out_bool"])
        assert list(more.result_vars) == ["out_sin", "out_cos", "out_bool"]

    def test_plus_input_vars_appends_last(self) -> None:
        more = LATENCY.plus_input_vars("offset")
        assert more.bind()["input_vars"][-1] == "offset"

    def test_merge_applies_only_declared_fields(self) -> None:
        overlay = bn.SweepSpec(tag="slow", const_vars={"timeout_s": 30})
        merged = LATENCY.merge(overlay)
        assert merged.tag == "slow"
        assert merged.title == "Request latency", "an unset field must not clear"
        assert merged.const_vars is not None
        assert dict(merged.const_vars) == {"offset": 0.1, "timeout_s": 30}

    def test_an_explicit_none_clears_a_field(self) -> None:
        assert LATENCY.with_(tag=None).tag is None

    def test_an_unknown_field_is_rejected(self) -> None:
        with pytest.raises(TypeError) as ctx:
            LATENCY.with_(repeats=3)
        assert "no field(s) ['repeats']" in str(ctx.value)

    def test_run_configuration_has_no_field(self) -> None:
        """A spec that carried repeats or run_cfg would be a rival BenchCfg."""
        from dataclasses import fields

        names = {f.name for f in fields(bn.SweepSpec)}
        for excluded in ("repeats", "run_cfg", "plot_callbacks", "auto_plot", "aggregate"):
            assert excluded not in names


class TestBind(unittest.TestCase):
    """Phase 1: a spec reaches ``plot_sweep`` as ``**spec.bind()``.

    Accepting a spec in ``plot_sweep``'s first positional slot is phase 2 of
    plan 18, deferred until the D5 tag-precedence decision (A5 §6) is confirmed.
    """

    def test_plot_sweep_with_bind_is_deterministic(self) -> None:
        keys = []
        for _ in range(2):
            bench = _bench()
            try:
                res = bench.plot_sweep(**LATENCY.bind(), plot_callbacks=False)
                keys.append(res.bench_cfg.hash_persistent(True))
            finally:
                bench.close()
        assert keys[0] == keys[1]

    def test_a_dict_override_on_the_bound_arguments_wins(self) -> None:
        bench = _bench()
        try:
            res = bench.plot_sweep(**{**LATENCY.bind(), "tag": "override"}, plot_callbacks=False)
        finally:
            bench.close()
        assert res.bench_cfg.tag == "override"

    def test_the_spec_title_reaches_the_config(self) -> None:
        bench = _bench()
        try:
            res = bench.plot_sweep(**LATENCY.bind(), plot_callbacks=False)
        finally:
            bench.close()
        assert res.bench_cfg.title == "Request latency"

    def test_bind_returns_mutable_lists(self) -> None:
        """plot_sweep converts its variable lists in place."""
        bound = LATENCY.bind()
        assert isinstance(bound["input_vars"], list)
        assert isinstance(bound["result_vars"], list)
        assert isinstance(bound["const_vars"], list)
        assert isinstance(bound["const_vars"][0], list)

    def test_bind_does_not_share_state_between_calls(self) -> None:
        first = LATENCY.bind()
        first["result_vars"].append("out_cos")
        assert LATENCY.bind()["result_vars"] == ["out_sin"]

    def test_bind_with_a_worker_checks_names_up_front(self) -> None:
        spec = bn.SweepSpec(input_vars=["nope"], result_vars=["out_sin"])
        with pytest.raises(KeyError) as ctx:
            spec.bind(ExampleBenchCfg)
        assert "Available parameters" in str(ctx.value)

    def test_bind_with_a_worker_accepts_valid_names(self) -> None:
        assert "input_vars" in LATENCY.bind(ExampleBenchCfg)

    def test_bind_checks_const_and_result_names_too(self) -> None:
        for field, spec in {
            "const": bn.SweepSpec(const_vars={"nope": 1}),
            "result": bn.SweepSpec(result_vars=["nope"]),
        }.items():
            with self.subTest(field=field), pytest.raises(KeyError):
                spec.bind(ExampleBenchCfg)


class TestBindValidatesDuplicates(unittest.TestCase):
    """The cross-plan wire: bind() runs plot_sweep's duplicate validation.

    A spec is the main *source* of duplicates -- composing overlapping groups from
    several places is exactly what specs make easy -- so it must not be able to
    hand plot_sweep a declaration plot_sweep will then reject. Failing at bind()
    puts the error where the composition that caused it is in view.
    """

    def test_a_duplicate_input_var_raises_at_bind(self) -> None:
        spec = bn.SweepSpec(input_vars=["theta", "theta"], result_vars=["out_sin"])
        with pytest.raises(ValueError) as ctx:
            spec.bind(ExampleBenchCfg)
        assert "one dataset dimension" in str(ctx.value)

    def test_a_duplicate_arising_from_composition_raises(self) -> None:
        """plus_input_vars is how it happens in practice."""
        with pytest.raises(ValueError):
            LATENCY.plus_input_vars("theta").bind(ExampleBenchCfg)

    def test_a_duplicate_result_var_is_warned_and_dropped_once(self) -> None:
        import warnings

        spec = LATENCY.plus_result_vars("out_sin")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            bound = spec.bind(ExampleBenchCfg)
        assert bound["result_vars"] == ["out_sin"]
        assert len([w for w in caught if "declared twice" in str(w.message)]) == 1

    def test_the_survivor_is_the_caller_s_own_declaration_form(self) -> None:
        """Bound arguments must stay bindable to a different worker, so the
        entries returned are the spec's strings and dicts, not resolved params."""
        bound = LATENCY.plus_result_vars("out_sin").bind(ExampleBenchCfg)
        assert bound["result_vars"] == ["out_sin"]
        assert isinstance(bound["input_vars"][0], dict)

    def test_conflicting_duplicate_consts_raise_at_bind(self) -> None:
        spec = bn.SweepSpec(result_vars=["out_sin"], const_vars=[("offset", 0.1), ("offset", 0.2)])
        with pytest.raises(ValueError) as ctx:
            spec.bind(ExampleBenchCfg)
        assert "different values" in str(ctx.value)

    def test_equal_duplicate_consts_collapse_silently(self) -> None:
        spec = bn.SweepSpec(result_vars=["out_sin"], const_vars=[("offset", 0.1), ("offset", 0.1)])
        assert spec.bind(ExampleBenchCfg)["const_vars"] == [["offset", 0.1]]

    def test_bind_without_a_worker_does_not_validate(self) -> None:
        """There is nothing to resolve names against, so plot_sweep validates instead."""
        spec = bn.SweepSpec(input_vars=["theta", "theta"], result_vars=["out_sin"])
        assert spec.bind()["input_vars"] == ["theta", "theta"]

    def test_a_clean_spec_is_unchanged_by_validation(self) -> None:
        assert LATENCY.bind(ExampleBenchCfg) == LATENCY.bind()


class TestOneSpecTwoWorkers(unittest.TestCase):
    """P2 — the property that makes cross-environment drift detectable."""

    def _cfg(self, worker):
        bench = _bench(worker)
        try:
            return bench.plot_sweep(**LATENCY.bind(), plot_callbacks=False).bench_cfg
        finally:
            bench.close()

    def test_two_workers_differ_only_in_bench_name(self) -> None:
        a, b = self._cfg(ExampleBenchCfg), self._cfg(OtherWorker)
        assert a.bench_name != b.bench_name
        assert a.tag == b.tag
        assert [v.name for v in a.input_vars] == [v.name for v in b.input_vars]
        assert [v.name for v in a.result_vars] == [v.name for v in b.result_vars]
        assert sorted((c[0].name, c[1]) for c in a.const_vars) == sorted(
            (c[0].name, c[1]) for c in b.const_vars
        )

    def test_renaming_only_the_bench_name_leaves_the_rest_identical(self) -> None:
        """The declaration is the same object, so nothing else *can* drift."""
        a, b = self._cfg(ExampleBenchCfg), self._cfg(OtherWorker)
        replaced = a.hash_persistent(True) != b.hash_persistent(True)
        assert replaced, "bench_name is hashed, so the keys must differ"
        for cfg in (a, b):
            assert cfg.title == "Request latency"

    def test_diff_specs_names_every_differing_field(self) -> None:
        drifted = LATENCY.plus_result_vars("out_cos").with_(tag="other")
        diff = bn.diff_specs(LATENCY, drifted)
        assert len(diff) == 2, diff
        assert any(line.startswith("result_vars:") for line in diff)
        assert any(line.startswith("tag:") for line in diff)

    def test_identical_specs_diff_to_nothing(self) -> None:
        assert bn.diff_specs(LATENCY, LATENCY) == []


class TestDescribe(unittest.TestCase):
    def test_describe_lists_only_declared_fields_by_name(self) -> None:
        text = bn.SweepSpec(input_vars=["theta"], result_vars=["out_sin"]).describe()
        assert "input_vars: theta" in text
        assert "result_vars: out_sin" in text
        assert "tag" not in text

    def test_describe_renders_sweep_dicts_and_consts_by_name(self) -> None:
        text = LATENCY.describe()
        assert "input_vars: theta" in text
        assert "const_vars: offset=0.1" in text


if __name__ == "__main__":
    unittest.main()
