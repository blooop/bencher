"""Prototype B for ticket #1110: the rasterize fallback.

Question: can a report item with no rerun lowering be rendered to PNG headlessly
in the CURRENT pixi env and logged into a rerun recording as rr.EncodedImage?

Measures, for (1) a real bencher holoviews plot and (2) a plotly figure of the
kind ("volume","plotly") / optuna produce:
  - does headless PNG export work at all, and via which backend/dependency
  - which export deps are already in the pixi env vs would be new
  - wall time per plot
  - PNG size at report-typical dimensions

Run:  pixi run python plans/research/prototypes_1110/proto_b_rasterize.py
"""

from __future__ import annotations

import io
import time
from pathlib import Path

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

report: list[str] = []


def check_dep(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def main() -> None:  # noqa: PLR0915
    # ---- dependency inventory --------------------------------------------
    for dep in ("kaleido", "selenium", "matplotlib", "plotly", "rerun"):
        report.append(f"dep {dep!r} importable in pixi env: {check_dep(dep)}")

    # ---- 1. real bencher holoviews plot ----------------------------------
    import bencher as bch
    from bencher.example.example_simple_float import SimpleFloat
    from bencher.results.holoview_results.curve_result import CurveResult

    bench = SimpleFloat().to_bench(bch.BenchRunCfg(repeats=5))
    res = bench.plot_sweep(plot_callbacks=False)
    plot = res.to(CurveResult)  # a pn layout wrapping a pn.pane.HoloViews
    import panel as pn

    if isinstance(plot, pn.viewable.Viewable):
        hv_obj = plot.select(pn.pane.HoloViews)[0].object
    else:
        hv_obj = plot
    report.append(f"holoviews object: {type(hv_obj)}")

    import holoviews as hv

    # Path A (zero new deps): render through the matplotlib backend.
    hv.extension("matplotlib")
    t0 = time.perf_counter()
    try:
        fig = hv.render(hv_obj, backend="matplotlib")
        report.append("holoviews->mpl: rendered WITH bencher's bokeh-era opts intact")
    except Exception as exc:  # noqa: BLE001
        # Found while prototyping: bencher labels curves with the vdim name
        # (holoview_result.py:298 `label=var`), and hv's mpl style-transform
        # machinery treats a legend label equal to a dimension name as a dim()
        # style mapping, vectorizing it -> matplotlib ValueError. The bokeh
        # backend is unaffected. Workaround: relabel colliding elements.
        report.append(
            f"holoviews->mpl with original labels: FAILED ({type(exc).__name__}: {exc}); "
            "retrying with dim-name-colliding labels suffixed"
        )

        def _delabel(el):
            if el.label in {d.name for d in el.dimensions()}:
                return el.relabel(el.label + "​")  # zero-width space
            return el

        stripped = hv_obj.map(_delabel, specs=hv.core.element.Element)
        fig = hv.render(stripped, backend="matplotlib")
    fig.set_size_inches(7, 4)  # ~700x400 at dpi=100, report-typical
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    hv_png = buf.getvalue()
    t_hv = time.perf_counter() - t0
    (OUT / "holoviews_curve_mpl.png").write_bytes(hv_png)
    report.append(
        f"holoviews->PNG via matplotlib backend: OK, {t_hv * 1000:.0f} ms, {len(hv_png)} bytes"
    )

    # Path B (bokeh export): needs selenium + a webdriver; expected to fail here.
    hv.extension("bokeh")
    try:
        t0 = time.perf_counter()
        from bokeh.io.export import get_screenshot_as_png  # noqa: F401

        bokeh_fig = hv.render(hv_obj, backend="bokeh")
        img = get_screenshot_as_png(bokeh_fig)  # raises without selenium/webdriver
        t_bk = time.perf_counter() - t0
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        (OUT / "holoviews_curve_bokeh.png").write_bytes(buf.getvalue())
        report.append(f"holoviews->PNG via bokeh export: OK, {t_bk * 1000:.0f} ms")
    except Exception as exc:  # noqa: BLE001
        report.append(f"holoviews->PNG via bokeh export: FAILED ({type(exc).__name__}: {exc})")

    # ---- 2. plotly figures: a go.Volume (what ("volume","plotly") makes) --
    import numpy as np
    import plotly.graph_objs as go

    xs, ys, zs = np.mgrid[0:1:8j, 0:1:8j, 0:1:8j]
    vol_fig = go.Figure(
        data=go.Volume(
            x=xs.flatten(),
            y=ys.flatten(),
            z=zs.flatten(),
            value=np.sin(xs * 3 + ys * 2 + zs).flatten(),
            isomin=-1,
            isomax=1,
            opacity=0.1,
            surface_count=20,
        ),
        layout=go.Layout(width=600, height=600, title="volume (as VolumeResult builds it)"),
    )
    try:
        t0 = time.perf_counter()
        vol_png = vol_fig.to_image(format="png")  # requires kaleido
        t_pl = time.perf_counter() - t0
        (OUT / "plotly_volume.png").write_bytes(vol_png)
        report.append(f"plotly volume->PNG: OK, {t_pl * 1000:.0f} ms, {len(vol_png)} bytes")
        plotly_ok = True
    except Exception as exc:  # noqa: BLE001
        report.append(f"plotly volume->PNG: FAILED ({type(exc).__name__}: {exc})")
        plotly_ok = False
        vol_png = None

    # An optuna-style 2D plotly figure (optimization history is a scatter+line).
    hist_fig = go.Figure(
        data=[go.Scatter(y=np.random.default_rng(0).random(30).cumsum(), mode="markers+lines")],
        layout=go.Layout(width=700, height=400, title="optuna-style history figure"),
    )
    try:
        t0 = time.perf_counter()
        hist_png = hist_fig.to_image(format="png")
        t_h = time.perf_counter() - t0
        (OUT / "plotly_history.png").write_bytes(hist_png)
        report.append(f"plotly 2D fig->PNG: OK, {t_h * 1000:.0f} ms, {len(hist_png)} bytes")
    except Exception as exc:  # noqa: BLE001
        report.append(f"plotly 2D fig->PNG: FAILED ({type(exc).__name__}: {exc})")
        hist_png = None

    # ---- 3. log whatever rendered into a rerun recording ------------------
    import rerun as rr

    rrd_path = OUT / "rasterized_report.rrd"
    rr.init("bencher_1110_rasterize_proto")
    rr.save(str(rrd_path))
    t0 = time.perf_counter()
    rr.log("report/holoviews_curve", rr.EncodedImage(contents=hv_png, media_type="image/png"))
    if plotly_ok and vol_png:
        rr.log("report/plotly_volume", rr.EncodedImage(contents=vol_png, media_type="image/png"))
    if hist_png:
        rr.log("report/plotly_history", rr.EncodedImage(contents=hist_png, media_type="image/png"))
    rr.log(
        "report/omissions",
        rr.TextDocument(
            "Items rasterized to PNG (interactivity lost): holoviews curve"
            + (", plotly volume" if plotly_ok else "")
            + ". Plotly export "
            + ("worked." if plotly_ok else "FAILED: kaleido not in env."),
            media_type=rr.MediaType.MARKDOWN,
        ),
    )
    t_log = time.perf_counter() - t0
    rr.disconnect()
    report.append(
        f"rr.EncodedImage logging: OK, {t_log * 1000:.0f} ms, rrd={rrd_path.stat().st_size} bytes"
    )

    print("\n".join(report))


if __name__ == "__main__":
    main()
