"""A plot that fails to render must leave a mark the caller can see.

``to_auto`` catches every plugin/callback failure so one bad plot cannot abort a
whole report. That is the right call, but recording it with ``logger.exception``
alone made it invisible: loggers are off by default in library use, so the report
was written *missing plots* while every caller-visible signal still said success
— no warning, a zero exit code, and an HTML file that looks complete unless you
already know which plot should have been there.
"""

import unittest
import warnings

import panel as pn

import bencher as bn
from bencher.results.render_failure import RenderFailedWarning, report_render_failure


def _failing_plot(_res, **_kwargs):
    raise RuntimeError("synthetic plot failure")


def _working_plot(_res, **_kwargs):
    return pn.pane.Markdown("WORKING_PLOT")


def _raise_overlay_failure(*_args, **_kwargs):
    raise RuntimeError("synthetic overlay failure")


def _already_handled_exception() -> ValueError:
    """An exception whose ``except`` block has been left, so ``sys.exc_info()`` is clear."""
    try:
        raise ValueError("boom")
    except ValueError as exc:
        return exc


class _OverTimeSweep(bn.ParametrizedSweep):
    """Categorical input over time — gives the regression report some history."""

    endpoint = bn.StringSweep(["a", "b"], doc="endpoint")
    latency = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)

    def benchmark(self):
        self.latency = 10.0 if self.endpoint == "a" else 20.0


class Sweep(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=[0, 2])
    y = bn.ResultFloat()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.y = self.x * 2
        return self.get_results_values_as_dict()


def _sweep_result():
    bench = bn.Bench("render_failure_visibility", Sweep())
    return bench.plot_sweep(
        "vis",
        input_vars=[Sweep.param.x],
        result_vars=[Sweep.param.y],
        run_cfg=bn.BenchRunCfg(
            execution=bn.ExecutionCfg(repeats=1), cache=bn.CacheCfg(samples=False)
        ),
        plot_callbacks=False,
    )


class TestFailureIsVisible(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _sweep_result()

    def _to_auto(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            panes = self.res.to_auto(plot_list=[_failing_plot, _working_plot])
        return panes, caught

    def test_failure_warns(self):
        """A warning reaches a test runner that never configured logging."""
        _, caught = self._to_auto()
        msgs = [str(w.message) for w in caught if issubclass(w.category, RenderFailedWarning)]
        self.assertTrue(msgs, "expected a RenderFailedWarning")
        self.assertIn("synthetic plot failure", " ".join(msgs))

    def test_failure_leaves_a_visible_pane(self):
        """The gap is legible to whoever opens the HTML, not only whoever re-runs it."""
        panes, _ = self._to_auto()
        markers = [p for p in panes if isinstance(p, pn.pane.Markdown)]
        self.assertTrue(
            any("failed to render" in m.object for m in markers),
            "expected a visible failure pane",
        )
        self.assertTrue(
            any("_failing_plot" in m.object for m in markers),
            "failure pane should name what failed",
        )

    def test_working_plot_still_renders(self):
        """One failure must not cost the plots that did work."""
        panes, _ = self._to_auto()
        objs = [getattr(p, "object", "") for p in panes]
        self.assertIn("WORKING_PLOT", objs)

    def test_failure_does_not_raise(self):
        """Unchanged contract: a bad plot never aborts the report."""
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            self.res.to_auto(plot_list=[_failing_plot])


class TestReportRenderFailureHelper(unittest.TestCase):
    def test_helper_warns_and_returns_a_pane(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            pane = report_render_failure("Thing 'x'", ValueError("boom"))
        self.assertIsInstance(pane, pn.pane.Markdown)
        self.assertIn("Thing 'x'", pane.object)
        self.assertIn("boom", pane.object)
        self.assertEqual(1, len(caught))
        self.assertTrue(issubclass(caught[0].category, RenderFailedWarning))

    def test_helper_still_logs(self):
        """Callers already capturing the logger keep working."""
        with (
            self.assertLogs(level="ERROR") as captured,
            warnings.catch_warnings(record=True),
        ):
            warnings.simplefilter("always")
            report_render_failure("Thing 'y'", ValueError("boom"))
        self.assertTrue(any("Thing 'y'" in m for m in captured.output))

    def test_logged_traceback_comes_from_the_exception(self):
        """The traceback must not depend on the caller still being in ``except``.

        The helper takes the exception explicitly, so it is legitimate to call it
        after the ``except`` block has been left. Deriving the traceback from the
        ambient ``sys.exc_info()`` instead logs a bare "no exception" placeholder
        with no traceback header at all.
        """
        exc = _already_handled_exception()
        with (
            self.assertLogs(level="ERROR") as captured,
            warnings.catch_warnings(record=True),
        ):
            warnings.simplefilter("always")
            report_render_failure("Thing 'z'", exc)
        joined = "\n".join(captured.output)
        self.assertIn("ValueError: boom", joined)
        # Only a real traceback renders this header; the sys.exc_info() fallback
        # would emit a placeholder line instead.
        self.assertIn("Traceback (most recent call last)", joined)

    def test_warning_is_publicly_importable(self):
        """Filtering the warning is the point, so the class must be public API."""
        self.assertIs(bn.RenderFailedWarning, RenderFailedWarning)


class TestRegressionOverlayFailureIsVisible(unittest.TestCase):
    """The regression overlay shares ``to_auto_plots``' best-effort contract.

    It sits ten lines above the ``extra_panels`` handler in the same function and
    had the same silent-skip problem: a regression overlay that raised vanished
    from the report with no caller-visible signal.
    """

    @classmethod
    def setUpClass(cls):
        run_cfg = bn.BenchRunCfg()
        run_cfg.time.over_time = True
        run_cfg.regression.enabled = True
        run_cfg.visualization.auto_plot = False
        run_cfg.execution.headless = True
        bench = bn.Bench("render_failure_overlay", _OverTimeSweep(), run_cfg=run_cfg)
        for i in range(2):
            run_cfg.time.clear_history = i == 0
            run_cfg.cache.clear = True
            bench.plot_sweep(
                input_vars=["endpoint"],
                result_vars=["latency"],
                run_cfg=run_cfg,
                time_src=f"2026-0{i + 1}-01 renderfail{i}",
            )
        cls.res = bench.results[-1]

    def test_failing_overlay_warns_and_leaves_a_visible_pane(self):
        report = self.res.regression_report
        self.assertIsNotNone(report, "fixture should produce a regression report")
        for r in report.results:
            self.assertIsNotNone(r.historical, "fixture needs history for the overlay path")
            r.render_overlay = _raise_overlay_failure

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            panel = self.res.to_auto_plots()

        msgs = [str(w.message) for w in caught if issubclass(w.category, RenderFailedWarning)]
        self.assertTrue(msgs, "expected a RenderFailedWarning for the failing overlay")
        self.assertIn("synthetic overlay failure", " ".join(msgs))
        self.assertIsNotNone(panel, "one bad overlay must not abort the report")
        objs = [str(getattr(p, "object", "")) for p in panel]
        self.assertTrue(
            any("Regression overlay" in o and "failed to render" in o for o in objs),
            "expected a visible failure pane naming the failing overlay",
        )


if __name__ == "__main__":
    unittest.main()
