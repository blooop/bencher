| Metric | Value |
|--------|-------|
| Total tests | 1350 |
| Total time | 97.38s |
| Mean | 0.0721s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.748 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.210 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.500 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.426 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.228 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.170 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.082 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.922 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.741 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.114 |

</details>