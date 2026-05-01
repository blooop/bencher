| Metric | Value |
|--------|-------|
| Total tests | 1368 |
| Total time | 111.78s |
| Mean | 0.0817s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.699 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.060 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.178 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.010 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.952 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.931 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.786 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.764 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.470 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.323 |

</details>