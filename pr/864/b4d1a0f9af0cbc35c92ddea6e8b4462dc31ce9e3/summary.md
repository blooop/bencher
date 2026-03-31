| Metric | Value |
|--------|-------|
| Total tests | 1134 |
| Total time | 106.89s |
| Mean | 0.0943s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.513 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.329 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.798 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.946 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.882 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.851 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.254 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src_and_cat` | 1.117 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.103 |
| `test.test_bencher.TestBencher::test_combinations` | 1.093 |

</details>