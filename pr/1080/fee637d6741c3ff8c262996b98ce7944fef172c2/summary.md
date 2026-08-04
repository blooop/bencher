| Metric | Value |
|--------|-------|
| Total tests | 2880 |
| Total time | 154.94s |
| Mean | 0.0538s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.009 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 8.670 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.240 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.942 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.065 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.061 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.812 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.694 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.665 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.489 |

</details>