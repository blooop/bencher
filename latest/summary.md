| Metric | Value |
|--------|-------|
| Total tests | 1681 |
| Total time | 125.36s |
| Mean | 0.0746s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.379 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.301 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.838 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.502 |
| `test.test_split_render_examples::test_split_render_roundtrip[result_image/example_result_image_to_video.py]` | 3.234 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 2.785 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.765 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.686 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 2.674 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.348 |

</details>