| Metric | Value |
|--------|-------|
| Total tests | 1162 |
| Total time | 107.70s |
| Mean | 0.0927s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.359 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.505 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.791 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.050 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.906 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.712 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.367 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.108 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src_and_cat` | 1.068 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.041 |

</details>