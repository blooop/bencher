| Metric | Value |
|--------|-------|
| Total tests | 908 |
| Total time | 123.41s |
| Mean | 0.1359s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 46.974 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 8.000 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.734 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 2.042 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.931 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 1.920 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.686 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.281 |
| `test.test_generated_examples::test_generated_example[0_float/over_time/sweep_0_float_3_cat_over_time.py]` | 1.208 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_1_cat_over_time.py]` | 1.194 |

</details>