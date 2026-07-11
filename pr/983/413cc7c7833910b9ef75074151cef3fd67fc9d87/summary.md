| Metric | Value |
|--------|-------|
| Total tests | 1903 |
| Total time | 136.62s |
| Mean | 0.0718s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.771 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.302 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.040 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.826 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.548 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.037 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.982 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.951 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.778 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.744 |

</details>