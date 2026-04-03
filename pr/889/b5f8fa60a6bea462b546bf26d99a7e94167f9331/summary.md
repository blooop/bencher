| Metric | Value |
|--------|-------|
| Total tests | 1185 |
| Total time | 105.57s |
| Mean | 0.0891s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.443 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.259 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.995 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.270 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.065 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.882 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.512 |
| `test.test_over_time_repeats.TestHeatmapResultOverTime::test_heatmap_over_time_no_repeats` | 1.092 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.041 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.029 |

</details>