| Metric | Value |
|--------|-------|
| Total tests | 927 |
| Total time | 106.56s |
| Mean | 0.1150s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 35.533 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 7.329 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 7.013 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 5.067 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.544 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.287 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 1.169 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.041 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.941 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 0.861 |

</details>