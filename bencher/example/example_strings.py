import bencher as bn


class TestPrinting(bn.ParametrizedSweep):
    # INPUTS
    a = bn.StringSweep(default=None, string_list=["a1", "a2"], allow_None=True)
    b = bn.StringSweep(default=None, string_list=["b1", "b2"], allow_None=True)
    c = bn.StringSweep(default=None, string_list=["c1", "c2"], allow_None=True)
    d = bn.StringSweep(default=None, string_list=["d1", "d2"], allow_None=True)

    # RESULTS
    result = bn.ResultString()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        self.result = self.a
        if self.b is not None:
            self.result += f",{self.b}"
        if self.c is not None:
            self.result += f",{self.c}"
        if self.d is not None:
            self.result += f",{self.d}"
        self.result += "\n\ttab\n\t\ttab2"

        self.result = bn.tabs_in_markdown(self.result)
        return super().__call__()


def example_strings(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = bn.Bench("strings", TestPrinting(), run_cfg=run_cfg)

    for s in [
        ["a"],
        ["a", "b"],
        ["a", "b", "c"],
        ["a", "b", "c", "d"],
    ]:
        bench.plot_sweep(f"String Panes {s}", input_vars=s)

    return bench


if __name__ == "__main__":
    bn.run(example_strings)
