| Metric | Value |
|--------|-------|
| Total tests | 1253 |
| Total time | 107.51s |
| Mean | 0.0858s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.279 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.112 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.881 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.143 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.959 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.811 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.441 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.080 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.035 |
| `test.test_bencher.TestBencher::test_combinations` | 0.928 |

</details>