"""Auto-generated example: Rerun Backend Choice — the same sweep rendered by panel and by rerun."""

import bencher as bn
from bencher.example.example_image import BenchPolygons


def example_rerun_backend_choice(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Backend Choice — the same sweep rendered by panel and by rerun."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, cache_results=False)
    bench = BenchPolygons().to_bench(run_cfg)

    # The only difference between the two sweeps below. Everything else -- the
    # benchmark, the input vars, the result vars -- is identical.
    for backend in ("panel", "rerun"):
        bench.run_cfg.backend = backend
        bench.plot_sweep(
            f"Polygons rendered by the {backend} backend",
            input_vars=["sides", "color"],
            result_vars=["polygon", "area"],
            description=f"The same sweep, rendered by the ``{backend}`` backend.  "
            "``backend`` is a per-chart-type preference applied during plot selection, "
            "not a different report: a chart type the preferred backend implements "
            "renders through it and the rest keep their best other implementation.  "
            "Here that one chart type is ``panes``.",
        )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_backend_choice, subsampling_divisions=4)
