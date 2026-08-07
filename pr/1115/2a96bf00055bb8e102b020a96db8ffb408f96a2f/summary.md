| Metric | Value |
|--------|-------|
| Total tests | 2931 |
| Total time | 153.49s |
| Mean | 0.0524s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.339 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.385 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.072 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.151 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.976 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.089 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 3.054 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.892 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.748 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.321 |

</details>