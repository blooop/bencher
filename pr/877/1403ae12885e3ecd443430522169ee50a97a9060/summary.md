| Metric | Value |
|--------|-------|
| Total tests | 1150 |
| Total time | 103.06s |
| Mean | 0.0896s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.969 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.127 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.824 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.138 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.818 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.499 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.219 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.208 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 1.136 |
| `test.test_over_time_repeats.TestShowAggregatedTimeTab::test_curve_aggregated_tab_absent_when_disabled` | 1.086 |

</details>