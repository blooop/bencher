| Metric | Value |
|--------|-------|
| Total tests | 1136 |
| Total time | 106.35s |
| Mean | 0.0936s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.651 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.468 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.781 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.048 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.836 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.675 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.305 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.192 |
| `test.test_bencher.TestBencher::test_combinations` | 1.133 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.121 |

</details>