| Metric | Value |
|--------|-------|
| Total tests | 1356 |
| Total time | 119.35s |
| Mean | 0.0880s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.995 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.482 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.545 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.211 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.182 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.072 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 3.031 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.964 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.596 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.429 |

</details>