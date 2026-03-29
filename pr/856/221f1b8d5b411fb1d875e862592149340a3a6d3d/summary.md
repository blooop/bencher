| Metric | Value |
|--------|-------|
| Total tests | 1019 |
| Total time | 113.41s |
| Mean | 0.1113s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 25.221 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.422 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.194 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.763 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.344 |
| `test.test_generated_examples::test_generated_example[advanced/advanced_cartesian_animation.py]` | 3.079 |
| `test.test_over_time_repeats.TestHeatmapResultOverTime::test_heatmap_over_time_no_repeats` | 1.250 |
| `test.test_bencher.TestBencher::test_combinations` | 1.195 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.111 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.106 |

</details>