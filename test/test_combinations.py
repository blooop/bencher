from __future__ import annotations

import pytest
import unittest
from hypothesis import given, settings, strategies as st
import bencher as bn
from datetime import datetime

from strenum import StrEnum
from enum import auto
from param import Parameter
from itertools import combinations


class Enum1(StrEnum):
    """A generic enum"""

    enum1_val1 = auto()
    enum1_val2 = auto()


class Enum2(StrEnum):
    """Another generic enum"""

    enum2_val1 = auto()
    enum2_val2 = auto()


class BenchCfgTest(bn.ParametrizedSweep):
    """A class for representing all types of input"""

    float1 = bn.FloatSweep(default=0, bounds=[0, 1], doc="generic float 1", samples=2)
    float2 = bn.FloatSweep(default=0, bounds=[0, 1], doc="generic float 2", samples=2)
    int1 = bn.IntSweep(default=0, bounds=[0, 2], doc="generic int 1")
    int2 = bn.IntSweep(default=0, bounds=[0, 2], doc="generic int 2")
    bool1 = bn.BoolSweep(doc="generic bool 1")
    bool2 = bn.BoolSweep(doc="generic bool 2")
    enum1 = bn.EnumSweep(Enum1)
    enum2 = bn.EnumSweep(Enum2)


class BenchCfgTestOut(bn.ParametrizedSweep):
    """A class for representing all types of result"""

    out1 = bn.ResultVar(doc="generic result variable 1")
    out2 = bn.ResultVar(doc="generic result variable 2")
    outvec2 = bn.ResultVec(2, doc="A generic 2D vector")
    outvec3 = bn.ResultVec(3, doc="A generic 3D vector")


def bench_func(cfg: BenchCfgTest) -> BenchCfgTestOut:
    """A generic benchmark function"""
    output = BenchCfgTestOut()
    output.out1 = cfg.float1
    output.out2 = 2.0
    output.outvec2 = [0, 1]
    output.outvec3 = [0, 1, 2]
    return output


# all possible types of input
input_types = [
    BenchCfgTest.param.float1,
    BenchCfgTest.param.float2,
    BenchCfgTest.param.int1,
    BenchCfgTest.param.int2,
    BenchCfgTest.param.bool1,
    BenchCfgTest.param.bool2,
    BenchCfgTest.param.enum1,
    BenchCfgTest.param.enum2,
]

# all possible types of result
result_var_permutations = [
    [BenchCfgTestOut.param.out1],
    [BenchCfgTestOut.param.out1, BenchCfgTestOut.param.out2],
    # [BenchCfgTestOut.param.outvec2],
    # [BenchCfgTestOut.param.outvec3],
]


# the function used to generate all possible combination or permutations of input
generator_func = combinations

input_var_permutations = []
all_inputs = []

# all possible permutations of the input for a given number of inputs
for num_inputs in range(1, 3):
    input_var_permutations.extend([list(c) for c in generator_func(input_types, num_inputs)])


for p in input_var_permutations:
    print(",".join([pa.name for pa in p]))


@pytest.mark.skip
class TestAllCombinations(unittest.TestCase):
    """This class uses hypothesis to test as large a range as possible of input parameter combinations to make sure bencher always returns an error message rather than crashing.  After a long running parameter sweep the highest priority is to show as much data as possible even if some of the data processing or visualisations are not possible to calculate. (and result in an exception)"""

    def run_bencher_over_time(
        self,
        input_vars: list[Parameter],
        result_vars: list[bn.ResultVar],
        repeats: int,
    ):
        """Base function used to run benchers with a set of inputs,results and repeats over time"""
        bench = bn.Bench("test_bencher", bench_func, BenchCfgTest)

        for i in range(2):
            bench.plot_sweep(
                title="test_unique_filenames",
                input_vars=input_vars,
                result_vars=result_vars,
                run_cfg=bn.BenchRunCfg(
                    repeats=repeats,
                    over_time=True,
                    clear_history=i == 0,  # clear the history on the first iteration
                ),
                time_src=datetime(
                    1970, 1, i + 1
                ),  # repeatable time so outputs are same at the pixel level
            )

    @settings(deadline=10000, max_examples=50)
    @given(
        input_vars=st.sampled_from(input_var_permutations),
        result_vars=st.sampled_from(result_var_permutations),
        repeats=st.sampled_from([1, 2]),
    )
    def test_all_input_combinations_over_time_hyp(
        self,
        input_vars: list[Parameter],
        result_vars: list[bn.ResultVar],
        repeats: int,
    ):
        """Use hypothesis to enumerate combinations of inputs to bencher

        Args:
            input_vars (list[Parameter]): all possible sets of inputs
            result_vars (list[bn.ResultVar]): all possible sets of results
            repeats (int): 1 or 2 repeats (more than 2 repeats hits the same code as 2 repeats)
        """
        self.run_bencher_over_time(input_vars, result_vars, repeats)

    def test_falsifying_examples(self):
        """This test runs all the falsifying examples that were caught by hypothesis"""

        # TODO this has been been "fixed" by catching the pandas keyerrors for plot_surface_holo().  It needs to be fixed properly by investigating aggregation of bool datatypes.  At the moment bool variables can cause agreggation errors. Possibly convert the bool to an enum type??
        self.run_bencher_over_time(
            [
                BenchCfgTest.param.float1,
                BenchCfgTest.param.enum1,
                BenchCfgTest.param.bool1,
            ],
            [BenchCfgTestOut.param.out1],
            1,
        )

        # Properly fixed
        self.run_bencher_over_time(
            [
                BenchCfgTest.param.bool1,
                BenchCfgTest.param.bool2,
                BenchCfgTest.param.enum1,
                BenchCfgTest.param.enum2,
            ],
            [BenchCfgTestOut.param.out1],
            1,
        )

        # TODO, These inputs need to be fixed.
        # self.run_bencher_over_time(
        #     [BenchCfgTest.param.float1],
        #     [BenchCfgTestOut.param.outvec3],
        #     1,
        # )

        # self.run_bencher_over_time(
        #     [BenchCfgTest.param.float1, BenchCfgTest.param.float2],
        #     [BenchCfgTestOut.param.outvec2],
        #     1,
        # )
