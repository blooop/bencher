# from bencher import Pa#
import param

from holoviews import opts

opts.defaults(
    opts.Points(tools=["hover"]),
    opts.Curve(tools=["hover"]),
    opts.Bars(tools=["hover"]),
    opts.HeatMap(tools=["hover"]),
)


class PlotBase:
    def title(self, x: param.Parameter, y: param.Parameter, z: param.Parameter = None) -> str:
        if z is None:
            return f"{x.name} vs {y.name}"
        return f"{z.name} vs ({x.name} vs {y.name})"
