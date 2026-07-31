| Metric | Value |
|--------|-------|
| Total tests | 2548 |
| Total time | 118.40s |
| Mean | 0.0465s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 13.931 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.974 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.854 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.605 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.132 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.652 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.307 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.299 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.251 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.995 |

</details>