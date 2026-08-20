| Metric | Value |
|--------|-------|
| Total tests | 2936 |
| Total time | 125.75s |
| Mean | 0.0428s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 13.743 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.973 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.835 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.545 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.208 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.395 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.362 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.334 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.300 |
| `test.test_render.TestCollect::test_collect_constructs_far_fewer_objects_than_render` | 2.211 |

</details>