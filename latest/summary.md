| Metric | Value |
|--------|-------|
| Total tests | 2827 |
| Total time | 153.19s |
| Mean | 0.0542s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 17.785 |
| `test.test_split_render_examples::test_split_render_subprocess_media` | 6.058 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 5.761 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_drift.py]` | 4.048 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 3.955 |
| `test.test_blob_store_races.TestGCRacingAReader::test_readers_and_a_collector_interleave_without_corruption` | 3.249 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 3.149 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.014 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 2.842 |
| `test.test_generated_examples::test_generated_example[regression/example_regression_tuning_noise.py]` | 2.821 |

</details>