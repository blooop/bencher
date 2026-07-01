| Metric | Value |
|--------|-------|
| Total tests | 1740 |
| Total time | 125.43s |
| Mean | 0.0721s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.427 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 8.602 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.367 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 3.177 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.041 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 2.981 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.779 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.508 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.297 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.213 |

</details>