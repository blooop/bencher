| Metric | Value |
|--------|-------|
| Total tests | 2857 |
| Total time | 134.27s |
| Mean | 0.0470s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.705 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.574 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.521 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.411 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 2.945 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.451 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.188 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.171 |
| `test.test_split_render_examples::test_split_render_roundtrip[result_image/example_result_image_to_video.py]` | 1.857 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.854 |

</details>