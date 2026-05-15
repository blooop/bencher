import bencher as bn
from bencher.example.example_simple_float import example_simple_float

if __name__ == "__main__":
    br = bn.BenchRunner(run_tag="test_run")
    br.add(example_simple_float)
    br.run(
        repeats=2, subsampling_divisions=2, max_repeats=4, max_subsampling_divisions=4, save=True
    )
