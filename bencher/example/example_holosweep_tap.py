# THIS IS NOT A WORKING EXAMPLE YET

# pylint: disable=duplicate-code,unused-argument


import bencher as bch
import math
import random
import numpy as np
import holoviews as hv

from strenum import StrEnum
from enum import auto


class Function(StrEnum):
    fn_cos = auto()
    fn_sin = auto()
    fn_log = auto()
    fn_arctan = auto()

    def call(self, arg) -> float:
        """Calls the function defined by the name of the enum

        Returns:
            float: The result of calling the function defined by the enum
        """
        return getattr(np, self.removeprefix("fn_"))(arg)


class PlotFunctions(bch.ParametrizedSweep):
    phase = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=5
    )

    freq = bch.FloatSweep(default=1, bounds=[0, math.pi], doc="Input angle", units="rad", samples=5)

    theta = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=10
    )

    compute_fn = bch.EnumSweep(Function)

    fn_output = bch.ResultVar(units="v", doc="sin of theta with some noise")

    out_sum = bch.ResultVar(units="v", doc="The sum")

    hmap = bch.ResultHmap()

    def __call__(self, plot=True, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        noise = 0.1

        self.fn_output = self.compute_fn.call(self.phase + self.freq * self.theta) + random.uniform(
            0, noise
        )
        self.hmap = self.plot_holo(plot)

        return self.get_results_values_as_dict()

    def plot_holo(self, plot=True) -> hv.core.ViewableElement:
        """Plots a generic representation of the object that is not a basic hv datatype. In this case its an image of the values of the object, but it could be any representation of the object, e.g. a screenshot of the object state"""
        if plot:
            pt = hv.Text(0, 0, f"phase:{self.phase}\nfreq:{self.freq}\ntheta:{self.theta}")
            pt *= hv.Ellipse(0, 0, 1)
            return pt
        return None

    def calc_vec(self, **kwargs) -> dict:
        theta = self.param.theta.values()
        kwargs.pop("theta", 0)
        dat = [self.__call__(plot=False, theta=i, **kwargs)["fn_output"] for i in theta]
        # print(dat)
        self.out_sum = sum(dat)
        self.hmap = hv.Curve((theta, dat), "theta", "voltage")
        # pt = hv.Text(0, 0, f"{self.compute_fn}\n{self.phase}\n{self.freq}")
        # pt *= hv.Ellipse(0, 0, 1)
        return self.get_results_values_as_dict()


def example_holosweep_tap(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    wv = PlotFunctions()

    run_cfg.use_optuna = True
    run_cfg.auto_plot = False
    bench = bch.Bench("waves", wv, run_cfg=run_cfg, report=report)

    res = bench.plot_sweep(
        "phase",
        input_vars=[PlotFunctions.param.theta, PlotFunctions.param.freq],
        result_vars=[PlotFunctions.param.fn_output, PlotFunctions.param.hmap],
        run_cfg=run_cfg,
    )

    bench.report.append(res.describe_sweep())
    bench.report.append(res.to_heatmap_tap(PlotFunctions.param.fn_output))

    return bench


def example_holosweep_tap_slider(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:  # pragma: no cover
    wv = PlotFunctions()

    run_cfg.use_optuna = True
    bench = bch.Bench("waves", wv, run_cfg=run_cfg, report=report)

    res = bench.plot_sweep(
        "phase",
        input_vars=[PlotFunctions.param.theta, PlotFunctions.param.freq, PlotFunctions.param.phase],
        result_vars=[PlotFunctions.param.fn_output],
        run_cfg=run_cfg,
    )

    print(res.get_best_trial_params())
    bench.report.append(res.get_best_holomap())

    heatmap = res.to_heatmap().opts(tools=["hover", "tap"])
    posxy = hv.streams.Tap(source=heatmap, x=0, y=0)
    sld1 = wv.param.phase.as_slider()

    def tap_plot(x, y):
        print(x, y)
        selres = bch.get_nearest_coords(res.ds, theta=x, freq=y, phase=sld1.value, repeat=1)
        return res.hmaps[bch.hmap_canonical_input(selres)]

    tap_dmap = hv.DynamicMap(tap_plot, streams=[posxy])

    bench.report.append_tab(heatmap + tap_dmap, "Interactive Heatmap")
    bench.report.append(sld1)

    bench.report.append_tab(res.to_curve(), "Slider view")

    return bench


if __name__ == "__main__":
    example_holosweep_tap(bch.BenchRunCfg()).report.show()


# todo  https://discourse.holoviz.org/t/pointdraw-as-parameterized-class/3539
