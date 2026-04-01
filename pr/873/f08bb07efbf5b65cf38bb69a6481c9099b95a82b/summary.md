| Metric | Value |
|--------|-------|
| Total tests | 1136 |
| Total time | 107.71s |
| Mean | 0.0948s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.877 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.469 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.834 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.061 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.898 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.680 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.291 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.239 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.125 |
| `test.test_bencher.TestBencher::test_combinations` | 1.103 |

</details>