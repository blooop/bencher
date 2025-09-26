import bencher as bch
from bencher.example.example_video import example_video
from bencher.example.example_image import example_image
from bencher.example.meta.example_meta_levels import example_meta_levels
from bencher.example.meta.example_meta_cat import example_meta_cat
from bencher.example.meta.example_meta_float import example_meta_float


def example_docs(run_cfg: bch.BenchRunCfg | None = None) -> bch.BenchReport:
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    report = bch.BenchReport("example_docs")

    run_cfg.repeats = 1
    run_cfg.level = 2

    for example in (
        example_image,
        example_video,
        example_meta_cat,
        example_meta_float,
        example_meta_levels,
    ):
        result = example(run_cfg)
        bench_report = getattr(result, "report", None)
        if isinstance(bench_report, bch.BenchReport):
            # Merge reports by copying each pane from src into dest
            for pane in list(bench_report.pane):
                report.append_tab(pane, name=getattr(pane, "name", None))

    return report


if __name__ == "__main__":
    example_docs().show()
