# pylint: skip-file  #this is experimental still


import holoviews as hv
import numpy as np
import pandas as pd
import panel as pn

# import streamz
# import streamz.dataframe
from holoviews import opts
from holoviews.streams import Buffer
from tornado import gen
from tornado.ioloop import PeriodicCallback

hv.extension("bokeh")


count = 0
buffer = Buffer(np.zeros((0, 2)), length=50)

dataType = pd.DataFrame()


@gen.coroutine
def f():
    global count
    count += 1
    buffer.send(np.array([[count, np.random.rand()]]))


def plot(**kwargs):
    # print(dat)
    return hv.Curve(**kwargs)


cb = PeriodicCallback(f, 1)
cb.start()

# dmap = hv.DynamicMap(hv.Curve, streams=[buffer]).opts(padding=0.1, width=600)
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
    for i in range(2):
        dfstream.send(next(brownian))


cb = PeriodicCallback(update_callback, 1)
cb.start()

# update_button = pn.widgets.Button(name="Update Grid", button_type="primary")
# update_button.on_click(update_callback)

pn.Row(plot()).show()
