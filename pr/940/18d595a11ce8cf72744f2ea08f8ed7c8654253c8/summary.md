| Metric | Value |
|--------|-------|
| Total tests | 1397 |
| Total time | 111.92s |
| Mean | 0.0801s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.646 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.749 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.351 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.165 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.954 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.871 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.725 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.722 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.298 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.260 |

</details>