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


class FunctionInputs(bch.ParametrizedSweep):
    phase = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=5
    )

    freq = bch.FloatSweep(default=1, bounds=[0, math.pi], doc="Input angle", units="rad", samples=5)

    theta = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=10
    )

    compute_fn = bch.EnumSweep(Function)


class FunctionOutputs(bch.ParametrizedSweep):
    fn_output = bch.ResultVar(units="v", doc="sin of theta with some noise")

    out_sum = bch.ResultVar(units="v", doc="The sum")

    hmap = bch.ResultHmap()

    hmap2 = bch.ResultHmap()


def bench_fn(self, **kwargs) -> dict:
    fin = FunctionInputs()
    fin.update_params_from_kwargs(**kwargs)

    output = FunctionOutputs()

    output.fn_output = fin.compute_fn.call(fin.phase + fin.freq * fin.theta) + random.uniform(0, 0)
    output.hmap = hv.Text(0, 0, f"{fin.phase}\n{fin.freq}\n {fin.theta}")
    output.hmap2 = hv.Ellipse(0, 0, 1)
    return output


def plot_holo(self, plot=True) -> hv.core.ViewableElement:
    """Plots a generic representation of the object that is not a basic hv datatype. In this case its an image of the values of the object, but it could be any representation of the object, e.g. a screenshot of the object state"""
    if plot:
        pt = hv.Text(0, 0, f"{self.phase}\n{self.freq}\n {self.theta}")
        pt *= hv.Ellipse(0, 0, 1)
        return pt
    return None


def example_holosweep(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    # wv = PlotFunctions()

    bench = bch.Bench(
        "waves", bench_fn, worker_input_cfg=FunctionInputs, run_cfg=run_cfg, report=report
    )

    res = bench.plot_sweep(
        "phase",
        input_vars=[FunctionInputs.param.theta, FunctionInputs.param.freq],
        result_vars=[
            FunctionOutputs.param.fn_output,
            FunctionOutputs.param.hmap,
            FunctionOutputs.param.hmap2,
        ],
    )

    # bench.report.append(res.summarise_sweep())
    # bench.report.append(res.to_optuna())
    # bench.report.append(res.get_best_holomap())
    # bench.report.append(res.to_curve(), "Slider view")
    # bench.report.append(res.to_holomap().layout())
    # print(res.to_holomap())
    bench.report.append(res.to_holomap())
    # bench.report.append(res.to_holomap())

    return bench


if __name__ == "__main__":
    bench_run = bch.BenchRunner(example_holosweep)
    bench_run.run(level=4, show=True)
