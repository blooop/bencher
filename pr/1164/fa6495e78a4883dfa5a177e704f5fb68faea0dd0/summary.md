| Metric | Value |
|--------|-------|
| Total tests | 3309 |
| Total time | 145.66s |
| Mean | 0.0440s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 12.409 |
| `test.test_complete_report::test_complete_bundle_cli_and_legacy_compare` | 3.792 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.084 |
| `test.test_object_store::test_local_create_is_atomic_across_processes` | 3.022 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 2.619 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 2.370 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.298 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 2.013 |
| `test.test_axis_units.TestLineAxisUnits::test_line_axis_labels_show_units` | 1.896 |
| `test.test_import_cost::test_import_bencher_does_not_load_the_heavy_optional_deps` | 1.839 |

</details>