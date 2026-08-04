| Metric | Value |
|--------|-------|
| Total tests | 2853 |
| Total time | 151.45s |
| Mean | 0.0531s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.839 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.136 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.977 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.843 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.541 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 3.013 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.971 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.696 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.661 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.485 |

</details>