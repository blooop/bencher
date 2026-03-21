import bencher as bn
from bencher.example.meta.example_meta import BenchMeta


def example_meta_float(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = BenchMeta().to_bench(run_cfg)

    bench.plot_sweep(
        title="Sweeping Floating Point Variables",
        input_vars=[bn.p("float_vars", [1, 2, 3])],
        const_vars=dict(categorical_vars=0, level=3),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_float)
