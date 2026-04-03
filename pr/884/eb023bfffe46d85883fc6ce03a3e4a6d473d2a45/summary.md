| Metric | Value |
|--------|-------|
| Total tests | 1170 |
| Total time | 97.74s |
| Mean | 0.0835s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.556 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.492 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.951 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 3.524 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.019 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 2.868 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.281 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src_and_cat` | 1.240 |
| `test.test_over_time_repeats.TestHeatmapResultOverTime::test_heatmap_over_time_no_repeats` | 1.158 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.151 |

</details>