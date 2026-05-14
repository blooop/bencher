| Metric | Value |
|--------|-------|
| Total tests | 1368 |
| Total time | 120.02s |
| Mean | 0.0877s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.130 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.522 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.554 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.239 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.093 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 3.067 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.960 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.823 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.640 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.487 |

</details>