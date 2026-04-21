| Metric | Value |
|--------|-------|
| Total tests | 1326 |
| Total time | 120.56s |
| Mean | 0.0909s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.336 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.664 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.271 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.083 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 3.083 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.059 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.843 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.603 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.583 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.480 |

</details>