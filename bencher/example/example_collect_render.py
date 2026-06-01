"""Example: collect benchmark samples, then render the report separately.

Demonstrates the collect/render split. ``Bench.collect`` runs the sweep and
computes regression detection but builds **no** holoviews/panel objects, so it
is safe to call from a process that holds foreign C-extension state (e.g. ROS
``rclpy``/DDS) where in-process plotting + garbage collection can segfault. The
result is persisted and rendered later — here in the same process for brevity,
but in practice via a fresh subprocess::

    python -m bencher.render result.pkl output_dir
"""

import tempfile
from pathlib import Path

import bencher as bn
from bencher.example.benchmark_data import ExampleBenchCfg


def example_collect_render(
    run_cfg: bn.BenchRunCfg | None = None, report: bn.BenchReport | None = None
) -> bn.Bench:
    """Collect without plotting, persist, then render the report from disk."""
    run_cfg = run_cfg or bn.BenchRunCfg(repeats=2)
    bench = ExampleBenchCfg().to_bench(run_cfg, report)

    # Collection phase — no holoviews/bokeh objects are constructed here.
    result = bench.collect(
        input_vars=["theta"],
        result_vars=["out_sin"],
        title="Collect/render split",
    )

    out_dir = Path(tempfile.mkdtemp(prefix="bencher_collect_render_"))
    result_path = out_dir / "result.pkl"
    bn.save_result(result, result_path)

    # Render phase — build + save the HTML report from the persisted result.
    # In production run this in a separate process:
    #   python -m bencher.render <result_path> <out_dir>
    saved = bn.render_report(result_path, out_dir)
    print(f"Saved result to {result_path}\nRendered report to {saved}")
    return bench


if __name__ == "__main__":
    example_collect_render()
