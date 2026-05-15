| Metric | Value |
|--------|-------|
| Total tests | 1387 |
| Total time | 117.89s |
| Mean | 0.0850s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.693 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.290 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.384 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.151 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.112 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.044 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 3.000 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.839 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.577 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.388 |

</details>