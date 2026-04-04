| Metric | Value |
|--------|-------|
| Total tests | 1206 |
| Total time | 101.65s |
| Mean | 0.0843s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.640 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.768 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.887 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.136 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.068 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.760 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.452 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.129 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_with_repeats` | 1.021 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.890 |

</details>