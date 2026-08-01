| Metric | Value |
|--------|-------|
| Total tests | 2785 |
| Total time | 122.03s |
| Mean | 0.0438s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 15.136 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 5.053 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.859 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.611 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.231 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.393 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.369 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.343 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.237 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.021 |

</details>