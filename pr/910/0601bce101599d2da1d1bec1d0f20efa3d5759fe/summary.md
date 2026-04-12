| Metric | Value |
|--------|-------|
| Total tests | 1254 |
| Total time | 102.68s |
| Mean | 0.0819s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.863 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.695 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.888 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.152 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.896 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.678 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.429 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.123 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src` | 0.911 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 0.883 |

</details>