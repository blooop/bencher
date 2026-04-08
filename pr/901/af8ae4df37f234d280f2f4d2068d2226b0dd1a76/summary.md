| Metric | Value |
|--------|-------|
| Total tests | 1253 |
| Total time | 110.13s |
| Mean | 0.0879s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.561 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.156 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.975 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.072 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.050 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.874 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.495 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.130 |
| `test.test_over_time_repeats.TestHeatmapResultOverTime::test_heatmap_over_time_no_repeats` | 1.068 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.047 |

</details>