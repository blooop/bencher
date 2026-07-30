| Metric | Value |
|--------|-------|
| Total tests | 2355 |
| Total time | 153.24s |
| Mean | 0.0651s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.471 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.737 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.259 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.998 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.288 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.253 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 3.125 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.093 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.919 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.596 |

</details>