"""Every generated example, re-run with ``backend="svg"``: the svg backend is a run_cfg swap.

No example is written for the svg backend. Each existing example takes a ``run_cfg``, so
``example_x(bn.BenchRunCfg(backend="svg"))`` draws it with the svg charts. Here every
chart the svg backend claims must render a self-contained SVG, and every shape it does not
claim must fall back to the holoviews (or plotly) twin, with the report built without
error.
"""

from __future__ import annotations

import importlib

import pytest

import bencher as bn
from bencher.example.meta.generate_examples import SVG_GALLERY
from bencher.plugins.registry import get_registry
from bencher.results.svg_result import CHARTS
from test.helpers import assert_embeddable_svg
from test.test_generated_examples import GENERATED_DIR, _examples

_NAMED_ONLY = [name for name, chart in CHARTS.items() if not chart.auto]


def _example_fn(example_path):
    rel = example_path.relative_to(GENERATED_DIR).with_suffix("")
    mod = importlib.import_module(".".join(("bencher.example.generated", *rel.parts)))
    return next(v for k, v in vars(mod).items() if k.startswith("example_") and callable(v))


def _twin_backend(name: str) -> str:
    return "plotly" if name in ("surface", "volume") else "holoviews"


@pytest.mark.parametrize("example_path", _examples, ids=lambda p: str(p.relative_to(GENERATED_DIR)))
def test_generated_example_with_svg_backend(example_path):
    run_cfg = bn.BenchRunCfg(backend="svg", subsampling_divisions=2, repeats=2)
    # plot_sweep builds the report with auto_plot: every fallback chart renders here.
    bench = _example_fn(example_path)(run_cfg)
    registry = get_registry()
    for res in bench.results:
        data = res.to_bench_data()
        chosen = {p.name: p.backend for p in registry.select(data, backend="svg")}
        default = {p.name: p.backend for p in registry.select(data, backend=None)}
        # The backend swaps who draws a chart, never which charts a sweep gets.
        assert chosen.keys() == default.keys()
        for name, backend in chosen.items():
            if name in CHARTS:
                assert backend in ("svg", _twin_backend(name)), name
            else:
                assert backend == default[name], name
        claimed = [name for name, backend in chosen.items() if backend == "svg"]
        svgs = res.to_svgs(claimed)
        result_vars = res.bench_cfg.result_vars
        for name in claimed:
            if any(isinstance(rv, CHARTS[name].result_types) for rv in result_vars):
                assert any(key.startswith(f"{name}_") for key in svgs), name
            else:
                # No result var the svg chart draws: its render hands over to the twin.
                assert registry.get(name, "svg").fallback is not None, name
        # The named-only charts draw whatever sweep their rule matches.
        svgs.update(res.to_svgs(_NAMED_ONLY))
        for svg in svgs.values():
            assert_embeddable_svg(svg)


def test_svg_gallery_names_existing_examples():
    stems = {p.stem for p in _examples}
    pages = [entry.page_stem for entry in SVG_GALLERY]
    assert {entry.stem for entry in SVG_GALLERY} <= stems
    assert len(pages) == len(set(pages))
    assert not stems & set(pages)
