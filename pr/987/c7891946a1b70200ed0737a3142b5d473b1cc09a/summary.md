| Metric | Value |
|--------|-------|
| Total tests | 1850 |
| Total time | 108.99s |
| Mean | 0.0589s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.770 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.763 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.753 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.656 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.157 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.365 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.215 |
| `test.test_split_render_examples::test_split_render_roundtrip[result_image/example_result_image_to_video.py]` | 2.213 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.168 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.902 |

</details>