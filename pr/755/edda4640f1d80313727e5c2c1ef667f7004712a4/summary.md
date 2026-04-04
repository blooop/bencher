| Metric | Value |
|--------|-------|
| Total tests | 1185 |
| Total time | 95.91s |
| Mean | 0.0809s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.114 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.571 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.640 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.398 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.952 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.850 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.257 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.206 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.948 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 0.911 |

</details>