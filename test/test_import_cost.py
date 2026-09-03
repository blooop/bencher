"""``import bencher`` must not drag in the heavy plot/media dependencies.

Importing ``hvplot.pandas``/``hvplot.xarray`` costs ~2s, nearly all of it inside
``colorcet``, which builds ~200 matplotlib colormaps in its module body. ``moviepy``
costs another ~0.2s and pulls all of ``IPython`` behind it (via
``moviepy.video.io.display_in_notebook``). None of it is needed to define a sweep or
run a benchmark -- only to render a plot or write a video -- and every one of those
modules used to be imported at module scope, so *every* ``import bencher`` paid for
them. That is ~3.2s down to ~1.1s, measured back to back on one machine.

These are the imports that can silently undo it. ``hvplot.pandas`` and
``hvplot.xarray`` are especially easy to reintroduce: they exist purely to attach the
``.hvplot`` accessor, so a plotting module that uses ``da.hvplot.line(...)`` looks like
it needs them at module scope. It does not -- ``hvplot_of(da).line(...)`` returns
the accessor and imports hvplot as it goes (see
``bencher/results/hvplot_accessor.py``). Three of the nine files that carried those
imports never touched the accessor at all.

Asserted in a subprocess, because the test session itself imports hvplot the moment
any other test builds a plot.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

# Not merely slow -- each is unreachable without an explicit user action (drawing a
# plot, encoding a video), so loading it at import time is pure cost.
DEFERRED = ("hvplot", "colorcet", "moviepy", "IPython")

PROBE = """
import sys
import bencher  # noqa: F401
print(",".join(sorted(m for m in %r if m in sys.modules)))
"""


def test_import_bencher_does_not_load_the_heavy_optional_deps() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", PROBE % (DEFERRED,)],
        capture_output=True,
        text=True,
        check=True,
    )
    leaked = [m for m in proc.stdout.strip().split(",") if m]
    assert not leaked, (
        f"`import bencher` now loads {leaked}, which it had been kept clear of. "
        "Something gained a module-scope import of one of them -- most likely an "
        "`import hvplot.pandas` / `import hvplot.xarray` added to a plotting module "
        "to make a `.hvplot` accessor call work. Reach the accessor through "
        "`hvplot_of(obj)` instead (bencher/results/hvplot_accessor.py), and import "
        "moviepy inside the method that encodes video. Each of these costs every "
        "caller ~0.2-2s on `import bencher`."
    )


# A plot path that never reaches the accessor must not pay for it either. Each of
# these methods has a `return None` exit -- an unplottable dataset, or a branch that
# builds the plot with `hv.` instead -- and an entry-point guard imported hvplot on
# all of them, which is the same 2.3s the module-scope imports cost.
EARLY_RETURN_PROBE = """
import sys
import numpy as np
import xarray as xr
import bencher as bn


class Cfg(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=(0, 3))
    y = bn.FloatSweep(default=0, bounds=(0, 3))
    out = bn.ResultFloat()

    def benchmark(self):
        self.out = self.x + self.y


bench = bn.Bench("probe", Cfg(), run_cfg=bn.BenchRunCfg(auto_plot=False))
res = bench.plot_sweep("probe", input_vars=["x", "y"], result_vars=["out"])

# One dimension: to_heatmap_ds cannot draw a heatmap and returns None.
ds = xr.Dataset({"out": ("x", np.arange(4.0))}, coords={"x": np.arange(4.0)})
assert res.to_heatmap_ds(ds, res.bench_cfg.result_vars[0]) is None
print("hvplot" in sys.modules)
"""


def test_a_plot_path_that_returns_early_does_not_import_hvplot() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", EARLY_RETURN_PROBE],
        capture_output=True,
        text=True,
        check=True,
    )
    loaded = proc.stdout.strip().splitlines()[-1]
    assert loaded == "False", (
        "to_heatmap_ds returned None without drawing anything, but imported hvplot "
        "(~2.3s) on the way. Register the accessor at the expression that uses it, "
        "not at the top of the method -- an entry-point guard pays the import on "
        "every early return and on every branch that plots with `hv.` instead."
    )


def test_every_accessor_use_goes_through_the_helper() -> None:
    """No module may reach ``.hvplot`` directly, which is what makes the above hold.

    ``hvplot_of()`` returning the accessor means a plot path cannot use hvplot
    without importing it, and cannot import it without using it -- but only while
    every call site actually goes through it. A stray ``da.hvplot.line(...)`` works
    in the test suite (some earlier test in the same process has already registered
    the accessor) and in a report that draws more than one plot, and fails only for
    the user whose script draws that one plot and nothing else. So it is asserted
    structurally rather than by running anything.
    """
    package = Path(__file__).resolve().parent.parent / "bencher"
    helper = package / "results" / "hvplot_accessor.py"
    offenders = []
    for path in package.rglob("*.py"):
        if path == helper:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            # `x.hvplot` as an attribute load, i.e. the accessor -- not `import
            # hvplot.pandas`, which is an Import node and is caught by the test above.
            if isinstance(node, ast.Attribute) and node.attr == "hvplot":
                offenders.append(f"{path.relative_to(package).as_posix()}:{node.lineno}")
    assert not offenders, (
        f"{offenders} reach the `.hvplot` accessor directly. Whether that works "
        "depends on whether something else already imported hvplot in the same "
        "process, so it passes here and in any multi-plot report, then raises "
        "`AttributeError: no attribute 'hvplot'` for the user who draws only this "
        "plot. Use `hvplot_of(obj)` from bencher.results.hvplot_accessor instead."
    )


# Same shape as the accessor case: an encoder that writes nothing should not load
# the encoder. `write()` with no appended frames is a no-op that still returned a
# filename, so the import at the top of the method was pure cost.
NO_FRAMES_PROBE = """
import sys
from bencher.video_writer import VideoWriter

vw = VideoWriter()
vw.write()
print("moviepy" in sys.modules)
"""


def test_writing_a_video_with_no_frames_does_not_import_moviepy() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", NO_FRAMES_PROBE],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip().splitlines()[-1] == "False", (
        "VideoWriter.write() with no frames encodes nothing but imported moviepy "
        "(~0.2s, and all of IPython behind it). Import it under the `if` that "
        "actually encodes."
    )
