| Metric | Value |
|--------|-------|
| Total tests | 1104 |
| Total time | 75.23s |
| Mean | 0.0681s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.286 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.791 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.070 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.927 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.613 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.448 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src` | 1.147 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 0.916 |
| `test.test_bencher.TestBencher::test_combinations` | 0.899 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.883 |

</details>