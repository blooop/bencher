| Metric | Value |
|--------|-------|
| Total tests | 1355 |
| Total time | 116.57s |
| Mean | 0.0860s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.868 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.503 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.401 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.144 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.869 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.791 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.779 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.519 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.322 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.428 |

</details>