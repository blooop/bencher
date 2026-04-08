| Metric | Value |
|--------|-------|
| Total tests | 1095 |
| Total time | 74.22s |
| Mean | 0.0678s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 20.797 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.216 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.796 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.966 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.416 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.342 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.057 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.034 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.918 |
| `test.test_bencher.TestBencher::test_combinations` | 0.901 |

</details>