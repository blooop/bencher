| Metric | Value |
|--------|-------|
| Total tests | 1924 |
| Total time | 132.59s |
| Mean | 0.0689s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.275 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.017 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.923 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.697 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.450 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.948 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.918 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.741 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.654 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.453 |

</details>