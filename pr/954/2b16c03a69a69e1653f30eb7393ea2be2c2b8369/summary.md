| Metric | Value |
|--------|-------|
| Total tests | 1467 |
| Total time | 132.82s |
| Mean | 0.0905s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.050 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.914 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.443 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.351 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.327 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 3.151 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.065 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.955 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.712 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.612 |

</details>