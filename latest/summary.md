| Metric | Value |
|--------|-------|
| Total tests | 4244 |
| Total time | 394.26s |
| Mean | 0.0929s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 10.630 |
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 10.397 |
| `test.test_ab::test_ab_png_dir_writes_one_png_per_metric` | 6.653 |
| `test.test_ab::test_ab_images_without_a_github_remote_keeps_text_and_exits_0` | 6.502 |
| `test.test_ab::test_ab_images_pushes_them_to_the_evidence_ref_and_links_them` | 6.351 |
| `test.test_ab::test_ab_without_images_pushes_nothing` | 6.295 |
| `test.test_ab::test_ab_runs_an_ignored_interpreter_on_the_base_side_too` | 5.933 |
| `test.test_ab::test_ab_judges_a_claim_on_a_metric_the_change_adds` | 5.918 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 5.873 |
| `test.test_svg_seaborn::test_seaborn_styles_are_the_same_bytes_in_two_processes[seaborn]` | 5.830 |

</details>