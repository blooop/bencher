| Metric | Value |
|--------|-------|
| Total tests | 2066 |
| Total time | 116.90s |
| Mean | 0.0566s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 14.545 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.696 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.478 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.715 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 3.479 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.273 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.441 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.349 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.331 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.222 |

</details>