# pylint: skip-file  #this is experimental still


import holoviews as hv
import pandas as pd
import panel as pn
from bokeh.models import HoverTool
from hvplot import pandas  # noqa

datadict = dict(
    x=[1, 5],
    y=[4, 10],
    img=[
        "https://raw.githubusercontent.com/holoviz/panel/master/doc/_static/logo_horizontal.png",
        "https://raw.githubusercontent.com/holoviz/panel/master/doc/_static/logo_stacked.png",
    ],
)


hover = HoverTool(
    tooltips="""
    <div>
        <div>
            <img src="@img" width=100 style="float: left; margin: 0px 15px 15px 0px; border="2"></img>
        <div>
            <span style="font-size: 15px;">Location</span>
            <span style="font-size: 10px; color: #696;">(@x, @y)</span>
        </div>
    </div>

"""
)

df_test = pd.DataFrame.from_dict(datadict)


hvds = hv.Dataset(df_test)

pt = hv.Scatter(hvds, kdims=["x"], vdims=["y"], hover_cols=["img"], tools=[hover])

pn.Row(pt).show()

# pt =df_test.hvplot.scatter(x="x", y="y", hover_cols=["img"], tools=[hover])

# pt.show()
