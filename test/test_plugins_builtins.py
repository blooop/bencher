"""Tests for the built-in plot plugins and the registry-dispatched to_auto path
(A1 Phase 2: built-ins wrapped as plugins, no renderer logic changes)."""

import unittest

import panel as pn

import bencher as bn
from bencher.plotting.plot_filter import PlotFilter
from bencher.plugins import BenchData, get_registry, plot_plugin, unregister_plugin
from bencher.plugins.builtins import (
    CALLBACK_TO_PLUGIN,
    LegacyResultPlugin,
    register_builtin_plugins,
)
from bencher.results.bench_result import BenchResult
from bencher.results.holoview_results.line_result import LineResult

BUILTIN_ORDER = ["bar", "box_whisker", "curve", "line", "heatmap", "histogram", "volume", "panes"]


class Linear(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = self.x * 2.0


class FloatCat(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    kind = bn.StringSweep(["a", "b"])
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = self.x * (2.0 if self.kind == "a" else 3.0)


def run_sweep(sweep_cls=Linear, repeats: int = 1) -> BenchResult:
    bench = bn.Bench("test_plugins_builtins", sweep_cls())
    return bench.plot_sweep(
        "sweep",
        input_vars=[v for v in ("x", "kind") if hasattr(sweep_cls, v)],
        result_vars=["value"],
        run_cfg=bn.BenchRunCfg(repeats=repeats, cache_results=False, cache_samples=False),
        auto_plot=False,
    )


def _pane_types(panes) -> list[type]:
    return [type(p) for p in panes]


class TestBuiltinRegistration(unittest.TestCase):
    def test_builtins_registered_on_import(self):
        names = [p.name for p in get_registry().all()]
        for name in BUILTIN_ORDER:
            self.assertIn(name, names)

    def test_priority_encodes_legacy_order(self):
        reg = get_registry()
        priorities = [reg.get(name).priority for name in BUILTIN_ORDER]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_callback_mapping_covers_default_callbacks(self):
        for cb in BenchResult.default_plot_callbacks():
            self.assertIn(cb, CALLBACK_TO_PLUGIN)

    def test_registration_is_idempotent(self):
        before = len(get_registry().all())
        register_builtin_plugins()
        self.assertEqual(len(get_registry().all()), before)

    def test_builtins_require_legacy_result(self):
        plugin = get_registry().get("line")
        self.assertIn("legacy_result", plugin.requires)
        # A pure BenchData (no live result) must not select the wrapped built-ins.
        self.assertNotIn(plugin, get_registry().select(BenchData.fake()))


class TestToAutoParity(unittest.TestCase):
    """The registry-dispatched to_auto must reproduce the legacy callback loop."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep()

    def legacy_to_auto(self, **kwargs) -> list:
        """The pre-plugin to_auto loop, reproduced verbatim for comparison."""
        panes = []
        plot_kwargs = self.res.set_plot_size(**kwargs)
        self.res.plt_cnt_cfg.print_debug = False  # as to_auto does; silences mismatch panes
        try:
            for cb in BenchResult.default_plot_callbacks():
                try:
                    pane = cb(self.res, override=False, **plot_kwargs)
                except Exception:  # pylint: disable=broad-except
                    pane = None
                if pane is not None:
                    panes.append(pane)
        finally:
            self.res.plt_cnt_cfg.print_debug = True
        return panes

    def test_default_output_matches_legacy(self):
        new = list(self.res.to_auto())
        legacy = self.legacy_to_auto()
        self.assertEqual(_pane_types(new), _pane_types(legacy))

    def test_default_output_matches_legacy_float_cat_repeats(self):
        """Richer shape: float + cat inputs with repeats activates bar/box/curve paths."""
        res = run_sweep(FloatCat, repeats=2)
        plot_kwargs = res.set_plot_size()
        res.plt_cnt_cfg.print_debug = False
        legacy = []
        try:
            for cb in BenchResult.default_plot_callbacks():
                try:
                    pane = cb(res, override=False, **plot_kwargs)
                except Exception:  # pylint: disable=broad-except
                    pane = None
                if pane is not None:
                    legacy.append(pane)
        finally:
            res.plt_cnt_cfg.print_debug = True
        new = list(res.to_auto())
        self.assertEqual(_pane_types(new), _pane_types(legacy))
        self.assertGreaterEqual(len(new), 1)

    def test_plot_list_name_and_callable_equivalent(self):
        by_callable = self.res.to_auto(plot_list=[LineResult.to_plot])
        by_name = self.res.to_auto(plot_list=["line"])
        self.assertEqual(_pane_types(by_callable), _pane_types(by_name))
        self.assertGreater(len(by_name), 0)

    def test_remove_plots_by_name(self):
        # On this 1-float sweep only the line plot matches, so removing it by
        # name leaves nothing and the placeholder message appears.
        full = self.res.to_auto()
        self.assertGreaterEqual(len(full), 1)
        removed = self.res.to_auto(remove_plots=["line"])
        self.assertEqual(len(removed), 1)
        self.assertIn("No Plotters", removed[0].object)

    def test_numeric_only_excludes_panes(self):
        reg = get_registry()
        data = self.res.to_bench_data()
        selected_names = [p.name for p in reg.select(data)]
        self.assertIn("panes", selected_names)
        # numeric_only routes through exclude; verify against the select() call to_auto makes
        numeric_names = [p.name for p in reg.select(data, exclude={"panes"})]
        self.assertNotIn("panes", numeric_names)
        # and the end-to-end call still renders something
        self.assertGreater(len(self.res.to_auto(numeric_only=True)), 0)

    def test_unknown_callable_still_invoked(self):
        def marker(res, **kwargs):  # pylint: disable=unused-argument
            return pn.pane.Markdown("marker")

        panes = self.res.to_auto(plot_list=[marker])
        self.assertEqual([p.object for p in panes], ["marker"])


class TestUserPluginsInToAuto(unittest.TestCase):
    """User plugins registered against the global registry appear in reports."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep()

    def tearDown(self):
        unregister_plugin("user.extra")
        unregister_plugin("line")
        register_builtin_plugins()

    def test_user_plugin_rendered_by_default(self):
        @plot_plugin(name="user.extra")
        def _extra(data: BenchData) -> pn.viewable.Viewable:
            return pn.pane.Markdown(f"user plugin: {len(data.dataset.data_vars)} vars")

        panes = self.res.to_auto()
        markdowns = [p.object for p in panes if isinstance(p, pn.pane.Markdown)]
        self.assertTrue(any("user plugin" in m for m in markdowns))

    def test_user_plugin_receives_bench_data(self):
        seen = {}

        @plot_plugin(name="user.extra")
        def _extra(data: BenchData) -> pn.viewable.Viewable:
            seen["dataset"] = data.dataset
            seen["plt_cnt_cfg"] = data.plt_cnt_cfg
            return pn.pane.Markdown("ok")

        self.res.to_auto()
        self.assertIs(seen["dataset"], self.res.ds)
        self.assertIs(seen["plt_cnt_cfg"], self.res.plt_cnt_cfg)

    def test_override_builtin_by_name(self):
        @plot_plugin(name="line", priority=85)
        def _my_line(_: BenchData) -> pn.viewable.Viewable:
            return pn.pane.Markdown("replaced line")

        panes = self.res.to_auto(plot_list=["line"])
        self.assertEqual([p.object for p in panes], ["replaced line"])

    def test_failing_user_plugin_logged_not_raised(self):
        @plot_plugin(name="user.extra")
        def _boom(_: BenchData) -> pn.viewable.Viewable:
            raise RuntimeError("intentional plugin failure")

        with self.assertLogs(level="ERROR") as captured:
            panes = self.res.to_auto()
        self.assertTrue(any("user.extra" in msg for msg in captured.output))
        self.assertGreater(len(panes), 0)


class TestToBenchData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep()

    def test_fields(self):
        data = self.res.to_bench_data()
        self.assertIs(data.dataset, self.res.ds)
        self.assertEqual([v.name for v in data.input_vars], ["x"])
        self.assertEqual([v.name for v in data.result_vars], ["value"])
        self.assertIs(data.plt_cnt_cfg, self.res.plt_cnt_cfg)
        self.assertIs(data.legacy_result, self.res)
        self.assertTrue(data.has("legacy_result"))

    def test_render_kwargs_passthrough(self):
        data = self.res.to_bench_data(render_kwargs={"override": True})
        self.assertEqual(data.render_kwargs, {"override": True})


class TestLegacyResultPlugin(unittest.TestCase):
    def test_render_delegates_with_kwargs(self):
        calls = {}

        def fake_callback(result, **kwargs):
            calls["result"] = result
            calls["kwargs"] = kwargs
            return pn.pane.Markdown("out")

        plugin = LegacyResultPlugin(
            name="fake",
            backend="test",
            match=PlotFilter.match_all(),
            priority=0,
            requires=frozenset({"legacy_result"}),
            callback=fake_callback,
        )
        marker = object()
        data = BenchData.fake().with_changes(legacy_result=marker, render_kwargs={"override": True})
        pane = plugin.render(data)
        self.assertEqual(pane.object, "out")
        self.assertIs(calls["result"], marker)
        self.assertEqual(calls["kwargs"], {"override": True})


if __name__ == "__main__":
    unittest.main()
