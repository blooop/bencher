| Metric | Value |
|--------|-------|
| Total tests | 2513 |
| Total time | 154.15s |
| Mean | 0.0613s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.297 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.485 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.212 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.601 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.374 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 3.090 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 3.024 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.000 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.830 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.578 |

</details>