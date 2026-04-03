| Metric | Value |
|--------|-------|
| Total tests | 1170 |
| Total time | 101.39s |
| Mean | 0.0867s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.541 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.062 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.803 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.104 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.073 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.929 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.362 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.332 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.311 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.970 |

</details>