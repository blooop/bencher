| Metric | Value |
|--------|-------|
| Total tests | 1136 |
| Total time | 99.14s |
| Mean | 0.0873s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.929 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.924 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.525 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.336 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.830 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.505 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.103 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 0.997 |
| `test.test_bencher.TestBencher::test_combinations` | 0.954 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 0.937 |

</details>