# import numpy as np

# import bencher as bn


# class VolumeSample(bn.ParametrizedSweep):
#     """A class to represent a 3D point in space."""

#     pos_samples = 1

#     x = bn.FloatSweep(
#         default=0, bounds=[-1.0, 1.0], samples=pos_samples, doc="x coordinate of the sample volume"
#     )
#     y = bn.FloatSweep(
#         default=0, bounds=[-1.0, 1.0], samples=pos_samples, doc="y coordinate of the sample volume"
#     )
#     z = bn.FloatSweep(
#         default=0, bounds=[-1.0, 1.0], samples=pos_samples, doc="z coordinate of the sample volume"
#     )

#     vec_samples = 5

#     vec_x = bn.FloatSweep(
#         default=0, bounds=[-1.0, 1.0], samples=vec_samples, doc="x coordinate of the sample volume"
#     )
#     vec_y = bn.FloatSweep(
#         default=0, bounds=[-1.0, 1.0], samples=vec_samples, doc="y coordinate of the sample volume"
#     )
#     vec_z = bn.FloatSweep(
#         default=0, bounds=[-1.0, 1.0], samples=vec_samples, doc="z coordinate of the sample volume"
#     )


# class VolumeResult(bn.ParametrizedSweep):
#     """A class to represent the properties of a volume sample."""

#     vec_dir = bn.ResultVec(3, "vec", doc="A vector field with an interesting shape")


# def bench_fn(point: VolumeSample, normalise=False) -> VolumeResult:
#     """This function takes a 3D point as input and returns distance of that point to the origin.

#     Args:
#         point (VolumeSample): Sample point

#     Returns:
#         VolumeResult: Value at that point
#     """
#     output = VolumeResult()

#     vec = np.array([point.vec_x, point.vec_y, point.vec_z])

#     if normalise:
#         norm = np.linalg.norm(vec)
#         if norm > 0:
#             vec /= norm

#     output.vec_dir = list(vec)
#     return output


# def example_cone(run_cfg: bn.BenchRunCfg) -> bn.Bench:
#     """Example of how to perform a 3D floating point parameter sweep

#     Args:
#         run_cfg (BenchRunCfg): configuration of how to perform the param sweep

#     Returns:
#         Bench: results of the parameter sweep
#     """
#     bench = bn.Bench("Bencher_Example_Cone", bench_fn, VolumeSample)

#     bench.plot_sweep(
#         input_vars=[
#             VolumeSample.param.x,
#             VolumeSample.param.y,
#             VolumeSample.param.z,
#             VolumeSample.param.vec_x,
#             VolumeSample.param.vec_y,
#             VolumeSample.param.vec_z,
#         ],
#         result_vars=[
#             VolumeResult.param.vec_dir,
#         ],
#         title="Float 3D cone Example",
#         description="""This example shows how to sample 3 floating point variables and plot a vector field representation of the results.  The benchmark function returns the distance to the origin""",
#         run_cfg=run_cfg,
#     )

#     return bench


# if __name__ == "__main__":
#     ex_run_cfg = bn.BenchRunCfg()
#     ex_run_cfg.cache_results = True
#     example_cone(ex_run_cfg).report.show()
