| Metric | Value |
|--------|-------|
| Total tests | 2936 |
| Total time | 131.29s |
| Mean | 0.0447s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.544 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 5.313 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.042 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.665 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.379 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.631 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.456 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.430 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.416 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.323 |

</details>