import rerun as rr
import rerun.blueprint as rrb
import bencher as bch

rr.init("rerun_example_tabs", spawn=True)


class SweepRerunTabs(bch.ParametrizedSweep):
    theta = bch.FloatSweep(default=1, bounds=[1, 4], doc="Input angle", units="rad", samples=10)

    # We'll return just a simple value since we're handling rerun logging directly
    result_value = bch.ResultVar(doc="Simple result for tracking")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # Create a unique entity path for this theta value
        entity_path = f"theta_{self.theta:.2f}/boxes"

        print(f"Logging to rerun path: {entity_path} with theta={self.theta}")

        # Log to rerun with the specific entity path
        rr.log(entity_path, rr.Boxes2D(half_sizes=[self.theta, 1]))

        # Also log some additional data to make sure it's visible
        rr.log(f"{entity_path}/info", rr.TextDocument(f"Theta value: {self.theta:.2f}"))

        # Return a simple result
        self.result_value = self.theta

        return super().__call__(**kwargs)


def create_blueprint_with_tabs(theta_values):
    """Create a blueprint with tabs for each theta value"""

    # Create a list of Spatial2DViews, one for each theta value
    tab_views = []
    for theta in theta_values:
        view = rrb.Spatial2DView(name=f"θ = {theta:.2f}", origin=f"theta_{theta:.2f}")
        tab_views.append(view)

    # Create the blueprint with a tab container
    blueprint = rrb.Blueprint(rrb.Tabs(*tab_views))

    return blueprint


def example_rerun_tabs(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example showing how to organize rerun results in tabs using blueprint system"""

    # Create the sweep configuration
    sweep = SweepRerunTabs()

    # Set default run config if not provided
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg(level=3)

    # Predefined theta values based on level (matching what the bencher will actually use)
    if run_cfg.level == 1:
        theta_values = [1.0]
    elif run_cfg.level == 2:
        theta_values = [1.0, 4.0]
    else:  # level 3 and above
        theta_values = [1.0, 2.5, 4.0]

    print(f"Setting up tabs for theta values: {theta_values}")

    # Create and send the blueprint first
    blueprint = create_blueprint_with_tabs(theta_values)
    rr.send_blueprint(blueprint)
    print("Blueprint sent to rerun")

    # Now run the actual sweep (this will log all data to rerun)
    bench = sweep.to_bench(run_cfg, report)
    bench.plot_sweep()

    print("Finished logging data to rerun")
    print(
        "Check the Rerun viewer window that opened - it should show tabs with the different theta values!"
    )

    # Don't try to capture the rerun window - just let the native viewer show the tabs
    # The rerun viewer should already be showing the tabbed interface

    return bench


if __name__ == "__main__":
    bench = example_rerun_tabs(bch.BenchRunCfg(level=3))
    print("Example completed successfully!")
    print("The Rerun viewer window should be open showing tabs for each theta value.")
    print("Each tab contains the boxes for that specific theta value.")

    # Keep the script running briefly so the rerun viewer stays open
    import time

    time.sleep(2)
    print("Script completed. The Rerun viewer window should remain open.")
