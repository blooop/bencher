

"""
Example: PyVista Meshes as Bencher Result Variables

This example demonstrates how to use PyVista to create and visualize three types of meshes (sphere, cube, cylinder) as result variables in Bencher, matching the style of other Bencher examples. You can sweep mesh type and color.
"""

import bencher as bch
import pyvista as pv
import panel as pn

try:
    from enum import StrEnum
except ImportError:
    from strenum import StrEnum

pn.extension("vtk")


class MeshType(StrEnum):
    Sphere = "sphere"
    Cube = "cube"
    Cylinder = "cylinder"

def render_pyvista_mesh(ref, color="lightblue", **kwargs):
    # Handle Bencher's per-cell rendering: ref may be a ResultReference or a dict
    # if isinstance(ref, dict):
    #     ref = ref.get("vtk_mesh", ref)
    # if ref is None or not hasattr(ref, "obj"):
    #     return pn.pane.Markdown("No mesh to display")
    mesh = ref
    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(mesh, color=color)
    vtk_pane = pn.pane.VTK(
        plotter.ren_win, sizing_mode="stretch_width", height=300, orientation_widget=True
    )
    return vtk_pane

class BenchPyVistaMesh(bch.ParametrizedSweep):
    mesh_type = bch.EnumSweep(MeshType, default=MeshType.Sphere, doc="Type of mesh to display")
    color = bch.StringSweep(
        ["lightblue", "lightgreen", "lightcoral"], default="lightblue", doc="Mesh color"
    )
    vtk_mesh = bch.ResultReference(doc="VTK visualization of mesh")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        mesh = self.create_mesh(self.mesh_type.value)
        self.vtk_mesh = bch.ResultReference(
            obj=mesh, container=render_pyvista_mesh, doc="VTK visualization of mesh"
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
        title="PyVista Mesh Sweep",
        input_vars=[BenchPyVistaMesh.param.mesh_type, BenchPyVistaMesh.param.color],
        result_vars=[BenchPyVistaMesh.param.vtk_mesh],
        description="Sweep mesh type and color, displaying PyVista meshes as result variables using Panel's VTK pane.",
    )
    return bench


if __name__ == "__main__":
    example_pyvista_mesh().report.show()
