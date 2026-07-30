| Metric | Value |
|--------|-------|
| Total tests | 2133 |
| Total time | 141.81s |
| Mean | 0.0665s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.868 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.379 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.036 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.874 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.550 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 3.007 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.974 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.791 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.709 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.532 |

</details>