| Metric | Value |
|--------|-------|
| Total tests | 2291 |
| Total time | 98.41s |
| Mean | 0.0430s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 11.950 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.230 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.156 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.894 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 2.419 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 2.417 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 1.785 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 1.777 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 1.628 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 1.623 |

</details>