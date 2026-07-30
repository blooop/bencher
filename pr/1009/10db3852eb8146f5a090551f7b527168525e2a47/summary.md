| Metric | Value |
|--------|-------|
| Total tests | 2114 |
| Total time | 109.01s |
| Mean | 0.0516s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 13.625 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 4.767 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.659 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 3.725 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.262 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.448 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.328 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.225 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 1.976 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 1.971 |

</details>