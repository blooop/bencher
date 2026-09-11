| Metric | Value |
|--------|-------|
| Total tests | 3112 |
| Total time | 141.75s |
| Mean | 0.0455s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 13.922 |
| `test.test_blob_store_races.TestGCRacingAReader::test_readers_and_a_collector_interleave_without_corruption` | 3.405 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.224 |
| `test.test_axis_units.TestLineAxisUnits::test_line_axis_labels_show_units` | 2.689 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 2.643 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.226 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 2.177 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 1.899 |
| `test.test_import_cost::test_import_bencher_does_not_load_the_heavy_optional_deps` | 1.810 |
| `test.test_import_cost::test_writing_a_video_with_no_frames_does_not_import_moviepy` | 1.798 |

</details>