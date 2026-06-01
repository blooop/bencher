| Metric | Value |
|--------|-------|
| Total tests | 1397 |
| Total time | 100.74s |
| Mean | 0.0721s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.081 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.107 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.910 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.502 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.480 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.469 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.412 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.164 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 1.898 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.524 |

</details>