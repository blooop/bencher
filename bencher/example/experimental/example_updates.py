import itertools

import holoviews as hv
import numpy as np
import pandas as pd
import panel as pn
from holoviews import opts
from holoviews.streams import Buffer
from tornado import gen
from tornado.ioloop import PeriodicCallback

hv.extension("bokeh")


counter = itertools.count(1)
buffer = Buffer(np.zeros((0, 2)), length=50)


@gen.coroutine
def f():
    buffer.send(np.array([[next(counter), np.random.rand()]]))


def plot(**kwargs):
    return hv.Curve(**kwargs)


cb = PeriodicCallback(f, 1)
cb.start()

dmap = hv.DynamicMap(plot, streams=[buffer]).opts(padding=0.1, width=600)

pn.Row(dmap).show()


example = pd.DataFrame({"x": [], "y": [], "count": []}, columns=["x", "y", "count"])
dfstream = Buffer(example, length=100, index=False)


def plot():
    curve_dmap = hv.DynamicMap(hv.Curve, streams=[dfstream])
    point_dmap = hv.DynamicMap(hv.Points, streams=[dfstream])
    (curve_dmap * point_dmap).opts(
        opts.Points(color="count", line_color="black", size=5, padding=0.1, xaxis=None, yaxis=None),
        opts.Curve(line_width=1, color="black"),
    )


def gen_brownian():
    x, y, count = 0, 0, 0
    while True:
        x += np.random.randn()
        y += np.random.randn()
        count += 1
        yield pd.DataFrame([(x, y, count)], columns=["x", "y", "count"])


@gen.coroutine
def update_callback():
    brownian = gen_brownian()
    for _ in range(2):
        dfstream.send(next(brownian))


cb = PeriodicCallback(update_callback, 1)
cb.start()

pn.Row(plot()).show()
