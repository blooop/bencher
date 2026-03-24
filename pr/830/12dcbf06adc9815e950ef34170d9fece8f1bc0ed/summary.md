| Metric | Value |
|--------|-------|
| Total tests | 908 |
| Total time | 127.72s |
| Mean | 0.1407s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 49.256 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 7.863 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 7.037 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 2.108 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 2.012 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 1.936 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.724 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.371 |
| `test.test_generated_examples::test_generated_example[0_float/over_time/sweep_0_float_3_cat_over_time.py]` | 1.281 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_1_cat_over_time.py]` | 1.137 |

</details>