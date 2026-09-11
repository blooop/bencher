"""Contract: where the pane group sits among ``to_auto_plots``' report sections.

Plugin priority orders one ``to_auto`` call. It cannot reach this file's subject,
which is a level up: ``to_auto_plots`` composes the tab out of sections -- sweep
summary, failed samples, regression, ``extra_panels``, the pane group, Aggregated
View, Over Time, the chart grid, post-description -- and a sweep whose subject is a
per-sample recording had its viewer below the aggregate curves derived from it.

The assertions are on the resulting section order and count, never on how the split
is implemented, so a rewrite that keeps the layout keeps them green.
"""

from __future__ import annotations

import unittest

import panel as pn
from PIL import Image, ImageDraw

import bencher as bn
from bencher.plugins import plot_plugin, unregister_plugin
from bencher.plugins.builtins import PANES_PLUGIN_NAME, register_builtin_plugins
from bencher.results.bench_result import NO_PLOTTERS_MESSAGE

PANE_MARKER = "pane-group-marker"
AGGREGATED_HEADING = "### Aggregated View"


class PaneAndMetric(bn.ParametrizedSweep):
    """A pane-typed result beside a numeric one, so both sections have content."""

    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    picture = bn.ResultImage()
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        path = bn.gen_image_path("report_section_order")
        img = Image.new("RGB", (16, 16), (0, 0, 0))
        ImageDraw.Draw(img).line([(0, 0), (15, int(self.x * 7))], fill=(255, 0, 0))
        img.save(path, "PNG")
        self.picture = path
        self.value = self.x * 2.0


class MetricOnly(bn.ParametrizedSweep):
    """Nothing pane-typed: the pane group must add no section at all."""

    x = bn.FloatSweep(default=0, bounds=[0, 2], samples=3)
    value = bn.ResultFloat(units="m")

    def benchmark(self):
        self.value = self.x * 2.0


def _run(sweep_cls, **plot_sweep_kwargs):
    bench = bn.Bench("test_report_section_order", sweep_cls())
    return bench.plot_sweep(
        "sweep",
        input_vars=["x"],
        result_vars=[v for v in ("picture", "value") if hasattr(sweep_cls, v)],
        run_cfg=bn.BenchRunCfg(repeats=1, cache_results=False, cache_samples=False),
        auto_plot=False,
        **plot_sweep_kwargs,
    )


def _walk(obj):
    """Every pane in a section's subtree. Sections arrive as bare ``pn.Column``s, so
    what a section *is* has to be read from what it contains."""
    yield obj
    for child in getattr(obj, "objects", None) or ():
        yield from _walk(child)


def _sections_holding(plots, text: str) -> list[int]:
    """Indices of the report sections whose subtree carries this markdown text."""
    return [
        i
        for i, section in enumerate(plots)
        if any(getattr(p, "object", None) == text for p in _walk(section))
    ]


def _sections_holding_type(plots, pane_type: type) -> list[int]:
    return [
        i
        for i, section in enumerate(plots)
        if any(isinstance(p, pane_type) for p in _walk(section))
    ]


def _heading_index(plots) -> int:
    """The Aggregated View heading, which is a section in its own right."""
    for i, section in enumerate(plots):
        obj = getattr(section, "object", None)
        if isinstance(obj, str) and obj.startswith(AGGREGATED_HEADING):
            return i
    raise AssertionError("no Aggregated View section, so nothing was ordered")


