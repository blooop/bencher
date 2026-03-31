| Metric | Value |
|--------|-------|
| Total tests | 1136 |
| Total time | 112.80s |
| Mean | 0.0993s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.731 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.706 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.985 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.148 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.018 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.912 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.376 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.301 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.299 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.191 |

</details>