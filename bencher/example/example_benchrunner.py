import bencher as bch
from bencher.example.inputs_1_float.example_1_float_0_cat_in_2_out import (
    example_1_float_0_cat_in_2_out,
)
from bencher.example.inputs_1_float.example_1_float_1_cat_in_2_out import (
    example_1_float_1_cat_in_2_out,
)

if __name__ == "__main__":
    br = bch.BenchRunner(run_tag="test_run")
    br.add(example_1_float_0_cat_in_2_out)
    br.add(example_1_float_1_cat_in_2_out)
    br.run(repeats=2, level=2, max_repeats=4, max_level=4, save=True)
