| Metric | Value |
|--------|-------|
| Total tests | 2931 |
| Total time | 155.26s |
| Mean | 0.0530s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 15.222 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.797 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.765 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.481 |
| `test.test_blob_store_races.TestGCRacingAReader::test_readers_and_a_collector_interleave_without_corruption` | 3.201 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.190 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.385 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.299 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.218 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.047 |

</details>