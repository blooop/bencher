| Metric | Value |
|--------|-------|
| Total tests | 2081 |
| Total time | 116.40s |
| Mean | 0.0559s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.904 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.461 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.178 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.299 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 2.814 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.400 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.039 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 1.986 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.963 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.738 |

</details>