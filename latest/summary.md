| Metric | Value |
|--------|-------|
| Total tests | 2936 |
| Total time | 147.31s |
| Mean | 0.0502s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.748 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.023 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.938 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.424 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.985 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.092 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.809 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.641 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.474 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.293 |

</details>