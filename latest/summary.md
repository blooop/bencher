| Metric | Value |
|--------|-------|
| Total tests | 1095 |
| Total time | 78.05s |
| Mean | 0.0713s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.693 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.452 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 4.096 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 3.112 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.469 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.396 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.107 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.052 |
| `test.test_over_time_repeats.TestShowAggregatedTimeTab::test_aggregated_tab_present_when_enabled` | 1.012 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.950 |

</details>