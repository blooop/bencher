| Metric | Value |
|--------|-------|
| Total tests | 1387 |
| Total time | 109.24s |
| Mean | 0.0788s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.745 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.778 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.026 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.536 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.935 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.854 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.824 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.541 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.410 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.327 |

</details>