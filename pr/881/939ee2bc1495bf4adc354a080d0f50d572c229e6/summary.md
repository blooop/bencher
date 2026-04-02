| Metric | Value |
|--------|-------|
| Total tests | 1157 |
| Total time | 114.91s |
| Mean | 0.0993s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.996 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.833 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.988 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.111 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.001 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.941 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.446 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.372 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.253 |
| `test.test_over_time_repeats.TestShowAggregatedTimeTab::test_curve_aggregated_tab_absent_when_disabled` | 1.142 |

</details>