| Metric | Value |
|--------|-------|
| Total tests | 1136 |
| Total time | 108.06s |
| Mean | 0.0951s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.210 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.416 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.866 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.058 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.861 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.702 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.264 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.191 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.111 |
| `test.test_bencher.TestBencher::test_combinations` | 1.105 |

</details>