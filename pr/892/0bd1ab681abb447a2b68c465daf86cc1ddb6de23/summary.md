| Metric | Value |
|--------|-------|
| Total tests | 1185 |
| Total time | 101.42s |
| Mean | 0.0856s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.798 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.079 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.818 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.071 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.026 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.773 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.472 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.024 |
| `test.test_bencher.TestBencher::test_combinations` | 0.978 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.966 |

</details>