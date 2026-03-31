| Metric | Value |
|--------|-------|
| Total tests | 1128 |
| Total time | 122.65s |
| Mean | 0.1087s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 29.524 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.410 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.273 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.983 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.294 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.806 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.552 |
| `test.test_bench_result_base.TestBenchResultBase::test_select_level` | 1.506 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.410 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.402 |

</details>