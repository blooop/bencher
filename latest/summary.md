| Metric | Value |
|--------|-------|
| Total tests | 1355 |
| Total time | 100.20s |
| Mean | 0.0739s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.267 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.109 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.597 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.440 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.199 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.187 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.111 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.883 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.749 |
| `test.test_bencher.TestBencher::test_cache_size_propagation` | 1.347 |

</details>