| Metric | Value |
|--------|-------|
| Total tests | 1406 |
| Total time | 117.69s |
| Mean | 0.0837s |
| Median | 0.0015s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.373 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.239 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.470 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.118 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.060 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.930 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.891 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.688 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.561 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.431 |

</details>