| Metric | Value |
|--------|-------|
| Total tests | 4133 |
| Total time | 581.04s |
| Mean | 0.1406s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.182 |
| `test.test_ab::test_ab_on_a_clean_tree_names_the_head_even_when_its_output_is_not_ignored` | 12.682 |
| `test.test_ab::test_ab_images_pushes_them_to_the_evidence_ref_and_links_them` | 10.067 |
| `test.test_ab::test_ab_images_without_a_github_remote_keeps_text_and_exits_0` | 9.546 |
| `test.test_ab::test_ab_without_images_pushes_nothing` | 9.241 |
| `test.test_ab::test_ab_png_dir_writes_one_png_per_metric` | 8.630 |
| `test.test_svg_seaborn::test_seaborn_styles_are_the_same_bytes_in_two_processes[seaborn-ticks]` | 8.295 |
| `test.test_ab::test_ab_measures_each_side_with_its_own_code` | 8.078 |
| `test.test_svg_seaborn::test_seaborn_styles_are_the_same_bytes_in_two_processes[seaborn]` | 7.913 |
| `test.test_evidence_flow::test_every_svg_keeps_the_motion_rule` | 7.533 |

</details>