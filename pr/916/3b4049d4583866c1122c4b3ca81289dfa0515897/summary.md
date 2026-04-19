| Metric | Value |
|--------|-------|
| Total tests | 1297 |
| Total time | 99.02s |
| Mean | 0.0763s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.540 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.450 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.889 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.194 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.805 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.759 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.176 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.151 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 0.918 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.912 |

</details>