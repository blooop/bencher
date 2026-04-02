| Metric | Value |
|--------|-------|
| Total tests | 1157 |
| Total time | 109.99s |
| Mean | 0.0951s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 24.409 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.482 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.864 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.071 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.902 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.729 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.395 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.332 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.313 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.225 |

</details>