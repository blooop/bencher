# pylint: disable=duplicate-code
import numpy as np
import bencher as bch


class VolumeSweep(bch.ParametrizedSweep):
    """A class to represent a 3D point in space."""

    x = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="x coordinate of the sample volume", samples=4
    )
    y = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="y coordinate of the sample volume", samples=5
    )
    z = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="z coordinate of the sample volume", samples=6
    )

    value = bch.ResultVar("ul", doc="The scalar value of the 3D volume field")
    occupancy = bch.ResultVar(
        "occupied", doc="If the value is > 0.5 this point is considered occupied"
    )
    interesting = bch.ResultVar("ul", doc="A more interesting scalar field")
    interesting_vec = bch.ResultVec(3, "vec", doc="A vector field with an interesting shape")
    interesting_vec_and_occ = bch.ResultVec(
        3, "vec", doc="The same vector field but only showing values in a sphere of radius 0.5"
    )

    def __call__(self, **kwargs) -> dict:
        """This function takes a 3D point as input and returns distance of that point to the origin."""
        self.update_params_from_kwargs(**kwargs)
        self.value = np.linalg.norm(np.array([self.x, self.y, self.z]))  # distance to origin
        self.occupancy = float(self.value < 0.5)
        # from https://plotly.com/python/3d-volume-plots/
        self.interesting = np.sin(np.pi * self.x) * np.cos(np.pi * self.z) * np.sin(np.pi * self.y)
        self.interesting_vec = [
            np.sin(np.pi * self.x),
            np.cos(np.pi * self.z),
            np.sin(np.pi * self.y),
        ]

        if self.occupancy:
            self.interesting_vec_and_occ = self.interesting_vec
        else:
            self.interesting_vec_and_occ = [0, 0, 0]

        return super().__call__()


def example_floats3D(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Example of how to perform a 3D floating point parameter sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    bench = VolumeSweep().to_bench(run_cfg)

    bench.plot_sweep(
        title="Float 3D Example",
        input_vars=["x", "y", "z"],
        result_vars=[
            "value",
            "occupancy",
            "interesting",
        ],
        description="""This example shows how to sample 3 floating point variables and plot a volumetric representation of the results.  The benchmark function returns the distance to the origin""",
        post_description="Here you can see concentric shells as the value of the function increases with distance from the origin. The occupancy graph should show a sphere with radius=0.5",
    )

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.level = 6
    example_floats3D(ex_run_cfg).report.show()
