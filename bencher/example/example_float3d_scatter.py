# pylint: disable=duplicate-code
import numpy as np
import bencher as bch
import holoviews as hv
import pandas as pd

hv.extension("plotly")


class ScatterSweep(bch.ParametrizedSweep):
    """A class to represent a 3D scatter plot example."""

    category_type = bch.StringSweep(
        ["sphere", "cube", "helix"], doc="Type of 3D pattern to generate"
    )

    scatter_points = bch.ResultScatter3D(doc="3D scatter point dataset with x,y,z coordinates")
    avg_distance = bch.ResultVar("ul", doc="Average distance from origin")
    # avg_intensity = bch.ResultVar("ul", doc="Average intensity value")

    def __call__(self, **kwargs) -> dict:
        """Generate multiple 3D scatter points for each category."""
        self.update_params_from_kwargs(**kwargs)

        # Initialize arrays for storing points
        x_points = []
        y_points = []
        z_points = []
        distances = []
        intensities = []

        num_points = 30

        # Generate multiple points for the selected category
        for i in range(num_points):
            t = i / (num_points - 1)  # Normalize to [0, 1]

            if self.category_type == "sphere":
                # Spherical distribution
                phi = t * 4 * np.pi  # More rotations for denser sampling
                theta = np.arccos(1 - 2 * (t * 0.8 + 0.1))  # Avoid poles
                radius = 1.5 + 0.5 * np.sin(t * 6 * np.pi)
                x = radius * np.sin(theta) * np.cos(phi)
                y = radius * np.sin(theta) * np.sin(phi)
                z = radius * np.cos(theta)
                self.category = 1  # sphere category code
                intensity = np.abs(np.sin(np.linalg.norm([x, y, z]) * 2))

            elif self.category_type == "cube":
                # Cube edge and face pattern
                if i < num_points // 2:
                    # Edge points
                    edge = int(t * 12) % 12
                    s = (t * 12) % 1
                    if edge < 4:  # Bottom edges
                        positions = [
                            (s - 0.5, -0.5, -0.5),
                            (0.5, s - 0.5, -0.5),
                            (0.5 - s, 0.5, -0.5),
                            (-0.5, 0.5 - s, -0.5),
                        ]
                        x, y, z = [2 * p for p in positions[edge]]
                    elif edge < 8:  # Top edges
                        positions = [
                            (s - 0.5, -0.5, 0.5),
                            (0.5, s - 0.5, 0.5),
                            (0.5 - s, 0.5, 0.5),
                            (-0.5, 0.5 - s, 0.5),
                        ]
                        x, y, z = [2 * p for p in positions[edge - 4]]
                    else:  # Vertical edges
                        positions = [
                            (-0.5, -0.5, s - 0.5),
                            (0.5, -0.5, s - 0.5),
                            (0.5, 0.5, s - 0.5),
                            (-0.5, 0.5, s - 0.5),
                        ]
                        x, y, z = [2 * p for p in positions[edge - 8]]
                else:
                    # Face center points
                    face = i % 6
                    offset = 0.3 * np.sin(t * 2 * np.pi)
                    if face == 0:  # front
                        x, y, z = offset, offset, 1
                    elif face == 1:  # back
                        x, y, z = offset, offset, -1
                    elif face == 2:  # right
                        x, y, z = 1, offset, offset
                    elif face == 3:  # left
                        x, y, z = -1, offset, offset
                    elif face == 4:  # top
                        x, y, z = offset, 1, offset
                    else:  # bottom
                        x, y, z = offset, -1, offset
                self.category = 2  # cube category code
                intensity = np.abs(x * y * z) / 8 + 0.1

            else:  # helix
                # Helical pattern
                angle = t * 8 * np.pi  # More rotations
                height = (t - 0.5) * 4  # Height from -2 to 2
                radius = 1.2 + 0.4 * np.cos(t * 10 * np.pi)
                x = radius * np.cos(angle)
                y = radius * np.sin(angle)
                z = height
                self.category = 3  # helix category code
                intensity = (np.abs(z) + 2) / 4

            # Store the point
            x_points.append(x)
            y_points.append(y)
            z_points.append(z)
            distance = np.linalg.norm([x, y, z])
            distances.append(distance)
            intensities.append(intensity)

        # Create pandas DataFrame for the scatter points

        scatter_df = pd.DataFrame(
            {
                "x": x_points,
                "y": y_points,
                "z": z_points,
                "distance": distances,
                "intensity": intensities,
                "color_value": [d * i for d, i in zip(distances, intensities)],
            }
        )

        # Store as ResultScatter3D
        self.scatter_points = bch.ResultScatter3D(scatter_df)
        self.avg_distance = np.mean(distances)

        return super().__call__()


def example_float3d_scatter(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example of how to create a 3D scatter plot with bencher

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep
        report (BenchReport): report to add results to

    Returns:
        Bench: results of the parameter sweep
    """
    bench = ScatterSweep().to_bench(run_cfg=run_cfg, report=report)

    res = bench.plot_sweep(
        title="Float 3D Scatter Example - Three Distinct Patterns",
        result_vars=["scatter_points"],
        description="""This example demonstrates 3D scatter plots with three distinct patterns: sphere, cube, and helix. Each category generates 30 points with unique geometric patterns stored as ResultScatter3D.""",
        post_description="The visualization shows three separate 3D scatter plots - spherical distribution, cubic edge/face pattern, and helical trajectory - automatically rendered as interactive 3D scatter plots.",
    )

    bench.report.append(res.to_scatter3d())
    # Add automatic 3D scatter plot visualization
    # bench.add(bch.Scatter3DResult)

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.level = 4
    example_float3d_scatter(ex_run_cfg).report.show()
