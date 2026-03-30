| Metric | Value |
|--------|-------|
| Total tests | 1128 |
| Total time | 105.65s |
| Mean | 0.0937s |
| Median | 0.0015s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.899 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.345 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.848 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.946 |
| `test.test_generated_examples::test_generated_example[advanced/advanced_cartesian_animation.py]` | 2.923 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.901 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.328 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.305 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.247 |
| `test.test_bencher.TestBencher::test_combinations` | 1.081 |

</details>