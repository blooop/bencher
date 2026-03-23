| Metric | Value |
|--------|-------|
| Total tests | 922 |
| Total time | 105.45s |
| Mean | 0.1144s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 34.831 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.996 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 6.825 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 4.937 |
| `test.test_report.TestReport::test_example_floats2D_report` | 2.867 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.528 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.247 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.023 |
| `test.test_result_bool.TestVolumeResult::test_volume_3float_multi_repeat` | 0.869 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.862 |

</details>