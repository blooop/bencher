| Metric | Value |
|--------|-------|
| Total tests | 3663 |
| Total time | 389.99s |
| Mean | 0.1065s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.456 |
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 16.762 |
| `test.test_ab::test_ab_png_dir_writes_one_png_per_metric` | 9.997 |
| `test.test_ab::test_ab_images_pushes_them_to_the_evidence_ref_and_links_them` | 9.989 |
| `test.test_ab::test_ab_images_without_a_github_remote_keeps_text_and_exits_0` | 9.729 |
| `test.test_ab::test_ab_without_images_pushes_nothing` | 9.555 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 9.547 |
| `test.test_ab::test_ab_runs_an_ignored_interpreter_on_the_base_side_too` | 9.533 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 9.361 |
| `test.test_ab::test_ab_reports_which_side_failed_and_keeps_its_output` | 9.332 |

</details>