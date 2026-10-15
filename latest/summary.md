| Metric | Value |
|--------|-------|
| Total tests | 3449 |
| Total time | 326.82s |
| Mean | 0.0948s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.536 |
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 18.211 |
| `test.test_ab::test_ab_explicit_base_and_image_url` | 10.199 |
| `test.test_ab::test_ab_runs_an_ignored_interpreter_on_the_base_side_too` | 9.963 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 9.888 |
| `test.test_ab::test_ab_reports_which_side_failed_and_keeps_its_output` | 9.551 |
| `test.test_ab::test_ab_base_imports_its_own_package_over_an_absolute_path_to_the_candidate` | 7.686 |
| `test.test_core_install::test_run_compare_and_ab_work_without_the_plotting_stack` | 6.789 |
| `test.test_complete_report::test_complete_bundle_cli_and_legacy_compare` | 6.100 |
| `test.test_ab::test_ab_fails_when_the_base_still_imports_the_candidates_code` | 4.942 |

</details>