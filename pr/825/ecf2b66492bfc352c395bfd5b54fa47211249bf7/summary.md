| Metric | Value |
|--------|-------|
| Total tests | 922 |
| Total time | 109.81s |
| Mean | 0.1191s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 35.355 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 7.251 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 7.240 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 5.677 |
| `test.test_report.TestReport::test_example_floats2D_report` | 3.103 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.643 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.366 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.037 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 0.913 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.907 |

</details>