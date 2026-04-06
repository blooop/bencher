| Metric | Value |
|--------|-------|
| Total tests | 1222 |
| Total time | 104.65s |
| Mean | 0.0856s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.611 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.095 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.801 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.025 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.996 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.743 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.436 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.355 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.026 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_no_repeats` | 1.022 |

</details>