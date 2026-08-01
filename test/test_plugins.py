from __future__ import annotations

import dataclasses
import unittest
from unittest.mock import patch

import panel as pn
import xarray as xr

from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.plotting.plt_cnt_cfg import PltCntCfg
from bencher.plugins import (
    BenchData,
    Capability,
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

        data2 = data.with_changes(optimizer_study=object())
        self.assertTrue(data2.has("optimizer_study"))
        self.assertFalse(data.has("optimizer_study"), "with_changes must not mutate original")

    def test_has_capability_accepts_enum(self) -> None:
        data = BenchData.fake().with_changes(cache=object())
        self.assertTrue(data.has(Capability.CACHE))
        self.assertTrue(data.has("cache"))

    def test_has_unknown_capability_raises(self) -> None:
        """An unknown capability name raises (with the valid vocabulary) instead of
        silently reading as 'absent' (plan 23 C10)."""
        data = BenchData.fake()
        with self.assertRaises(ValueError) as ctx:
            data.has("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))
        for cap in Capability:
            self.assertIn(cap.value, str(ctx.exception))

    def test_frozen(self) -> None:
        data = BenchData.fake()
        # frozen dataclasses raise FrozenInstanceError, a subclass of AttributeError
        with self.assertRaises(AttributeError):
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

    def test_register_typoed_capability_raises(self) -> None:
        """A misspelled capability in requires raises at registration, naming the bad
        string and the valid vocabulary, instead of yielding a plugin that is
        permanently, silently unselectable (plan 23 C10)."""

        @plot_plugin(
            name="typo",
            backend="t",
            requires={"legacy_resutl"},  # cspell:disable-line
            register=False,
        )
        def _stub(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("x")

        with self.assertRaises(ValueError) as ctx:
            self.reg.register(_stub)
        msg = str(ctx.exception)
        self.assertIn("legacy_resutl", msg)  # cspell:disable-line
        self.assertIn("typo", msg)
        for cap in Capability:
            self.assertIn(cap.value, msg)

    def test_select_does_not_abort_on_post_registration_capability_mutation(self) -> None:
        """Selection runs mid-run, after an expensive sweep, and both production call
        sites leave select() outside their try/except. A plugin whose `requires` went
        bad after registration is rejected with a reason, not raised (never crash
        mid-run)."""

        @plot_plugin(
            name="mutated",
            backend="t",
            match=PlotFilter(
                float_range=VarRange.unbounded(),
                cat_range=VarRange.unbounded(),
                repeats_range=VarRange.unbounded(),
                input_range=VarRange.unbounded(),
            ),
            register=False,
        )
        def _stub(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("x")

        self.reg.register(_stub)
        _stub.requires = frozenset({"bogus_capability"})  # mutate after registration

        data = _data_with_floats(1)
        with self.assertLogs("bencher.plugins.registry", level="WARNING"):
            self.assertEqual(self.reg.select(data), ())
        reasons = [d.reason for d in self.reg.explain(data) if d.name == "mutated"]
        self.assertIn("invalid capability", reasons[0])

    def test_register_valid_capability_strings_accepted(self) -> None:
        """External plugins passing valid plain strings keep working."""

        @plot_plugin(
            name="valid_caps",
            backend="t",
            requires={"legacy_result", "cache"},
            register=False,
        )
        def _stub(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("x")

        self.reg.register(_stub)
        self.assertIs(self.reg.get("valid_caps"), _stub)

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
            float_range=VarRange.unbounded(),
            cat_range=VarRange.unbounded(),
            repeats_range=VarRange.unbounded(),
            input_range=VarRange.unbounded(),
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

        # gamma opts out of every shape explicitly; selection must skip it.
        @plot_plugin(
            name="gamma",
            backend="hv",
            match=PlotFilter(float_range=VarRange.none()),
            register=False,
        )
        def _gamma(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("gamma")

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

    def test_named_only_plugin_requires_explicit_naming(self) -> None:
        """auto=False plugins never appear in automatic selection, but naming them
        via include or only selects them."""

        @plot_plugin(
            name="delta",
            backend="hv",
            match=self.permissive_filter,
            priority=20,
            register=False,
            auto=False,
        )
        def _delta(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("delta")

        self.reg.register(_delta)
        data = _data_with_floats(1)
        self.assertNotIn("delta", [p.name for p in self.reg.select(data)])
        self.assertEqual([p.name for p in self.reg.select(data, include=["delta"])], ["delta"])
        self.assertEqual([p.name for p in self.reg.select(data, only="delta")], ["delta"])

    def test_plugin_without_auto_attribute_is_automatic(self) -> None:
        """Plugins predating the `auto` attribute must keep appearing automatically."""
        permissive = self.permissive_filter

        class NoAutoAttr:
            name = "epsilon"
            backend = "hv"
            match = permissive
            priority = 1
            requires = frozenset()

            def render(self, _: BenchData) -> pn.viewable.Viewable:
                return _make_pane("epsilon")

        self.reg.register(NoAutoAttr())
        self.assertIn("epsilon", [p.name for p in self.reg.select(_data_with_floats(1))])

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
            float_range=VarRange.unbounded(),
            cat_range=VarRange.unbounded(),
            repeats_range=VarRange.unbounded(),
            input_range=VarRange.unbounded(),
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
        shape. Before plan 23 P6 the default ranges were empty, so a plugin author
        who wrote the obvious ``match=PlotFilter()`` hid it forever."""
        reg = PluginRegistry()
        reg.mark_entry_points_loaded()

        @plot_plugin(name="global.smoke", register=False)
        def _smoke(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("smoke")

        reg.register(_smoke)
        for n_floats in (0, 1, 3):
            selected = reg.select(_data_with_floats(n_floats))
            self.assertEqual([p.name for p in selected], ["global.smoke"])


class TestDefaultPlotFilterIsPermissive(unittest.TestCase):
    """Plan 23 P6 (C3): a default-constructed filter can no longer hide a plugin.

    ``PlotFilter.match_all()`` used to exist only because ``PlotFilter()`` matched
    nothing; every field now defaults to ``VarRange.unbounded()`` and the classmethod
    is gone."""

    SHAPES = (
        PltCntCfg(),
        PltCntCfg(float_cnt=3, cat_cnt=2, repeats=5, inputs_cnt=5),
        PltCntCfg(panel_cnt=2),
    )

    def test_default_filter_matches_various_shapes(self) -> None:
        f = PlotFilter()
        for cfg in self.SHAPES:
            self.assertTrue(f.matches_result(cfg, "default", override=False).overall)

    def test_match_all_is_gone(self) -> None:
        self.assertFalse(hasattr(PlotFilter, "match_all"))

    def test_plugin_without_a_match_rule_is_never_hidden(self) -> None:
        """The plugin.py footgun: declaring a plugin with no match rule, or with the
        obvious ``match=PlotFilter()``, must leave it eligible for every shape."""
        reg = PluginRegistry()
        reg.mark_entry_points_loaded()

        @plot_plugin(name="p6.implicit", register=False)
        def _implicit(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("implicit")

        @plot_plugin(name="p6.explicit", match=PlotFilter(), register=False)
        def _explicit(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("explicit")

        reg.register(_implicit)
        reg.register(_explicit)
        for cfg in self.SHAPES:
            data = BenchData.fake(plt_cnt_cfg=cfg)
            names = sorted(p.name for p in reg.select(data))
            self.assertEqual(names, ["p6.explicit", "p6.implicit"], msg=str(cfg))


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

    def test_skip_entry_point_with_bad_capability(self) -> None:
        """Entry-point loading is lazy (first lookup, possibly mid-run), so a
        third-party plugin with an invalid capability is skipped with a visible
        warning instead of aborting the run; explicit register() still raises
        (plan 23 C10 + the never-crash-mid-run principle)."""

        @plot_plugin(name="ep_typo", backend="t", requires={"nope"}, register=False)
        def _stub(_: BenchData) -> pn.viewable.Viewable:
            return _make_pane("x")

        class FakeEP:
            name = "ep_typo"

            def load(self):
                return _stub

        reg = PluginRegistry()
        with patch("bencher.plugins.registry.metadata.entry_points") as ep_mock:
            ep_mock.return_value = [FakeEP()]
            with self.assertLogs("bencher.plugins.registry", level="WARNING") as cm:
                self.assertEqual(reg.all(), ())
        self.assertIn("nope", "\n".join(cm.output))

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

            def load(self):
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

            def load(self):
                return factory

        with patch("bencher.plugins.registry.metadata.entry_points") as ep_mock:
            ep_mock.return_value = [FakeEP()]
            names = sorted(p.name for p in reg.all())
            self.assertEqual(names, ["ep.one", "ep.two"])


class TestDeletedPlotGates(unittest.TestCase):
    """Plan 23 P6 (C4): ``vector_len`` and ``result_vars`` are gone.

    They were declared on both ``PltCntCfg`` and ``PlotFilter`` and read on
    every plot-selection pass, but nothing in the package ever assigned the
    ``PltCntCfg`` side -- so both always held their default ``1`` and both
    gates (``VarRange.exactly(1)``) always passed. They could not filter anything,
    including ``surface_result``'s "exactly one scalar result" intent, which
    is why deleting them leaves plot selection byte-identical.

    Populating them instead would have been the breaking option: with every
    filter defaulting to ``VarRange.exactly(1)``, a real ``vector_len`` would have
    made *every* plot reject any sweep containing a ``ResultVec(size > 1)``,
    and a real ``result_vars`` would have made every plot reject any sweep
    with more than one result variable -- which is most of them.
    """

    def test_plt_cnt_cfg_no_longer_declares_them(self):
        params = PltCntCfg.param.objects()
        self.assertNotIn("vector_len", params)
        self.assertNotIn("result_vars", params)

    def test_plot_filter_no_longer_declares_them(self):
        fields = {f.name for f in dataclasses.fields(PlotFilter)}
        self.assertNotIn("vector_len", fields)
        self.assertNotIn("result_vars", fields)

    def test_selection_ignores_them(self):
        # A sweep shape that the deleted gates would have rejected had they
        # ever been populated still matches a permissive filter.
        cfg = PltCntCfg(float_cnt=1, cat_cnt=0, panel_cnt=0, repeats=1, inputs_cnt=1)
        res = PlotFilter(
            float_range=VarRange.exactly(1),
            cat_range=VarRange.unbounded(),
            panel_range=VarRange.unbounded(),
            repeats_range=VarRange.at_least(1),
            input_range=VarRange.at_least(1),
        ).matches_result(cfg, "probe", False)
        self.assertTrue(res.overall)


if __name__ == "__main__":
    unittest.main()
