| Metric | Value |
|--------|-------|
| Total tests | 3369 |
| Total time | 128.82s |
| Mean | 0.0382s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 11.340 |
| `test.test_complete_report::test_complete_bundle_cli_and_legacy_compare` | 3.563 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash_isolated` | 2.791 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.713 |
| `test.test_object_store::test_local_create_is_atomic_across_processes` | 2.562 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 2.513 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.055 |
| `test.test_axis_units.TestLineAxisUnits::test_line_axis_labels_show_units` | 1.888 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.808 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 1.729 |

</details>