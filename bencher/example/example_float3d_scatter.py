# pylint: disable=duplicate-code
import numpy as np
import bencher as bch


class ScatterSweep(bch.ParametrizedSweep):
    """A class to represent a 3D scatter plot example."""

    x = bch.FloatSweep(
        default=0, bounds=[-2.0, 2.0], doc="x coordinate for scatter points", samples=8
    )
    y = bch.FloatSweep(
        default=0, bounds=[-2.0, 2.0], doc="y coordinate for scatter points", samples=8
    )
    z = bch.FloatSweep(
        default=0, bounds=[-2.0, 2.0], doc="z coordinate for scatter points", samples=8
    )

    distance = bch.ResultVar("ul", doc="Distance from origin to the point")
    category = bch.ResultVar("cat", doc="Categorical classification based on distance")
    intensity = bch.ResultVar("ul", doc="Intensity value based on trigonometric function")
    color_value = bch.ResultVar("ul", doc="Color mapping value for visualization")

    def __call__(self, **kwargs) -> dict:
        """Calculate scatter point properties based on 3D coordinates."""
        self.update_params_from_kwargs(**kwargs)
        
        # Calculate distance from origin
        self.distance = np.linalg.norm(np.array([self.x, self.y, self.z]))
        
        # Categorize points based on distance
        if self.distance < 1.0:
            self.category = "close"
        elif self.distance < 2.0:
            self.category = "medium"
        else:
            self.category = "far"
        
        # Create intensity based on trigonometric functions
        self.intensity = np.abs(
            np.sin(self.x) * np.cos(self.y) * np.sin(self.z)
        )
        
        # Color value combining distance and intensity
        self.color_value = self.distance * self.intensity

        return super().__call__()


def example_float3d_scatter(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    """Example of how to create a 3D scatter plot with bencher

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep
        report (BenchReport): report to add results to

    Returns:
        Bench: results of the parameter sweep
    """
    bench = ScatterSweep().to_bench(run_cfg=run_cfg, report=report)

    bench.plot_sweep(
        title="Float 3D Scatter Example",
        input_vars=["x", "y", "z"],
        result_vars=[
            "distance",
            "category", 
            "intensity",
            "color_value",
        ],
        description="""This example demonstrates a 3D scatter plot using bencher. Points are sampled in 3D space and colored based on their distance from origin and trigonometric intensity values.""",
        post_description="The scatter plot shows points categorized by distance (close, medium, far) with color intensity based on combined distance and trigonometric functions.",
    )

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.level = 6
    example_float3d_scatter(ex_run_cfg).report.show()