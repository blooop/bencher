| Metric | Value |
|--------|-------|
| Total tests | 1301 |
| Total time | 114.91s |
| Mean | 0.0883s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.914 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.325 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.377 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.120 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.850 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.794 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.759 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.447 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.257 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.578 |

</details>