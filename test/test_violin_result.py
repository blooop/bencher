import unittest
import bencher as bch
import panel as pn

from bencher.example.benchmark_data import SimpleBenchClass, AllSweepVars
from bencher.results.holoview_results.violin_result import ViolinResult


class TestViolinResult(unittest.TestCase):
    def test_to_violin(self):
        """Test that the to_violin method produces the expected panel object."""
        # Create a benchmark with categorical data for a violin plot
        asv = AllSweepVars()
        bench = bch.Bench("test_violin_plot", asv)

        # Configure the benchmark to run with multiple repeats
        run_cfg = bch.BenchRunCfg(repeats=3, auto_plot=False)

        # Run the benchmark with a categorical input
        result = bench.plot_sweep(
            title="Violin Plot Test",
            input_vars=[asv.param.var_string],  # Use the string sweep as categorical input
            result_vars=[asv.param.result],
            run_cfg=run_cfg,
            plot_callbacks=False,
        )

        # Get a violin plot function from the result
        get_violin_plot = ViolinResult.from_bench_result(result)

        # Generate the violin plot
        violin_plot = get_violin_plot(result_var=asv.param.result, override=True)

        # Verify that the result is a panel object
        self.assertIsInstance(violin_plot, pn.viewable.Viewable)

    def test_violin_filter(self):
        """Test that the filter in to_violin correctly filters data."""
        # Create a benchmark with inappropriate data structure for a violin plot
        sbc = SimpleBenchClass()
        bench = bch.Bench("test_violin_filter", sbc)

        # Configure with only one repeat (not enough for a violin plot)
        run_cfg = bch.BenchRunCfg(repeats=1, auto_plot=False)

        # Run the benchmark
        result = bench.plot_sweep(
            title="Invalid Violin Plot Test",
            input_vars=[sbc.param.var1],  # Integer input instead of categorical
            result_vars=[sbc.param.result],
            run_cfg=run_cfg,
            plot_callbacks=False,
        )

        # Get a violin plot function from the result
        get_violin_plot = ViolinResult.from_bench_result(result)

        # Try to generate a violin plot with override=False
        # This should return a Markdown object explaining why it's not appropriate
        violin_plot = get_violin_plot(result_var=sbc.param.result, override=False)

        # Verify that we get a Markdown object (not a proper violin plot)
        self.assertIsInstance(violin_plot, pn.pane.Markdown)
