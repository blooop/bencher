| Metric | Value |
|--------|-------|
| Total tests | 1423 |
| Total time | 111.34s |
| Mean | 0.0782s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 18.045 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.238 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.332 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.151 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.710 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.621 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 2.611 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.448 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_step.py]` | 2.257 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src_and_cat` | 1.090 |

</details>