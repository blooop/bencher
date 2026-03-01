# pylint: disable=duplicate-code


import numpy as np

import bencher as bch


class VolumeSweep(bch.ParametrizedSweep):
    """A class to represent a 3D point in space and its properties."""

    # Inputs
    x = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="x coordinate of the sample volume", samples=9
    )
    y = bch.FloatSweep(
        default=0, bounds=[-2.0, 2.0], doc="y coordinate of the sample volume", samples=10
    )
    z = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="z coordinate of the sample volume", samples=11
    )

    surf_x = bch.FloatSweep(default=0, bounds=[-1.0, 1.0], doc="surface x coordinate", samples=9)

    surf_y = bch.FloatSweep(default=0, bounds=[-1.0, 1.0], doc="surface y coordinate", samples=11)

    # Results
    p1_dis = bch.ResultVar("m", direction=bch.OptDir.minimize, doc="The distance to p1")
    p2_dis = bch.ResultVar("m", direction=bch.OptDir.minimize, doc="The distance to p2")
    total_dis = bch.ResultVar(
        "m", direction=bch.OptDir.minimize, doc="The total distance to all points"
    )
    surf_value = bch.ResultVar(
        "ul", direction=bch.OptDir.maximize, doc="The scalar value of the 3D volume field"
    )

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        cur_point = np.array([self.x, self.y, self.z])
        self.p1_dis = np.linalg.norm(p1 - cur_point)
        self.p2_dis = np.linalg.norm(p2 - cur_point)
        self.total_dis = self.p1_dis + self.p2_dis
        self.surf_value = self.total_dis + np.linalg.norm(
            np.array(
                [
                    np.cos(self.surf_x - surf_x_max),
                    2 * np.cos(self.surf_y - surf_y_max),
                    self.z,
                ]
            )
        )
        return super().__call__()


p1 = np.array([0.4, 0.6, 0.0])
p2 = np.array([-0.8, -0.2, 0.0])
surf_x_max = 0.5
surf_y_max = -0.2


def example_floats2D_workflow(
    run_cfg: bch.BenchRunCfg, bench: bch.Bench | None = None
) -> bch.Bench:
    """Example of how to perform a 3D floating point parameter sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    if bench is None:
        bench = bch.Bench("Bencher_Example_Floats", VolumeSweep())
    res = bench.plot_sweep(
        input_vars=["x", "y"],
        result_vars=["total_dis", "p1_dis", "p2_dis"],
        const_vars=dict(z=0),
        title="Float 2D Example",
        run_cfg=run_cfg,
    )
    recovered_p1 = res.get_optimal_vec(VolumeSweep.param.p1_dis, res.bench_cfg.input_vars)
    print(f"recovered p1: {recovered_p1}, distance: {np.linalg.norm(recovered_p1 - p1[:2])}")
    recovered_p2 = res.get_optimal_vec(VolumeSweep.param.p2_dis, res.bench_cfg.input_vars)
    print(f"recovered p2: {recovered_p2} distance: {np.linalg.norm(recovered_p2 - p2[:2])}")
    run_cfg.use_optuna = True
    for rv in res.bench_cfg.result_vars:
        bench.plot_sweep(
            input_vars=["surf_x", "surf_y"],
            result_vars=["surf_value"],
            const_vars=res.get_optimal_inputs(rv, True),
            title=f"Slice of 5D space for {rv}",
            description="""This example shows how to sample 3 floating point variables and plot a 3D vector field of the results.""",
            run_cfg=run_cfg,
        )
    return bench


def example_floats3D_workflow(
    run_cfg: bch.BenchRunCfg, bench: bch.Bench | None = None
) -> bch.Bench:
    """Example of how to perform a 3D floating point parameter sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    if bench is None:
        bench = bch.Bench("Bencher_Example_Floats", VolumeSweep())
    res = bench.plot_sweep(
        input_vars=["x", "y", "z"],
        result_vars=["total_dis", "p1_dis", "p2_dis"],
        title="Float 3D Example",
        description="""This example shows how to sample 3 floating point variables and plot a volumetric representation of the results.  The benchmark function returns the distance to the origin""",
        post_description="Here you can see concentric shells as the value of the function increases with distance from the origin. The occupancy graph should show a sphere with radius=0.5",
        run_cfg=run_cfg,
    )
    recovered_p1 = res.get_optimal_vec(VolumeSweep.param.p1_dis, res.bench_cfg.input_vars)
    print(f"recovered p1: {recovered_p1}, distance: {np.linalg.norm(recovered_p1 - p1)}")
    recovered_p2 = res.get_optimal_vec(VolumeSweep.param.p2_dis, res.bench_cfg.input_vars)
    print(f"recovered p2: {recovered_p2} distance: {np.linalg.norm(recovered_p2 - p2)}")
    run_cfg.use_optuna = True
    for rv in res.bench_cfg.result_vars:
        bench.plot_sweep(
            input_vars=["surf_x", "surf_y"],
            result_vars=["surf_value"],
            const_vars=res.get_optimal_inputs(rv, True),
            title=f"Slice of 5D space for {rv}",
            description="""This example shows how to sample 3 floating point variables and plot a 3D vector field of the results.""",
            run_cfg=run_cfg,
        )
    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()

    bench_ex = example_floats2D_workflow(ex_run_cfg)
    example_floats3D_workflow(ex_run_cfg, bench_ex)

    bench_ex.report.show()
