| Metric | Value |
|--------|-------|
| Total tests | 1467 |
| Total time | 120.16s |
| Mean | 0.0819s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 15.978 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.247 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.034 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 3.952 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.143 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.824 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.671 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.653 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.332 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.297 |

</details>