"""This file contains an example of how to define benchmarking parameters sweeps. Categorical values are defined as enums and passed to EnumSweep classes, other types of sweeps are defined by their respective classes.

You can define a subclass which contains an input configuration which can be passed to a function in a type safe way. You can combine the subclass with a higher level class which contains more configuration parameters.  This is to help manage the complexity of large configuration/parameter spaces.
"""

import math
import random
from enum import auto
from strenum import StrEnum
from bencher.variables.inputs import IntSweep, FloatSweep, StringSweep, EnumSweep, BoolSweep
from bencher.variables.results import ResultVar, OptDir
from bencher.variables.parametrised_sweep import ParametrizedSweep


class PostprocessFn(StrEnum):
    """Apply a postprocessing step to the data"""

    absolute = auto()  # return the abs of the output data
    negate = auto()  # return the negative of the output data


class NoiseDistribution(StrEnum):
    """A categorical variable describing the types of random noise"""

    uniform = auto()  # uniform random noiase
    gaussian = auto()  # gaussian noise
    lognorm = auto()  # lognorm noise


def negate_fn(fn_input: float):
    """returns the negative of the input

    Args:
        fn_input (float): any float value

    Returns:
        float: negative of the input
    """
    return -fn_input


class ExampleBenchCfg(ParametrizedSweep):
    theta = FloatSweep(default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30)
    offset = FloatSweep(default=0, bounds=[0, 0.3], doc="dc offset", units="v", samples=30)
    postprocess_fn = EnumSweep(PostprocessFn)

    noisy = BoolSweep(
        default=False, doc="Optionally add random noise to the output of the function"
    )
    noise_distribution = EnumSweep(NoiseDistribution, doc=NoiseDistribution.__doc__)
    sigma = FloatSweep(
        default=1,
        bounds=[0, 10],
        doc="The standard deviation of the noise",
        units="v",
    )

    out_sin = ResultVar(units="v", direction=OptDir.minimize, doc="sin of theta with some noise")
    out_cos = ResultVar(units="v", direction=OptDir.minimize, doc="cos of theta with some noise")
    out_bool = ResultVar(units="%", doc="sin > 0.5")

    def __call__(self, **kwwargs) -> dict:
        self.update_params_from_kwargs(**kwwargs)

        noise = self.calculate_noise()
        postprocess_fn = abs if self.postprocess_fn == PostprocessFn.absolute else negate_fn

        self.out_sin = postprocess_fn(self.offset + math.sin(self.theta) + noise)
        self.out_cos = postprocess_fn(self.offset + math.cos(self.theta) + noise)
        self.out_bool = self.out_sin > 0.5
        return self.get_results_values_as_dict()

    def calculate_noise(self):
        noise = 0.0
        if self.noisy:
            match self.noise_distribution:
                case NoiseDistribution.uniform:
                    noise = random.uniform(0, self.sigma)
                case NoiseDistribution.gaussian:
                    noise = random.gauss(0, self.sigma)
                case NoiseDistribution.lognorm:
                    noise = random.lognormvariate(0, self.sigma)

        return noise


def call(**kwargs) -> dict:
    return ExampleBenchCfg().__call__(**kwargs)


class AllSweepVars(ParametrizedSweep):
    """A class containing all the sweep types, This class is used for unit testing how the configuration classes are serialised and hashed"""

    var_float = FloatSweep(default=5, bounds=(0, 10), units="m/s")
    var_int = IntSweep(default=3, bounds=[0, 4])
    var_int_big = IntSweep(default=0, bounds=[0, 100], samples=3)
    var_bool = BoolSweep()
    var_string = StringSweep(["string1", "string2"])
    var_enum = EnumSweep(PostprocessFn)

    result = ResultVar()

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.result = self.var_float + self.var_int
        return self.get_results_values_as_dict()


class SimpleBenchClass(ParametrizedSweep):
    var1 = IntSweep(default=0, bounds=[0, 2])

    result = ResultVar()

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.result = self.var1
        return self.get_results_values_as_dict()


class SimpleBenchClassFloat(ParametrizedSweep):
    var1 = FloatSweep(bounds=[0, 100])

    result = ResultVar()

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.result = self.var1
        return self.get_results_values_as_dict()
