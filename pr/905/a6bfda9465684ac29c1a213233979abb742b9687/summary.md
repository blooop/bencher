| Metric | Value |
|--------|-------|
| Total tests | 1104 |
| Total time | 76.51s |
| Mean | 0.0693s |
| Median | 0.0010s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 21.252 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 5.120 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.853 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.960 |
| `test.test_bencher.TestBencher::test_combinations_over_time` | 1.699 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.492 |
| `test.test_time_event_curve.TestTimeEventCurvePlot::test_curve_with_string_time_src_and_cat` | 1.143 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.042 |
| `test.test_bencher.TestBencher::test_combinations` | 1.019 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_no_subsampling_when_below_default_max` | 0.924 |

</details>