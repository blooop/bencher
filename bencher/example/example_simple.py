# you need this import to be able to reference a class from a static method in that class
from __future__ import annotations

import math
import random
import time
from datetime import datetime
from enum import auto

from strenum import StrEnum

import bencher as bch


# define a class with the output variables you want to benchmark. It must inherit from ParametrizedSweep (which inherits from param.Parametrized). Param is a python library that allows you to track metadata about parameters.  I would recommend reading at least the intro: https://param.holoviz.org/.  I have extended param with some extra metadata such is the units of the variable so that it can automatically be plotted.
class OutputCfg(bch.ParametrizedSweep):
    """A class for defining what variables the benchmark function returns and metadata on those variables"""

    # Documenting the variable here with enables automatic summaries of what has been benchmarked.
    # This made up example uses accuracy as an example, but the variable defined here can be any metric that is important for the performance of a system.  You can also define the direction of the optimisation i.e. to minimise or maximise the metric.
    accuracy = bch.ResultVar(
        units="%", direction=bch.OptDir.maximize, doc="The accuracy of the algorithm."
    )


# Define categorical variables with enums that inherit from StrEnum.  In this example, its just an arbitrary set of categories that have an unknown influence on the metric you want to understand. In a real world case these would be a set of conditions or settings you are benchmarking
class AlgoSetting(StrEnum):
    """Use enums to describe categorical input.  In this example they are given names that describe how they affect the function output, but in a real world example these will be some settings to an algorithm that you want to understand how they affect the metric you are trying to optimise."""

    # add some random noise to the output.  When your algorithm has noisy output it often is an indication that something is not quite right.  The graphs should show that you want to avoid the "noisy" setting in your algorithm
    noisy = auto()

    # This is the setting with the best performance, and characterising that that is is the goal of the benchmarking
    optimum = auto()

    poor = auto()  # this setting results in poor performance


# define a class with the input variables you want to benchmark.  It must inherit from ParametrizeSweep. This class defines a struct that is passed to the benchmark function.  The function must be pure and so we define it as a staticmethod that takes an InputCfg class and returns an OutputCfg class. By accepting and returning parametrized classes the metadata about what the relationship between the input and output are easy to track.
class InputCfg(bch.ParametrizedSweep):
    # The variables must be defined as one of the Sweep types, i.e, FloatSweep, IntSweep, EnumSweep from bencher.bench_vars
    # theta = FloatSweep(default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30)

    # Define sweep variables by passing in an enum class name. The first element of the enum is the default by convention, but you can override the default in the constructor
    algo_setting_enum = bch.EnumSweep(AlgoSetting, default=AlgoSetting.poor)

    # In this case there are no units so its marked as unitless or ul. You can define how many evenly distributed samples to sample the parameter with
    algo_setting_float = bch.FloatSweep(
        default=0.0,
        bounds=[0.0, 6.0],
        doc="This represents a continuous input value to your function that affects the desired output in a way you want to characterise.",
        units="ul",
        samples=10,
    )

    # define the objective function you want to benchmark. It must be static and have no side effects. It should accept 1 input of type InputCfg (or whatever your input config class is called) and return the OutputCfg class you have defined
    @staticmethod
    def bench_function(cfg: InputCfg) -> OutputCfg:
        """Takes an ExampleBenchCfgIn and returns a ExampleBenchCfgOut output.  This is just a dummy example so the behavior of the function is rather transparent, but in a real use case the function would be a black box you want to characterise."""
        output = OutputCfg()

        output.accuracy = 50 + math.sin(cfg.algo_setting_float) * 5

        # this simulates random long term change in the function
        output.accuracy += time.localtime(datetime.now().second).tm_sec / 30

        match cfg.algo_setting_enum:
            case AlgoSetting.noisy:
                # add some random noise to the output.  When your algorithm has noisy output it often is an indication that something is not quite right.  The graphs should show that you want to avoid the "noisy" setting in your algorithm
                output.accuracy += random.uniform(-10, 10)
            case AlgoSetting.optimum:
                output.accuracy += 30  # This is the setting with the best performance, and characterising that is is the goal of the benchmarking
            case AlgoSetting.poor:
                output.accuracy -= 20  # this setting results in poor performance
        return output


