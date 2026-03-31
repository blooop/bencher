| Metric | Value |
|--------|-------|
| Total tests | 1134 |
| Total time | 108.19s |
| Mean | 0.0954s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.000 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.397 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.925 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.977 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.867 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.866 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.317 |
| `test.test_bencher.TestBencher::test_combinations` | 1.135 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.122 |
| `test.test_over_time_repeats.TestShowAggregatedTimeTab::test_curve_aggregated_tab_absent_when_disabled` | 1.119 |

</details>