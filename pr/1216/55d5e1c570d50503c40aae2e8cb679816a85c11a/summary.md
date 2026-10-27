| Metric | Value |
|--------|-------|
| Total tests | 4212 |
| Total time | 657.16s |
| Mean | 0.1560s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.233 |
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 16.424 |
| `test.test_ab::test_ab_without_images_pushes_nothing` | 9.794 |
| `test.test_ab::test_ab_images_pushes_them_to_the_evidence_ref_and_links_them` | 9.772 |
| `test.test_ab::test_ab_images_without_a_github_remote_keeps_text_and_exits_0` | 9.710 |
| `test.test_ab::test_ab_explicit_base_and_image_url` | 9.678 |
| `test.test_ab::test_ab_png_dir_writes_one_png_per_metric` | 9.634 |
| `test.test_ab::test_ab_reports_which_side_failed_and_keeps_its_output` | 9.602 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 9.550 |
| `test.test_svg_seaborn::test_seaborn_styles_are_the_same_bytes_in_two_processes[seaborn]` | 9.550 |

</details>