if __name__ == "__main__":
    # pass the objective function you have defined to bencher.  This benchmark function can be reused for multiple sweeps.  You also need to pass the inputCfg to the bencher so that it can process the metadata about the input configuration.
    bench = bch.Bench("Bencher_Example_Categorical", InputCfg.bench_function, InputCfg)

    # Bencher needs to know the metadata of the variable in order to automatically sweep and plot it, so it is passed by using param's metadata syntax.  InputCfg.param.* is how to access the metadata defined in the class description.  Unfortunately vscode autocomplete doesn't work with params metaclass machinery so you will need to look at the class definition to get a list of possible settings. Define what parameter you want to sweep over and the result variable you want to plot.  If you pass 1 input, it will perform a 1D sweep over that dimension and plot a line or a bar graph of the result (depending on if that variable on continuous or discrete).  In this example we are going to sweep the enum variable and record the accuracy.
    bench.plot_sweep(
        input_vars=[InputCfg.param.algo_setting_enum],
        result_vars=[OutputCfg.param.accuracy],
        title="Simple example 1D enum sweep",
        description="""Sample all the values in enum setting and record the resulting accuracy.  The algo_setting_float is not mentioned in the inputs and so it takes the default value that was set in the InputCfg class.  Repeats=10 so the benchmark function is called 10 times serially.  This is why the function must be pure, if a past call to the function affects the future call to the function (through global side effects) any statistics you calculate will not be correct. 
        """,
        post_description="Here you can see the affect of each setting on the output and the optimum is clearly the best.",
        run_cfg=bch.BenchRunCfg(repeats=10),
    )

    # There is also a floating point input setting that affects the performance of the algorithm.  By passing only the float setting, the InputCfg class will use the default setting of the categorical value so you can understand the float setting in isolation
    bench.plot_sweep(
        input_vars=[InputCfg.param.algo_setting_float],
        result_vars=[OutputCfg.param.accuracy],
        title="Simple example 1D float sweep",
        description="""Perform a 1D sweep over the continuous variable algo_setting_float taking sweep the bounds and number of samples from the InputCfg class definition.  The algo_setting_enum is not mentioned in the inputs and so it takes the default value that was set in the InputCfg class.  Repeats=10 so the benchmark function is called 10 times serially.  
        """,
        post_description="The plot shows the output is affected by the float input in a continuous way with a peak around 1.5",
        run_cfg=bch.BenchRunCfg(repeats=10),
    )

    # This sweep is a combination of the previous two sweeps
    bench.plot_sweep(
        input_vars=[
            InputCfg.param.algo_setting_float,
            InputCfg.param.algo_setting_enum,
        ],
        result_vars=[OutputCfg.param.accuracy],
        title="Simple example 2D sweep",
        description="""Perform a 2D sweep over the enum and continuous variable to see how they act together.  Here the setting use_optuna=True so additional graphs a plotted at the end. 
        """,
        post_description="In this example function the two input settings combine in a linear and predictable way, so the best combination of settings is enum = AlgoSetting.optimum and float = 1.33.  Setting use_optuna=True adds a plot of how much each input parameter affects the metric and a printout of the best parameter values found during the sweep.  If the value for repeat is high it is an indication there is something wrong with your benchmark function. The repeat should have no affect on the value of the function if calls to the function are independent.  This can be useful to detect undesired side effects in your code",
        run_cfg=bch.BenchRunCfg(repeats=10, use_optuna=True, serve_xarray=True, serve_pandas=True),
    )

    # In the last example we track the value of the categorical values over time.
    # run this code in a loop twice to simulate calling the benchmarking function at different times.  The most common use case for tracking over time would be run once a day during nightly benchmarking
    bench.plot_sweep(
        input_vars=[InputCfg.param.algo_setting_enum],
        result_vars=[OutputCfg.param.accuracy],
        const_vars=[(InputCfg.param.algo_setting_float, 1.33)],
        title="Simple example 1D sweep over time",
        description="""Once you have found the optimal settings for your algorithm you want to make sure that the performance is not lost over time.  You can set variables to a constant value and in this case the float value is set to its optimum value.  The first time this function is run only the results from sweeping the categorical value is plotted (the same as example 1), but the second time it is run a graph the values over time is shown. [Run the code again if you don't see a graph over time]. If the graphs over time shows long term changes (not just noise), it indicate there is another external factor that is affecting your performance over time, i.e. dependencies changing, physical degradation of equipment, an unnoticed bug from a pull request etc...

        This shows the basic features of bencher.  These examples are purposefully simplified to demonstrate its features in isolation and don't reeally show the real advantages of bencher.  If you only have a few inputs and outputs its not that complicated to throw together some plots of performance.  The power of bencher is that when you have a system with many moving parts that all interact with each other, teasing apart those influences becomes much harder because the parameter spaces combine quite quickly into a high dimensional mess. Bencher makes it easier to experiment with different combination of inputs to gain an intuition of the system performance. Bencher can plot up to 6D input natively and you can add custom plots if you have exotic data types or state spaces [WIP]. 
        """,
        post_description="",
        run_cfg=bch.BenchRunCfg(repeats=10, over_time=True, clear_history=False),
    )

    # launch web server and view
    bench.report.show()
