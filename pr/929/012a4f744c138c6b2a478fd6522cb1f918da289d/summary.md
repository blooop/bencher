| Metric | Value |
|--------|-------|
| Total tests | 1355 |
| Total time | 120.82s |
| Mean | 0.0892s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.227 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.669 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.340 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.035 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.016 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.838 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.824 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.644 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.529 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.461 |

</details>