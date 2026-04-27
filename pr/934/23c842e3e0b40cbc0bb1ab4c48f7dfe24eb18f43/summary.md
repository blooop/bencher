| Metric | Value |
|--------|-------|
| Total tests | 1368 |
| Total time | 108.90s |
| Mean | 0.0796s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.903 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.735 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.024 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.552 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.905 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.898 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.857 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.702 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.365 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.246 |

</details>