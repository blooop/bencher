| Metric | Value |
|--------|-------|
| Total tests | 1825 |
| Total time | 131.61s |
| Mean | 0.0721s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.179 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.150 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.027 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.725 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.342 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.978 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.972 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.803 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.667 |
| `test.test_split_render_examples::test_split_render_roundtrip[result_image/example_result_image_to_video.py]` | 2.538 |

</details>