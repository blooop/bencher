| Metric | Value |
|--------|-------|
| Total tests | 1411 |
| Total time | 97.99s |
| Mean | 0.0694s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 14.907 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.830 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.724 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.509 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.446 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.441 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.394 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.308 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 1.834 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 1.792 |

</details>