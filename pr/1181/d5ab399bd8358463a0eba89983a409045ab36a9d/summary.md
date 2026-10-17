| Metric | Value |
|--------|-------|
| Total tests | 3520 |
| Total time | 341.20s |
| Mean | 0.0969s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 18.836 |
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.496 |
| `test.test_ab::test_ab_explicit_base_and_image_url` | 10.784 |
| `test.test_ab::test_ab_judges_a_claim_on_a_metric_the_change_adds` | 10.729 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 10.603 |
| `test.test_ab::test_ab_reports_which_side_failed_and_keeps_its_output` | 10.187 |
| `test.test_ab::test_ab_runs_an_ignored_interpreter_on_the_base_side_too` | 10.165 |
| `test.test_ab::test_ab_base_imports_its_own_package_over_an_absolute_path_to_the_candidate` | 7.727 |
| `test.test_core_install::test_run_compare_and_ab_work_without_the_plotting_stack` | 6.628 |
| `test.test_complete_report::test_complete_bundle_cli_and_legacy_compare` | 6.245 |

</details>