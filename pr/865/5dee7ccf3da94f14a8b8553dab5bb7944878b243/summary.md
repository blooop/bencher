| Metric | Value |
|--------|-------|
| Total tests | 1134 |
| Total time | 109.66s |
| Mean | 0.0967s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.064 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.379 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.038 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.979 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.957 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.796 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.300 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.132 |
| `test.test_bencher.TestBencher::test_combinations` | 1.119 |
| `test.test_over_time_repeats.TestShowAggregatedTimeTab::test_curve_aggregated_tab_absent_when_disabled` | 1.091 |

</details>