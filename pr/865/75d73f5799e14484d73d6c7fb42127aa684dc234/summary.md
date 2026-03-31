| Metric | Value |
|--------|-------|
| Total tests | 1134 |
| Total time | 108.52s |
| Mean | 0.0957s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.284 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.373 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.002 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.021 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.978 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.629 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.290 |
| `test.test_bencher.TestBencher::test_combinations` | 1.121 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.121 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.090 |

</details>