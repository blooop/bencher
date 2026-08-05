| Metric | Value |
|--------|-------|
| Total tests | 2914 |
| Total time | 153.26s |
| Mean | 0.0526s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.314 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.398 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.140 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.507 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.170 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.085 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.994 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.972 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.955 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.577 |

</details>