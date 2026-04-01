| Metric | Value |
|--------|-------|
| Total tests | 1136 |
| Total time | 95.31s |
| Mean | 0.0839s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.314 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.640 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.311 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.026 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.802 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.404 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.089 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 0.978 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 0.964 |
| `test.test_bencher.TestBencher::test_combinations` | 0.932 |

</details>