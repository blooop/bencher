| Metric | Value |
|--------|-------|
| Total tests | 1170 |
| Total time | 101.97s |
| Mean | 0.0871s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.939 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.251 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.815 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.102 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/cartesian_animation.py]` | 3.036 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.793 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.409 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.037 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.955 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src` | 0.911 |

</details>