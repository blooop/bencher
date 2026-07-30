| Metric | Value |
|--------|-------|
| Total tests | 2176 |
| Total time | 125.61s |
| Mean | 0.0577s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 15.748 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 5.333 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.084 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.976 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.278 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.423 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.422 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.214 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.092 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.029 |

</details>