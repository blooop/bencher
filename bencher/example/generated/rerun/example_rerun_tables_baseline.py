"""Auto-generated example: Rerun Tables Baseline — tables in panel plus many rerun windows."""

from functools import partial

import bencher as bn
from bencher.example.example_rerun_over_time import ControlSystemSweep


def example_rerun_tables_baseline(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Tables Baseline — tables in panel plus many rerun windows."""
    bench = ControlSystemSweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["damping_ratio", "omega_n"],
        result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
        description="The reference report the single-viewer destination is judged "
        "against: scalar metrics rendered as tables in panel, plus one embedded rerun "
        "web viewer PER SAMPLE.  ``table`` and ``tabulator`` are named-only plot types, "
        "so they are requested explicitly via ``plot_list``; ``panes`` renders each "
        "sample's ``ResultRerun`` recording as its own iframe.  At the default sampling "
        "(5 damping ratios x 3 natural frequencies) that is 15 independent wasm viewers "
        "on one page.",
        post_description="This is the 'before' report that ``rerun_summary`` / "
        "``rerun_grid`` replace with a single merged viewer — see "
        "https://github.com/blooop/bencher/issues/1112 for the measured baseline "
        "(iframe count, total .rrd bytes, save time, peak memory).",
        plot_callbacks=[
            partial(
                bn.BenchResult.to_auto_plots,
                plot_list=["table", "tabulator", "panes"],
            )
        ],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_tables_baseline, subsampling_divisions=3)
