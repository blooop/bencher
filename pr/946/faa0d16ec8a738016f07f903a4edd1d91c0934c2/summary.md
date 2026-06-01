| Metric | Value |
|--------|-------|
| Total tests | 1397 |
| Total time | 111.64s |
| Mean | 0.0799s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.387 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.856 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.379 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.158 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.829 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.754 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.641 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.450 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.257 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.414 |

</details>