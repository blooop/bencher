# pylint: skip-file  #this is experimental still

import holoviews as hv
import numpy as np
import panel as pn
from holoviews import opts, streams

xs = np.linspace(-3, 3, 400)

hv.extension("bokeh")


def function(xs, time):
    "Some time varying function"
    return np.exp(np.sin(xs + np.pi / time))


def integral(limit, time):
    print(limit, time)
    limit = -3 if limit is None else np.clip(limit, -3, 3)
    curve = hv.Curve((xs, function(xs, time)))[limit:]
    area = hv.Area((xs, function(xs, time)))[:limit]
    summed = area.dimension_values("y").sum() * 0.015  # Numeric approximation
    return area * curve * hv.VLine(limit) * hv.Text(limit + 0.8, 2.0, f"{summed:.2f}")


integral_streams = [streams.Stream.define("Time", time=1.0)(), streams.PointerX().rename(x="limit")]

integral_dmap = hv.DynamicMap(integral, streams=integral_streams)

integral_dmap.opts(
    opts.Area(color="#fff8dc", line_width=2), opts.Curve(color="black"), opts.VLine(color="red")
)

pn.Row(integral_dmap).show()
