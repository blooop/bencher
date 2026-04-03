| Metric | Value |
|--------|-------|
| Total tests | 1170 |
| Total time | 110.21s |
| Mean | 0.0942s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.165 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.648 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.940 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.051 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.944 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.765 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.474 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.126 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.101 |
| `test.test_bencher.TestBencher::test_combinations` | 1.076 |

</details>