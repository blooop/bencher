| Metric | Value |
|--------|-------|
| Total tests | 919 |
| Total time | 124.54s |
| Mean | 0.1355s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 46.892 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 7.936 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.625 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 2.157 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.995 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 1.931 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.756 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.356 |
| `test.test_generated_examples::test_generated_example[0_float/over_time/sweep_0_float_3_cat_over_time.py]` | 1.275 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_1_cat_over_time.py]` | 1.156 |

</details>