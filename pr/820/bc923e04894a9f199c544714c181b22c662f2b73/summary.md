| Metric | Value |
|--------|-------|
| Total tests | 910 |
| Total time | 102.06s |
| Mean | 0.1122s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 35.448 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultVar]` | 7.161 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 6.968 |
| `test.test_report.TestReport::test_example_floats2D_report` | 2.958 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.556 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.277 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.016 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.909 |
| `test.test_result_bool.TestVolumeResult::test_volume_3float_multi_repeat` | 0.863 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 0.858 |

</details>