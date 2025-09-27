# pylint: disable=duplicate-code


import numpy as np

import bencher as bch


class VolumeSample(bch.ParametrizedSweep):
    """A class to represent a 3D point in space."""

    x = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="x coordinate of the sample volume", samples=9
    )
    y = bch.FloatSweep(
        default=0, bounds=[-2.0, 2.0], doc="y coordinate of the sample volume", samples=10
    )
    z = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="z coordinate of the sample volume", samples=11
    )

    surf_x = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="z coordinate of the sample volume", samples=9
    )

    surf_y = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="z coordinate of the sample volume", samples=11
    )


class VolumeResult(bch.ParametrizedSweep):
    """A class to represent the properties of a volume sample."""

    # value = bch.ResultVar("ul", doc="The scalar value of the 3D volume field")
    p1_dis = bch.ResultVar("m", direction=bch.OptDir.minimize, doc="The distance to p1")
    p2_dis = bch.ResultVar("m", direction=bch.OptDir.minimize, doc="The distance to p2")
    total_dis = bch.ResultVar(
        "m", direction=bch.OptDir.minimize, doc="The total distance to all points"
    )
    surf_value = bch.ResultVar(
        "ul", direction=bch.OptDir.maximize, doc="The scalar value of the 3D volume field"
    )
    # occupancy = bch.ResultVar("occupied", doc="If the value is > 0.5 this point is considered occupied")


p1 = np.array([0.4, 0.6, 0.0])
p2 = np.array([-0.8, -0.2, 0.0])
surf_x_max = 0.5
surf_y_max = -0.2


def bench_fn(point: VolumeSample) -> VolumeResult:
    """This function takes a 3D point as input and returns distance of that point to the origin.

    Args:
        point (VolumeSample): Sample point

    Returns:
        VolumeResult: Value at that point
    """

    cur_point = np.array([point.x, point.y, point.z])

    output = VolumeResult()
    output.p1_dis = np.linalg.norm(p1 - cur_point)
    output.p2_dis = np.linalg.norm(p2 - cur_point)
    output.total_dis = output.p1_dis + output.p2_dis

    output.surf_value = output.total_dis + np.linalg.norm(
        np.array(
            [np.cos(point.surf_x - surf_x_max), 2 * np.cos(point.surf_y - surf_y_max), point.z]
        )
    )

    return output


def example_floats2D_workflow(run_cfg: bch.BenchRunCfg, bench: bch.Bench = None) -> bch.Bench:
    """Example of how to perform a 3D floating point parameter sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    if bench is None:
        bench = bch.Bench("Bencher_Example_Floats", bench_fn, VolumeSample)

    # run_cfg.debug = False

    res = bench.plot_sweep(
        input_vars=[VolumeSample.param.x, VolumeSample.param.y],
        result_vars=[
            VolumeResult.param.total_dis,
            VolumeResult.param.p1_dis,
            VolumeResult.param.p2_dis,
        ],
        const_vars=[VolumeSample.param.z.with_const(0)],
        title="Float 2D Example",
        run_cfg=run_cfg,
    )
    recovered_p1 = res.get_optimal_vec(VolumeResult.param.p1_dis, res.bench_cfg.input_vars)
    print(f"recovered p1: {recovered_p1}, distance: {np.linalg.norm(recovered_p1 - p1[:2])}")
    # within tolerance of sampling
    # assert np.linalg.norm(recovered_p1 - p1[:2]) < 0.15

    recovered_p2 = res.get_optimal_vec(VolumeResult.param.p2_dis, res.bench_cfg.input_vars)
    print(f"recovered p2: {recovered_p2} distance: {np.linalg.norm(recovered_p2 - p2[:2])}")
    # within tolerance of sampling
    # assert np.linalg.norm(recovered_p2 - p2[:2]) < 0.15

    run_cfg.use_optuna = True
    for rv in res.bench_cfg.result_vars:
        bench.plot_sweep(
            input_vars=[VolumeSample.param.surf_x, VolumeSample.param.surf_y],
            result_vars=[
                VolumeResult.param.surf_value,
            ],
            const_vars=res.get_optimal_inputs(rv, True),
            title=f"Slice of 5D space for {rv.name}",
            description="""This example shows how to sample 3 floating point variables and plot a 3D vector field of the results.""",
            run_cfg=run_cfg,
        )

    return bench


def example_floats3D_workflow(run_cfg: bch.BenchRunCfg, bench: bch.Bench = None) -> bch.Bench:
    """Example of how to perform a 3D floating point parameter sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    if bench is None:
        bench = bch.Bench("Bencher_Example_Floats", bench_fn, VolumeSample)

    # run_cfg.debug = False

    res = bench.plot_sweep(
        input_vars=[VolumeSample.param.x, VolumeSample.param.y, VolumeSample.param.z],
        result_vars=[
            VolumeResult.param.total_dis,
            VolumeResult.param.p1_dis,
            VolumeResult.param.p2_dis,
            # get_optimal_inputsm.occupancy,
        ],
        title="Float 3D Example",
        description="""This example shows how to sample 3 floating point variables and plot a volumetric representation of the results.  The benchmark function returns the distance to the origin""",
        post_description="Here you can see concentric shells as the value of the function increases with distance from the origin. The occupancy graph should show a sphere with radius=0.5",
        run_cfg=run_cfg,
    )

    recovered_p1 = res.get_optimal_vec(VolumeResult.param.p1_dis, res.bench_cfg.input_vars)
    print(f"recovered p1: {recovered_p1}, distance: {np.linalg.norm(recovered_p1 - p1)}")
    # within tolerance of sampling
    # assert np.linalg.norm(recovered_p1 - p1) < 0.15

    recovered_p2 = res.get_optimal_vec(VolumeResult.param.p2_dis, res.bench_cfg.input_vars)
    print(f"recovered p2: {recovered_p2} distance: {np.linalg.norm(recovered_p2 - p2)}")
    # within tolerance of sampling
    # assert np.linalg.norm(recovered_p2 - p2) < 0.15

    run_cfg.use_optuna = True
    for rv in res.bench_cfg.result_vars:
        bench.plot_sweep(
            input_vars=[VolumeSample.param.surf_x, VolumeSample.param.surf_y],
            result_vars=[
                VolumeResult.param.surf_value,
            ],
            const_vars=res.get_optimal_inputs(rv, True),
            title=f"Slice of 5D space for {rv.name}",
            description="""This example shows how to sample 3 floating point variables and plot a 3D vector field of the results.""",
            run_cfg=run_cfg,
        )

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()

    bench_ex = example_floats2D_workflow(ex_run_cfg)
    example_floats3D_workflow(ex_run_cfg, bench_ex)

    bench_ex.report.show()
