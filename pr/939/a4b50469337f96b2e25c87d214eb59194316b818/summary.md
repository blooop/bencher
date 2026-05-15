| Metric | Value |
|--------|-------|
| Total tests | 1387 |
| Total time | 111.52s |
| Mean | 0.0804s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.250 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.813 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.361 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.135 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.977 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.842 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.783 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.691 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.265 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.487 |

</details>