| Metric | Value |
|--------|-------|
| Total tests | 928 |
| Total time | 81.14s |
| Mean | 0.0874s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.624 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.885 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.547 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.994 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.522 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.243 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 1.157 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.029 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.873 |
| `test.test_result_bool.TestVolumeResult::test_volume_3float_multi_repeat` | 0.861 |

</details>