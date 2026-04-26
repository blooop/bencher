| Metric | Value |
|--------|-------|
| Total tests | 1379 |
| Total time | 115.41s |
| Mean | 0.0837s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.081 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.070 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.466 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.175 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.167 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.961 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.858 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.814 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.355 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.511 |

</details>