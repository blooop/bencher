| Metric | Value |
|--------|-------|
| Total tests | 921 |
| Total time | 102.18s |
| Mean | 0.1109s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 34.087 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 7.014 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 6.198 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 4.807 |
| `test.test_report.TestReport::test_example_floats2D_report` | 2.744 |
| `test.test_generated_examples::test_generated_example[1_float/over_time/sweep_1_float_3_cat_over_time.py]` | 1.438 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.229 |
| `test.test_generated_examples::test_generated_example[1_float/over_time_repeats/sweep_1_float_3_cat_over_time_repeats.py]` | 1.183 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 0.948 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 0.863 |

</details>