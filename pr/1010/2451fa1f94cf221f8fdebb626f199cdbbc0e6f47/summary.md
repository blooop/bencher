| Metric | Value |
|--------|-------|
| Total tests | 2183 |
| Total time | 108.48s |
| Mean | 0.0497s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 13.515 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.772 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.760 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.627 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.134 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.387 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.216 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.118 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.901 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.790 |

</details>