| Metric | Value |
|--------|-------|
| Total tests | 980 |
| Total time | 88.75s |
| Mean | 0.0906s |
| Median | 0.0020s |

<details>
<summary>Top 10 slowest tests</summary>

| Test | Time (s) |
|------|----------|
| `test.test_bench_examples.TestBenchExamples::test_example_meta` | 22.871 |
| `test.test_over_time_save_perf::test_save_faster_without_aggregated_tab` | 4.990 |
| `test.test_hash_persistent.TestCrossProcessDeterminism::test_hash_stable_across_two_processes[ResultBool]` | 3.836 |
| `test.test_generated_examples::test_generated_example[result_types/result_image/result_image_to_video.py]` | 2.921 |
| `test.test_over_time_repeats.TestMaxSliderPoints::test_default_subsampling_caps_at_max` | 2.440 |
| `test.test_bench_runner.TestBenchRunner::test_benchrunner_unified_interface` | 1.197 |
| `test.test_optuna_result.TestOptunaResult::test_collect_optuna_plots_with_repeats` | 1.054 |
| `test.test_optuna_result.TestOptunaReportRouting::test_optuna_plots_per_sweep_tab` | 1.017 |
| `test.test_result_bool.TestVolumeResult::test_volume_3float_multi_repeat` | 0.860 |
| `test.test_bencher.TestBencher::test_combinations` | 0.825 |

</details>