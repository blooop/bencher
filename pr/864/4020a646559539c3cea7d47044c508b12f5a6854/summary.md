| Metric | Value |
|--------|-------|
| Total tests | 1128 |
| Total time | 107.83s |
| Mean | 0.0956s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 23.308 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.052 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.865 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.329 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.125 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.854 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.266 |
| `test.test_bencher.TestBencher::test_combinations` | 1.110 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.056 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 1.005 |

</details>