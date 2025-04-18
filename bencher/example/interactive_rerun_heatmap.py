#!/usr/bin/env python3
"""
Interactive Heatmap with Rerun Integration

This module creates a visualization that integrates HoloViews with Rerun to display
Gaussian distributions in Rerun when hovering over points in a heatmap.
The heatmap displays the mean and kurtosis of the distributions.
"""

import numpy as np
import pandas as pd
import holoviews as hv
import panel as pn
import rerun as rr
from scipy.stats import kurtosis, norm
from bokeh.models import CustomJS, HoverTool

import bencher as bch
from bencher.utils_rerun import rrd_to_pane


class InteractiveRerunHeatmap:
    """
    Creates an interactive heatmap where hovering over a cell shows the corresponding
    distribution in Rerun.
    """

    def __init__(self, n_datasets=50, n_samples=100):
        """
        Initialize with the number of datasets and samples per dataset.

        Args:
            n_datasets (int): Number of datasets to generate
            n_samples (int): Number of samples per dataset
        """
        self.n_datasets = n_datasets
        self.n_samples = n_samples
        self.df = None
        self.rrd_paths = []
        self.viewer_iframe = None

    def generate_data(self):
        """
        Generate multiple datasets, each containing samples from a Gaussian distribution.
        For each dataset, compute the mean and kurtosis.
        """
        data = []

        for i in range(self.n_datasets):
            # Generate samples with random mean and scale
            loc = np.random.uniform(-2, 2)
            scale = np.random.uniform(0.5, 1.5)
            samples = np.random.normal(loc=loc, scale=scale, size=self.n_samples)

            # Compute statistics
            mean_value = np.mean(samples)
            kurt_value = kurtosis(samples)

            # Save samples data
            data.append((mean_value, kurt_value, samples, i))

        # Create DataFrame with the data
        self.df = pd.DataFrame(data, columns=["mean", "kurtosis", "samples", "dataset_id"])
        return self.df

    def log_data_to_rerun(self):
        """
        Log histogram data for each dataset using Rerun and store the RRD file paths.
        """
        # Initialize Rerun
        rr.init("heatmap_with_rerun", spawn=False)

        # Store RRD file paths
        self.rrd_paths = []

        # Log histogram data for each dataset
        for idx, row in self.df.iterrows():
            samples = row["samples"]
            dataset_id = row["dataset_id"]

            # Create a unique RRD file for each dataset
            rrd_path = f"cachedir/rrd/dataset_{dataset_id}.rrd"

            # Create a new recording for this dataset
            rr.init(f"dataset_{dataset_id}")

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
                    positions=[(row["mean"], row["kurtosis"], 0.0)],
                    radii=[0.1],
                    colors=[(255, 0, 0)],
                ),
            )

            # Log text information
            rr.log(
                "info", rr.TextDocument(f"Mean: {row['mean']:.4f}\nKurtosis: {row['kurtosis']:.4f}")
            )

            # Save to file
            rr.save(rrd_path)
            self.rrd_paths.append(rrd_path)

        return self.rrd_paths

    def create_heatmap(self):
        """
        Create an interactive heatmap where hovering over a cell dynamically loads
        the corresponding distribution in the Rerun viewer.
        """
        # Make sure we have generated data first
        if self.df is None:
            self.generate_data()
            self.log_data_to_rerun()

        # Create a HoloViews Dataset
        hv_dataset = hv.Dataset(self.df, kdims=["mean", "kurtosis"], vdims=["dataset_id"])

        # Create a HeatMap from the dataset
        heatmap = hv.HeatMap(hv_dataset, kdims=["mean", "kurtosis"], vdims=["dataset_id"])

        # Set up viewer container
        viewer_container = pn.Column(
            pn.pane.Markdown("## Hover over the heatmap to see distribution"),
            pn.pane.HTML('<div id="rerun-viewer"></div>', width=600, height=400),
        )

        # Set up the JavaScript callback for loading Rerun viewer on hover
        callback = CustomJS(
            args=dict(dataset_ids=self.df["dataset_id"].tolist()),
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

        # Add the hover tool with the callback
        hover = HoverTool(
            tooltips=[("Mean", "@mean{0.00}"), ("Kurtosis", "@kurtosis{0.00}")], callback=callback
        )

        # Apply the hover tool to the heatmap
        heatmap = heatmap.opts(
            tools=[hover],
            colorbar=True,
            width=800,
            height=600,
            cmap="plasma",
            title="Mean vs Kurtosis of Gaussian Distributions",
        )

        # Create the layout
        layout = pn.Row(heatmap, viewer_container)

        return layout

    def serve_rerun_viewer(self, port=8080):
        """
        Serve the Rerun viewer on the specified port.

        Args:
            port (int): Port number to serve the Rerun viewer on
        """
        # Serve the Rerun viewer using the updated API
        print(f"Serving Rerun viewer on port {port}")
        try:
            # Use the newer serve_web API
            rr.serve_web(port=port, open_browser=False)
        except AttributeError:
            # Fallback for older versions of Rerun
            try:
                rr.serve(open_browser=False)
                print(
                    "Note: Using default port as the port parameter is not supported in this version of Rerun"
                )
            except Exception as e:
                print(f"Error starting Rerun server: {e}")
        return port


def run_interactive_heatmap(n_datasets=10, n_samples=100):
    """
    Run the interactive heatmap demo.

    Args:
        n_datasets (int): Number of datasets to generate
        n_samples (int): Number of samples per dataset

    Returns:
        panel.layout.Row: The interactive visualization
    """
    # Create the interactive heatmap
    heatmap = InteractiveRerunHeatmap(n_datasets=n_datasets, n_samples=n_samples)

    # Generate data
    heatmap.generate_data()

    # Log data to Rerun
    heatmap.log_data_to_rerun()

    # Serve the Rerun viewer
    heatmap.serve_rerun_viewer()

    # Create the heatmap
    layout = heatmap.create_heatmap()

    return layout


if __name__ == "__main__":
    # Initialize HoloViews extension
    hv.extension("bokeh")

    # Run the interactive heatmap demo
    layout = run_interactive_heatmap(n_datasets=10, n_samples=100)

    # Show the layout
    layout.show()
