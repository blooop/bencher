import bencher as bch
from bencher.example.inputs_0_float import example_1_cat_2_out
from bencher.example.inputs_0_float import example_2_cat_2_out

if __name__ == "__main__":
    br = bch.BenchRunner()
    br.add_run(example_1_cat_2_out)
    br.add_run(example_2_cat_2_out)
    br.run(repeats=2, level=2, max_repeats=4, max_level=4, show=True)
