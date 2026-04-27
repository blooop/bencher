| Metric | Value |
|--------|-------|
| Total tests | 1358 |
| Total time | 90.61s |
| Mean | 0.0667s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 15.852 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.656 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.467 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.605 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.337 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.251 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.126 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.110 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 1.775 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.024 |

</details>