| Metric | Value |
|--------|-------|
| Total tests | 1479 |
| Total time | 117.12s |
| Mean | 0.0792s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.316 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.879 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.321 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.376 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.987 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 2.978 |
| `test.test_split_render_examples::test_split_render_roundtrip[result_image/example_result_image_to_video.py]` | 2.742 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.635 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.631 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 2.627 |

</details>