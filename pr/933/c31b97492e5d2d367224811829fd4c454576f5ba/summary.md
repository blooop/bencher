| Metric | Value |
|--------|-------|
| Total tests | 1358 |
| Total time | 115.51s |
| Mean | 0.0851s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.292 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.131 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.369 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.113 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.109 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.054 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.847 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.815 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.511 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.335 |

</details>