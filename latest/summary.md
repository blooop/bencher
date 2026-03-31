| Metric | Value |
|--------|-------|
| Total tests | 1128 |
| Total time | 107.08s |
| Mean | 0.0949s |
| Median | 0.0015s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.171 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.386 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.884 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.965 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.899 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.865 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.310 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.276 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.255 |
| `test.test_bencher.TestBencher::test_combinations` | 1.093 |

</details>