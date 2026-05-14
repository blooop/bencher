| Metric | Value |
|--------|-------|
| Total tests | 1368 |
| Total time | 109.76s |
| Mean | 0.0802s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.233 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.751 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.192 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.130 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.909 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.796 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.658 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.652 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.263 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.246 |

</details>