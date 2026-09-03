"""``import bencher`` must not drag in the heavy plot/media dependencies.

Importing ``hvplot.pandas``/``hvplot.xarray`` costs ~2s, nearly all of it inside
``colorcet``, which builds ~200 matplotlib colormaps in its module body. ``moviepy``
costs another ~0.2s and pulls all of ``IPython`` behind it (via
``moviepy.video.io.display_in_notebook``). None of it is needed to define a sweep or
run a benchmark -- only to render a plot or write a video -- and every one of those
modules used to be imported at module scope, so *every* ``import bencher`` paid for
them. That is ~3.3s down to ~1.0s.

These are the imports that can silently undo it. ``hvplot.pandas`` and
``hvplot.xarray`` are especially easy to reintroduce: they exist purely to attach the
``.hvplot`` accessor, so a plotting module that uses ``da.hvplot.line(...)`` looks like
it needs them at module scope. It does not -- ``ensure_hvplot()`` registers the
accessor at the point of use (see ``bencher/results/hvplot_accessor.py``). Six of the
nine files that carried those imports never touched the accessor at all.

Asserted in a subprocess, because the test session itself imports hvplot the moment
any other test builds a plot.
"""

from __future__ import annotations

import subprocess
import sys

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
        "to make a `.hvplot` accessor call work. Call `ensure_hvplot()` inside the "
        "method that uses the accessor instead (bencher/results/hvplot_accessor.py), "
        "and import moviepy inside the method that encodes video. Each of these costs "
        "every caller ~0.2-2s on `import bencher`."
    )
