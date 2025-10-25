"""
Example: PyVista Meshes as Bencher Result Variables with Interactive Display

This example demonstrates how to use PyVista to create and visualize three types of meshes
(sphere, cube, cylinder) as result variables in Bencher with interactive VTK panes for
dynamic display.

You can sweep mesh type and color with interactive 3D visualizations.
"""

import bencher as bch
import pyvista as pv
import panel as pn

try:
    from enum import StrEnum
except ImportError:
    from strenum import StrEnum

pn.extension("vtk")

#   - libx11-6 # required for VTK rendering
#   - libxrender1 # required for VTK rendering
#   - libegl1-mesa # required for PyVista/Panel off-screen rendering
#   - libosmesa6 # required for PyVista/Panel off-screen rendering
#   - mesa-utils # provides glxinfo and other OpenGL utilities
#   - libgl1-mesa-dri # provides swrast_dri.so for software rasterizer


class MeshType(StrEnum):
    Sphere = "sphere"
    Cube = "cube"
    Cylinder = "cylinder"


def render_pyvista_mesh_interactive(mesh, color="lightblue", **kwargs):
    """Create interactive VTK pane for dynamic display (when supported)"""
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(mesh, color=color)

    # Zoom out by setting camera position further away
    plotter.camera.zoom(0.7)  # Zoom out (values < 1 zoom out, > 1 zoom in)

    vtk_pane = pn.pane.VTK(
        plotter.ren_win, sizing_mode="stretch_width", height=300, orientation_widget=True
    )
    return vtk_pane


class BenchPyVistaMesh(bch.ParametrizedSweep):
    mesh_type = bch.EnumSweep(MeshType, default=MeshType.Sphere, doc="Type of mesh to display")
    color = bch.StringSweep(
        ["lightblue", "lightgreen", "lightcoral"], default="lightblue", doc="Mesh color"
    )
    mesh_interactive = bch.ResultReference(doc="Interactive VTK visualization of mesh")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        mesh = self.create_mesh(self.mesh_type)

        # Create interactive version for dynamic display
        self.mesh_interactive = bch.ResultReference(
            obj=mesh, container=render_pyvista_mesh_interactive, doc="Interactive VTK visualization"
        )
        return super().__call__()

    @staticmethod
    def create_mesh(mesh_type: str):
        if mesh_type == "sphere":
            return pv.Sphere(radius=1.0, center=(0, 0, 0))
        elif mesh_type == "cube":
            return pv.Cube(center=(0, 0, 0), x_length=2, y_length=2, z_length=2)
        elif mesh_type == "cylinder":
            return pv.Cylinder(center=(0, 0, 0), direction=(0, 1, 0), radius=1.0, height=2.0)
        else:
            raise ValueError(f"Unknown mesh type: {mesh_type}")


def example_pyvista_mesh(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    bench = bch.Bench("pyvista_mesh", BenchPyVistaMesh(), run_cfg=run_cfg, report=report)
    bench.plot_sweep(
        title="PyVista Mesh Sweep - Interactive Display",
        input_vars=[BenchPyVistaMesh.param.mesh_type, BenchPyVistaMesh.param.color],
        result_vars=[BenchPyVistaMesh.param.mesh_interactive],
        description="Sweep mesh type and color with interactive 3D VTK visualizations.",
    )
    return bench


if __name__ == "__main__":
    # Example usage for interactive display
    bench = example_pyvista_mesh()

    # For dynamic display with interactive VTK widgets:
    bench.report.save()
    # bench.report.show()
