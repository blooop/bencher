| Metric | Value |
|--------|-------|
| Total tests | 2207 |
| Total time | 100.32s |
| Mean | 0.0455s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 12.967 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.829 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 3.693 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.814 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 2.716 |
| `test.test_axis_units.TestCurveAxisUnits::test_curve_axis_labels_show_units` | 2.117 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.033 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 1.703 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 1.612 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 1.545 |

</details>