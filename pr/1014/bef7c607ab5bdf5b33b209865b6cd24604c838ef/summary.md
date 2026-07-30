| Metric | Value |
|--------|-------|
| Total tests | 2321 |
| Total time | 149.00s |
| Mean | 0.0642s |
| Median | 0.0030s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.275 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.504 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.221 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.977 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.494 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.298 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 3.050 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.858 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.767 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.521 |

</details>