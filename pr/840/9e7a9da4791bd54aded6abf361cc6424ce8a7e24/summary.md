| Metric | Value |
|--------|-------|
| Total tests | 947 |
| Total time | 92.47s |
| Mean | 0.0976s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.009 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.586 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.310 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.737 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.541 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.380 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.303 |
| `test.test_generated_examples::test_generated_example[2_float/over_time/sweep_2_float_2_cat_over_time.py]` | 1.067 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.053 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.051 |

</details>