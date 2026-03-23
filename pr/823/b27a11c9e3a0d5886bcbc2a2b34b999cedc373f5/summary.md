| Metric | Value |
|--------|-------|
| Total tests | 915 |
| Total time | 107.94s |
| Mean | 0.1180s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 36.114 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 7.562 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 7.064 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 5.150 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.604 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.316 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.072 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.993 |
| `test.test_generated_examples::test_generated_example[3_float/over_time/sweep_3_float_2_cat_over_time.py]` | 0.886 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 0.859 |

</details>