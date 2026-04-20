| Metric | Value |
|--------|-------|
| Total tests | 1308 |
| Total time | 91.89s |
| Mean | 0.0702s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.970 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.705 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.631 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.446 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.415 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.264 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.714 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.206 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 0.925 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 0.828 |

</details>