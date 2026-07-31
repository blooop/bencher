| Metric | Value |
|--------|-------|
| Total tests | 2431 |
| Total time | 147.52s |
| Mean | 0.0607s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.553 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.267 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.228 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.604 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.486 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.991 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.967 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.934 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.710 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.654 |

</details>