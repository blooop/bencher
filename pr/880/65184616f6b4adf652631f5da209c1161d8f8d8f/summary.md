| Metric | Value |
|--------|-------|
| Total tests | 1154 |
| Total time | 106.26s |
| Mean | 0.0921s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.100 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.449 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.739 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.034 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.832 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.710 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.379 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.307 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_slider_subsampled` | 1.146 |
| `test.test_bencher.TestBencher::test_combinations` | 1.056 |

</details>