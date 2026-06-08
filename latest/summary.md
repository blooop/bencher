| Metric | Value |
|--------|-------|
| Total tests | 1468 |
| Total time | 124.05s |
| Mean | 0.0845s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.476 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.221 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.319 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.207 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.131 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.959 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.833 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.782 |
| `test.test_split_render_examples::test_split_render_roundtrip[result_image/example_result_image_to_video.py]` | 2.289 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.280 |

</details>