| Metric | Value |
|--------|-------|
| Total tests | 1136 |
| Total time | 102.31s |
| Mean | 0.0901s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.698 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.124 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.818 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.139 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.801 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.527 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.271 |
| `test.test_bench_result_base.TestAggOverDimsStd::test_2d_agg_both_dims` | 1.255 |
| `test.test_over_time_repeats.TestShowAggregatedTimeTab::test_curve_aggregated_tab_absent_when_disabled` | 1.084 |
| `test.test_bencher.TestBencher::test_combinations` | 1.076 |

</details>