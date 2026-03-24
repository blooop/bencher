| Metric | Value |
|--------|-------|
| Total tests | 931 |
| Total time | 106.70s |
| Mean | 0.1146s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 35.756 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 7.265 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 6.951 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 4.991 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.560 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.320 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.284 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 1.166 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.973 |
| `test.test_result_bool.TestVolumeResult::test_volume_3float_multi_repeat` | 0.871 |

</details>