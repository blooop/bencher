| Metric | Value |
|--------|-------|
| Total tests | 1170 |
| Total time | 98.82s |
| Mean | 0.0845s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.125 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.682 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.839 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.145 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.024 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.732 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.502 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.145 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_no_repeats` | 1.064 |
| `test.test_bencher.TestBencher::test_combinations` | 0.923 |

</details>