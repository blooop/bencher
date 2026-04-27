| Metric | Value |
|--------|-------|
| Total tests | 1358 |
| Total time | 108.91s |
| Mean | 0.0802s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.954 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.671 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.216 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.162 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.875 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.791 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.646 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.634 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.272 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.250 |

</details>