# import math

# import bencher as bn


# def bench_function(
#     theta: float = 0,
#     offset: float = 0,
#     scale: float = 1.0,
#     trig_func: str = "sin",
#     **kwargs,  # pylint: disable=unused-argument
# ) -> dict:
#     """All the other examples use classes and parameters to define the inputs and outputs to the function. However it makes the code less flexible when integrating with other systems, so this example shows a more basic interface that accepts and returns dictionaries.  The classes still need to be defined however because that is how the sweep and plotting settings are calculated"""
#     output = {}

#     if trig_func == "sin":
#         output["voltage"] = offset + math.sin(theta) * scale
#     elif trig_func == "cos":
#         output["voltage"] = offset + math.cos(theta) * scale

#     return output


# class InputCfg(bn.ParametrizedSweep):
#     """This class is used to define the default values and bounds of the variables to benchmark."""

#     theta = bn.FloatSweep(
#         default=0.0,
#         bounds=[0.0, 6.0],
#         doc="Input angle to the trig function",
#         units="rad",
#         samples=10,
#     )

#     offset = bn.FloatSweep(
#         default=0.0,
#         bounds=[0.0, 3.0],
#         doc="Add an offset voltage to the result of the trig function",
#         units="v",
#         samples=5,
#     )

#     trig_func = bn.StringSweep(["sin", "cos"], doc="Select what trigonometric function use")


# class OutputVoltage(bn.ParametrizedSweep):
#     voltage = bn.ResultFloat(units="v", doc="Output voltage")


# if __name__ == "__main__":
#     # pass the objective function you have defined to bencher.  The other examples pass the InputCfg type, but this benchmark function accepts a kwargs dictionary so you don't need to pass the inputCfg type.
#     bench = bn.Bench("Bencher_Example_Categorical", bench_function)

#     # Bencher needs to know the metadata of the variable in order to automatically sweep and plot it, so it is passed by using param's metadata syntax.  InputCfg.param.* is how to access the metadata defined in the class description.
#     bench.plot_sweep(
#         input_vars=[InputCfg.param.theta, InputCfg.param.offset],
#         result_vars=[OutputVoltage.param.voltage],
#         title="Example with kwarg inputs and dict output",
#         description=bench_function.__doc__,
#     )

#     # launch web server and view
#     bench.report.show()