class TestPaneGroupPlacement(unittest.TestCase):
    """The pane group's slot, pinned with a stub renderer.

    A stub, because the question is where the pane group's output lands and how many
    times, and the real renderer's output is a ``pn.Column`` indistinguishable at a
    glance from the chart grid's. A uniquely-named marker is unambiguous wherever it
    appears. The real renderer gets its own class below.
    """

    @classmethod
    def setUpClass(cls):
        cls.res = _run(PaneAndMetric, aggregate=["x"])

    def setUp(self):
        # Same (name, backend) as the built-in, which is the documented override.
        @plot_plugin(name=PANES_PLUGIN_NAME, backend="panel", priority=100)
        def _stub(_data) -> pn.viewable.Viewable:
            return pn.pane.Markdown(PANE_MARKER)

        self.addCleanup(register_builtin_plugins)
        self.addCleanup(unregister_plugin, PANES_PLUGIN_NAME)

    def _panes_at(self, **kwargs) -> tuple[list, list[int]]:
        plots = list(self.res.to_auto_plots(**kwargs))
        return plots, _sections_holding(plots, PANE_MARKER)

    def test_the_pane_group_comes_before_the_aggregated_view(self):
        plots, at = self._panes_at()
        self.assertTrue(at, "the pane group rendered nowhere")
        self.assertLess(at[0], _heading_index(plots))

    def test_the_pane_group_renders_exactly_once(self):
        """Rendering it early is worth nothing if the grid draws it again below."""
        _, at = self._panes_at()
        self.assertEqual(len(at), 1)

    def test_the_pane_group_follows_the_sweep_summary_and_extra_panels(self):
        """Regression is a warning and extra_panels is the caller's own injection, so
        both keep their place above the default layout."""
        injected = pn.pane.Markdown("### Injected")
        plots = list(self.res.to_auto_plots(extra_panels=[injected]))
        at = _sections_holding(plots, PANE_MARKER)
        self.assertTrue(at)
        self.assertGreater(at[0], plots.index(injected))

    def test_a_caller_removing_the_pane_group_gets_none_of_it(self):
        """The downstream workaround this replaces passed exactly this, to stop a
        double render; resurrecting the pane group here would undo the caller."""
        _, at = self._panes_at(remove_plots=[PANES_PLUGIN_NAME])
        self.assertEqual(at, [])

    def test_a_caller_restricting_plot_list_to_a_chart_gets_none_of_it(self):
        _, at = self._panes_at(plot_list=["line"])
        self.assertEqual(at, [])

    def test_a_numeric_only_caller_gets_none_of_it(self):
        _, at = self._panes_at(numeric_only=True)
        self.assertEqual(at, [])

    def test_a_caller_asking_only_for_the_pane_group_gets_it_once_and_no_placeholder(self):
        """The grid is empty once the pane group is lifted out of it, and its "nothing
        to show" placeholder would be a lie about a report that just showed something."""
        plots, at = self._panes_at(plot_list=[PANES_PLUGIN_NAME])
        self.assertEqual(len(at), 1)
        self.assertEqual(_sections_holding(plots, NO_PLOTTERS_MESSAGE), [])


class TestRealRenderer(unittest.TestCase):
    """The same placement through the real ``PaneResult.to_panes``, and the layout a
    sweep with nothing pane-typed must keep."""

    def test_the_images_come_before_the_aggregated_heading(self):
        plots = list(_run(PaneAndMetric, aggregate=["x"]).to_auto_plots())
        images = _sections_holding_type(plots, pn.pane.PNG)
        self.assertTrue(images, "no image section rendered, so nothing was ordered")
        self.assertLess(images[0], _heading_index(plots))
        # The first image section is the pane group, so it carries no chart. The grid
        # below holds images too -- the line plot's tap stream shows the hovered
        # sample -- which is why counting PNGs cannot stand in for counting sections.
        self.assertNotIn(images[0], _sections_holding_type(plots, pn.pane.HoloViews))

    def test_a_chart_only_sweep_keeps_its_layout(self):
        """Three sections, as before: sweep summary, chart grid, post-description. No
        empty pane section, no stray heading, no "nothing to show" placeholder."""
        plots = list(_run(MetricOnly).to_auto_plots())
        self.assertEqual(len(plots), 3)
        self.assertEqual(_sections_holding(plots, NO_PLOTTERS_MESSAGE), [])
        self.assertEqual(_sections_holding_type(plots, pn.pane.HoloViews), [1])

    def test_a_sweep_nothing_can_draw_still_says_so(self):
        """Dropping the empty grid is conditional on the pane group having drawn, so a
        report with nothing in it at all keeps its explanation."""
        plots = list(_run(MetricOnly).to_auto_plots(plot_list=["volume"]))
        self.assertTrue(
            _sections_holding(plots, NO_PLOTTERS_MESSAGE),
            "the empty-report explanation went missing",
        )


if __name__ == "__main__":
    unittest.main()
