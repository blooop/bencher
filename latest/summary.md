| Metric | Value |
|--------|-------|
| Total tests | 2932 |
| Total time | 127.03s |
| Mean | 0.0433s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 14.328 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.879 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.852 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.585 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.237 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.397 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.333 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.183 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.963 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 1.944 |

</details>