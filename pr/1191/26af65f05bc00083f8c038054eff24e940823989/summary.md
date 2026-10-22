| Metric | Value |
|--------|-------|
| Total tests | 3694 |
| Total time | 319.25s |
| Mean | 0.0864s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 14.737 |
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 13.864 |
| `test.test_ab::test_ab_reports_which_side_failed_and_keeps_its_output` | 9.745 |
| `test.test_ab::test_ab_images_pushes_them_to_the_evidence_ref_and_links_them` | 9.033 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 8.778 |
| `test.test_ab::test_ab_without_images_pushes_nothing` | 8.516 |
| `test.test_ab::test_ab_judges_a_claim_on_a_metric_the_change_adds` | 8.445 |
| `test.test_ab::test_ab_png_dir_writes_one_png_per_metric` | 8.413 |
| `test.test_ab::test_ab_images_without_a_github_remote_keeps_text_and_exits_0` | 8.342 |
| `test.test_ab::test_ab_runs_an_ignored_interpreter_on_the_base_side_too` | 8.154 |

</details>