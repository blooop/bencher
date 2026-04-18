| Metric | Value |
|--------|-------|
| Total tests | 1277 |
| Total time | 106.30s |
| Mean | 0.0832s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.486 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.065 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.827 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.041 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.929 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.798 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.409 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src_and_cat` | 1.149 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.011 |
| `test.test_bencher.TestBencher::test_combinations` | 0.900 |

</details>