| Metric | Value |
|--------|-------|
| Total tests | 2857 |
| Total time | 157.63s |
| Mean | 0.0552s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.001 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.364 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 6.125 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.547 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.314 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 3.005 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.999 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.765 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.722 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.536 |

</details>