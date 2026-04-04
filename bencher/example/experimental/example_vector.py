# """Example on how to sweep over function with vector outputs"""

# from math import cos, sin

# import numpy as np

# import bencher as bn


# class OffsetCfg(bn.ParametrizedSweep):
#     """A class for describing which parameters to sweep"""

#     dc_offset = bn.FloatSweep(
#         default=0,
#         bounds=[0.0, 2.0],
#         samples=4,
#         units="v",
#         doc="DC offset to add to the result of the signal",
#     )
#     phase_offset = bn.FloatSweep(
#         default=0,
#         bounds=[0.0, 3.14],
#         samples=4,
#         units="rad",
#         doc="phase offset that is added to the input before passing to the trig function",
#     )


# class SweepResult(bn.ParametrizedSweep):
#     """A class to describe the vector outputs of the benchmark function"""

#     sin_sweep = bn.ResultList(
#         index_name="time", index_units="s", units="v", doc="A list of values from a sin function"
#     )
#     cos_sweep = bn.ResultList(
#         index_name="time", index_units="s", units="v", doc="A list of values from a cos function"
#     )


# def sin_sweep(cfg: OffsetCfg) -> SweepResult:
#     """A function that returns vector outputs of the sin and cos functions

#     Args:
#         cfg (OffsetCfg): Options for phase and dc offset

#     Returns:
#         SweepResult: vectors with sin and cos results
#     """
#     res = SweepResult()
#     print(type(res.sin_sweep))
#     for i in np.arange(0, 6.28, 0.02):
#         res.sin_sweep.append(sin(i + cfg.phase_offset) + cfg.dc_offset, i)
#         # res.sin_sweep.indices.append(i)
#     for i in np.arange(0, 3.28, 0.02):
#         res.cos_sweep.append(cos(i + cfg.phase_offset) + cfg.dc_offset, i)
#         # res.cos_sweep.indices.append(i)
#     return res


# def example_vector() -> bn.Bench:
#     """Example on how to sweep over function with vector outputs"""
#     bencher = bn.Bench("vector output example", sin_sweep, OffsetCfg)

#     bencher.plot_sweep(
#         title="Sweep DC offset",
#         input_vars=[OffsetCfg.param.dc_offset],
#         result_vars=[SweepResult.param.sin_sweep, SweepResult.param.cos_sweep],
#         description="""This is an example of how to sample function that return a vector of unknown or varying size. In this example it returns the output of the sin and cos function for varying angles and a range of dc offsets""",
#         post_description="""The output shows stack of sin and cos functions as the dc offset increases""",
#     )

#     bencher.plot_sweep(
#         title="Sweep phase offset",
#         input_vars=[OffsetCfg.param.phase_offset],
#         result_vars=[SweepResult.param.sin_sweep, SweepResult.param.cos_sweep],
#         description="""This is an example of how to sample function that return a vector of unknown or varying size. In this example it returns the output of the sin and cos function for varying angles and a range of phase offsets""",
#         post_description="""The output shows different phases of the sin and cos functions""",
#     )

#     return bencher


# if __name__ == "__main__":
#     example_vector().plot()
