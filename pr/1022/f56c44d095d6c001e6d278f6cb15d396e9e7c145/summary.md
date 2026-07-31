| Metric | Value |
|--------|-------|
| Total tests | 2438 |
| Total time | 137.70s |
| Mean | 0.0565s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.310 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 5.834 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.608 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.061 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.999 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.349 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.850 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.806 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.770 |
| `test.test_split_render_examples::test_split_render_roundtrip[result_image/example_result_image_to_video.py]` | 2.591 |

</details>