| Metric | Value |
|--------|-------|
| Total tests | 1301 |
| Total time | 113.50s |
| Mean | 0.0872s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.549 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.340 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.217 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.139 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.828 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.770 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.712 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.446 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.281 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.540 |

</details>