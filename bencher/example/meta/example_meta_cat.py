import bencher as bch
from bencher.example.meta.example_meta import BenchMeta


def example_meta_cat(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    bench = BenchMeta().to_bench(run_cfg, report)

    bench.plot_sweep(
        title="Sweeping Categorical Variables",
        input_vars=[
            bch.p("categorical_vars", [1, 2, 3]),
            bch.p("sample_with_repeats", [1, 2]),
        ],
        const_vars=[
            ("float_vars", 0),
        ],
    )

    return bench


if __name__ == "__main__":
    example_meta_cat().report.show()
