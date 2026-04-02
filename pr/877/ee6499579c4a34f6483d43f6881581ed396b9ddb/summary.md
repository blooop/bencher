| Metric | Value |
|--------|-------|
| Total tests | 1162 |
| Total time | 106.49s |
| Mean | 0.0916s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.156 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.465 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.765 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.032 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.852 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.687 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.352 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.310 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.167 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.100 |

</details>