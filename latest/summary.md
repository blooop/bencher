| Metric | Value |
|--------|-------|
| Total tests | 1095 |
| Total time | 71.84s |
| Mean | 0.0656s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 19.924 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.663 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.878 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.844 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.696 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.480 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.013 |
| `test.test_over_time_repeats.TestShowAggregatedTimeTab::test_aggregated_tab_present_when_enabled` | 0.906 |
| `test.test_bencher.TestBencher::test_combinations` | 0.904 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 0.880 |

</details>