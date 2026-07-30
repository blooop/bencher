| Metric | Value |
|--------|-------|
| Total tests | 2066 |
| Total time | 131.92s |
| Mean | 0.0639s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.205 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 5.994 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.840 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.573 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.104 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.058 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.750 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.597 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.446 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.294 |

</details>