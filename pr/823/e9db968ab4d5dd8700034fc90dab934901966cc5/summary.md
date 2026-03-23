| Metric | Value |
|--------|-------|
| Total tests | 926 |
| Total time | 103.24s |
| Mean | 0.1115s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 34.116 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 7.532 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 6.583 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 4.929 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.548 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.218 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 1.177 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.170 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 0.921 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 0.841 |

</details>