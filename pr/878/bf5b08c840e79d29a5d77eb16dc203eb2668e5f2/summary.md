| Metric | Value |
|--------|-------|
| Total tests | 1145 |
| Total time | 109.48s |
| Mean | 0.0956s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.104 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.407 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.930 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.218 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.075 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.766 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.411 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.143 |
| `test.test_bencher.TestBencher::test_combinations` | 1.077 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.069 |

</details>