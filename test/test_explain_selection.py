"""Tests for the selection decision table (A2 Phase S2): registry.explain() and
BenchResult.explain_selection(). select() must be exactly the chosen subset."""

import unittest

import bencher as bn
from bencher.plugins import (
    PlotFilter,
    VarRange,
    get_registry,
    plot_plugin,
    unregister_plugin,
)
from bencher.results.bench_result import BenchResult


class Linear(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = self.x * 2.0


class Cat(bn.ParametrizedSweep):
    kind = bn.StringSweep(["a", "b"])
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = 2.0 if self.kind == "a" else 3.0


class TwoFloat(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    y = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = self.x * self.y


def run_sweep(sweep_cls, input_vars, repeats=1) -> BenchResult:
    bench = bn.Bench("test_explain_selection", sweep_cls())
    return bench.plot_sweep(
        "sweep",
        input_vars=input_vars,
        result_vars=[sweep_cls.param.value],
        run_cfg=bn.BenchRunCfg(repeats=repeats, auto_plot=False),
    )


class TestExplainMatchesSelect(unittest.TestCase):
    """The chosen subset of explain() must equal select(), for the three canonical
    sweep shapes, with and without selection filters."""

    @classmethod
    def setUpClass(cls):
        cls.results = {
            "1_float": run_sweep(Linear, [Linear.param.x]),
            "1_cat_repeats": run_sweep(Cat, [Cat.param.kind], repeats=2),
            "2_float": run_sweep(TwoFloat, [TwoFloat.param.x, TwoFloat.param.y]),
        }

    def assert_explain_matches_select(self, data, **kwargs):
        reg = get_registry()
        selected = [(p.name, p.backend) for p in reg.select(data, **kwargs)]
        chosen = [(d.name, d.backend) for d in reg.explain(data, **kwargs) if d.chosen]
        self.assertEqual(chosen, selected)

    def test_parity_across_shapes_and_filters(self):
        for shape, res in self.results.items():
            data = res.to_bench_data()
            with self.subTest(shape=shape):
                self.assert_explain_matches_select(data)
                self.assert_explain_matches_select(data, include=["line", "violin"])
                self.assert_explain_matches_select(data, exclude=["line"])
                self.assert_explain_matches_select(data, only="table")
                self.assert_explain_matches_select(data, backend="holoviews")

    def test_every_plugin_gets_a_decision(self):
        reg = get_registry()
        data = self.results["1_float"].to_bench_data()
        decisions = reg.explain(data)
        self.assertEqual(len(decisions), len(list(reg.all())))
        self.assertTrue(all(d.reason for d in decisions))

    def test_rejection_reasons(self):
        reg = get_registry()
        data = self.results["1_float"].to_bench_data()
        by_name = {d.name: d for d in reg.explain(data)}
        violin = by_name["violin"]  # named-only builtin
        self.assertFalse(violin.chosen)
        self.assertIn("named-only", violin.reason)
        line = by_name["line"]
        self.assertTrue(line.chosen)

    def test_shape_filter_rejection_reason(self):
        """Built-ins register match_all (shape gating still lives inside to_plot),
        so use a plugin with an honest filter to exercise the mismatch reason."""

        @plot_plugin(
            name="needs_two_floats",
            backend="test",
            match=PlotFilter(
                float_range=VarRange(2, 2),
                cat_range=VarRange(0, None),
                repeats_range=VarRange(1, None),
                input_range=VarRange(1, None),
            ),
        )
        def _two_floats(_: object):
            return None

        try:
            data = self.results["1_float"].to_bench_data()
            by_name = {d.name: d for d in get_registry().explain(data)}
            decision = by_name["needs_two_floats"]
            self.assertFalse(decision.chosen)
            self.assertIn("shape filter mismatch", decision.reason)
            self.assertIn("float", decision.reason)
            # and on a matching shape it is chosen
            data2 = self.results["2_float"].to_bench_data()
            by_name2 = {d.name: d for d in get_registry().explain(data2)}
            self.assertTrue(by_name2["needs_two_floats"].chosen)
        finally:
            unregister_plugin("needs_two_floats")

    def test_only_reasons(self):
        reg = get_registry()
        data = self.results["1_float"].to_bench_data()
        decisions = reg.explain(data, only="table")
        chosen = [d for d in decisions if d.chosen]
        self.assertEqual([d.name for d in chosen], ["table"])
        self.assertIn("only", chosen[0].reason)


class TestExplainFacade(unittest.TestCase):
    def test_explain_selection_table(self):
        res = run_sweep(Linear, [Linear.param.x])
        table = res.explain_selection()
        self.assertIn("chart type", table)
        self.assertIn("line", table)
        self.assertIn("named-only", table)  # violin et al. appear with their reason
        # plot_list entries go through the same normalization as to_auto
        table_named = res.explain_selection(plot_list=["violin"])
        self.assertIn("not named in include", table_named)


if __name__ == "__main__":
    unittest.main()
