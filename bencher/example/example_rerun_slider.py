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

    # This will be set dynamically based on the sweep
    parameter_value = param.Number(default=1.0, bounds=(1.0, 4.0), step=0.1)

    def __init__(self, bench_results, **params):
        # Get sweep information
        self.bench_results = bench_results
        self.input_var = bench_results.bench_cfg.input_vars[0]
        self.var_name = self.input_var.name
        self.var_values = bench_results.ds[self.var_name].values

        # Update parameter bounds and default based on the actual sweep
        param_bounds = (float(self.var_values.min()), float(self.var_values.max()))
        param_default = float(self.var_values[0])
        step_size = (param_bounds[1] - param_bounds[0]) / max(1, len(self.var_values) - 1)

        # Update the parameter definition
        self.param.parameter_value.bounds = param_bounds
        self.param.parameter_value.default = param_default
        self.param.parameter_value.step = step_size
        self.param.parameter_value.doc = f"{self.input_var.doc} ({self.input_var.units})"

        super().__init__(parameter_value=param_default, **params)

    @param.depends("parameter_value")
    def view(self):
        """Display the rerun result for the selected parameter value"""
        # Find closest value in the dataset
        idx = abs(self.var_values - self.parameter_value).argmin()
        closest_value = self.var_values[idx]

        # Get the corresponding rerun result
        result_data = self.bench_results.ds.sel({self.var_name: closest_value, "repeat": 1})
        rerun_pane = result_data.rerun_result.item()

        return pn.Column(
            pn.pane.Markdown(
                f"## Rerun Result for {self.var_name} = {closest_value:.2f} {self.input_var.units}"
            ),
            rerun_pane,
        )


def example_rerun_slider(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example showing how to navigate rerun results with a slider in a single window"""

    slider_bench = SweepRerunSlider().to_bench(run_cfg, report)

    # Create the sweep and get results
    results = slider_bench.plot_sweep(plot_callbacks=False)

    # Create interactive slider viewer that auto-adapts to sweep parameters
    viewer = RerunSliderViewer(results)

    # Get the parameter name and info from the sweep
    sweep_var = results.bench_cfg.input_vars[0]

    # Create the interactive panel with slider
    slider_app = pn.Column(
        pn.pane.Markdown("# Interactive Rerun Results"),
        pn.pane.Markdown(
            f"Use the slider below to navigate between different {sweep_var.name} values:"
        ),
        pn.Param(
            viewer,
            parameters=["parameter_value"],
            widgets={"parameter_value": pn.widgets.FloatSlider},
            name=f"{sweep_var.doc} ({sweep_var.units})",
        ),
        viewer.view,
    )

    bench.report.append(slider_app, "Interactive Rerun Slider")

    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    bench = example_rerun_slider(bch.BenchRunCfg(level=3))
    bench.report.show()  # Show the interactive slider in browser
