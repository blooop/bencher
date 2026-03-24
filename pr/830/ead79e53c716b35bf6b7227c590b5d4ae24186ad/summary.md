| Metric | Value |
|--------|-------|
| Total tests | 919 |
| Total time | 127.47s |
| Mean | 0.1387s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 47.595 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 8.013 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 7.445 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 2.061 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 2.017 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 1.933 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.789 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.367 |
| `test.test_generated_examples::test_generated_example[0_float/over_time/sweep_0_float_3_cat_over_time.py]` | 1.299 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_2_cat_over_time.py]` | 1.154 |

</details>