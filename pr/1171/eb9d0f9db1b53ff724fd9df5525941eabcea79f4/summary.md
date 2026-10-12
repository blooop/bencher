| Metric | Value |
|--------|-------|
| Total tests | 3335 |
| Total time | 182.28s |
| Mean | 0.0547s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 14.941 |
| `test.test_complete_report::test_complete_bundle_cli_and_legacy_compare` | 4.943 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash_isolated` | 3.956 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.695 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.319 |
| `test.test_object_store::test_local_create_is_atomic_across_processes` | 3.267 |
| `test.test_blob_store_races.TestGCRacingAReader::test_readers_and_a_collector_interleave_without_corruption` | 3.081 |
| `test.test_axis_units.TestLineAxisUnits::test_line_axis_labels_show_units` | 2.617 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.533 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 2.418 |

</details>