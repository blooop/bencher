| Metric | Value |
|--------|-------|
| Total tests | 3593 |
| Total time | 333.53s |
| Mean | 0.0928s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.279 |
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 15.277 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 9.465 |
| `test.test_ab::test_ab_png_dir_writes_one_png_per_metric` | 8.959 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 8.728 |
| `test.test_ab::test_ab_reports_which_side_failed_and_keeps_its_output` | 8.711 |
| `test.test_ab::test_ab_explicit_base_and_image_url` | 8.660 |
| `test.test_ab::test_ab_judges_a_claim_on_a_metric_the_change_adds` | 8.635 |
| `test.test_ab::test_ab_runs_an_ignored_interpreter_on_the_base_side_too` | 8.594 |
| `test.test_ab::test_ab_base_imports_its_own_package_over_an_absolute_path_to_the_candidate` | 6.570 |

</details>