import bencher as bch


class ExampleFile(bch.ParametrizedSweep):
    content = bch.StringSweep(["entry1", "entry2", "entry3"])

    file_result = bch.ResultPath()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        # this generates a unique filename and stores it in the cache directory
        filename = bch.gen_path(self.content, suffix=".txt")
        with open(filename, "w", encoding="utf-8") as text_file:
            text_file.write(f"content:{self.content}")
        self.file_result = filename
        return super().__call__()


def example_filepath(run_cfg: bch.BenchRunCfg | None = None):
    bench = ExampleFile().to_bench(run_cfg)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    example_filepath().report.show()
