import rerun as rr
import bencher as bch
import holoviews as hv
import panel as pn
import param

hv.extension("bokeh")
pn.extension()
rr.init("rerun_example_slider")


class SweepRerunSlider(bch.ParametrizedSweep):
    theta = bch.FloatSweep(default=1, bounds=[1, 4], doc="Input angle", units="rad", samples=10)

    rerun_result = bch.ResultContainer(doc="Rerun window with slider navigation")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Log to rerun first
        rr.log("s1", rr.Boxes2D(half_sizes=[self.theta, 1]))

        # Capture rerun window for this parameter value
        self.rerun_result = bch.capture_rerun_window(width=400, height=400)

        return super().__call__(**kwargs)


class RerunSliderViewer(param.Parameterized):
    """Interactive viewer for rerun results with slider navigation"""

    theta_value = param.Number(
        default=1.0, bounds=(1.0, 4.0), step=0.1, doc="Theta parameter value"
    )

    def __init__(self, bench_results, **params):
        super().__init__(**params)
        self.bench_results = bench_results
        self.theta_values = bench_results.ds.theta.values
        self.param.theta_value.bounds = (
            float(self.theta_values.min()),
            float(self.theta_values.max()),
        )
        self.param.theta_value.default = float(self.theta_values[0])
        self.theta_value = float(self.theta_values[0])

    @param.depends("theta_value")
    def view(self):
        """Display the rerun result for the selected theta value"""
        # Find closest theta value in the dataset
        idx = abs(self.theta_values - self.theta_value).argmin()
        closest_theta = self.theta_values[idx]

        # Get the corresponding rerun result
        result_data = self.bench_results.ds.sel(theta=closest_theta, repeat=1)
        rerun_pane = result_data.rerun_result.item()

        return pn.Column(
            pn.pane.Markdown(f"## Rerun Result for θ = {closest_theta:.2f}"), rerun_pane
        )


def example_rerun_slider(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example showing how to navigate rerun results with a slider in a single window"""

    bench = SweepRerunSlider().to_bench(run_cfg, report)

    # Create the sweep and get results
    results = bench.plot_sweep(plot_callbacks=False)

    # Create interactive slider viewer
    viewer = RerunSliderViewer(results)

    # Create the interactive panel with slider
    slider_app = pn.Column(
        pn.pane.Markdown("# Interactive Rerun Results"),
        pn.pane.Markdown("Use the slider below to navigate between different theta values:"),
        pn.Param(
            viewer, parameters=["theta_value"], widgets={"theta_value": pn.widgets.FloatSlider}
        ),
        viewer.view,
    )

    bench.report.append(slider_app, "Interactive Rerun Slider")

    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    bench = example_rerun_slider(bch.BenchRunCfg(level=3))
    bench.report.show()  # Show the interactive slider in browser
