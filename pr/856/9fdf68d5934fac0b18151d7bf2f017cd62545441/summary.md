| Metric | Value |
|--------|-------|
| Total tests | 1019 |
| Total time | 96.46s |
| Mean | 0.0947s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.297 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.517 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.522 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.346 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.104 |
| `test.test_generated_examples::test_generated_example[advanced/advanced_cartesian_animation.py]` | 2.743 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.227 |
| `test.test_over_time_repeats.TestCurveResultOverTime::test_curve_over_time_no_repeats` | 0.982 |
| `test.test_bencher.TestBencher::test_combinations` | 0.936 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.929 |

</details>