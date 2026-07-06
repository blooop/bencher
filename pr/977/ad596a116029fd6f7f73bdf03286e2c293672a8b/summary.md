| Metric | Value |
|--------|-------|
| Total tests | 1824 |
| Total time | 134.15s |
| Mean | 0.0735s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.165 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 8.816 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.623 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.988 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 3.458 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.226 |
| `test.test_split_render_examples::test_split_render_roundtrip[result_image/example_result_image_to_video.py]` | 2.916 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.812 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.777 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.393 |

</details>