| Metric | Value |
|--------|-------|
| Total tests | 2816 |
| Total time | 143.31s |
| Mean | 0.0509s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 16.671 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.040 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.877 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.013 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.966 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.064 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.809 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.790 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.636 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.461 |

</details>