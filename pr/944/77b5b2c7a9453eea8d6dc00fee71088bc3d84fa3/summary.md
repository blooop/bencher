| Metric | Value |
|--------|-------|
| Total tests | 1397 |
| Total time | 114.50s |
| Mean | 0.0820s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.971 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.137 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.273 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.082 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.009 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.005 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.842 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.813 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.491 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.355 |

</details>