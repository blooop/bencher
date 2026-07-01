from __future__ import annotations

import unittest
from unittest.mock import patch

import panel as pn
import xarray as xr

from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.plotting.plt_cnt_cfg import PltCntCfg
from bencher.plugins import (
    BenchData,
    PluginRegistry,
    RunMeta,
    get_registry,
    plot_plugin,
    register_plugin,
    unregister_plugin,
)


def _data_with_floats(n_floats: int) -> BenchData:
    cfg = PltCntCfg(float_cnt=n_floats, cat_cnt=0, repeats=1, inputs_cnt=n_floats)
    return BenchData.fake(plt_cnt_cfg=cfg)


def _make_pane(text: str) -> pn.viewable.Viewable:
    return pn.pane.Markdown(text)


class TestBenchData(unittest.TestCase):
    def test_fake_defaults(self) -> None:
        data = BenchData.fake()
        self.assertIsInstance(data.dataset, xr.Dataset)
        self.assertEqual(data.input_vars, ())
        self.assertEqual(data.result_vars, ())
        self.assertIsInstance(data.run_meta, RunMeta)
        self.assertIsNone(data.optimizer_study)
        self.assertEqual(data.baseline_runs, ())

    def test_has_capability(self) -> None:
        data = BenchData.fake()
        self.assertFalse(data.has("optimizer_study"))
        self.assertFalse(data.has("baseline_runs"))
        self.assertFalse(data.has("cache"))
        self.assertFalse(data.has("nonexistent"))

        data2 = data.with_changes(optimizer_study=object())
        self.assertTrue(data2.has("optimizer_study"))
        self.assertFalse(data.has("optimizer_study"), "with_changes must not mutate original")

    def test_frozen(self) -> None:
        data = BenchData.fake()
        with self.assertRaises(Exception):
            data.dataset = xr.Dataset()  # type: ignore[misc]


class TestRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = PluginRegistry()
        # Pretend entry points were already loaded so tests don't try to scan the
        # installed environment.
        self.reg.mark_entry_points_loaded()

    def test_register_and_get(self) -> None:
        @plot_plugin(name="t.foo", backend="t", match=PlotFilter(), register=False)
        def _foo(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("foo")

        self.reg.register(_foo)
        self.assertIs(self.reg.get("t.foo"), _foo)
        self.assertIn(_foo, self.reg.all())

    def test_register_requires_non_empty_name(self) -> None:
        @plot_plugin(name="x", register=False)
        def _stub(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("x")

        # Mutate to violate the contract.
        _stub.name = ""
        with self.assertRaises(ValueError):
            self.reg.register(_stub)

    def test_override_same_name_and_backend_replaces(self) -> None:
        @plot_plugin(name="dup", backend="a", register=False)
        def _a1(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("a1")

        @plot_plugin(name="dup", backend="a", register=False)
        def _a2(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("a2")

        self.reg.register(_a1)
        self.reg.register(_a2)
        self.assertIs(self.reg.get("dup"), _a2)
        self.assertEqual(len(self.reg.all()), 1)

    def test_same_name_different_backends_coexist(self) -> None:
        """The same chart type can be implemented by several backends; get(name)
        resolves to the highest-priority implementation, get(name, backend) is exact."""

        @plot_plugin(name="dup", backend="a", priority=10, register=False)
        def _a(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("a")

        @plot_plugin(name="dup", backend="b", priority=5, register=False)
        def _b(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("b")

        self.reg.register(_a)
        self.reg.register(_b)
        self.assertEqual(len(self.reg.all()), 2)
        self.assertIs(self.reg.get("dup"), _a)
        self.assertIs(self.reg.get("dup", backend="b"), _b)
        self.assertEqual(self.reg.implementations("dup"), (_a, _b))

    def test_unregister(self) -> None:
        @plot_plugin(name="t.foo", register=False)
        def _foo(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("foo")

        self.reg.register(_foo)
        self.reg.unregister("t.foo")
        self.assertIsNone(self.reg.get("t.foo"))

    def test_unregister_single_backend(self) -> None:
        @plot_plugin(name="t.foo", backend="a", register=False)
        def _a(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("a")

        @plot_plugin(name="t.foo", backend="b", register=False)
        def _b(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("b")

        self.reg.register(_a)
        self.reg.register(_b)
        self.reg.unregister("t.foo", backend="a")
        self.assertIs(self.reg.get("t.foo"), _b)
        # No backend given removes every remaining implementation.
        self.reg.unregister("t.foo")
        self.assertIsNone(self.reg.get("t.foo"))


class TestSelection(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = PluginRegistry()
        self.reg.mark_entry_points_loaded()

        self.permissive_filter = PlotFilter(
            float_range=VarRange(0, None),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(0, None),
            input_range=VarRange(0, None),
        )

        @plot_plugin(
            name="alpha",
            backend="hv",
            match=self.permissive_filter,
            priority=10,
            register=False,
        )
        def _alpha(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("alpha")

        @plot_plugin(
            name="beta",
            backend="plotly",
            match=self.permissive_filter,
            priority=5,
            register=False,
        )
        def _beta(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("beta")

        @plot_plugin(name="gamma", backend="hv", match=PlotFilter(), register=False)
        def _gamma(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("gamma")  # default PlotFilter never matches

        self.alpha, self.beta, self.gamma = _alpha, _beta, _gamma
        for p in (_alpha, _beta, _gamma):
            self.reg.register(p)

    def test_priority_order(self) -> None:
        data = _data_with_floats(1)
        names = [p.name for p in self.reg.select(data)]
        self.assertEqual(names, ["alpha", "beta"])  # gamma's filter excludes it

    def test_backend_preference_swaps_implementation(self) -> None:
        """`backend` states a preference: chart types the preferred backend implements
        swap to it; chart types it does not implement keep their best other backend.
        This is what lets one flag change the rendering library under the same plotters."""

        @plot_plugin(
            name="alpha",
            backend="plotly",
            match=self.permissive_filter,
            priority=1,
            register=False,
        )
        def _alpha_plotly(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("alpha-plotly")

        self.reg.register(_alpha_plotly)
        data = _data_with_floats(1)

        # No preference: highest-priority implementation per chart type.
        chosen = {p.name: p.backend for p in self.reg.select(data)}
        self.assertEqual(chosen, {"alpha": "hv", "beta": "plotly"})

        # Preferring plotly swaps alpha's implementation; beta already plotly.
        chosen = {p.name: p.backend for p in self.reg.select(data, backend="plotly")}
        self.assertEqual(chosen, {"alpha": "plotly", "beta": "plotly"})

        # Preferring hv keeps beta (only implemented in plotly) available.
        chosen = {p.name: p.backend for p in self.reg.select(data, backend="hv")}
        self.assertEqual(chosen, {"alpha": "hv", "beta": "plotly"})

    def test_select_dedupes_chart_types(self) -> None:
        """select() returns one implementation per chart type, not one per backend."""

        @plot_plugin(
            name="alpha",
            backend="plotly",
            match=self.permissive_filter,
            priority=1,
            register=False,
        )
        def _alpha_plotly(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("alpha-plotly")

        self.reg.register(_alpha_plotly)
        names = [p.name for p in self.reg.select(_data_with_floats(1))]
        self.assertEqual(sorted(names), ["alpha", "beta"])

    def test_include_exclude(self) -> None:
        data = _data_with_floats(1)
        self.assertEqual([p.name for p in self.reg.select(data, include=["alpha"])], ["alpha"])
        self.assertEqual([p.name for p in self.reg.select(data, exclude=["alpha"])], ["beta"])

    def test_only_short_circuits_filter(self) -> None:
        # `only` bypasses the match filter — gamma's default filter rejects everything,
        # but explicit selection by name should still succeed.
        data = _data_with_floats(1)
        picked = self.reg.select(data, only="gamma")
        self.assertEqual([p.name for p in picked], ["gamma"])

    def test_only_unknown_returns_empty(self) -> None:
        data = _data_with_floats(1)
        self.assertEqual(self.reg.select(data, only="nope"), ())

    def test_requires_capability_gating(self) -> None:
        @plot_plugin(
            name="needs_optimizer",
            backend="t",
            match=self.permissive_filter,
            requires={"optimizer_study"},
            register=False,
        )
        def _p(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("o")

        self.reg.register(_p)
        data = _data_with_floats(1)
        self.assertNotIn("needs_optimizer", [p.name for p in self.reg.select(data)])

        data2 = data.with_changes(optimizer_study=object())
        self.assertIn("needs_optimizer", [p.name for p in self.reg.select(data2)])


class TestRender(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = PluginRegistry()
        self.reg.mark_entry_points_loaded()
        self.permissive = PlotFilter(
            float_range=VarRange(0, None),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(0, None),
            input_range=VarRange(0, None),
        )

    def test_render_happy_path(self) -> None:
        @plot_plugin(name="ok", match=self.permissive, register=False)
        def _ok(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("ok-out")

        self.reg.register(_ok)
        rendered = self.reg.render(_data_with_floats(1))
        self.assertEqual(len(rendered), 1)
        name, pane = rendered[0]
        self.assertEqual(name, "ok")
        self.assertIsInstance(pane, pn.viewable.Viewable)

    def test_render_substitutes_error_pane(self) -> None:
        @plot_plugin(name="boom", match=self.permissive, register=False)
        def _boom(_: BenchData) -> pn.viewable.Viewable:
            raise RuntimeError("intentional test failure")

        self.reg.register(_boom)
        rendered = self.reg.render(_data_with_floats(1))
        self.assertEqual(len(rendered), 1)
        name, pane = rendered[0]
        self.assertEqual(name, "boom")
        self.assertIsInstance(pane, pn.pane.Markdown)
        self.assertIn("Plugin error", str(pane.object))
        self.assertIn("intentional test failure", str(pane.object))

    def test_render_strict_reraises(self) -> None:
        @plot_plugin(name="boom", match=self.permissive, register=False)
        def _boom(_: BenchData) -> pn.viewable.Viewable:
            raise RuntimeError("intentional test failure")

        self.reg.register(_boom)
        with self.assertRaises(RuntimeError):
            self.reg.render(_data_with_floats(1), strict=True)

    def test_render_one_failing_does_not_kill_others(self) -> None:
        @plot_plugin(name="ok", match=self.permissive, priority=1, register=False)
        def _ok(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("ok")

        @plot_plugin(name="boom", match=self.permissive, priority=0, register=False)
        def _boom(_: BenchData) -> pn.viewable.Viewable:
            raise ValueError("nope")

        self.reg.register(_ok)
        self.reg.register(_boom)
        rendered = self.reg.render(_data_with_floats(1))
        names = [name for name, _ in rendered]
        self.assertEqual(names, ["ok", "boom"])


class TestGlobalRegistration(unittest.TestCase):
    """Smoke-test the global registry shortcuts. Cleans up after itself."""

    def tearDown(self) -> None:
        unregister_plugin("global.smoke")

    def test_register_and_get_registry(self) -> None:
        @plot_plugin(name="global.smoke", match=PlotFilter())
        def _smoke(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("smoke")

        self.assertIs(get_registry().get("global.smoke"), _smoke)

    def test_register_plugin_function(self) -> None:
        @plot_plugin(name="global.smoke", match=PlotFilter(), register=False)
        def _smoke(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("smoke")

        register_plugin(_smoke)
        self.assertIs(get_registry().get("global.smoke"), _smoke)

    def test_default_match_is_always_eligible(self) -> None:
        """A plugin declared without a match rule must be selectable for any sweep
        shape — PlotFilter()'s empty default ranges would silently hide it forever."""
        reg = PluginRegistry()
        reg.mark_entry_points_loaded()

        @plot_plugin(name="global.smoke", register=False)
        def _smoke(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("smoke")

        reg.register(_smoke)
        for n_floats in (0, 1, 3):
            selected = reg.select(_data_with_floats(n_floats))
            self.assertEqual([p.name for p in selected], ["global.smoke"])


class TestPlotFilterMatchAll(unittest.TestCase):
    def test_match_all_matches_various_shapes(self) -> None:
        f = PlotFilter.match_all()
        for cfg in (
            PltCntCfg(),
            PltCntCfg(float_cnt=3, cat_cnt=2, repeats=5, inputs_cnt=5),
            PltCntCfg(panel_cnt=2, vector_len=4, result_vars=3),
        ):
            self.assertTrue(f.matches_result(cfg, "match_all", override=False).overall)

    def test_default_plot_filter_matches_nothing(self) -> None:
        # Documents the existing default: PlotFilter() is restrictive by design.
        self.assertFalse(PlotFilter().matches_result(PltCntCfg(), "default", False).overall)


class TestEntryPointDiscovery(unittest.TestCase):
    """Verify the entry-point loader is lazy and tolerant of failures."""

    def test_lazy_load_on_first_lookup(self) -> None:
        reg = PluginRegistry()
        with patch("bencher.plugins.registry.metadata.entry_points") as ep_mock:
            ep_mock.return_value = []
            reg.all()
            ep_mock.assert_called_once()
            # Second call must not re-scan.
            reg.all()
            ep_mock.assert_called_once()

    def test_skip_on_load_failure(self) -> None:
        reg = PluginRegistry()

        class FakeEP:
            name = "broken"

            def load(self):
                raise ImportError("simulated missing dep")

        with patch("bencher.plugins.registry.metadata.entry_points") as ep_mock:
            ep_mock.return_value = [FakeEP()]
            # Must not raise — broken plugin is skipped.
            reg.all()
            self.assertEqual(reg.all(), ())

    def test_load_plugin_instance(self) -> None:
        @plot_plugin(name="ep.alpha", match=PlotFilter(), register=False)
        def _alpha(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("alpha")

        reg = PluginRegistry()

        class FakeEP:
            name = "alpha"

            def load(self):  # noqa: ARG002 - mock signature
                return _alpha

        with patch("bencher.plugins.registry.metadata.entry_points") as ep_mock:
            ep_mock.return_value = [FakeEP()]
            self.assertIs(reg.get("ep.alpha"), _alpha)

    def test_load_factory_returning_iterable(self) -> None:
        @plot_plugin(name="ep.one", match=PlotFilter(), register=False)
        def _one(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("one")

        @plot_plugin(name="ep.two", match=PlotFilter(), register=False)
        def _two(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("two")

        def factory():
            return [_one, _two]

        reg = PluginRegistry()

        class FakeEP:
            name = "factory"

            def load(self):  # noqa: ARG002 - mock signature
                return factory

        with patch("bencher.plugins.registry.metadata.entry_points") as ep_mock:
            ep_mock.return_value = [FakeEP()]
            names = sorted(p.name for p in reg.all())
            self.assertEqual(names, ["ep.one", "ep.two"])


if __name__ == "__main__":
    unittest.main()
