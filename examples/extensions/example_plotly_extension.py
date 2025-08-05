"""
Example extension demonstrating how to create a third-party Bencher result extension.

This example shows a Plotly-based 3D visualization extension that could be
distributed as a separate package.
"""

from typing import Optional, List, Callable
import panel as pn

# Import Bencher extension system
from bencher.extensions import result_extension, ResultExtensionBase
from bencher.bench_cfg import BenchCfg
from bencher.variables.results import ResultVar


@result_extension(
    name="plotly_3d_example",
    version="1.0.0",
    description="Example 3D visualization extension using Plotly",
    author="Bencher Example",
    dependencies=["plotly>=5.0"],
    result_types=["ResultVar"],  # Can handle basic result variables
    plot_types=["3d_scatter", "3d_surface"],
    target_dimensions=[3],  # Supports 3D data
    auto_register=True,  # Automatically register when imported
)
class Plotly3DExtension(ResultExtensionBase):
    """Example extension providing 3D plotting capabilities with Plotly."""

    def can_handle(self, bench_cfg: BenchCfg) -> bool:
        """
        Check if this extension can handle the benchmark configuration.

        This extension handles cases with 2+ float input variables (for 3D plotting).
        """
        float_vars = [
            v for v in bench_cfg.input_vars if hasattr(v, "bounds") and len(v.bounds) == 2
        ]
        return len(float_vars) >= 2 and len(bench_cfg.result_vars) >= 1

    def to_plot(self, **kwargs) -> Optional[pn.panel]:
        """
        Create the primary 3D plot for this extension.

        This is the main plotting method that gets called automatically.
        """
        try:
            # Try 3D scatter first
            scatter_plot = self.to_3d_scatter(**kwargs)
            if scatter_plot is not None:
                return scatter_plot

            # Fallback to surface plot
            return self.to_3d_surface(**kwargs)

        except Exception as e:
            print(f"Plotly3D extension error: {e}")
            return None

    def to_3d_scatter(self, result_var: ResultVar = None, **kwargs) -> Optional[pn.panel]:
        """Create a 3D scatter plot using Plotly."""
        try:
            # Check if plotly is available
            import plotly.express as px

            # Get the dataset
            ds = self.to_dataset()
            if ds is None or len(ds.dims) < 2:
                return None

            # Get input variables (use first 2 for X,Y and result for Z)
            input_vars = list(ds.dims)[:2]
            if len(input_vars) < 2:
                return None

            # Get result variable
            if result_var is None and self.bench_cfg.result_vars:
                result_var = self.bench_cfg.result_vars[0]

            if result_var is None or result_var.name not in ds.data_vars:
                return None

            # Convert to pandas for easier plotting
            df = ds.to_dataframe().reset_index()

            # Create 3D scatter plot
            fig = px.scatter_3d(
                df,
                x=input_vars[0],
                y=input_vars[1],
                z=result_var.name,
                title=f"3D Scatter: {result_var.name} vs {input_vars[0]} vs {input_vars[1]}",
                **kwargs,
            )

            # Update layout for better appearance
            fig.update_layout(
                scene=dict(
                    xaxis_title=input_vars[0],
                    yaxis_title=input_vars[1],
                    zaxis_title=result_var.name,
                ),
                width=600,
                height=600,
            )

            # Return as Panel pane
            return pn.pane.Plotly(fig, sizing_mode="stretch_width")

        except ImportError:
            print("Plotly not available for 3D scatter plot")
            return None
        except Exception as e:
            print(f"Error creating 3D scatter plot: {e}")
            return None

    def to_3d_surface(self, result_var: ResultVar = None, **kwargs) -> Optional[pn.panel]:
        """Create a 3D surface plot using Plotly."""
        try:
            import plotly.graph_objects as go

            # Get the dataset
            ds = self.to_dataset()
            if ds is None:
                return None

            # Get result variable
            if result_var is None and self.bench_cfg.result_vars:
                result_var = self.bench_cfg.result_vars[0]

            if result_var is None or result_var.name not in ds.data_vars:
                return None

            # Get data array
            da = ds[result_var.name]
            if len(da.dims) < 2:
                return None

            # Create surface plot
            fig = go.Figure(
                data=[
                    go.Surface(
                        z=da.values,
                        x=da.coords[da.dims[0]].values,
                        y=da.coords[da.dims[1]].values,
                        colorscale="viridis",
                    )
                ]
            )

            fig.update_layout(
                title=f"3D Surface: {result_var.name}",
                scene=dict(
                    xaxis_title=da.dims[0], yaxis_title=da.dims[1], zaxis_title=result_var.name
                ),
                width=600,
                height=600,
            )

            return pn.pane.Plotly(fig, sizing_mode="stretch_width")

        except ImportError:
            print("Plotly not available for 3D surface plot")
            return None
        except Exception as e:
            print(f"Error creating 3D surface plot: {e}")
            return None

    def get_plot_callbacks(self) -> List[Callable]:
        """Return all available plotting methods for this extension."""
        return [
            self.to_3d_scatter,
            self.to_3d_surface,
            self.to_plot,  # The main plotting method
        ]

    def validate_dependencies(self) -> bool:
        """Check if Plotly is available."""
        try:
            import plotly  # noqa: F401

            return True
        except ImportError:
            return False


# Additional example: A simple text-based extension
@result_extension(
    name="text_summary_example",
    version="1.0.0",
    description="Example text summary extension",
    author="Bencher Example",
    dependencies=[],  # No external dependencies
    result_types=["ResultVar"],
    plot_types=["text_summary"],
    target_dimensions=[1, 2, 3],  # Works with any dimensionality
)
class TextSummaryExtension(ResultExtensionBase):
    """Simple example extension that provides text summaries."""

    def can_handle(self, bench_cfg: BenchCfg) -> bool:
        """This extension can handle any configuration with result variables."""
        return len(bench_cfg.result_vars) > 0

    def to_plot(self, **kwargs) -> Optional[pn.panel]:
        """Create a text summary of the results."""
        try:
            ds = self.to_dataset()
            if ds is None:
                return None

            # Create summary text
            summary_lines = ["## Benchmark Results Summary\n"]

            # Add dataset info
            summary_lines.append(f"**Dataset Shape**: {dict(ds.dims)}")
            summary_lines.append(f"**Variables**: {list(ds.data_vars)}")

            # Add statistics for each result variable
            for var_name in ds.data_vars:
                da = ds[var_name]
                summary_lines.append(f"\n### {var_name}")
                summary_lines.append(f"- **Mean**: {float(da.mean()):.4f}")
                summary_lines.append(f"- **Std**: {float(da.std()):.4f}")
                summary_lines.append(f"- **Min**: {float(da.min()):.4f}")
                summary_lines.append(f"- **Max**: {float(da.max()):.4f}")

            summary_text = "\n".join(summary_lines)

            # Return as Markdown panel
            return pn.pane.Markdown(summary_text, width=400, height=300, margin=(10, 10))

        except Exception as e:
            print(f"Error creating text summary: {e}")
            return None

    def get_plot_callbacks(self) -> List[Callable]:
        """Return available plotting methods."""
        return [self.to_plot]


if __name__ == "__main__":
    # Example of manual extension usage
    from bencher.extensions import get_registry

    print("Available extensions:")
    registry = get_registry()

    for metadata in registry.list_extensions():
        print(f"- {metadata.name} v{metadata.version}: {metadata.description}")

    print(f"\nTotal extensions: {len(registry.list_extensions())}")
