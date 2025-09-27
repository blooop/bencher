import bencher as bch
from bencher.example.meta.example_meta import BenchMeta


def example_meta_float(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = BenchMeta().to_bench(run_cfg)

    bench.plot_sweep(
        title="Sweeping Floating Point Variables",
        input_vars=[bch.p("float_vars", [1, 2, 3])],
        const_vars=dict(categorical_vars=0, level=3),
    )

    return bench


if __name__ == "__main__":
    example_meta_float().report.show()
