| Metric | Value |
|--------|-------|
| Total tests | 1323 |
| Total time | 116.06s |
| Mean | 0.0877s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.397 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.539 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.143 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.009 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.927 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.885 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.766 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.587 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.459 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.419 |

</details>