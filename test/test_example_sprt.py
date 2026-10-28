"""The SPRT gallery example sweeps the true failure rate and reports what the SPRT decides."""

import xml.etree.ElementTree as ET

import panel as pn

import bencher as bn
from bencher.example.example_sprt import example_sprt


def test_example_sprt_sweeps_the_failure_rate():
    run_cfg = bn.BenchRunCfg(clear_cache=True, auto_plot=False)
    bench = example_sprt(run_cfg, trials=200)
    ds = bench.results[-1].ds
    flaky = ds["flaky_rate"].values.ravel()
    runs = ds["mean_runs"].values.ravel()
    # The sweep runs from far below p0 to far above p1.
    assert flaky[0] < 0.05
    assert flaky[-1] > 0.95
    # Every point decides in fewer runs than the 531-run fixed-sample plan.
    assert (runs < 531).all()


def test_example_sprt_reports_one_sprt_chart():
    run_cfg = bn.BenchRunCfg(clear_cache=True, auto_plot=False)
    bench = example_sprt(run_cfg, trials=20)
    panes = bench.report.pane.select(pn.pane.SVG)
    assert len(panes) == 1
    svg = panes[0].object
    # The pane holds the chart from Sprt.to_svg(), not a path or an empty string.
    assert svg.startswith("<svg")
    root = ET.fromstring(svg)  # noqa: S314 - parses our own output
    title = root.find("{http://www.w3.org/2000/svg}title")
    assert title is not None
    # The walk at p1 ends with a verdict, so the title names it.
    assert title.text.split(":")[0] in {v.value for v in bn.SprtVerdict}
