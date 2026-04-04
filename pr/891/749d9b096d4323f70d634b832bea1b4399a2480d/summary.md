| Metric | Value |
|--------|-------|
| Total tests | 1206 |
| Total time | 106.64s |
| Mean | 0.0884s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.654 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.130 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.831 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.247 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.773 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.753 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.769 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.313 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.297 |
| `test.test_bencher.TestBencher::test_combinations` | 1.021 |

</details>