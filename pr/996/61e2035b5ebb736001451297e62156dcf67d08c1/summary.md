| Metric | Value |
|--------|-------|
| Total tests | 1987 |
| Total time | 139.80s |
| Mean | 0.0704s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.788 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.293 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.208 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 5.144 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.286 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 3.131 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.113 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.030 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.656 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.515 |

</details>