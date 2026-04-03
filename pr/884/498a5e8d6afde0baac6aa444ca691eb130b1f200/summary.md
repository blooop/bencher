| Metric | Value |
|--------|-------|
| Total tests | 1170 |
| Total time | 99.82s |
| Mean | 0.0853s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.215 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.090 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.674 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.025 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.015 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.822 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.316 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.250 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.027 |
| `test.test_over_time_repeats.TestHeatmapResultOverTime::test_heatmap_over_time_no_repeats` | 1.010 |

</details>