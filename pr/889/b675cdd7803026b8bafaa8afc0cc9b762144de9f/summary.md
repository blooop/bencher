| Metric | Value |
|--------|-------|
| Total tests | 1186 |
| Total time | 107.43s |
| Mean | 0.0906s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.982 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.328 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.093 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.275 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.101 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.023 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.533 |
| `test.test_over_time_repeats.TestHeatmapResultOverTime::test_heatmap_over_time_no_repeats` | 1.125 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.087 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.985 |

</details>