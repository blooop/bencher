| Metric | Value |
|--------|-------|
| Total tests | 1301 |
| Total time | 124.17s |
| Mean | 0.0954s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.935 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 6.021 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.586 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 3.132 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.080 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.072 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.874 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.862 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.749 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.453 |

</details>