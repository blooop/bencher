| Metric | Value |
|--------|-------|
| Total tests | 1326 |
| Total time | 109.23s |
| Mean | 0.0824s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.944 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.992 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.892 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.279 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.813 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.773 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.755 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.448 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.332 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.176 |

</details>