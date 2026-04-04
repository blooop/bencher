| Metric | Value |
|--------|-------|
| Total tests | 1206 |
| Total time | 104.59s |
| Mean | 0.0867s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.615 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.069 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.792 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.063 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.051 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.839 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.480 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.060 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.040 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_no_repeats` | 1.009 |

</details>