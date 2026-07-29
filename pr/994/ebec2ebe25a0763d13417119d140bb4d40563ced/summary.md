| Metric | Value |
|--------|-------|
| Total tests | 2003 |
| Total time | 110.08s |
| Mean | 0.0550s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 15.194 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.124 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.978 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.635 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 2.770 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.278 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.043 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 1.975 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 1.974 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.755 |

</details>