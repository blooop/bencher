| Metric | Value |
|--------|-------|
| Total tests | 4132 |
| Total time | 413.92s |
| Mean | 0.1002s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 11.538 |
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 11.417 |
| `test.test_ab::test_ab_images_pushes_them_to_the_evidence_ref_and_links_them` | 7.096 |
| `test.test_ab::test_ab_png_dir_writes_one_png_per_metric` | 6.855 |
| `test.test_ab::test_ab_without_images_pushes_nothing` | 6.754 |
| `test.test_ab::test_ab_images_without_a_github_remote_keeps_text_and_exits_0` | 6.708 |
| `test.test_svg_seaborn::test_seaborn_styles_are_the_same_bytes_in_two_processes[seaborn]` | 6.614 |
| `test.test_svg_seaborn::test_seaborn_styles_are_the_same_bytes_in_two_processes[seaborn-ticks]` | 6.385 |
| `test.test_ab::test_ab_reports_which_side_failed_and_keeps_its_output` | 6.321 |
| `test.test_ab::test_ab_runs_an_ignored_interpreter_on_the_base_side_too` | 6.286 |

</details>