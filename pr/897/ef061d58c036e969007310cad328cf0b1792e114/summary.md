| Metric | Value |
|--------|-------|
| Total tests | 1220 |
| Total time | 102.54s |
| Mean | 0.0841s |
| Median | 0.0015s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.659 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.681 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.839 |
| `test.test_generated_examples::test_generated_example[cartesian_animation/example_cartesian_animation.py]` | 3.135 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.866 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/example_result_image_to_video.py]` | 2.673 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.650 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src_and_cat` | 1.142 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.018 |
| `test.test_bencher.TestBencher::test_bench_cfg_hash` | 1.017 |

</details>