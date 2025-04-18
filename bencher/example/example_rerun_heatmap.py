#!/usr/bin/env python3
"""
Example: Interactive Rerun Heatmap

This example demonstrates creating an interactive heatmap visualization that shows
a Rerun recording when hovering over specific data points.
"""

import numpy as np
import holoviews as hv
import panel as pn
import rerun as rr
from scipy.stats import kurtosis, norm
from bokeh.models import CustomJS, HoverTool

import bencher as bch
from bencher.utils_rerun import rrd_to_pane


class RerunHeatmapExample(bch.ParametrizedSweep):
    """Example class that generates Gaussian distributions and provides interactive heatmap visualization"""

    # Input parameters
    n_datasets = bch.IntSweep(default=10, bounds=[5, 20], doc="Number of datasets to generate")
    n_samples = bch.IntSweep(default=100, bounds=[50, 500], doc="Number of samples per dataset")

    # Result variables
    heatmap_panel = bch.ResultContainer(doc="Interactive heatmap panel with Rerun integration")

    def __call__(self, **kwargs):
        """Generate data and create interactive visualization"""
        self.update_params_from_kwargs(**kwargs)

        # Initialize Rerun
        rr.init(f"rerun_heatmap_example", spawn=False)

        # Generate datasets with samples from Gaussian distributions
        data = []
        rrd_paths = []

        for i in range(self.n_datasets):
            # Generate samples with random mean and scale
            loc = np.random.uniform(-2, 2)
            scale = np.random.uniform(0.5, 1.5)
            samples = np.random.normal(loc=loc, scale=scale, size=self.n_samples)

            # Compute statistics
            mean_value = np.mean(samples)
            kurt_value = kurtosis(samples)

            # Create a unique RRD file for this dataset
            rrd_path = f"cachedir/rrd/dataset_{i}.rrd"

            # Create a new recording for this dataset
            rr.init(f"dataset_{i}")

            # Create histogram manually using numpy
            hist, bin_edges = np.histogram(samples, bins=30)

            # Log the histogram data using bar chart (only values parameter is supported)
            rr.log("histogram/bars", rr.BarChart(values=hist.tolist()))

            # Log bin centers as separate text for reference
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            bin_centers_text = "\n".join(
                [f"Bin {i}: {edge:.2f}" for i, edge in enumerate(bin_centers)]
            )
            rr.log("histogram/bin_centers", rr.TextDocument(bin_centers_text))

            # Log raw samples as a series of points
            rr.log(
                "histogram/samples",
                rr.Points2D(
                    [(i, val) for i, val in enumerate(samples)],
                    colors=[(0, 128, 255)] * len(samples),
                    radii=[1.0] * len(samples),
                ),
            )

            # Log stats as 3D points
            rr.log(
                "stats",
                rr.Points3D(
                    positions=[(mean_value, kurt_value, 0.0)], radii=[0.1], colors=[(255, 0, 0)]
                ),
            )

            # Log text information
            rr.log("info", rr.TextDocument(f"Mean: {mean_value:.4f}\nKurtosis: {kurt_value:.4f}"))

            # Save to file
            rr.save(rrd_path)

            # Store data
            data.append((mean_value, kurt_value, i))
            rrd_paths.append(rrd_path)

        # Create HoloViews dataset and heatmap
        import pandas as pd

        df = pd.DataFrame(data, columns=["mean", "kurtosis", "dataset_id"])
        hv_dataset = hv.Dataset(df, kdims=["mean", "kurtosis"], vdims=["dataset_id"])
        heatmap = hv.HeatMap(hv_dataset, kdims=["mean", "kurtosis"], vdims=["dataset_id"])

        # Set up viewer container
        viewer_container = pn.Column(
            pn.pane.Markdown("## Hover over the heatmap to see distribution in Rerun"),
            pn.pane.HTML('<div id="rerun-viewer"></div>', width=600, height=400),
        )

        # Set up the JavaScript callback for loading Rerun viewer on hover
        callback = CustomJS(
            args=dict(dataset_ids=df["dataset_id"].tolist()),
            code="""
            const index = cb_data.index.indices[0];
            if (index !== undefined) {
                const dataset_id = dataset_ids[index];
                
                // Update or create the iframe
                let viewer = document.getElementById('rerun-viewer');
                if (!viewer.querySelector('iframe')) {
                    const iframe = document.createElement('iframe');
                    iframe.style.width = '600px';
                    iframe.style.height = '400px';
                    iframe.style.border = 'none';
                    viewer.appendChild(iframe);
                } else {
                    viewer = viewer.querySelector('iframe');
                }
                
                // Set the src to the Rerun viewer for this dataset
                viewer.src = `http://localhost:8080/viewer?url=/cachedir/rrd/dataset_${dataset_id}.rrd`;
            }
        """,
        )

        # Add hover tool with callback
        hover = HoverTool(
            tooltips=[("Mean", "@mean{0.00}"), ("Kurtosis", "@kurtosis{0.00}")], callback=callback
        )

        # Configure the heatmap
        heatmap = heatmap.opts(
            tools=[hover],
            colorbar=True,
            width=800,
            height=600,
            cmap="plasma",
            title="Mean vs Kurtosis of Gaussian Distributions",
        )

        # Create the layout
        self.heatmap_panel = pn.Row(heatmap, viewer_container)

        # Serve the Rerun viewer if not already running
        try:
            # Use the newer serve_web API if available
            try:
                rr.serve_web(port=8080, open_browser=False)
            except AttributeError:
                # Fallback for older versions of Rerun
                print("Using older Rerun API - serve() without port parameter")
                rr.serve(open_browser=False)
        except Exception as e:
            print(f"Note: Rerun server might already be running: {e}")

        return super().__call__()


def example_rerun_heatmap(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """
    Example demonstrating an interactive heatmap with Rerun integration.

    Args:
        run_cfg: Configuration for the benchmark
        report: Report to append results to

    Returns:
        Bench: Benchmark results
    """
    # Initialize HoloViews
    hv.extension("bokeh")

    # Create a bench instance with our example
    bench = RerunHeatmapExample().to_bench(run_cfg, report)

    # Use a smaller range for the sweep to make it more manageable
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()

    # Set maximum level to avoid too many combinations
    run_cfg.level = 1

    # Run the benchmark
    res = bench.plot_sweep(
        title="Interactive Heatmap with Rerun Integration",
        description="""This example demonstrates how to create an interactive heatmap visualization
        using HoloViews that dynamically loads and displays Rerun recordings when hovering over
        specific data points. The heatmap shows the mean and kurtosis of Gaussian distributions.""",
        input_vars=["n_datasets", "n_samples"],
        result_vars=["heatmap_panel"],
        run_cfg=run_cfg,
    )

    # Append the result to the report
    bench.report.append(res.to_panes())

    return bench


if __name__ == "__main__":
    # Run the example with default configuration but with a smaller level to make it faster
    example_rerun_heatmap(bch.BenchRunCfg(level=1)).report.show()
