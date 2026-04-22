| Metric | Value |
|--------|-------|
| Total tests | 1333 |
| Total time | 99.67s |
| Mean | 0.0748s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.044 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.090 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.517 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.463 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.234 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.148 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.110 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.885 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.737 |
| `test.test_generated_examples::test_generated_example[0_float/over_time/example_sweep_0_float_0_cat_over_time.py]` | 1.140 |

</details>