| Metric | Value |
|--------|-------|
| Total tests | 3561 |
| Total time | 210.68s |
| Mean | 0.0592s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 11.208 |
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 10.825 |
| `test.test_ab::test_ab_png_dir_writes_one_png_per_metric` | 6.188 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 5.970 |
| `test.test_ab::test_ab_judges_a_claim_on_a_metric_the_change_adds` | 5.899 |
| `test.test_ab::test_ab_explicit_base_and_image_url` | 5.896 |
| `test.test_ab::test_ab_runs_an_ignored_interpreter_on_the_base_side_too` | 5.891 |
| `test.test_ab::test_ab_reports_which_side_failed_and_keeps_its_output` | 5.849 |
| `test.test_ab::test_ab_base_imports_its_own_package_over_an_absolute_path_to_the_candidate` | 4.536 |
| `test.test_core_install::test_run_compare_and_ab_work_without_the_plotting_stack` | 4.384 |

</details>